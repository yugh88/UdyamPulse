"""Real public-data benchmark: leakage guard and pipeline, run offline on the committed 4,000-loan SBA sample."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data_real.common import ROOT as DATA_REAL
from ml import benchmark_real as b
from ml.evaluate import Calibrator, calibration_table, metrics_with_ci, precision_at_k

SAMPLE_CSV = DATA_REAL / "samples" / "sba_7a_manufacturing_sample.csv"


@pytest.fixture(scope="module")
def sample_parquet(tmp_path_factory):
    import duckdb

    out = tmp_path_factory.mktemp("sba") / "sample.parquet"
    duckdb.connect().execute(f"COPY (SELECT * FROM read_csv('{SAMPLE_CSV}', all_varchar = true, header = true)) "
                             f"TO '{out}' (FORMAT parquet)")
    return out


def test_no_post_origination_field_can_become_a_feature():
    used = set().union(*b.SBA_FEATURE_SOURCES.values())
    assert not used & b.LEAKAGE_COLUMNS
    assert used <= b.ORIGINATION_COLUMNS
    assert set(b.SBA_FEATURE_SOURCES) == set(b.SBA_FEATURES)
    for col in ("LoanStatus", "ChargeOffDate", "PaidInFullDate", "GrossChargeOffAmount", "TermInMonths", "BankName"):
        assert col in b.LEAKAGE_COLUMNS and col not in b.ORIGINATION_COLUMNS


def test_loaded_frame_carries_only_origination_fields_and_the_label(sample_parquet):
    for design in ("horizon", "resolved"):
        df, counts = b.load_sba(sample_parquet, design)
        assert set(df.columns) == b.ORIGINATION_COLUMNS | {"charged_off"}
        assert set(df["charged_off"].unique()) <= {0, 1}
        assert not set(df.columns) & b.LEAKAGE_COLUMNS
    resolved, _ = b.load_sba(sample_parquet, "resolved")
    horizon, counts = b.load_sba(sample_parquet, "horizon")
    assert len(horizon) > len(resolved)  # active loans count as performing in the fixed-horizon design
    assert "approved_within_horizon_of_data_date" in counts["excluded"]  # the sample stops at FY2021


def test_features_are_built_without_leakage_and_target_encoding_uses_training_rows_only(sample_parquet):
    df, _ = b.load_sba(sample_parquet, "horizon")
    train = df["ApprovalFY"].astype(int).to_numpy() <= b.SBA_TRAIN_FY
    X = b.build_sba_features(df, train)
    assert list(X.columns) == b.SBA_FEATURES and "term_months" not in X.columns
    # Changing test-period labels must not change any test-period feature.
    flipped = df.copy()
    flipped.loc[~train, "charged_off"] = 1 - flipped.loc[~train, "charged_off"]
    X2 = b.build_sba_features(flipped, train)
    pd.testing.assert_frame_equal(X[~train], X2[~train])


def test_sample_benchmark_runs_end_to_end(sample_parquet):
    r = b.run_sba(sample_parquet, n_boot=50, state_holdout=0)
    assert r["provenance"] == "Real public data"
    assert 0.0 < r["test"]["auc"] < 1.0 and r["test"]["auc_ci95"][0] <= r["test"]["auc"] <= r["test"]["auc_ci95"][1]
    assert "comparison_resolved_only" in r
    assert r["leakage_guard"]["term_leakage_evidence"]["non_standard_term_share_charged_off"] > \
        r["leakage_guard"]["term_leakage_evidence"]["non_standard_term_share_paid_in_full"]
    md = b.to_markdown("SBA sample", r)
    assert "Real public data" in md and "95% bootstrap CI" in md


def test_bootstrap_ci_brackets_the_point_estimate_and_shrinks_with_n():
    rng = np.random.default_rng(0)
    small_y = rng.integers(0, 2, 400)
    big_y = rng.integers(0, 2, 8000)
    small = metrics_with_ci(small_y, small_y * 0.3 + rng.random(400) * 0.7, n_boot=200)
    big = metrics_with_ci(big_y, big_y * 0.3 + rng.random(8000) * 0.7, n_boot=200)
    for m in (small, big):
        assert m["auc_ci95"][0] <= m["auc"] <= m["auc_ci95"][1]
    width = lambda m: m["auc_ci95"][1] - m["auc_ci95"][0]  # noqa: E731
    assert width(big) < width(small)


def test_calibration_and_precision_helpers():
    rng = np.random.default_rng(1)
    p = rng.random(5000) * 0.2
    y = (rng.random(5000) < p).astype(int)
    table = calibration_table(y, p)
    assert len(table) == 10 and abs(table[-1]["observed"] - table[-1]["mean_predicted"]) < 0.05
    top = precision_at_k(y, p)
    assert top[0]["precision"] > y.mean() and top[0]["lift"] > 1
    cal = Calibrator.fit(p * 3, y)
    assert np.all(np.diff(cal(np.sort(p * 3))) >= 0)  # isotonic: never reverses the ranking
