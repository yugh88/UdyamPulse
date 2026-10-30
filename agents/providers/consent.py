"""Consent providers. The mock simulates an Account Aggregator (FIU-side) consent artefact with
purpose, data range, expiry and revocation, backed by the consent ledger (DPDP Act 2023)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from agents.providers.base import ConsentArtefact
from api.models.db import Consent, ConsentEvent, DataSnapshot, utcnow
from core.settings import get_settings

PURPOSE = "MSME working-capital underwriting and loan monitoring by the lender (Account Aggregator purpose code 101)"
FI_TYPES = ["DEPOSIT", "GST_GSTR1_3B", "EWAY_BILL", "ELECTRICITY", "EPFO"]


class ConsentError(PermissionError):
    pass


def _to_artefact(c: Consent) -> ConsentArtefact:
    return ConsentArtefact(
        consent_id=c.id, factory_id=c.factory_id, purpose=c.purpose, fi_types=list(c.fi_types),
        data_from=c.data_from, data_to=c.data_to, expires_on=c.expires_on, frequency=c.frequency, status=c.status,
    )


class MockAAConsentProvider:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _ledger(self, consent: Consent, event: str, actor: str, detail: dict | None = None) -> None:
        self.db.add(ConsentEvent(consent_id=consent.id, factory_id=consent.factory_id, event=event, actor=actor,
                                 detail=detail))

    def request(self, application_id: int, factory_id: str, as_of: date, actor: str) -> ConsentArtefact:
        existing = self._current(application_id)
        if existing and existing.status == "ACTIVE":
            return _to_artefact(existing)
        start = get_settings().panel_start
        c = Consent(
            id=f"AA-CNS-{uuid.uuid4().hex[:12].upper()}", application_id=application_id, factory_id=factory_id,
            purpose=PURPOSE, fi_types=FI_TYPES, data_from=start, data_to=as_of + timedelta(days=365),
            expires_on=as_of + timedelta(days=730), frequency="MONTHLY", status="ACTIVE",
        )
        self.db.add(c)
        self.db.flush()
        self._ledger(c, "GRANTED", actor, {"purpose": PURPOSE, "fi_types": FI_TYPES, "expires_on": str(c.expires_on)})
        self.db.commit()
        return _to_artefact(c)

    def revoke(self, application_id: int, actor: str) -> ConsentArtefact:
        c = self._current(application_id)
        if c is None:
            raise ConsentError("No consent on record for this application")
        if c.status != "REVOKED":
            c.status = "REVOKED"
            c.revoked_at = utcnow()
            self._ledger(c, "REVOKED", actor)
            deleted = self.db.query(DataSnapshot).filter_by(application_id=application_id).delete()
            self._ledger(c, "DELETION_JOB", "system", {"snapshots_deleted": deleted, "status": "completed"})
            self.db.commit()
        return _to_artefact(c)

    def active(self, application_id: int, as_of: date) -> ConsentArtefact | None:
        c = self._current(application_id)
        if c is None or c.status != "ACTIVE":
            return None
        if c.expires_on < as_of:
            c.status = "EXPIRED"
            self._ledger(c, "EXPIRED", "system")
            self.db.commit()
            return None
        return _to_artefact(c)

    def authorise_pull(self, application_id: int, factory_id: str, as_of: date, actor: str, detail: dict) -> ConsentArtefact:
        """Gate every data pull on an active consent; record the pull (or the blocked attempt) in the ledger."""
        art = self.active(application_id, as_of)
        if art is None:
            c = self._current(application_id)
            if c is not None:
                self._ledger(c, "PULL_BLOCKED", actor, {"reason": f"consent {c.status}", **detail})
                self.db.commit()
            raise ConsentError(f"No active consent for application {application_id}; data pull blocked")
        c = self._current(application_id)
        self._ledger(c, "DATA_PULL", actor, detail)
        return art

    def _current(self, application_id: int) -> Consent | None:
        return (
            self.db.query(Consent).filter_by(application_id=application_id).order_by(Consent.granted_at.desc()).first()
        )


class SahamatiAAConsentProvider:  # pragma: no cover - production adapter
    """Real AA integration (ReBIT FIU APIs via a licensed AA) — consent request, FI fetch, decryption."""

    def __init__(self, db: Session) -> None:
        raise NotImplementedError("Use UP_CONSENT_PROVIDER=mock_aa for the local prototype")


def get_consent_provider(db: Session) -> MockAAConsentProvider:
    if get_settings().consent_provider == "sahamati_aa":
        return SahamatiAAConsentProvider(db)  # type: ignore[return-value]
    return MockAAConsentProvider(db)
