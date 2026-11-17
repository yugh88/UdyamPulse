"""Tier C engine and Tier B calibration: deterministic, realistic, hero-preserving, offline-safe."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data_gen import calibrate, engine
from data_gen.generate import HERO_ID, SOURCE_COLUMNS

T, H = 36, 48


@pytest.fixture(scope="module")
def cal():
    return calibrate.load()


@pytest.fixture(scope="module")
def chunk(cal):
    macro = engine._macro(cal, T)  # noqa: SLF001
    ids = np.array([f"UP-F{i:04d}" for i in range(2, 4002)])
    return engine.simulate_chunk(np.random.SeedSequence(42).spawn(1)[0], ids, T, H, cal, macro)


def test_same_seed_same_panel(cal):
    macro = engine._macro(cal, T)  # noqa: SLF001
    ids = np.array([f"UP-F{i:04d}" for i in range(2, 202)])
    a = engine.simulate_chunk(np.random.SeedSequence(7), ids, T, H, cal, macro)
    b = engine.simulate_chunk(np.random.SeedSequence(7), ids, T, H, cal, macro)
    for x, y in zip(a, b, strict=True):
        pd.testing.assert_frame_equal(x, y)


def test_default_rates_and_variety(chunk):
    prof, signals, labels = chunk
    rate = prof["defaults"].mean()
    micro = prof.loc[prof.udyam_category == "micro", "defaults"].mean()
    small = prof.loc[prof.udyam_category == "small", "defaults"].mean()
    assert 0.06 <= rate <= 0.13, rate
    assert micro > small  # micro units default more often
    assert {"order_loss", "cash_squeeze", "buyer_default", "input_cost_spike", "diversion", "sudden"} <= set(
        prof["stress_type"].dropna())
    assert {"idiosyncratic", "macro", "contagion"} <= set(prof["stress_source"].dropna())
    stressed = prof["stress_month"] > 0
    assert (stressed & ~prof["defaults"]).sum() > (stressed & prof["defaults"]).sum() * 0.5  # many recover
    assert len(signals) == len(prof) * T and signals["aa_credits"].gt(0).all()


def test_labels_follow_the_default_month(chunk):
    prof, _, labels = chunk
    d = labels.merge(prof[["factory_id", "default_month"]], on="factory_id")
    pos = d[d.default_within_12m == 1]
    assert ((pos.default_month > pos.month) & (pos.default_month <= pos.month + 12)).all()
    post = d[d.is_post_default == 1]
    assert (post.month >= post.default_month).all()


def test_no_protected_attributes(chunk):
    prof, signals, _ = chunk
    banned = {"gender", "religion", "caste", "age", "ethnicity", "owner_gender"}
    assert not banned & set(prof.columns) and not banned & set(signals.columns)


def test_macro_shock_dents_hard_hit_sectors_more(cal):
    m = engine._macro(cal, T)  # noqa: SLF001
    at = engine.SHOCK_MONTH - 1
    dip = {s: m[s][at] / m[s][at - 1] for s in m}
    assert dip["auto_components"] < dip["food_processing"]  # the IIP shows autos fell far more in 2020


def test_hero_is_identical_to_the_demo_dataset(cal):
    macro = engine._macro(cal, T)  # noqa: SLF001
    _, hero_src, hero_labels = engine._hero_tables(T, H, cal, macro)  # noqa: SLF001
    from data_gen import generate

    demo = generate.generate(n_factories=500)
    for src, cols in SOURCE_COLUMNS.items():
        a = demo[src][demo[src].factory_id == HERO_ID][["month", *cols]].reset_index(drop=True)
        b = hero_src[src][hero_src[src].month <= 24][["month", *cols]].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        assert hero_src[src].month.max() == T
    assert hero_labels.loc[hero_labels.month == 20, "default_within_12m"].item() == 1


def test_calibration_falls_back_offline_and_cites_sources(tmp_path):
    fb = calibrate.calibrate(Path(tmp_path) / "missing.parquet")
    assert fb["source"] == "fallback"
    assert all("fallback" in v["source"] for v in fb["sectors"].values())
    committed = calibrate.load()
    for sector, p in committed["sectors"].items():
        assert p.get("source"), sector
        assert len(p["season"]) == 12 and abs(np.mean(p["season"]) - 1) < 0.02
    for target in committed["targets"].values():
        assert target["source"]
