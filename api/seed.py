"""Seed the OLTP database for the demo: users, a monitored portfolio (with consent and limits) and
pending applications including the hero factory. Usage: python -m api.seed"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from agents.base import set_sim_date
from agents.ews_agent import EarlyWarningAgent
from agents.policy_engine import assess_limit
from agents.providers.consent import MockAAConsentProvider
from agents.providers.lake import get_lake
from api.audit import Actor
from api.auth import hash_password
from api.models.db import Application, Base, SessionLocal, User, get_engine
from core.settings import get_settings
from core.timeline import month_end

DEMO_PASSWORD = "demo123"
HERO = "UP-F0001"
USERS = [
    ("rm1", "Relationship Manager · Ludhiana", "rm", None),
    ("co1", "Credit Officer · MSME Hub", "credit_officer", None),
    ("risk1", "Chief Risk Office", "risk", None),
    ("sharma", "Sharma Auto Components", "msme", HERO),
]
PORTFOLIO_SIZE = 140


def main() -> None:
    s = get_settings()
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    rng = np.random.default_rng(s.seed)
    seed_actor = Actor("seed", "system")
    lake = get_lake()
    profiles = lake.profiles().set_index("factory_id")
    scores = lake.scores(24)
    truth = pd.read_parquet(s.bronze / "_truth_factory.parquet").set_index("factory_id")
    labels = pd.read_parquet(s.gold / "labels.parquet")
    alive20 = set(labels[(labels.month == 20) & (labels.is_post_default == 0)].factory_id)

    s20 = scores[scores.month == 20].set_index("factory_id")
    # Pending applications: the hero plus one unit per band for the console list.
    pending = [HERO]
    for band in ("APPROVE", "WATCH", "HIGH_RISK"):
        cands = [f for f in s20[s20.band == band].index if f != HERO and f in alive20 and f not in pending]
        pending.append(str(rng.choice(cands)))
    watch_factory = pending[2]

    for username, display, role, fid in USERS + [("msme2", profiles.loc[watch_factory, "name"], "msme", watch_factory)]:
        db.add(User(username=username, display_name=display, role=role, factory_id=fid,
                    password_hash=hash_password(DEMO_PASSWORD)))
    db.commit()
    set_sim_date(db, s.sim_start)

    # Monitored portfolio: every eligible unit with a stress event in months 21-24, topped up at random.
    eligible = [f for f in s20.index if f in alive20 and f not in pending and s20.loc[f, "score"] >= 600]
    stressed = [f for f in eligible if pd.notna(truth.loc[f, "stress_month"]) and 21 <= truth.loc[f, "stress_month"] <= 24]
    others = [f for f in eligible if f not in stressed and s20.loc[f, "score"] >= 650]
    chosen = stressed + list(rng.choice(others, size=PORTFOLIO_SIZE - len(stressed), replace=False))

    consent = MockAAConsentProvider(db)
    for fid in chosen:
        p = profiles.loc[fid]
        m0 = int(rng.integers(10, 19))
        sc = scores[(scores.factory_id == fid) & (scores.month == m0)].iloc[0]
        hist = lake.history(fid, m0)
        annual = float(hist.tail(12).gst_turnover.sum() * 12 / len(hist.tail(12)))
        band = sc.band if sc.band != "HIGH_RISK" else "WATCH"
        lim = assess_limit(annual, float(p.loan_requested_inr), int(sc.score), band, float(hist.top_buyer_share.iloc[-1]))
        app = Application(
            factory_id=fid, state="MONITORING", channel="rm", requested_amount=float(p.loan_requested_inr),
            score=int(sc.score), band=sc.band, pd_12m=float(sc.pd_12m), score_month=m0, decision="APPROVED",
            decision_comment="Sanctioned under programme (seed data)", decided_by="co1",
            recommended_limit=lim.recommended_limit, sanctioned_limit=max(lim.recommended_limit, 1e5),
            pricing_band=lim.pricing_band, disbursed_on=month_end(m0) + timedelta(days=10),
            disbursement_ref=f"LOS-SEED{fid[-4:]}", last_ews_month=19,
        )
        db.add(app)
        db.flush()
        consent.request(app.id, fid, month_end(m0), "seed")

    for fid in pending:
        db.add(Application(factory_id=fid, state="APPLIED", channel="rm" if fid == HERO else "app",
                           requested_amount=float(profiles.loc[fid, "loan_requested_inr"])))
    db.commit()

    run = EarlyWarningAgent(db, seed_actor).run()
    print(f"seeded users={len(USERS) + 1} portfolio={len(chosen)} (stressed in window: {len(stressed)}) "
          f"pending={pending} initial_alerts={len(run.new_alerts)} sim_date={s.sim_start}")
    print(f"demo logins (password '{DEMO_PASSWORD}'): rm1, co1, risk1, sharma (MSME hero), msme2 (watch-band MSME)")
    db.close()


if __name__ == "__main__":
    main()
