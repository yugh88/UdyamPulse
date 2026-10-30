"""Data agent: obtains AA + GST consent, pulls the factory's silver data (only with active consent)
and runs reconciliation checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from agents.base import Agent, sim_date
from agents.providers.consent import ConsentError, get_consent_provider
from agents.providers.lake import get_lake
from api.models.db import Application, DataSnapshot
from core.timeline import last_visible_month, month_label


@dataclass
class Check:
    name: str
    status: str  # pass | warn | fail
    detail: str


@dataclass
class DataPullResult:
    factory_id: str
    months: int
    from_month: str
    to_month: str
    upto_month: int
    checks: list[Check]

    def to_dict(self) -> dict:
        return asdict(self)


def reconcile(history: pd.DataFrame) -> list[Check]:
    last3 = history.tail(3)
    last12 = history.tail(12)
    mismatch = float(last3["gst_bank_mismatch"].mean())
    gap = float(last3["einv_eway_gap"].mean())
    missing = int(last12["dq_missing_sources"].sum())
    late = int((last12["gst_filing_delay_days"] > 0).sum())
    return [
        Check("GST turnover vs bank credits", "pass" if mismatch <= 0.25 else "warn",
              f"{mismatch * 100:.0f}% average mismatch over 3 months (policy threshold 25%, §3.4)"),
        Check("E-invoice vs e-way bill value", "pass" if -0.05 <= gap <= 0.20 else "warn",
              f"e-way bills cover {(1 - gap) * 100:.0f}% of invoiced value"),
        Check("Data completeness (12 months)", "pass" if missing <= 3 else "warn",
              f"{missing} missing source-months, gaps forward-filled and flagged"),
        Check("GSTR-3B filing (12 months)", "pass" if late <= 1 else "warn",
              f"{12 - late} of 12 returns filed on time (§2.2)"),
    ]


class DataAgent(Agent):
    name = "data_agent"

    def grant_consent(self, app: Application):
        provider = get_consent_provider(self.db)
        return self.tool("consent_provider.request", provider.request, audit_app=app.id,
                         **{"application_id": app.id, "factory_id": app.factory_id, "as_of": sim_date(self.db),
                            "actor": self.actor.username})

    def revoke_consent(self, app: Application):
        provider = get_consent_provider(self.db)
        return self.tool("consent_provider.revoke", provider.revoke, audit_app=app.id,
                         **{"application_id": app.id, "actor": self.actor.username})

    def pull(self, app: Application) -> DataPullResult:
        """Raises ConsentError if consent is not active (revocation blocks all new pulls)."""
        today = sim_date(self.db)
        upto = last_visible_month(today)
        provider = get_consent_provider(self.db)
        self.tool("consent_provider.authorise_pull", provider.authorise_pull, audit_app=app.id,
                  **{"application_id": app.id, "factory_id": app.factory_id, "as_of": today,
                     "actor": self.actor.username, "detail": {"upto_month": upto}})
        history = self.tool("lake.history", get_lake().history, audit_app=app.id,
                            audit_output=lambda df: {"rows": len(df)},
                            **{"factory_id": app.factory_id, "upto_month": upto})
        checks = self.tool("reconcile", reconcile, audit_app=app.id,
                           audit_output=lambda cs: [asdict(c) for c in cs], **{"history": history})
        result = DataPullResult(
            factory_id=app.factory_id, months=len(history), from_month=month_label(int(history.month.min())),
            to_month=month_label(upto), upto_month=upto, checks=checks,
        )
        self.db.add(DataSnapshot(application_id=app.id, factory_id=app.factory_id, upto_month=upto,
                                 payload={"months": len(history), "checks": [asdict(c) for c in checks]}))
        self.db.commit()
        return result


__all__ = ["DataAgent", "DataPullResult", "ConsentError", "reconcile"]
