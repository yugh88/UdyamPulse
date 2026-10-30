"""Orchestrator agent: runs the loan-journey state machine and delegates to the specialist agents.

APPLIED -> CONSENTED -> SCORED -> MEMO_DRAFTED -> DECIDED -> DISBURSED -> MONITORING
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from sqlalchemy.orm import Session

from agents.base import Agent, sim_date
from agents.data_agent import DataAgent
from agents.memo_agent import MemoAgent
from agents.policy_engine import inr
from agents.providers.lake import get_lake
from api.audit import Actor, log_event
from api.models.db import Application, Notification
from ml.scoring import get_scorer

TRANSITIONS: dict[str, set[str]] = {
    "APPLIED": {"CONSENTED"},
    "CONSENTED": {"SCORED"},
    "SCORED": {"SCORED", "MEMO_DRAFTED"},
    "MEMO_DRAFTED": {"MEMO_DRAFTED", "DECIDED"},
    "DECIDED": {"DISBURSED"},
    "DISBURSED": {"MONITORING"},
    "MONITORING": set(),
}


class InvalidTransition(Exception):
    pass


class Orchestrator(Agent):
    name = "orchestrator"

    def __init__(self, db: Session, actor: Actor) -> None:
        super().__init__(db, actor)
        self.data_agent = DataAgent(db, actor)
        self.memo_agent = MemoAgent(db, actor)

    # ---- state machine ----------------------------------------------------------------------
    def _transition(self, app: Application, new_state: str) -> None:
        if new_state not in TRANSITIONS.get(app.state, set()):
            raise InvalidTransition(f"Cannot move application {app.id} from {app.state} to {new_state}")
        old = app.state
        app.state = new_state
        log_event(self.db, self.actor, agent=self.name, tool="state_machine", action="transition",
                  inputs={"from": old, "to": new_state}, output={"state": new_state}, application_id=app.id,
                  commit=False)

    def _notify(self, factory_id: str, text: str) -> None:
        self.db.add(Notification(factory_id=factory_id, text=text, sim_date=sim_date(self.db)))

    # ---- journey steps ----------------------------------------------------------------------
    def create(self, factory_id: str, requested_amount: float | None, channel: str) -> Application:
        profile = get_lake().profile(factory_id)
        app = Application(factory_id=factory_id, requested_amount=requested_amount or profile["loan_requested_inr"],
                          channel=channel, state="APPLIED")
        self.db.add(app)
        self.db.flush()
        log_event(self.db, self.actor, agent=self.name, tool="applications", action="create",
                  inputs={"factory_id": factory_id, "requested_amount": app.requested_amount, "channel": channel},
                  output={"id": app.id}, application_id=app.id)
        return app

    def consent(self, app: Application) -> dict:
        artefact = self.data_agent.grant_consent(app)
        pull = self.data_agent.pull(app)
        app.data_checks = [asdict(c) for c in pull.checks]
        if app.state == "APPLIED":
            self._transition(app, "CONSENTED")
        self._notify(app.factory_id, "Consent received via Account Aggregator for your loan application. "
                                     "Purpose: working-capital assessment and monitoring. You can revoke it any time in the app.")
        self.db.commit()
        return {"consent": asdict(artefact), "data_pull": pull.to_dict()}

    def revoke(self, app: Application) -> dict:
        artefact = self.data_agent.revoke_consent(app)
        self._notify(app.factory_id, "Your data-sharing consent has been revoked. The bank will not fetch new data "
                                     "and previously fetched copies are being deleted.")
        self.db.commit()
        return asdict(artefact)

    def score(self, app: Application) -> dict:
        pull = self.data_agent.pull(app)  # raises ConsentError if consent was revoked
        row = get_lake().features(app.factory_id, pull.upto_month)
        result = self.tool("scoring_engine.explain", get_scorer().explain_row, audit_app=app.id,
                           **{"row": row}).to_dict()
        app.score, app.band, app.pd_12m = result["score"], result["band"], result["pd_12m"]
        app.score_month, app.score_detail = result["month"], result
        app.data_checks = [asdict(c) for c in pull.checks]
        self._transition(app, "SCORED")
        self.db.commit()
        return result

    def draft_memo(self, app: Application) -> dict:
        if app.score_detail is None:
            raise InvalidTransition("Score the application before drafting a memo")
        if app.state not in ("SCORED", "MEMO_DRAFTED"):
            raise InvalidTransition(f"Cannot draft memo in state {app.state}")
        lake = get_lake()
        pull = self.data_agent.pull(app)
        history = lake.history(app.factory_id, pull.upto_month)
        memo = self.memo_agent.draft(app, lake.profile(app.factory_id), history, app.score_detail)
        app.memo, app.memo_pdf = memo, memo["pdf_path"]
        app.recommended_limit, app.pricing_band = memo["recommended_limit"], memo["pricing_band"]
        self._transition(app, "MEMO_DRAFTED")
        self.db.commit()
        return memo

    def decide(self, app: Application, decision: str, comment: str, sanctioned_limit: float | None) -> dict:
        if not comment or not comment.strip():
            raise ValueError("A decision comment is mandatory")
        self._transition(app, "DECIDED")
        app.decision, app.decision_comment, app.decided_by = decision, comment.strip(), self.actor.username
        if decision == "APPROVED":
            app.sanctioned_limit = sanctioned_limit or app.recommended_limit
            app.kfs = key_fact_statement(app)
            self._notify(app.factory_id, f"Good news! Your working-capital limit of {inr(app.sanctioned_limit)} is "
                                         "approved. Please review the Key Fact Statement before signing.")
        else:
            self._notify(app.factory_id, "Your application was not approved this time. Open the app to see the "
                                         "main reasons and your 90-day improvement plan, or request a human review.")
        log_event(self.db, self.actor, agent=self.name, tool="credit_decision", action=decision.lower(),
                  inputs={"comment": comment, "sanctioned_limit": app.sanctioned_limit},
                  output={"decision": decision}, application_id=app.id, commit=False)
        self.db.commit()
        return {"decision": decision, "kfs": app.kfs}

    def disburse(self, app: Application) -> dict:
        if app.decision != "APPROVED":
            raise InvalidTransition("Only approved applications can be disbursed")
        self._transition(app, "DISBURSED")
        app.disbursement_ref = f"LOS-{uuid.uuid4().hex[:10].upper()}"
        app.disbursed_on = sim_date(self.db)
        log_event(self.db, self.actor, agent=self.name, tool="los_stub.disburse", action="disburse",
                  inputs={"amount": app.sanctioned_limit, "to": "borrower's own account (direct, per DLD 2025)"},
                  output={"ref": app.disbursement_ref}, application_id=app.id, commit=False)
        self._transition(app, "MONITORING")
        app.last_ews_month = app.score_month
        self._notify(app.factory_id, f"Your limit of {inr(app.sanctioned_limit or 0)} is now active in your "
                                     f"account (ref {app.disbursement_ref}).")
        self.db.commit()
        return {"disbursement_ref": app.disbursement_ref, "disbursed_on": str(app.disbursed_on), "state": app.state}


def key_fact_statement(app: Application) -> dict:
    """KFS stub (RBI Digital Lending Directions 2025). Final APR is computed by the lender's LOS."""
    return {
        "status": "STUB — generated by the regulated lender's LOS in production",
        "lender": "Sample Bank Ltd (Regulated Entity)",
        "technology_service_provider": "UdyamPulse",
        "product": "Working-capital cash credit (MSME)",
        "sanctioned_limit": inr(app.sanctioned_limit or 0),
        "interest": f"{app.pricing_band} (EBLR-linked, floating)",
        "fees": "Processing fee and CGTMSE guarantee fee as per schedule (shown in rupees before signing)",
        "apr": "Annual Percentage Rate disclosed by the lender's LOS before execution",
        "tenor": "12 months, renewable on review",
        "disbursal": "Directly to the borrower's own bank account; no pass-through accounts",
        "cooling_off": "Borrower may exit within the look-up period without penalty",
        "grievance": "Nodal grievance redressal officer of the lender; escalation to RBI Integrated Ombudsman",
        "ai_disclosure": "AI-assisted analysis was used; the decision was made by an authorised credit officer",
    }
