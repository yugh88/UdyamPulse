"""Gold layer: 60+ monthly factory features on 1/3/6/12-month windows, grouped into five pillars.

Every feature at month t uses only data from months <= t (no look-ahead). Each feature carries
metadata (pillar + plain-language template) so SHAP reasons can be rendered for humans.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.settings import get_settings

PILLARS: dict[str, dict] = {
    "order_book": {"label": "Order book & dispatch", "weight": 0.25},
    "cash_flow": {"label": "Cash-flow health", "weight": 0.25},
    "production": {"label": "Production intensity", "weight": 0.20},
    "receivables": {"label": "Receivable quality", "weight": 0.15},
    "compliance": {"label": "Compliance discipline", "weight": 0.15},
}


@dataclass(frozen=True)
class FeatureMeta:
    pillar: str
    template: str  # "{v}" is replaced by the formatted value
    kind: str  # pct_chg | pct | days | days_delta | count | months | x | years | num


FEATURES: dict[str, FeatureMeta] = {
    # ---- Order book & dispatch ----
    "eway_value_chg_1v3": FeatureMeta("order_book", "E-way bill value {v} vs 3-month average", "pct_chg"),
    "eway_value_chg_1v2": FeatureMeta("order_book", "E-way bill value {v} vs 8-week baseline", "pct_chg"),
    "eway_value_chg_3v12": FeatureMeta("order_book", "E-way bill value (3m) {v} vs 12-month average", "pct_chg"),
    "eway_value_yoy": FeatureMeta("order_book", "E-way bill value {v} year-on-year", "pct_chg"),
    "eway_count_chg_1v3": FeatureMeta("order_book", "E-way bill count {v} vs 3-month average", "pct_chg"),
    "eway_count_chg_3v12": FeatureMeta("order_book", "E-way bill count (3m) {v} vs 12-month average", "pct_chg"),
    "einvoice_value_chg_1v3": FeatureMeta("order_book", "E-invoice value {v} vs 3-month average", "pct_chg"),
    "einvoice_value_chg_3v12": FeatureMeta("order_book", "E-invoice value (3m) {v} vs 12-month average", "pct_chg"),
    "einvoice_value_yoy": FeatureMeta("order_book", "Invoiced sales {v} year-on-year", "pct_chg"),
    "einvoice_value_slope_6": FeatureMeta("order_book", "6-month sales trend {v} per month", "pct_chg"),
    "einvoice_count_chg_1v3": FeatureMeta("order_book", "E-invoice count {v} vs 3-month average", "pct_chg"),
    "po_cover_months": FeatureMeta("order_book", "Open purchase orders cover {v} of sales", "months"),
    "po_cover_chg_1v3": FeatureMeta("order_book", "Order-book cover {v} vs 3-month average", "pct_chg"),
    "eway_to_einvoice_ratio": FeatureMeta("order_book", "E-way bills match {v} of invoiced value", "pct"),
    "eway_value_cv_6": FeatureMeta("order_book", "Dispatch volatility (6m CV) at {v}", "pct"),
    "einvoice_value_cv_12": FeatureMeta("order_book", "Sales volatility (12m CV) at {v}", "pct"),
    # ---- Cash-flow health ----
    "net_inflow_ratio_1": FeatureMeta("cash_flow", "Net bank inflow margin {v} this month", "pct"),
    "net_inflow_ratio_3": FeatureMeta("cash_flow", "Net bank inflow margin {v} over 3 months", "pct"),
    "net_inflow_ratio_6": FeatureMeta("cash_flow", "Net bank inflow margin {v} over 6 months", "pct"),
    "credits_chg_1v3": FeatureMeta("cash_flow", "Bank credits {v} vs 3-month average", "pct_chg"),
    "credits_chg_3v12": FeatureMeta("cash_flow", "Bank credits (3m) {v} vs 12-month average", "pct_chg"),
    "credits_yoy": FeatureMeta("cash_flow", "Bank credits {v} year-on-year", "pct_chg"),
    "balance_chg_1v1": FeatureMeta("cash_flow", "Average balance {v} in 30 days", "pct_chg"),
    "balance_chg_1v3": FeatureMeta("cash_flow", "Average balance {v} vs 3-month average", "pct_chg"),
    "balance_cv_6": FeatureMeta("cash_flow", "Balance volatility (6m CV) at {v}", "pct"),
    "balance_to_debits_1": FeatureMeta("cash_flow", "Cash cushion of {v} of monthly outflows", "pct"),
    "balance_to_debits_3": FeatureMeta("cash_flow", "3-month cash cushion of {v} of outflows", "pct"),
    "bounces_1": FeatureMeta("cash_flow", "{v} cheque/NACH bounces this month", "count"),
    "bounces_3": FeatureMeta("cash_flow", "{v} cheque/NACH bounces in 3 months", "count"),
    "bounces_6": FeatureMeta("cash_flow", "{v} cheque/NACH bounces in 6 months", "count"),
    "bounces_12": FeatureMeta("cash_flow", "{v} cheque/NACH bounces in 12 months", "count"),
    "debits_to_credits_3": FeatureMeta("cash_flow", "Outflows are {v} of inflows (3m)", "pct"),
    "loan_to_turnover": FeatureMeta("cash_flow", "Requested loan is {v} of annual turnover", "pct"),
    # ---- Production intensity ----
    "kwh_chg_1v3": FeatureMeta("production", "Electricity use {v} vs 3-month average", "pct_chg"),
    "kwh_chg_1v2": FeatureMeta("production", "kWh {v} vs 8-week baseline", "pct_chg"),
    "kwh_chg_3v12": FeatureMeta("production", "Electricity use (3m) {v} vs 12-month average", "pct_chg"),
    "kwh_yoy": FeatureMeta("production", "Electricity use {v} year-on-year", "pct_chg"),
    "kwh_vs_sector": FeatureMeta("production", "Power intensity {v} vs sector peers", "pct_chg"),
    "kwh_per_lakh_3": FeatureMeta("production", "{v} kWh per ₹1 lakh of sales", "num"),
    "kwh_slope_6": FeatureMeta("production", "6-month power-use trend {v} per month", "pct_chg"),
    "kwh_cv_6": FeatureMeta("production", "Power-use volatility (6m CV) at {v}", "pct"),
    "rm_ratio_1": FeatureMeta("production", "Raw-material purchases at {v} of sales", "pct"),
    "rm_ratio_3": FeatureMeta("production", "Raw-material purchases at {v} of sales (3m)", "pct"),
    "rm_chg_1v3": FeatureMeta("production", "Raw-material purchases {v} vs 3-month average", "pct_chg"),
    "rm_chg_3v12": FeatureMeta("production", "Raw-material purchases (3m) {v} vs 12-month average", "pct_chg"),
    # ---- Receivable quality ----
    "top_buyer_share_1": FeatureMeta("receivables", "Top buyer is {v} of sales", "pct"),
    "top_buyer_share_6": FeatureMeta("receivables", "Top buyer averaged {v} of sales (6m)", "pct"),
    "buyer_hhi": FeatureMeta("receivables", "Buyer concentration index (HHI) at {v}", "num"),
    "top_buyer_share_chg_1v6": FeatureMeta("receivables", "Top-buyer share {v} vs 6-month average", "pct_chg"),
    "days_to_pay_1": FeatureMeta("receivables", "Buyers pay in {v}", "days"),
    "days_to_pay_3": FeatureMeta("receivables", "Buyers pay in {v} (3m average)", "days"),
    "days_to_pay_chg_1v3": FeatureMeta("receivables", "Days-to-pay {v} vs 3-month average", "days_delta"),
    "days_to_pay_chg_3v12": FeatureMeta("receivables", "Days-to-pay (3m) {v} vs 12-month average", "days_delta"),
    "days_to_pay_slope_6": FeatureMeta("receivables", "Days-to-pay trend {v} per month", "days_delta"),
    "n_buyers": FeatureMeta("receivables", "{v} active buyers", "count"),
    # ---- Compliance discipline ----
    "gst_delay_1": FeatureMeta("compliance", "GSTR-3B filed {v} late", "days"),
    "gst_delay_3": FeatureMeta("compliance", "GSTR-3B filed {v} late on average (3m)", "days"),
    "gst_late_months_3": FeatureMeta("compliance", "{v} late GST filings in 3 months", "count"),
    "gst_late_months_6": FeatureMeta("compliance", "{v} late GST filings in 6 months", "count"),
    "gst_late_months_12": FeatureMeta("compliance", "{v} late GST filings in 12 months", "count"),
    "gst_consecutive_late": FeatureMeta("compliance", "{v} consecutive late GST filings", "count"),
    "epfo_chg_1v3": FeatureMeta("compliance", "EPFO headcount {v} vs 3-month average", "pct_chg"),
    "epfo_chg_3v12": FeatureMeta("compliance", "EPFO headcount (3m) {v} vs 12-month average", "pct_chg"),
    "epfo_drop_months_6": FeatureMeta("compliance", "{v} months of EPFO headcount decline (6m)", "count"),
    "gst_bank_mismatch_1": FeatureMeta("compliance", "GST turnover vs bank credits gap of {v}", "pct"),
    "gst_bank_mismatch_3": FeatureMeta("compliance", "GST vs bank gap averages {v} (3m)", "pct"),
    "vintage_years": FeatureMeta("compliance", "{v} in business", "years"),
}
FEATURE_NAMES: list[str] = list(FEATURES)


def format_value(name: str, value: float) -> str:
    kind = FEATURES[name].kind
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    if kind == "pct_chg":
        arrow = "↑" if value > 0 else "↓"
        return f"{arrow}{abs(value) * 100:.0f}%"
    if kind == "pct":
        return f"{value * 100:.0f}%"
    if kind == "days":
        return f"{value:.0f} days"
    if kind == "days_delta":
        return f"{'+' if value >= 0 else '−'}{abs(value):.0f} days"
    if kind == "count":
        return f"{value:.0f}"
    if kind == "months":
        return f"{value:.1f} months"
    if kind == "years":
        return f"{value:.0f} years"
    return f"{value:.2f}" if abs(value) < 10 else f"{value:.0f}"


def describe(name: str, value: float) -> str:
    return FEATURES[name].template.replace("{v}", format_value(name, value))


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.replace(0, np.nan)


def _slope(x: pd.Series, w: int) -> pd.Series:
    """Rolling OLS slope normalised by the window mean (fractional change per month)."""
    t = np.arange(w) - (w - 1) / 2
    denom = (t**2).sum()

    def f(v: np.ndarray) -> float:
        m = v.mean()
        return float((t * (v - m)).sum() / denom / m) if m else 0.0

    return x.rolling(w, min_periods=w).apply(f, raw=True)


def _factory_features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("month")
    out = pd.DataFrame({"factory_id": g["factory_id"], "month": g["month"]}, index=g.index)

    def mean(col: str, w: int, shift: int = 0) -> pd.Series:
        return g[col].shift(shift).rolling(w, min_periods=1).mean()

    def chg(col: str, w: int) -> pd.Series:
        return _safe_div(g[col], mean(col, w, shift=1)) - 1

    def chg_3v12(col: str) -> pd.Series:
        return _safe_div(mean(col, 3), mean(col, 12)) - 1

    def cv(col: str, w: int) -> pd.Series:
        return _safe_div(g[col].rolling(w, min_periods=3).std(), mean(col, w))

    def yoy(col: str) -> pd.Series:
        return _safe_div(g[col], g[col].shift(12)) - 1

    out["eway_value_chg_1v3"] = chg("eway_value", 3)
    out["eway_value_chg_1v2"] = chg("eway_value", 2)
    out["kwh_chg_1v3"] = chg("kwh", 3)
    out["kwh_chg_1v2"] = chg("kwh", 2)
    out["eway_value_chg_3v12"] = chg_3v12("eway_value")
    out["eway_value_yoy"] = yoy("eway_value")
    out["eway_count_chg_1v3"] = chg("eway_count", 3)
    out["eway_count_chg_3v12"] = chg_3v12("eway_count")
    out["einvoice_value_chg_1v3"] = chg("einvoice_value", 3)
    out["einvoice_value_chg_3v12"] = chg_3v12("einvoice_value")
    out["einvoice_value_yoy"] = yoy("einvoice_value")
    out["einvoice_value_slope_6"] = _slope(g["einvoice_value"], 6)
    out["einvoice_count_chg_1v3"] = chg("einvoice_count", 3)
    po_cover = _safe_div(g["open_po_value"], mean("einvoice_value", 3))
    out["po_cover_months"] = po_cover
    out["po_cover_chg_1v3"] = _safe_div(po_cover, po_cover.shift(1).rolling(3, min_periods=1).mean()) - 1
    out["eway_to_einvoice_ratio"] = _safe_div(g["eway_value"], g["einvoice_value"])
    out["eway_value_cv_6"] = cv("eway_value", 6)
    out["einvoice_value_cv_12"] = cv("einvoice_value", 12)

    net = g["aa_credits"] - g["aa_debits"]
    for w in (1, 3, 6):
        out[f"net_inflow_ratio_{w}"] = _safe_div(
            net.rolling(w, min_periods=1).sum(), g["aa_credits"].rolling(w, min_periods=1).sum()
        )
    out["credits_chg_1v3"] = chg("aa_credits", 3)
    out["credits_chg_3v12"] = chg_3v12("aa_credits")
    out["credits_yoy"] = yoy("aa_credits")
    out["balance_chg_1v1"] = chg("avg_balance", 1)
    out["balance_chg_1v3"] = chg("avg_balance", 3)
    out["balance_cv_6"] = cv("avg_balance", 6)
    out["balance_to_debits_1"] = _safe_div(g["avg_balance"], g["aa_debits"])
    out["balance_to_debits_3"] = _safe_div(mean("avg_balance", 3), mean("aa_debits", 3))
    for w in (1, 3, 6, 12):
        out[f"bounces_{w}"] = g["bounces"].rolling(w, min_periods=1).sum()
    out["debits_to_credits_3"] = _safe_div(mean("aa_debits", 3), mean("aa_credits", 3))
    out["loan_to_turnover"] = _safe_div(g["loan_requested_inr"], mean("gst_turnover", 12) * 12)

    out["kwh_chg_3v12"] = chg_3v12("kwh")
    out["kwh_yoy"] = yoy("kwh")
    kwh_per_lakh = _safe_div(mean("kwh", 3), mean("einvoice_value", 3) / 1e5)
    out["kwh_per_lakh_3"] = kwh_per_lakh
    out["kwh_slope_6"] = _slope(g["kwh"], 6)
    out["kwh_cv_6"] = cv("kwh", 6)
    out["rm_ratio_1"] = _safe_div(g["rm_purchases"], g["einvoice_value"])
    out["rm_ratio_3"] = _safe_div(mean("rm_purchases", 3), mean("einvoice_value", 3))
    out["rm_chg_1v3"] = chg("rm_purchases", 3)
    out["rm_chg_3v12"] = chg_3v12("rm_purchases")

    top = g["top_buyer_share"]
    n = g["n_buyers"].clip(lower=2)
    out["top_buyer_share_1"] = top
    out["top_buyer_share_6"] = top.rolling(6, min_periods=1).mean()
    out["buyer_hhi"] = top**2 + (1 - top) ** 2 / (n - 1)
    out["top_buyer_share_chg_1v6"] = _safe_div(top, top.shift(1).rolling(6, min_periods=1).mean()) - 1
    dtp = g["avg_days_to_pay"]
    out["days_to_pay_1"] = dtp
    out["days_to_pay_3"] = mean("avg_days_to_pay", 3)
    out["days_to_pay_chg_1v3"] = dtp - mean("avg_days_to_pay", 3, shift=1)
    out["days_to_pay_chg_3v12"] = mean("avg_days_to_pay", 3) - mean("avg_days_to_pay", 12)
    out["days_to_pay_slope_6"] = _slope(dtp, 6) * dtp.rolling(6, min_periods=1).mean()
    out["n_buyers"] = g["n_buyers"]

    delay = g["gst_filing_delay_days"]
    late = (delay > 0).astype(float)
    out["gst_delay_1"] = delay
    out["gst_delay_3"] = mean("gst_filing_delay_days", 3)
    for w in (3, 6, 12):
        out[f"gst_late_months_{w}"] = late.rolling(w, min_periods=1).sum()
    run = late.groupby((late == 0).cumsum()).cumsum()
    out["gst_consecutive_late"] = run
    out["epfo_chg_1v3"] = chg("epfo_headcount", 3)
    out["epfo_chg_3v12"] = chg_3v12("epfo_headcount")
    hc_drop = (g["epfo_headcount"].pct_change() < -0.03).astype(float)
    out["epfo_drop_months_6"] = hc_drop.rolling(6, min_periods=1).sum()
    out["gst_bank_mismatch_1"] = g["gst_bank_mismatch"]
    out["gst_bank_mismatch_3"] = g["gst_bank_mismatch"].rolling(3, min_periods=1).mean()
    out["vintage_years"] = g["vintage_years"] + (g["month"] - g["month"].max()) / 12
    return out


def compute_features(silver: pd.DataFrame, profile: pd.DataFrame) -> pd.DataFrame:
    df = silver.merge(
        profile[["factory_id", "sector", "n_buyers", "vintage_years", "loan_requested_inr"]], on="factory_id"
    )
    parts = [_factory_features(g) for _, g in df.groupby("factory_id", sort=True)]
    feats = pd.concat(parts, ignore_index=True)

    # Cross-sectional: power intensity relative to sector peers in the same month.
    feats = feats.merge(df[["factory_id", "month", "sector"]], on=["factory_id", "month"])
    sector_median = feats.groupby(["sector", "month"])["kwh_per_lakh_3"].transform("median")
    feats["kwh_vs_sector"] = _safe_div(feats["kwh_per_lakh_3"], sector_median) - 1
    feats = feats.drop(columns=["sector"])

    feats = feats.replace([np.inf, -np.inf], np.nan)
    missing = set(FEATURE_NAMES) - set(feats.columns)
    assert not missing, f"features not computed: {missing}"
    return feats[["factory_id", "month", *FEATURE_NAMES]]


def build_gold() -> pd.DataFrame:
    s = get_settings()
    silver = pd.read_parquet(s.silver / "factory_month.parquet")
    profile = pd.read_parquet(s.silver / "factories.parquet")
    feats = compute_features(silver, profile)
    s.gold.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(s.gold / "features.parquet", index=False)
    labels = pd.read_parquet(s.bronze / "_truth_monthly.parquet")
    labels.to_parquet(s.gold / "labels.parquet", index=False)
    return feats
