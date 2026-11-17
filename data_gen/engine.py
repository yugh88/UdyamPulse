"""Tier C: large calibrated synthetic panel (UP_DATASET=full: 50,000 factories, scale: 1,00,000) x 36 months.

Vectorised with NumPy over chunks of 5,000 factories; each chunk has its own seed (SeedSequence.spawn), so the
output is identical however it is scheduled. Writes the same bronze tables as the demo generator, partitioned
by sector (`bronze/<source>/sector=<s>/chunk-<k>.parquet`, rows sorted by factory and month), so the silver
and gold builds run unchanged.

Realism beyond the demo generator:
- **Calibrated macro**: sector seasonality, growth and noise from MoSPI IIP (data_gen/calibration.yaml), and a
  macro demand shock at `SHOCK_MONTH` shaped like the 2020 recovery and scaled down (`shock_scale`).
- **Factory random effects**: a latent quality term shifts stress hazard and default odds.
- **Buyer-network contagion**: large buyers are shared by several suppliers; a buyer in distress cuts orders
  to all of them, and some buyers default outright (receivables written off).
- **Five stress types**: order loss, cash squeeze, buyer default, input-cost spike, fraud-like diversion,
  plus a few sudden defaults with almost no warning.
- **Recoveries and false alarms**: most stressed factories recover at varied speeds; some healthy ones have
  temporary dips. Good and bad are not trivially separable.
- **Messy data**: missing months, multi-month source outages, late GST filings, GST-vs-bank mismatches,
  outliers, duplicates, partial e-invoice coverage below the ₹5 Cr threshold.

The hero factory (UP-F0001, Sharma Auto Components) is copied verbatim from the demo generator for months
1-24, so the demo story is identical in every dataset size. No protected attributes exist anywhere.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from core.settings import get_settings
from core.timeline import month_start
from data_gen import calibrate
from data_gen import generate as legacy
from data_gen.generate import CLUSTERS, DESCRIPTORS, HERO_ID, SECTORS, SOURCE_COLUMNS, SUFFIXES, SURNAMES, turnover_band

log = logging.getLogger("udyampulse.engine")
CHUNK = 5_000
SHOCK_MONTH = 26  # the macro shock lands inside the panel so a shock hold-out can train before and test across it
STRESS_TYPES = ["order_loss", "cash_squeeze", "buyer_default", "input_cost_spike", "diversion", "sudden"]
LEGACY_TYPE = {"order_loss": "buyer_loss", "cash_squeeze": "payment_stretch"}  # demo generator's names


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _macro(cal: dict, n_months: int) -> dict[str, np.ndarray]:
    """Per-sector monthly multiplier: calibrated seasonality x trend x shock (index 0 = month 1)."""
    scale = float(cal.get("shock_scale", 0.3))
    out = {}
    cal_months = np.array([month_start(t).month for t in range(1, n_months + 1)])
    for sector in SECTORS:
        p = cal["sectors"][sector]
        season = np.asarray(p["season"])[cal_months - 1]
        depth = scale * float(p["shock"].get("depth_apr2020_vs_apr2019") or -0.6)
        rec = int(p["shock"].get("months_to_95pct") or 6) + 2
        shock = np.ones(n_months)
        for t in range(SHOCK_MONTH, min(n_months, SHOCK_MONTH + rec) + 1):
            shock[t - 1] = 1 + depth * (1 - (t - SHOCK_MONTH) / rec)
        out[sector] = season * shock
    return out


def _attributes(rng: np.random.Generator, ids: np.ndarray, cal: dict) -> pd.DataFrame:
    n = len(ids)
    sectors = np.array(list(SECTORS))
    sector = sectors[rng.integers(0, len(sectors), n)]
    home = np.array([SECTORS[s]["home"] for s in sector])
    other = np.array(CLUSTERS)[rng.integers(0, len(CLUSTERS), n)]
    cluster = np.where(rng.random(n) < 0.6, home, other)
    micro = rng.random(n) < float(cal["targets"]["micro_share"]["value"])
    annual = np.where(micro, rng.uniform(1.2, 10.0, n), rng.uniform(10.0, 60.0, n))
    fragility = np.clip(rng.beta(2, 5, n) + 0.08 * micro, 0, 1)
    n_buyers = np.where(micro, rng.integers(3, 12, n), rng.integers(6, 30, n))
    top_share = np.clip(rng.beta(3, 5, n) * np.where(n_buyers < 8, 1.3, 0.9), 0.12, 0.85)
    growth = np.array([cal["sectors"][s]["growth"] for s in sector]) + rng.normal(0, 0.05, n)
    sur, desc_i, suf = rng.integers(0, len(SURNAMES), n), rng.integers(0, 6, n), rng.integers(0, len(SUFFIXES), n)
    names = [f"{SURNAMES[a]} {DESCRIPTORS[s][b]} {SUFFIXES[c]}" for a, s, b, c in zip(sur, sector, desc_i, suf, strict=True)]
    return pd.DataFrame({
        "factory_id": ids, "name": names, "sector": sector, "cluster": cluster,
        "udyam_category": np.where(micro, "micro", "small"),
        "vintage_years": np.round(rng.gamma(2.5, 4.0, n) + 1, 1), "annual_turnover_cr": np.round(annual, 2),
        "n_buyers": n_buyers, "loan_requested_inr": np.round(annual * 1e7 * rng.uniform(0.08, 0.25, n), -4),
        "fragility": fragility, "quality": rng.normal(0, 0.6, n), "growth": growth, "top_share": top_share,
        "dtp_offset": rng.normal(0, 8, n) + 25 * fragility,
        "cushion": rng.uniform(0.15, 0.6, n) * (1 - 0.5 * fragility),
        "po_cover": rng.uniform(1.0, 3.0, n) * (1 - 0.3 * fragility),
        # e-invoicing is mandatory above ₹5 Cr turnover; smaller units invoice only part of their sales
        "einv_coverage": np.where(annual >= 5, rng.uniform(0.86, 0.99, n), rng.uniform(0.35, 0.85, n)),
        "bank_mismatch": np.where(rng.random(n) < 0.03, rng.uniform(0.27, 0.35, n), 0.0),
        "headcount": np.where(micro, rng.integers(8, 45, n), rng.integers(45, 220, n)),
    })


def _events(rng: np.random.Generator, f: pd.DataFrame, horizon: int, cal: dict) -> pd.DataFrame:
    """One stress event per factory at most (the earliest of idiosyncratic, macro and buyer contagion)."""
    n = len(f)
    frag, micro, q = f["fragility"].to_numpy(), (f["udyam_category"] == "micro").to_numpy(), f["quality"].to_numpy()
    never = horizon + 99
    # Idiosyncratic stress over the hidden horizon.
    p_idio = _sigmoid(-3.3 + 3.2 * frag + 0.35 * micro - 0.6 * q)
    m_idio = np.where(rng.random(n) < p_idio, rng.integers(4, horizon - 5, n), never)
    # Macro shock: fragile factories in hard-hit sectors tip into stress in the shock window.
    depth = np.array([abs(cal["sectors"][s]["shock"].get("depth_apr2020_vs_apr2019") or 0.6) for s in f["sector"]])
    p_macro = _sigmoid(-5.6 + 3.0 * frag + 1.6 * depth - 0.5 * q)
    m_macro = np.where(rng.random(n) < p_macro, SHOCK_MONTH + rng.integers(0, 3, n), never)
    # Buyer network: a large buyer serves ~40 suppliers of one sector; 8% of buyers hit distress, a third of
    # those default. Suppliers that lean on that buyer are hit together.
    n_buyers = max(5, n // 40)
    buyer_sector = np.array(list(SECTORS))[rng.integers(0, len(SECTORS), n_buyers)]
    buyer = np.empty(n, dtype=int)
    for s in SECTORS:
        idx = np.where(f["sector"].to_numpy() == s)[0]
        pool = np.where(buyer_sector == s)[0]
        pool = pool if len(pool) else np.arange(n_buyers)
        buyer[idx] = rng.choice(pool, len(idx))
    distressed = rng.random(n_buyers) < 0.08
    buyer_month = np.where(distressed, rng.integers(5, horizon - 6, n_buyers), never)
    buyer_defaults = distressed & (rng.random(n_buyers) < 0.35)
    exposed = f["top_share"].to_numpy() > 0.28
    m_buyer = np.where(exposed & (buyer_month[buyer] < never), buyer_month[buyer] + rng.integers(0, 2, n), never)

    month = np.minimum(np.minimum(m_idio, m_macro), m_buyer)
    has = month < never
    source = np.select([month == m_buyer, month == m_macro], ["contagion", "macro"], "idiosyncratic")
    types = rng.choice(STRESS_TYPES[:5], n, p=[0.36, 0.22, 0.10, 0.18, 0.14])
    types = np.where(source == "contagion", np.where(buyer_defaults[buyer], "buyer_default", "order_loss"), types)
    types = np.where(source == "macro", np.where(rng.random(n) < 0.7, "order_loss", "cash_squeeze"), types)
    stress_depth = rng.uniform(0.25, 0.5, n)
    stress_depth = np.where(source == "contagion", np.clip(f["top_share"].to_numpy() * rng.uniform(0.7, 1.2, n), 0.2, 0.7),
                            stress_depth)
    type_risk = pd.Series(types).map({"order_loss": 0.0, "cash_squeeze": 0.3, "buyer_default": 0.5,
                                      "input_cost_spike": -0.5, "diversion": 0.9}).to_numpy()
    p_def = _sigmoid(-1.45 + 2.2 * frag + 0.55 * micro + 2.0 * (stress_depth - 0.35) + type_risk - 0.7 * q
                     - 1.2 * f["cushion"].to_numpy())
    defaults = has & (rng.random(n) < p_def)
    # Sudden failures: rare defaults with almost no operating warning (fraud, a fire, a promoter dispute).
    sudden = ~has & (rng.random(n) < 0.006 + 0.01 * frag)
    month = np.where(sudden, rng.integers(6, horizon - 5, n), month)
    types = np.where(sudden, "sudden", types)
    defaults = defaults | sudden
    sma2 = np.where(defaults, month + np.where(sudden, 1, rng.integers(3, 5, n)), -1)
    ev = pd.DataFrame({
        "stress_month": np.where(has | sudden, month, -1), "stress_type": np.where(has | sudden, types, None),
        "stress_source": np.where(sudden, "sudden", np.where(has, source, None)),
        "stress_depth": np.where(has, stress_depth, 0.0), "ramp": rng.integers(1, 3, n),
        "recovery_rate": rng.uniform(0.08, 0.35, n), "recovery_floor": rng.uniform(0.0, 0.3, n),
        "defaults": defaults, "sma2_month": sma2, "default_month": np.where(defaults, sma2 + 1, -1),
        "buyer_id": buyer,
        # False alarms: a temporary 2-3 month dip in orders at a healthy factory.
        "dip_month": np.where(rng.random(n) < 0.10, rng.integers(3, horizon - 3, n), -1),
        "dip_depth": rng.uniform(0.10, 0.25, n), "dip_len": rng.integers(2, 4, n),
    })
    return ev


def _levels(ev: pd.DataFrame, T: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(stress level 0..1.6, precursor 0..0.5, months since onset, dip) as N x T arrays."""
    t = np.arange(1, T + 1)[None, :]
    sm = ev["stress_month"].to_numpy()[:, None].astype(float)
    sm = np.where(sm < 0, np.inf, sm)
    k = t - sm + 1
    ramp = ev["ramp"].to_numpy()[:, None]
    level = np.clip(k / ramp, 0, 1)
    level = np.where(k >= 1, level, 0.0)
    rec = ev["recovery_rate"].to_numpy()[:, None]
    floor = ev["recovery_floor"].to_numpy()[:, None]
    hold = k - ramp - 2
    recovering = (~ev["defaults"].to_numpy()[:, None]) & (hold > 0)
    level = np.where(recovering, np.maximum(floor, level - rec * hold), level)
    dm = ev["default_month"].to_numpy()[:, None].astype(float)
    dm = np.where(dm < 0, np.inf, dm)
    level = np.where(t >= dm, 1.6, level)
    sudden = (ev["stress_type"] == "sudden").to_numpy()[:, None]
    level = np.where(sudden & (t < dm), 0.0, level)  # no build-up before a sudden default
    pre = np.where((t >= sm - 5) & (t < sm) & ~sudden, 0.1 * (t - sm + 6), 0.0)
    dip_m = ev["dip_month"].to_numpy()[:, None].astype(float)
    dip_m = np.where(dip_m < 0, np.inf, dip_m)
    dip = np.where((t >= dip_m) & (t < dip_m + ev["dip_len"].to_numpy()[:, None]), ev["dip_depth"].to_numpy()[:, None], 0.0)
    return level, pre, np.where(np.isfinite(k), k - 1, -99), dip


def simulate_chunk(seed: np.random.SeedSequence, ids: np.ndarray, T: int, horizon: int, cal: dict,
                   macro: dict[str, np.ndarray], attrs: pd.DataFrame | None = None,
                   events: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(profiles + truth, monthly signals, labels) for one chunk. `attrs`/`events` pin a scripted factory."""
    rng = np.random.default_rng(seed)
    f = _attributes(rng, ids, cal) if attrs is None else attrs
    ev = _events(rng, f, horizon, cal) if events is None else events
    n = len(f)
    lvl, pre, k, dip = _levels(ev, T)
    typ = ev["stress_type"].to_numpy()[:, None]
    depth = ev["stress_depth"].to_numpy()[:, None]
    sec = f["sector"].to_numpy()
    sector_p = {s: SECTORS[s] for s in SECTORS}
    col = lambda key: np.array([sector_p[s][key] for s in sec])[:, None]  # noqa: E731
    noise_sd = np.sqrt(np.array([cal["sectors"][s]["noise_sd"] for s in sec]) ** 2 + 0.04 ** 2)[:, None]
    m_macro = np.stack([macro[s] for s in sec])
    t = np.arange(1, T + 1)[None, :]
    base = (f["annual_turnover_cr"].to_numpy() * 1e7 / 12)[:, None]
    growth = f["growth"].to_numpy()[:, None]
    hit_scale = np.select([typ == "order_loss", typ == "buyer_default", typ == "cash_squeeze",
                           typ == "input_cost_spike", typ == "diversion"], [1.0, 0.8, 0.45, 0.15, 0.2], 0.3)
    order_hit = np.clip(depth * np.minimum(lvl, 1.0) * hit_scale + 0.6 * np.maximum(lvl - 1.0, 0), 0, 0.95)
    rev = base * (1 + growth) ** (t / 12) * m_macro * (1 + rng.normal(0, 1, (n, T)) * noise_sd)
    rev = rev * (1 - order_hit) * (1 - 0.08 * pre) * (1 - dip)
    rev = np.maximum(rev, base * 0.02)
    lag = np.concatenate([rev[:, :2], 0.5 * rev[:, 1:-1] + 0.5 * rev[:, :-2]], axis=1)

    einv_cov = f["einv_coverage"].to_numpy()[:, None]
    einv_val = rev * einv_cov
    eway_val = einv_val * rng.uniform(0.86, 0.97, (n, T))
    einv_cnt = rng.poisson(np.maximum(einv_val / (col("inv_size_lakh") * 1e5), 1))
    eway_cnt = rng.poisson(np.maximum(einv_cnt * 0.9, 1))
    gst_turnover = rev * (1 + rng.normal(0, 0.02, (n, T)))

    top0 = f["top_share"].to_numpy()[:, None]
    lost = (typ == "order_loss") | (typ == "buyer_default")
    top = np.where(lost & (lvl > 0), top0 * (1 - order_hit) / np.maximum(1 - top0 * order_hit, 1e-6), top0)
    top = np.clip(top + rng.normal(0, 0.015, (n, T)), 0.05, 0.95)

    onset = (lvl > 0) & (k >= 1)
    dtp = col("dtp") + f["dtp_offset"].to_numpy()[:, None] + rng.normal(0, 4, (n, T)) + 12 * pre
    dtp = dtp + np.where(typ == "cash_squeeze", 35 * lvl, np.where(onset, 10 * lvl, 0))

    credits = 1.12 * lag * (1 + rng.normal(0, 0.04, (n, T)))
    credits *= 1 - f["bank_mismatch"].to_numpy()[:, None]
    credits *= np.where((typ == "diversion") & (lvl > 0), 1 - 0.4 * np.minimum(lvl, 1), 1)
    credits *= np.where((typ == "cash_squeeze") & (lvl > 0), 1 - 0.3 * np.minimum(lvl, 1), 1)
    writeoff = (typ == "buyer_default") & (k >= 0) & (k <= 2)  # receivables from the failed buyer never arrive
    credits *= np.where(writeoff, 1 - 0.5 * top0, 1)
    margin = col("margin")
    cost_spike = np.where((typ == "input_cost_spike") & (lvl > 0), 0.35 * np.minimum(lvl, 1), 0)
    fixed = base * 0.08
    debits = (1.12 * rev * (1 - margin) * (1 + cost_spike) + fixed) * (1 + rng.normal(0, 0.03, (n, T)))
    debits = np.where(lvl > 0, np.maximum(debits, 0.95 * credits + fixed * np.minimum(lvl, 1)), debits)

    cash_stress = np.where(lvl > 0, np.clip((k + 1) / 2, 0, 1) * np.minimum(lvl, 1), 0)
    balance = (f["cushion"].to_numpy()[:, None] * base) * (1 + rng.normal(0, 0.12, (n, T))) \
        * (1 - 0.75 * cash_stress) * (1 - 0.4 * pre) * np.where(writeoff, 0.6, 1)
    balance = np.maximum(balance, 5e4 * rng.uniform(0.5, 1.5, (n, T)))
    lam = 0.02 + 0.12 * f["fragility"].to_numpy()[:, None] + 0.5 * pre + np.where(k >= 1, 2.2 * cash_stress, 0)
    bounces = rng.poisson(lam)

    kwh_hit = order_hit * np.where(lost, 0.75, 0.6)
    season_k = np.stack([np.asarray(cal["sectors"][s]["season"])[[month_start(x).month - 1 for x in range(1, T + 1)]]
                         for s in sec])
    kwh = rev / (1 - order_hit + 1e-9) * (1 - kwh_hit) / 1e5 * col("kwh_per_lakh")
    kwh *= season_k ** 0.3 * (1 + rng.normal(0, 0.04, (n, T)))
    rm = rev * col("rm_ratio") * (1 + rng.normal(0, 0.06, (n, T))) * (1 - 0.5 * order_hit) * (1 + cost_spike)
    po_cover = f["po_cover"].to_numpy()[:, None] * (1 - 1.2 * order_hit) * (1 - 0.6 * pre) * (1 + rng.normal(0, 0.08, (n, T)))
    open_po = np.maximum(rev * po_cover, 0)

    late_p = np.where(onset & (k >= 2), 0.75, 0.04 + 0.2 * f["fragility"].to_numpy()[:, None] + 0.3 * pre)
    gst_delay = np.where(rng.random((n, T)) < late_p, rng.integers(1, 16, (n, T)), 0)
    gst_delay = np.where(onset & (k >= 2) & (gst_delay > 0), gst_delay + rng.integers(10, 30, (n, T)), gst_delay)
    hc = f["headcount"].to_numpy()[:, None] * (1 + 0.02 * t / 12) * (1 - 0.15 * np.minimum(lvl, 1.6) * (k >= 1))
    headcount = np.maximum(np.round(hc + rng.normal(0, 1.5, (n, T))), 2).astype(int)

    values = {
        "einvoice_count": einv_cnt, "einvoice_value": einv_val, "eway_count": eway_cnt, "eway_value": eway_val,
        "top_buyer_share": top, "avg_days_to_pay": np.maximum(dtp, 7.0), "aa_credits": credits, "aa_debits": debits,
        "avg_balance": balance, "bounces": bounces, "kwh": kwh, "rm_purchases": rm, "open_po_value": open_po,
        "gst_turnover": gst_turnover, "gst_filing_delay_days": gst_delay, "epfo_headcount": headcount,
    }
    # Outliers: rare keying or unit errors (x3-x8) in value columns.
    for c in ("einvoice_value", "eway_value", "aa_credits", "kwh", "rm_purchases"):
        spike = rng.random((n, T)) < 0.002
        values[c] = np.where(spike, values[c] * rng.uniform(3, 8, (n, T)), values[c])
    signals = pd.DataFrame({"factory_id": np.repeat(f["factory_id"].to_numpy(), T), "month": np.tile(np.arange(1, T + 1), n),
                            "sector": np.repeat(sec, T)})
    for c, v in values.items():
        signals[c] = np.asarray(v).reshape(-1)

    dm = ev["default_month"].to_numpy()
    sma = ev["sma2_month"].to_numpy()
    tt = np.tile(np.arange(1, T + 1), n)
    dmr, smr = np.repeat(dm, T), np.repeat(sma, T)
    labels = pd.DataFrame({
        "factory_id": signals["factory_id"], "month": tt,
        "default_within_12m": ((dmr > 0) & (tt < dmr) & (dmr <= tt + 12)).astype(int),
        "months_to_sma2": np.where((smr > 0) & (smr > tt), smr - tt, np.nan),
        "is_post_default": ((dmr > 0) & (tt >= dmr)).astype(int),
    })
    profile = pd.concat([f, ev], axis=1)
    return profile, signals, labels


def _split_sources(rng: np.random.Generator, signals: pd.DataFrame, ingest_base: datetime) -> dict[str, pd.DataFrame]:
    """Per-source raw tables with missing months, multi-month outages and duplicate deliveries."""
    out = {}
    hero = (signals["factory_id"] == HERO_ID).to_numpy()
    ids = signals["factory_id"].to_numpy()
    uniq, inv = np.unique(ids, return_inverse=True)
    for source, cols in SOURCE_COLUMNS.items():
        keep = (rng.random(len(signals)) > 0.015) | hero
        # 3% of factories lose one source for a 3-6 month block (portal outage, consent lapse, meter change).
        outage = rng.random(len(uniq)) < 0.03
        start = rng.integers(2, max(3, signals["month"].max() - 6), len(uniq))
        length = rng.integers(3, 7, len(uniq))
        m = signals["month"].to_numpy()
        in_out = outage[inv] & (m >= start[inv]) & (m < start[inv] + length[inv]) & ~hero
        df = signals.loc[keep & ~in_out, ["factory_id", "month", "sector", *cols]]
        dupes = df[(rng.random(len(df)) < 0.005) & (df["factory_id"] != HERO_ID).to_numpy()]
        df = pd.concat([df, dupes], ignore_index=True)
        df["_source"] = source
        df["_ingested_at"] = ingest_base + pd.to_timedelta(rng.integers(0, 50_000, len(df)), unit="m")
        out[source] = df.sort_values(["factory_id", "month"]).reset_index(drop=True)
    return out


def _hero_tables(T: int, horizon: int, cal: dict, macro: dict) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    """The hero exactly as in the demo dataset (months 1-24), continued by the engine for months 25..T."""
    demo = legacy.generate(n_factories=500)
    hero_src = {s: demo[s][demo[s]["factory_id"] == HERO_ID].copy() for s in SOURCE_COLUMNS}
    prof = demo["factories"][demo["factories"]["factory_id"] == HERO_ID].copy()
    truth = demo["_truth_factory"][demo["_truth_factory"]["factory_id"] == HERO_ID].iloc[0]
    if T > 24:
        h = legacy._hero()  # noqa: SLF001
        attrs = pd.DataFrame([{
            "factory_id": HERO_ID, "name": h.name, "sector": h.sector, "cluster": h.cluster,
            "udyam_category": h.udyam_category, "vintage_years": h.vintage_years,
            "annual_turnover_cr": h.annual_turnover_cr, "n_buyers": h.n_buyers, "loan_requested_inr": h.loan_requested_inr,
            "fragility": h.fragility, "quality": 0.0, "growth": h.growth, "top_share": h.top_share,
            "dtp_offset": h.dtp_offset, "cushion": h.cushion, "po_cover": h.po_cover, "einv_coverage": h.einv_coverage,
            "bank_mismatch": 0.0, "headcount": h.headcount}])
        ev = pd.DataFrame([{"stress_month": h.stress_month, "stress_type": "order_loss", "stress_source": "scripted",
                            "stress_depth": h.stress_depth, "ramp": 1, "recovery_rate": 0.0, "recovery_floor": 0.0,
                            "defaults": True, "sma2_month": h.sma2_month, "default_month": h.default_month,
                            "buyer_id": -1, "dip_month": -1, "dip_depth": 0.0, "dip_len": 2}])
        _, sig, _ = simulate_chunk(np.random.SeedSequence(7), np.array([HERO_ID]), T, horizon, cal, macro,
                                   attrs=attrs, events=ev)
        late = sig[sig["month"] > 24].copy()
        # Continue from where the scripted story ends: scale each level series to meet month 24.
        for src, cols in SOURCE_COLUMNS.items():
            m24 = hero_src[src][hero_src[src]["month"] == 24]
            for col in cols:
                if col in ("top_buyer_share", "avg_days_to_pay", "gst_filing_delay_days", "bounces") or m24.empty:
                    continue
                eng = float(sig.loc[sig["month"] == 24, col].iloc[0])
                if eng:
                    late[col] = late[col] * float(m24[col].iloc[0]) / eng
                    if col.endswith("_count") or col == "epfo_headcount":
                        late[col] = late[col].round().astype(int)
        for s, cols in SOURCE_COLUMNS.items():
            extra = late[["factory_id", "month", *cols]].copy()
            extra["_source"] = s
            extra["_ingested_at"] = hero_src[s]["_ingested_at"].max() + timedelta(minutes=1)
            hero_src[s] = pd.concat([hero_src[s], extra], ignore_index=True)
    for s in hero_src:
        hero_src[s]["sector"] = "auto_components"
    tt = np.arange(1, T + 1)
    d, sma = int(truth["default_month"]), int(truth["sma2_month"])
    labels = pd.DataFrame({"factory_id": HERO_ID, "month": tt, "default_within_12m": ((tt < d) & (d <= tt + 12)).astype(int),
                           "months_to_sma2": np.where(sma > tt, sma - tt, np.nan), "is_post_default": (tt >= d).astype(int)})
    prof = prof.assign(stress_month=truth["stress_month"], stress_type="order_loss", stress_source="scripted",
                       defaults=True, sma2_month=sma, default_month=d)
    return prof, hero_src, labels


def build(n_factories: int | None = None, out_dir: Path | None = None, chunk: int = CHUNK) -> dict:
    """Generate the panel into `<lake>/bronze`. Returns run statistics (rows, defaults, seconds, peak memory)."""
    import resource

    s = get_settings()
    n_factories = n_factories or s.n_factories
    T, horizon = s.n_months, s.n_months + 12
    bronze = out_dir or s.bronze
    t0 = time.perf_counter()
    cal = calibrate.load()
    if cal.get("source") == "fallback":
        log.warning("engine: calibration FALLBACK in use (no MoSPI data); run `make data-real && python -m data_gen.calibrate`")
    macro = _macro(cal, T)
    bronze.mkdir(parents=True, exist_ok=True)
    for src in SOURCE_COLUMNS:
        for old in (bronze / src).glob("**/*.parquet") if (bronze / src).exists() else []:
            old.unlink()
    ingest_base = datetime(2026, 7, 1)
    seeds = np.random.SeedSequence(s.seed).spawn((n_factories + chunk - 1) // chunk)
    profiles, labels_all = [], []
    hero_prof, hero_src, hero_labels = _hero_tables(T, horizon, cal, macro)
    profiles.append(hero_prof)
    labels_all.append(hero_labels)
    for c, seq in enumerate(seeds):
        lo, hi = c * chunk + 2, min((c + 1) * chunk + 1, n_factories)
        if lo > hi:
            break
        ids = np.array([f"UP-F{i:04d}" for i in range(lo, hi + 1)])
        prof, sig, lab = simulate_chunk(seq, ids, T, horizon, cal, macro)
        tables = _split_sources(np.random.default_rng(seq.spawn(1)[0]), sig, ingest_base)
        if c == 0:
            for src in tables:
                tables[src] = pd.concat([hero_src[src], tables[src]], ignore_index=True)
        for src, df in tables.items():
            for sector, part in df.groupby("sector"):
                p = bronze / src / f"sector={sector}"
                p.mkdir(parents=True, exist_ok=True)
                part.drop(columns="sector").to_parquet(p / f"chunk-{c:05d}.parquet", index=False)
        profiles.append(prof)
        labels_all.append(lab)
        log.info("chunk %s: factories %s-%s (%.1fs)", c, lo, hi, time.perf_counter() - t0)
    prof = pd.concat(profiles, ignore_index=True)
    prof["sector_label"] = prof["sector"].map(lambda x: SECTORS[x]["label"])
    prof["turnover_band"] = prof["annual_turnover_cr"].map(turnover_band)
    prof["udyam_number"] = "UDYAM-SYN-" + prof["factory_id"].str[5:]
    profile_cols = ["factory_id", "name", "sector", "sector_label", "cluster", "udyam_category", "vintage_years",
                    "annual_turnover_cr", "turnover_band", "n_buyers", "loan_requested_inr", "udyam_number"]
    prof[profile_cols].to_parquet(bronze / "factories.parquet", index=False)
    truth = prof[["factory_id", "stress_month", "stress_type", "stress_source", "defaults", "sma2_month",
                  "default_month", "udyam_category", "sector", "cluster"]].copy()
    for c in ("stress_month", "sma2_month", "default_month"):
        truth[c] = truth[c].where(truth[c] > 0)
    truth["stress_type"] = truth["stress_type"].map(lambda x: LEGACY_TYPE.get(x, x))
    truth["defaults"] = truth["defaults"].astype(int)
    truth.to_parquet(bronze / "_truth_factory.parquet", index=False)
    labels = pd.concat(labels_all, ignore_index=True)
    labels.to_parquet(bronze / "_truth_monthly.parquet", index=False)
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if __import__("sys").platform == "darwin" else 1024)
    live = labels[labels["is_post_default"] == 0]
    stats = {
        "factories": int(len(prof)), "months": T, "factory_months": int(len(labels)),
        "defaults": int(truth["defaults"].sum()), "default_rate": round(float(truth["defaults"].mean()), 4),
        "default_rate_micro": round(float(truth.loc[truth.udyam_category == "micro", "defaults"].mean()), 4),
        "default_rate_small": round(float(truth.loc[truth.udyam_category == "small", "defaults"].mean()), 4),
        "stressed_rate": round(float(truth["stress_month"].notna().mean()), 4),
        "stress_types": truth["stress_type"].value_counts().to_dict(),
        "stress_sources": truth["stress_source"].value_counts().to_dict(),
        "monthly_label_rate": round(float(live["default_within_12m"].mean()), 4),
        "calibration_source": cal.get("source"), "shock_month": SHOCK_MONTH,
        "seconds": round(time.perf_counter() - t0, 1), "peak_rss_mb": round(peak_mb),
    }
    log.info("engine done: %s", stats)
    return stats
