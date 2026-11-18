"""What-if simulation: change a few raw signals for the latest months, recompute the same features the
model was trained on, and re-score. Read-only: nothing here is persisted or treated as a decision."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.features import FEATURE_NAMES, _factory_features, _safe_div

WINDOW_MONTHS = 3  # flow adjustments apply to the latest three months
# Stocks are point-in-time snapshots: a change applies to the current snapshot only. Rewriting past order-book
# snapshots made the 3-month order-cover change read as *improving* when dispatches fell (audit M10).
STOCK_COLUMNS = frozenset({"open_po_value"})


@dataclass(frozen=True)
class Lever:
    key: str
    label: str
    unit: str  # "%" (relative change), "pp" (percentage points) or "days" / "count" (absolute change)
    min: float
    max: float
    step: float
    columns: tuple[str, ...]
    help: str


LEVERS: tuple[Lever, ...] = (
    Lever("dispatch_pct", "Dispatches and sales", "%", -50, 50, 5,
          ("eway_value", "eway_count", "einvoice_value", "einvoice_count", "gst_turnover", "open_po_value", "rm_purchases"),
          "E-way bills, e-invoices, GST turnover, open orders and raw-material purchases move together"),
    Lever("kwh_pct", "Electricity use", "%", -50, 50, 5, ("kwh",), "Production proxy from the power meter"),
    Lever("credits_pct", "Bank inflows", "%", -50, 50, 5, ("aa_credits",), "Credits seen through the Account Aggregator"),
    Lever("top_buyer_share_pp", "Top-buyer share", "pp", -30, 30, 5, ("top_buyer_share",), "Share of sales to the largest buyer"),
    Lever("days_to_pay_days", "Days buyers take to pay", "days", -30, 45, 5, ("avg_days_to_pay",), "Average receivable days"),
    Lever("bounces_count", "Cheque/NACH bounces per month", "count", 0, 4, 1, ("bounces",), "Added to each of the latest months"),
)
LEVER_BY_KEY = {lv.key: lv for lv in LEVERS}


def apply_adjustments(history: pd.DataFrame, adjustments: dict[str, float]) -> pd.DataFrame:
    """Return a copy of the factory's monthly history with the adjustments applied to the latest months."""
    unknown = set(adjustments) - set(LEVER_BY_KEY)
    if unknown:
        raise KeyError(f"unknown levers: {sorted(unknown)}")
    out = history.sort_values("month").copy()
    window = out["month"] > out["month"].max() - WINDOW_MONTHS
    latest = out["month"] == out["month"].max()
    for key, raw in adjustments.items():
        lv = LEVER_BY_KEY[key]
        value = float(np.clip(raw, lv.min, lv.max))
        for col in lv.columns:
            recent = latest if col in STOCK_COLUMNS else window
            series = out.loc[recent, col].astype(float)
            if lv.unit == "%":
                series = series * (1 + value / 100)
            elif lv.unit == "pp":
                series = (series + value / 100).clip(0.02, 0.98)
            else:
                series = (series + value).clip(lower=0)
            out[col] = out[col].astype(float)
            out.loc[recent, col] = series
    return out


def simulated_features(history: pd.DataFrame, profile: dict, base_row: pd.Series, adjustments: dict[str, float]) -> pd.Series:
    """Feature row for the latest month after the adjustments, built by the training feature code."""
    adj = apply_adjustments(history, adjustments)
    for col in ("sector", "n_buyers", "vintage_years", "loan_requested_inr"):
        adj[col] = profile[col]
    row = _factory_features(adj).iloc[-1].copy()
    # The sector median is held fixed: one factory changing does not move its peers.
    base_intensity, base_rel = base_row["kwh_per_lakh_3"], base_row["kwh_vs_sector"]
    sector_median = base_intensity / (1 + base_rel) if pd.notna(base_rel) and pd.notna(base_intensity) else np.nan
    row["kwh_vs_sector"] = float(_safe_div(pd.Series([row["kwh_per_lakh_3"]]), pd.Series([sector_median])).iloc[0]) - 1
    row["vintage_years"] = base_row["vintage_years"]  # age does not change in a what-if
    row = row.replace([np.inf, -np.inf], np.nan)
    return row[["factory_id", "month", *FEATURE_NAMES]]
