"""Audit M10: the model must move in the economically sensible direction for directional signals."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from agents.providers.lake import get_lake
from ml.features import FEATURE_NAMES, MONOTONE
from ml.scoring import get_scorer
from ml.simulate import simulated_features

# lever, change, direction the score may move, tolerated share of factories moving the other way. Levers that
# touch only constrained features must never move the wrong way. Composite levers also move unconstrained
# intensity features (power per ₹ of sales, change in buyer concentration), so small exceptions remain and
# are bounded here rather than hidden.
CASES = [
    ("credits_pct", -30, -1, 0.0), ("bounces_count", 2, -1, 0.0),
    ("days_to_pay_days", 30, -1, 0.0), ("days_to_pay_days", -20, 1, 0.0),
    ("dispatch_pct", -30, -1, 0.06), ("dispatch_pct", 30, 1, 0.06),
    ("kwh_pct", -30, -1, 0.25), ("top_buyer_share_pp", 15, -1, 0.35),
]
MAX_WRONG_WAY_POINTS = 20


def _sample(n: int = 40) -> list[str]:
    ids = get_lake().profiles()["factory_id"].tolist()
    rng = np.random.default_rng(0)
    return ["UP-F0001", *rng.choice([i for i in ids if i != "UP-F0001"], n, replace=False).tolist()]


@pytest.mark.parametrize("lever,change,direction,tolerance", CASES)
def test_simulated_changes_move_the_score_the_sensible_way(lever, change, direction, tolerance):
    lake, scorer = get_lake(), get_scorer()
    wrong, n = [], 0
    for fid in _sample(80):
        history = lake.history(fid, 20)
        if len(history) < 12:
            continue
        n += 1
        base_row = lake.features(fid, 20)
        base = scorer.explain_row(base_row).score
        sim = scorer.explain_row(simulated_features(history, lake.profile(fid), base_row, {lever: change})).score
        if (sim - base) * direction < -1e-9:  # moved against the allowed direction
            wrong.append((fid, base, sim))
    assert len(wrong) <= tolerance * n, f"{lever} {change:+}: {len(wrong)}/{n} moved the wrong way: {wrong[:5]}"
    assert all(abs(sim - base) <= MAX_WRONG_WAY_POINTS for _, base, sim in wrong), wrong


def test_every_constrained_feature_is_monotone_in_the_trained_model():
    scorer = get_scorer()
    feats = pd.read_parquet(get_lake_gold()).sample(300, random_state=1)
    grid = np.linspace(-2, 2, 9)
    for name, direction in MONOTONE.items():
        if not direction:
            continue
        col = feats[name].fillna(feats[name].median())
        spread = col.std() or 1.0
        rows = pd.concat([feats.assign(**{name: col + g * spread}) for g in grid], keys=range(len(grid)))
        pdv = scorer.predict_pd(rows[FEATURE_NAMES]).reshape(len(grid), -1)
        steps = np.diff(pdv, axis=0) * direction
        assert (steps >= -1e-12).all(), f"{name} is not monotone ({direction:+})"


def get_lake_gold():
    from core.settings import get_settings

    return get_settings().gold / "features.parquet"
