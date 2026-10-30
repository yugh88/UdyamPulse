"""Synthetic MSME factory panel generator.

Produces 500 factories x 24 months of consented operating signals (GST e-invoice, e-way bill,
Account Aggregator bank data, electricity, ERP, EPFO) and writes them to `lake/bronze/` as Parquet.

No real entity data is used anywhere. Ranges are informed by public aggregates; see CALIBRATION.md.
The generator simulates a hidden 36-month horizon so 12-month-ahead default labels exist for every
visible month, but only months 1..24 of signals are exposed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from core.settings import get_settings
from core.timeline import month_start

HIDDEN_HORIZON = 36
HERO_ID = "UP-F0001"
HERO_NAME = "Sharma Auto Components"

# Calendar-month seasonality (Jan..Dec) and economics per sector.
SECTORS: dict[str, dict] = {
    "auto_components": dict(
        label="Auto components", home="Ludhiana", margin=0.11, rm_ratio=0.56, dtp=62,
        kwh_per_lakh=95.0, inv_size_lakh=2.2,
        season=[1.02, 1.00, 1.08, 0.94, 0.95, 0.97, 0.98, 1.00, 1.03, 1.06, 1.02, 0.95],
    ),
    "engineering": dict(
        label="Engineering", home="Rajkot", margin=0.13, rm_ratio=0.50, dtp=70,
        kwh_per_lakh=80.0, inv_size_lakh=3.5,
        season=[1.00, 1.02, 1.12, 0.93, 0.96, 0.98, 0.97, 0.98, 1.00, 1.02, 1.00, 1.02],
    ),
    "textiles": dict(
        label="Textiles", home="Tiruppur", margin=0.08, rm_ratio=0.62, dtp=55,
        kwh_per_lakh=70.0, inv_size_lakh=1.6,
        season=[0.94, 0.92, 0.98, 0.95, 0.96, 1.00, 1.06, 1.10, 1.10, 1.06, 0.98, 0.95],
    ),
    "ceramics": dict(
        label="Ceramics", home="Morbi", margin=0.10, rm_ratio=0.45, dtp=58,
        kwh_per_lakh=160.0, inv_size_lakh=1.9,
        season=[1.04, 1.04, 1.06, 1.00, 0.98, 0.90, 0.86, 0.90, 0.98, 1.06, 1.08, 1.10],
    ),
    "food_processing": dict(
        label="Food processing", home="Indore", margin=0.07, rm_ratio=0.70, dtp=35,
        kwh_per_lakh=55.0, inv_size_lakh=1.2,
        season=[1.08, 1.06, 1.04, 0.98, 0.94, 0.92, 0.92, 0.94, 0.98, 1.04, 1.06, 1.04],
    ),
}
CLUSTERS = ["Ludhiana", "Rajkot", "Tiruppur", "Morbi", "Indore", "Pune"]
SURNAMES = [
    "Gupta", "Patel", "Mehta", "Agarwal", "Iyer", "Reddy", "Bansal", "Desai", "Jain", "Kapoor",
    "Malhotra", "Nair", "Rathod", "Shah", "Sethi", "Verma", "Chawla", "Joshi", "Kumar", "Pillai",
    "Saini", "Thakkar", "Vora", "Bhatt", "Goyal", "Arora", "Menon", "Kothari", "Parikh", "Grewal",
]
DESCRIPTORS = {
    "auto_components": ["Precision Forgings", "Auto Parts", "Gears", "Castings", "Fasteners", "Brake Systems"],
    "engineering": ["Engineering Works", "Pumps", "Valves", "Machine Tools", "Fabricators", "Bearings"],
    "textiles": ["Knitwear", "Garments", "Spinning Mills", "Fabrics", "Apparel Exports", "Hosiery"],
    "ceramics": ["Ceramics", "Vitrified Tiles", "Sanitaryware", "Granito", "Tiles", "Clay Works"],
    "food_processing": ["Foods", "Agro Processors", "Spices", "Snacks", "Flour Mills", "Dairy Products"],
}
SUFFIXES = ["Pvt Ltd", "Industries", "Enterprises", "& Sons", "LLP", "Udyog"]
STRESS_TYPES = ["buyer_loss", "payment_stretch", "diversion"]


@dataclass
class Factory:
    factory_id: str
    name: str
    sector: str
    cluster: str
    udyam_category: str
    vintage_years: float
    annual_turnover_cr: float
    n_buyers: int
    loan_requested_inr: float
    fragility: float
    growth: float
    top_share: float
    dtp_offset: float
    cushion: float
    po_cover: float
    einv_coverage: float
    bank_mismatch: float
    headcount: int
    stress_month: int | None = None
    stress_type: str | None = None
    stress_depth: float = 0.0
    ramp: int = 1
    defaults: bool = False
    sma2_month: int | None = None
    default_month: int | None = None


def turnover_band(cr: float) -> str:
    for upper, label in [(5, "< 5 Cr"), (10, "5–10 Cr"), (25, "10–25 Cr"), (50, "25–50 Cr")]:
        if cr < upper:
            return label
    return "50–100 Cr"


def _make_factory(i: int, rng: np.random.Generator) -> Factory:
    sector = str(rng.choice(list(SECTORS)))
    home = SECTORS[sector]["home"]
    cluster = home if rng.random() < 0.6 else str(rng.choice([c for c in CLUSTERS if c != home]))
    micro = rng.random() < 0.6
    annual = float(rng.uniform(1.2, 10.0) if micro else rng.uniform(10.0, 60.0))
    fragility = float(np.clip(rng.beta(2, 5) + (0.08 if micro else 0.0), 0, 1))
    n_buyers = int(rng.integers(3, 12) if micro else rng.integers(6, 30))
    top_share = float(np.clip(rng.beta(3, 5) * (1.3 if n_buyers < 8 else 0.9), 0.12, 0.85))
    name = f"{rng.choice(SURNAMES)} {rng.choice(DESCRIPTORS[sector])} {rng.choice(SUFFIXES)}"
    f = Factory(
        factory_id=f"UP-F{i:04d}",
        name=name,
        sector=sector,
        cluster=cluster,
        udyam_category="micro" if micro else "small",
        vintage_years=round(float(rng.gamma(2.5, 4.0) + 1), 1),
        annual_turnover_cr=round(annual, 2),
        n_buyers=n_buyers,
        loan_requested_inr=round(annual * 1e7 * float(rng.uniform(0.08, 0.25)), -4),
        fragility=fragility,
        growth=float(rng.normal(0.08, 0.06)),
        top_share=top_share,
        dtp_offset=float(rng.normal(0, 8) + 25 * fragility),
        cushion=float(rng.uniform(0.15, 0.6) * (1 - 0.5 * fragility)),
        po_cover=float(rng.uniform(1.0, 3.0) * (1 - 0.3 * fragility)),
        einv_coverage=float(rng.uniform(0.86, 0.99)),
        bank_mismatch=float(rng.choice([0.0, rng.uniform(0.27, 0.35)], p=[0.97, 0.03])),
        headcount=int(rng.integers(8, 45) if micro else rng.integers(45, 220)),
    )
    # Hidden health trajectory: ~12% get a stress event within the 36-month hidden horizon.
    p_stress = 0.02 + 0.25 * fragility + (0.04 if micro else 0.0)
    if rng.random() < p_stress:
        f.stress_month = int(rng.integers(4, HIDDEN_HORIZON - 5))
        f.stress_type = str(rng.choice(STRESS_TYPES, p=[0.6, 0.25, 0.15]))
        f.stress_depth = float(rng.uniform(0.30, 0.50))
        f.ramp = int(rng.integers(1, 3))  # 4-8 weeks to full depth
        if f.stress_type == "payment_stretch":
            f.top_share = max(f.top_share, float(rng.uniform(0.52, 0.7)))
        p_default = 0.30 + 0.25 * fragility + (0.18 if micro else 0.0)
        if rng.random() < p_default:
            f.defaults = True
            f.sma2_month = f.stress_month + int(rng.integers(3, 5))
            f.default_month = f.sma2_month + 1
    return f


def _hero() -> Factory:
    return Factory(
        factory_id=HERO_ID, name=HERO_NAME, sector="auto_components", cluster="Ludhiana",
        udyam_category="small", vintage_years=14.0, annual_turnover_cr=18.0, n_buyers=9,
        loan_requested_inr=3.0e7, fragility=0.22, growth=0.07, top_share=0.41, dtp_offset=6.0,
        cushion=0.24, po_cover=1.5, einv_coverage=0.95, bank_mismatch=0.0, headcount=118,
        stress_month=21, stress_type="buyer_loss", stress_depth=0.42, ramp=1,
        defaults=True, sma2_month=25, default_month=26,
    )


def _stress_level(f: Factory, t: int) -> float:
    """0..1 fraction of full stress applied at month t (ramps in, recovers if no default)."""
    if f.stress_month is None or t < f.stress_month:
        return 0.0
    k = t - f.stress_month + 1
    level = min(1.0, k / f.ramp)
    if not f.defaults and k > f.ramp + 2:
        level = max(0.15, level - 0.25 * (k - f.ramp - 2))
    if f.defaults and f.default_month is not None and t >= f.default_month:
        level = 1.6
    return level


def _simulate(f: Factory, rng: np.random.Generator, n_months: int) -> list[dict]:
    sec = SECTORS[f.sector]
    base_monthly = f.annual_turnover_cr * 1e7 / 12
    rows: list[dict] = []
    revs: list[float] = []
    balance_ref = f.cushion * base_monthly
    for t in range(1, n_months + 1):
        cal = month_start(t).month
        lvl = _stress_level(f, t)
        k = t - f.stress_month if f.stress_month else -99
        order_hit = f.stress_depth * lvl if f.stress_type == "buyer_loss" else 0.45 * f.stress_depth * lvl
        rev = base_monthly * (1 + f.growth) ** (t / 12) * sec["season"][cal - 1]
        rev *= (1 + rng.normal(0, 0.05)) * (1 - order_hit)
        revs.append(rev)
        lag_rev = 0.5 * revs[-2] + 0.5 * revs[-3] if len(revs) >= 3 else rev

        einv_val = rev * f.einv_coverage
        eway_val = einv_val * rng.uniform(0.86, 0.97)
        einv_cnt = rng.poisson(max(einv_val / (sec["inv_size_lakh"] * 1e5), 1))
        eway_cnt = rng.poisson(max(einv_cnt * 0.9, 1))
        gst_turnover = rev * (1 + rng.normal(0, 0.02))

        top = f.top_share
        if f.stress_type == "buyer_loss" and lvl > 0:
            top = f.top_share * (1 - order_hit) / (1 - f.top_share * order_hit)
        top = float(np.clip(top + rng.normal(0, 0.015), 0.05, 0.95))

        dtp = sec["dtp"] + f.dtp_offset + rng.normal(0, 4)
        if f.stress_type == "payment_stretch":
            dtp += 35 * lvl
        elif lvl > 0 and k >= 1:
            dtp += 10 * lvl

        credits = 1.12 * lag_rev * (1 + rng.normal(0, 0.04))
        if f.bank_mismatch:
            credits *= 1 - f.bank_mismatch
        if f.stress_type == "diversion" and lvl > 0:
            credits *= 1 - 0.4 * lvl
        if f.stress_type == "payment_stretch" and lvl > 0:
            credits *= 1 - 0.3 * lvl
        fixed = base_monthly * 0.08
        debits = (1.12 * rev * (1 - sec["margin"]) + fixed) * (1 + rng.normal(0, 0.03))
        if lvl > 0:  # costs are sticky when revenue falls
            debits = max(debits, 0.95 * credits + fixed * lvl)

        cash_stress = min(1.0, max(0.0, (k + 1) / 2)) * min(lvl, 1.0) if lvl > 0 else 0.0
        balance = balance_ref * (1 + rng.normal(0, 0.12)) * (1 - 0.75 * cash_stress)
        balance = max(balance, 5e4 * rng.uniform(0.5, 1.5))

        lam = 0.02 + 0.12 * f.fragility + (2.2 * cash_stress if k >= 1 else 0.0)
        bounces = int(rng.poisson(lam))

        kwh_hit = order_hit * (0.75 if f.stress_type == "buyer_loss" else 0.6)
        kwh = rev / (1 - order_hit + 1e-9) * (1 - kwh_hit) / 1e5 * sec["kwh_per_lakh"]
        kwh *= sec["season"][cal - 1] ** 0.3 * (1 + rng.normal(0, 0.04))

        rm = rev * sec["rm_ratio"] * (1 + rng.normal(0, 0.06)) * (1 - 0.5 * order_hit)
        po_cover = f.po_cover * (1 - 1.2 * order_hit) * (1 + rng.normal(0, 0.08))
        open_po = max(rev * po_cover, 0)

        late_p = 0.04 + 0.2 * f.fragility
        if lvl > 0 and k >= 2:
            late_p = 0.75
        gst_delay = int(rng.integers(1, 16)) if rng.random() < late_p else 0
        if lvl > 0 and k >= 2 and gst_delay:
            gst_delay += int(rng.integers(10, 30))

        hc = f.headcount * (1 + 0.02 * t / 12) * (1 - 0.15 * lvl * (k >= 1))
        headcount = int(max(round(hc + rng.normal(0, 1.5)), 2))

        rows.append(dict(
            factory_id=f.factory_id, month=t,
            einvoice_count=int(einv_cnt), einvoice_value=einv_val, eway_count=int(eway_cnt),
            eway_value=eway_val, top_buyer_share=top, avg_days_to_pay=max(dtp, 7.0),
            aa_credits=credits, aa_debits=debits, avg_balance=balance, bounces=bounces,
            kwh=kwh, rm_purchases=rm, open_po_value=open_po, gst_turnover=gst_turnover,
            gst_filing_delay_days=gst_delay, epfo_headcount=headcount,
        ))
    return rows


def _apply_hero_script(rows: list[dict]) -> None:
    """Pin the hero's stress months so the demo narrative is exact (e-way -42%, kWh -32% in month 21)."""
    by_m = {r["month"]: r for r in rows}
    base = {k: np.mean([by_m[m][k] for m in (19, 20)]) for k in ("eway_value", "kwh", "avg_balance", "einvoice_value")}
    script = {
        21: dict(eway=0.58, kwh=0.68, bal=0.62, bounces=1, delay=0, dtp=4),
        22: dict(eway=0.52, kwh=0.63, bal=0.40, bounces=2, delay=9, dtp=12),
        23: dict(eway=0.47, kwh=0.60, bal=0.28, bounces=3, delay=24, dtp=18),
        24: dict(eway=0.45, kwh=0.58, bal=0.22, bounces=3, delay=31, dtp=22),
    }
    for m, s in script.items():
        r = by_m[m]
        r["eway_value"] = base["eway_value"] * s["eway"]
        r["einvoice_value"] = base["einvoice_value"] * (s["eway"] + 0.02)
        r["gst_turnover"] = r["einvoice_value"] / 0.95
        r["kwh"] = base["kwh"] * s["kwh"]
        r["avg_balance"] = base["avg_balance"] * s["bal"]
        r["bounces"] = s["bounces"]
        r["gst_filing_delay_days"] = s["delay"]
        r["avg_days_to_pay"] = by_m[20]["avg_days_to_pay"] + s["dtp"]
        r["eway_count"] = int(by_m[20]["eway_count"] * s["eway"])
        r["einvoice_count"] = int(by_m[20]["einvoice_count"] * (s["eway"] + 0.02))
        r["open_po_value"] = by_m[20]["open_po_value"] * (s["eway"] - 0.05)
        r["rm_purchases"] = by_m[20]["rm_purchases"] * (s["eway"] + 0.05)
    for m in range(1, 21):  # healthy and clean before the event
        by_m[m]["bounces"] = 0
        by_m[m]["gst_filing_delay_days"] = 0 if m != 7 else 3


def _labels(f: Factory, n_months: int) -> list[dict]:
    out = []
    for t in range(1, n_months + 1):
        d = f.default_month
        out.append(dict(
            factory_id=f.factory_id, month=t,
            default_within_12m=int(d is not None and t < d <= t + 12),
            months_to_sma2=(f.sma2_month - t) if f.sma2_month and f.sma2_month > t else None,
            is_post_default=int(d is not None and t >= d),
        ))
    return out


SOURCE_COLUMNS: dict[str, list[str]] = {
    "gst_returns": ["gst_turnover", "gst_filing_delay_days"],
    "einvoice": ["einvoice_count", "einvoice_value", "top_buyer_share", "avg_days_to_pay"],
    "ewaybill": ["eway_count", "eway_value"],
    "aa_bank": ["aa_credits", "aa_debits", "avg_balance", "bounces"],
    "electricity": ["kwh"],
    "erp": ["rm_purchases", "open_po_value"],
    "epfo": ["epfo_headcount"],
}


def generate(seed: int | None = None, n_factories: int | None = None) -> dict[str, pd.DataFrame]:
    s = get_settings()
    seed = s.seed if seed is None else seed
    n_factories = s.n_factories if n_factories is None else n_factories
    rng = np.random.default_rng(seed)

    factories = [_hero()] + [_make_factory(i, rng) for i in range(2, n_factories + 1)]
    signal_rows: list[dict] = []
    label_rows: list[dict] = []
    for f in factories:
        rows = _simulate(f, rng, s.n_months)
        if f.factory_id == HERO_ID:
            _apply_hero_script(rows)
        signal_rows += rows
        label_rows += _labels(f, s.n_months)

    signals = pd.DataFrame(signal_rows)
    profile = pd.DataFrame([dict(
        factory_id=f.factory_id, name=f.name, sector=f.sector, sector_label=SECTORS[f.sector]["label"],
        cluster=f.cluster, udyam_category=f.udyam_category, vintage_years=f.vintage_years,
        annual_turnover_cr=f.annual_turnover_cr, turnover_band=turnover_band(f.annual_turnover_cr),
        n_buyers=f.n_buyers, loan_requested_inr=f.loan_requested_inr,
        udyam_number=f"UDYAM-SYN-{f.factory_id[-4:]}",
    ) for f in factories])
    truth = pd.DataFrame([dict(
        factory_id=f.factory_id, stress_month=f.stress_month, stress_type=f.stress_type,
        defaults=int(f.defaults), sma2_month=f.sma2_month, default_month=f.default_month,
    ) for f in factories])
    labels = pd.DataFrame(label_rows)

    # Split into per-source raw event tables with realistic data-quality noise.
    ingest_base = datetime(2026, 7, 1)
    tables: dict[str, pd.DataFrame] = {"factories": profile}
    for source, cols in SOURCE_COLUMNS.items():
        df = signals[["factory_id", "month", *cols]].copy()
        hero = df["factory_id"] == HERO_ID
        keep = (rng.random(len(df)) > 0.015) | hero  # ~1.5% missing months per source
        df = df[keep]
        dupes = df[(rng.random(len(df)) < 0.005) & ~(df["factory_id"] == HERO_ID)].copy()
        df = pd.concat([df, dupes], ignore_index=True)
        df["_source"] = source
        df["_ingested_at"] = [ingest_base + timedelta(minutes=int(x)) for x in rng.integers(0, 50_000, len(df))]
        tables[source] = df.sort_values(["factory_id", "month"]).reset_index(drop=True)
    tables["_truth_factory"] = truth
    tables["_truth_monthly"] = labels
    return tables


def write_bronze(tables: dict[str, pd.DataFrame]) -> None:
    out = get_settings().bronze
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_parquet(out / f"{name}.parquet", index=False)


def summarize(tables: dict[str, pd.DataFrame]) -> dict[str, float]:
    prof, truth, lab = tables["factories"], tables["_truth_factory"], tables["_truth_monthly"]
    merged = truth.merge(prof[["factory_id", "udyam_category"]], on="factory_id")
    return dict(
        factories=len(prof),
        stressed_pct=round(float(100 * truth["stress_month"].notna().mean()), 1),
        default_rate_pct=round(float(100 * truth["defaults"].mean()), 1),
        default_rate_micro_pct=round(float(100 * merged.loc[merged.udyam_category == "micro", "defaults"].mean()), 1),
        default_rate_small_pct=round(float(100 * merged.loc[merged.udyam_category == "small", "defaults"].mean()), 1),
        monthly_label_rate_pct=round(float(100 * lab.loc[lab.is_post_default == 0, "default_within_12m"].mean()), 2),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--n", type=int, default=None, help="number of factories")
    args = parser.parse_args()
    tables = generate(args.seed, args.n)
    write_bronze(tables)
    print("bronze written:", {k: len(v) for k, v in tables.items()})
    print("summary:", summarize(tables))


if __name__ == "__main__":
    main()
