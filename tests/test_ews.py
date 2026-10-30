import json

import pandas as pd
import pytest

from agents.providers.lake import get_lake
from core.settings import get_settings
from ml.ews import evaluate, explain, next_best_action


def _inputs(**overrides) -> pd.DataFrame:
    base = dict(factory_id="T", month=10, eway_chg=0.0, kwh_chg=0.0, bounces=0, balance_chg_30d=0.0,
                top_buyer_share=0.3, dtp_increase=0.0, gst_bank_mismatch=0.05, consecutive_late=0,
                d_eway_value=0.0, d_einvoice_value=0.0, d_kwh=0.0, d_aa_credits=0.0, d_avg_balance=0.0,
                d_rm_purchases=0.0, d_epfo_headcount=0.0, d_bounces=0.0, d_dtp=0.0)
    base.update(overrides)
    return pd.DataFrame([base])


def _eval(**kw) -> pd.Series:
    return evaluate(_inputs(**kw), anomaly_model=None).iloc[0]


def test_healthy_month_raises_nothing():
    r = _eval()
    assert r.severity is None and next_best_action(r) is None


def test_order_loss_needs_both_eway_and_kwh_drop():
    assert not _eval(eway_chg=-0.45, kwh_chg=-0.10).order_loss
    assert not _eval(eway_chg=-0.30, kwh_chg=-0.35).order_loss
    r = _eval(eway_chg=-0.42, kwh_chg=-0.32)
    assert r.order_loss and r.severity == "high"
    assert next_best_action(r) == "visit + limit review"
    assert "e-way bills ↓42% and kWh ↓32%" in explain(r)[0]


@pytest.mark.parametrize("kw", [dict(bounces=2), dict(balance_chg_30d=-0.55)])
def test_cash_squeeze(kw):
    r = _eval(**kw)
    assert r.cash_squeeze and r.severity == "medium"


def test_buyer_risk_requires_concentration_and_slower_pay():
    assert not _eval(top_buyer_share=0.6, dtp_increase=10).buyer_risk
    assert not _eval(top_buyer_share=0.4, dtp_increase=25).buyer_risk
    assert _eval(top_buyer_share=0.6, dtp_increase=25).buyer_risk


def test_diversion_and_compliance_slip():
    assert _eval(gst_bank_mismatch=0.30).diversion
    assert not _eval(gst_bank_mismatch=0.20).diversion
    r = _eval(consecutive_late=2)
    assert r.compliance_slip and r.severity == "low" and next_best_action(r) == "call"


def test_hero_gets_high_alert_in_month_21():
    hits = get_lake().ews_hits("UP-F0001", [20, 21])
    m20, m21 = hits[hits.month == 20].iloc[0], hits[hits.month == 21].iloc[0]
    assert not isinstance(m20.severity, str)
    assert m21.severity == "high" and m21.order_loss
    assert m21.next_best_action == "visit + limit review"


def test_backtest_lead_time_target():
    report = json.loads((get_settings().reports / "ews_backtest.json").read_text())
    assert report["median_lead_days"] >= 60
    assert report["recall"] >= 0.7
