"""Deterministic credit-policy calculations (limit and pricing) with the clauses they rely on.
The LLM never computes these: they are injected into the memo as structured facts."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

BAND_FACTOR = {"APPROVE": 1.0, "WATCH": 0.6, "HIGH_RISK": 0.0}
SPREADS = [(750, "EBLR + 2.00% – 2.50%"), (700, "EBLR + 2.50% – 3.00%"), (650, "EBLR + 3.00% – 3.50%"),
           (550, "EBLR + 3.75% – 4.50%")]
TURNOVER_SHARE = 0.20
CONCENTRATION_LIMIT = 0.50
CONCENTRATION_HAIRCUT = 0.15
EXPOSURE_CAP = 10_00_00_000  # ₹10 crore


@dataclass
class LimitResult:
    annual_turnover: float
    turnover_limit: float
    band_factor: float
    concentration_haircut: bool
    recommended_limit: float
    requested: float
    pricing_band: str
    citations: list[str] = field(default_factory=list)


def pricing_band(score: int) -> str:
    for cut, label in SPREADS:
        if score >= cut:
            return label
    return "Not priced (decline)"


def assess_limit(annual_turnover: float, requested: float, score: int, band: str, top_buyer_share: float) -> LimitResult:
    cites = ["4.1", "4.2", "5.2"]
    base = TURNOVER_SHARE * annual_turnover
    factor = BAND_FACTOR[band]
    limit = base * factor
    haircut = top_buyer_share > CONCENTRATION_LIMIT
    if haircut:
        limit *= 1 - CONCENTRATION_HAIRCUT
        cites.append("4.3")
    limit = min(limit, requested, EXPOSURE_CAP)
    limit = math.floor(limit / 1e5) * 1e5  # round down to ₹1 lakh (§4.4)
    cites.append("4.4")
    return LimitResult(
        annual_turnover=annual_turnover, turnover_limit=base, band_factor=factor, concentration_haircut=haircut,
        recommended_limit=limit, requested=requested, pricing_band=pricing_band(score), citations=cites,
    )


def inr(amount: float) -> str:
    """Format rupees in crore / lakh as used in Indian credit memos."""
    if abs(amount) >= 1e7:
        return f"₹{amount / 1e7:.2f} Cr"
    if abs(amount) >= 1e5:
        return f"₹{amount / 1e5:.1f} lakh"
    return f"₹{amount:,.0f}"
