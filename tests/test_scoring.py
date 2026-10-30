import json

import numpy as np
import pytest

from agents.providers.lake import get_lake
from core.settings import get_settings
from ml.features import FEATURE_NAMES, FEATURES, PILLARS, describe
from ml.scoring import band_for, get_scorer, pd_to_score


def test_at_least_60_features_in_five_pillars():
    assert len(FEATURE_NAMES) >= 60
    assert {m.pillar for m in FEATURES.values()} == set(PILLARS)
    assert abs(sum(p["weight"] for p in PILLARS.values()) - 1.0) < 1e-9


def test_score_mapping_is_monotonic_and_bounded():
    pds = np.linspace(0.0001, 0.9999, 500)
    scores = pd_to_score(pds)
    assert np.all(np.diff(scores) <= 0), "higher PD must never give a higher score"
    assert scores.min() >= 300 and scores.max() <= 900


@pytest.mark.parametrize("score,band", [(900, "APPROVE"), (650, "APPROVE"), (649, "WATCH"), (550, "WATCH"),
                                        (549, "HIGH_RISK"), (300, "HIGH_RISK")])
def test_bands(score, band):
    assert band_for(score) == band


def test_hero_scores_in_approve_band_with_five_reasons():
    row = get_lake().features("UP-F0001", 20)
    res = get_scorer().explain_row(row)
    assert res.band == "APPROVE"
    assert 690 <= res.score <= 750
    assert len(res.reasons) == 5
    assert all(r.text and r.direction in ("risk_up", "risk_down") for r in res.reasons)
    assert len(res.pillars) == 5


def test_shap_points_add_up_to_score():
    row = get_lake().features("UP-F0001", 20)
    res = get_scorer().explain_row(row)
    total = res.base_points + sum(p["points"] for p in res.pillars)
    assert abs(total - res.score) <= 1.5


def test_reason_text_is_plain_language():
    assert describe("eway_value_chg_1v3", -0.38) == "E-way bill value ↓38% vs 3-month average"
    assert describe("bounces_3", 2) == "2 cheque/NACH bounces in 3 months"


def test_holdout_auc_target_met():
    metrics = json.loads((get_settings().reports / "metrics.json").read_text())
    assert metrics["test"]["auc"] >= 0.80
