"""Early-warning agent: runs on the simulated daily clock, turns EWS hits for monitored accounts into
alert cards with reasons, next-best action and an RM briefing. Stops pulling data if consent is revoked."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.base import Agent, sim_date
from agents.policy_engine import inr
from agents.providers.consent import ConsentError, get_consent_provider
from agents.providers.lake import get_lake
from agents.providers.llm import get_llm
from api.models.db import Alert, Application, Notification
from core.timeline import last_visible_month, month_label
from ml.ews import explain, next_best_action

SLA = {"high": "contact within 1 working day, visit within 3 [§8.3]",
       "medium": "contact within 3 working days [§8.3]",
       "low": "review at the next monthly call [§8.3]"}
MSME_MESSAGE = {
    "high": "Namaste from your bank. Our monitoring shows a sharp change in your dispatches and cash flow this month. "
            "Your relationship manager will call you to discuss support options. Reply HELP to talk now.",
    "medium": "Namaste from your bank. We noticed some changes in your business signals this month. "
              "Your relationship manager may reach out. Reply HELP for a call back.",
}


@dataclass
class EwsRun:
    as_of: str
    checked: int = 0
    new_alerts: list[int] = field(default_factory=list)
    blocked: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


class EarlyWarningAgent(Agent):
    name = "early_warning_agent"

    def run(self) -> EwsRun:
        today = sim_date(self.db)
        visible = last_visible_month(today)
        run = EwsRun(as_of=str(today))
        lake = get_lake()
        scores = lake.scores(visible)
        provider = get_consent_provider(self.db)
        apps = self.db.query(Application).filter(Application.state == "MONITORING").all()
        for app in apps:
            start = (app.last_ews_month or 0) + 1
            months = list(range(start, visible + 1))
            if not months:
                continue
            run.checked += 1
            try:
                provider.authorise_pull(app.id, app.factory_id, today, self.actor.username,
                                        {"purpose": "monitoring", "months": [months[0], months[-1]]})
            except ConsentError:
                run.blocked.append(app.id)
                continue
            hits = self.tool("ews.lookup", lake.ews_hits, audit_app=app.id,
                             audit_output=lambda df: {"rows": len(df)},
                             **{"factory_id": app.factory_id, "months": months})
            profile = lake.profile(app.factory_id)
            for _, row in hits.iterrows():
                if not isinstance(row["severity"], str):
                    continue
                if self.db.query(Alert).filter_by(application_id=app.id, month=int(row.month)).first():
                    continue
                sc = scores[(scores.factory_id == app.factory_id) & (scores.month == int(row.month))]
                score = int(sc.score.iloc[0]) if not sc.empty else None
                alert = self._make_alert(app, profile, row, score, today)
                self.db.add(alert)
                self.db.flush()
                run.new_alerts.append(alert.id)
                if row["severity"] in MSME_MESSAGE:
                    self.db.add(Notification(factory_id=app.factory_id, text=MSME_MESSAGE[row["severity"]],
                                             sim_date=today))
            app.last_ews_month = visible
            self.db.commit()
        return run

    def _make_alert(self, app: Application, profile: dict, row, score: int | None, today) -> Alert:
        sev = row["severity"]
        reasons = explain(row)
        action = next_best_action(row)
        facts = {"factory": profile["name"], "cluster": profile["cluster"], "sector": profile["sector_label"],
                 "severity": sev.upper(), "month": month_label(int(row.month)), "reasons": reasons,
                 "score": score, "exposure": inr(app.sanctioned_limit or 0), "action": action, "sla": SLA[sev]}
        draft = (
            f"{facts['factory']} ({facts['cluster']}, {facts['sector']}): {facts['severity']} alert for "
            f"{facts['month']}. " + " ".join(r.rstrip(".") + "." for r in reasons)
            + (f" Current Factory Health Score {score}." if score else "")
            + f" Exposure {facts['exposure']}. Next-best action: {action} — {facts['sla']}."
        )
        briefing = self.tool("llm.write", get_llm().write, audit_app=app.id,
                             **{"task": "RM early-warning briefing (3 sentences)", "facts": facts, "draft": draft})
        rules = [k for k in ("order_loss", "cash_squeeze", "buyer_risk", "diversion", "compliance_slip") if row[k]]
        if row["anomaly"]:
            rules.append("anomaly")
        return Alert(application_id=app.id, factory_id=app.factory_id, month=int(row.month), severity=sev,
                     rules=rules, reasons=reasons, next_best_action=action, briefing=briefing, raised_on=today)
