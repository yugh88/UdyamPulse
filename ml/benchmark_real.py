"""Real public-data benchmarks: does the UdyamPulse modelling pipeline work on real defaults?

This is a **methodology benchmark, not the Indian MSME score.** The same steps the product model uses
(features → LightGBM → isotonic calibration → SHAP → drift monitoring, judged by ml/evaluate.py) run on:

- **A1 · U.S. SBA 7(a) loans** (public domain): manufacturing (NAICS 31–33), approved FY2010 onward, with a
  resolved outcome (paid in full or charged off). Label: charged off. Split by approval year: train ≤ FY2016,
  validate FY2017, test FY2018+; plus a hold-out of whole states.
- **A2 · UCI Polish companies bankruptcy** (CC BY 4.0, Tomczak 2016): 64 financial ratios of real firms.
  Train on forecasting years 1–3, test on years 4–5. This checks the financial-health pillar's approach.

Leakage control: only fields known at loan approval may become features. `LEAKAGE_COLUMNS` lists every field
recorded later; `build_sba_features` refuses to run if one reaches the feature set (tests/test_real_data.py).

    python -m ml.benchmark_real            # both (needs `make data-real`)
    python -m ml.benchmark_real --only sba
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from core.settings import get_settings
from data_real.common import CACHE, load_checksums
from data_real.common import ROOT as DATA_REAL
from ml.evaluate import (
    Calibrator,
    calibration_table,
    expected_calibration_error,
    group_metrics,
    metrics_with_ci,
    precision_at_k,
    psi,
)

log = logging.getLogger("udyampulse.benchmark")

# ---------------------------------------------------------------- SBA 7(a)

SBA_FILE = CACHE / "sba_7a_fy2010plus.parquet"
# Recorded after approval, or describing the loan's current state: never a feature.
LEAKAGE_COLUMNS = frozenset({
    "LoanStatus", "PaidInFullDate", "ChargeOffDate", "GrossChargeOffAmount", "AsOfDate", "SoldSecMrktInd",
    "FirstDisbursementDate",
    # The bank the loan is *currently* assigned to; loans can move after default.
    "BankName", "BankFDICNumber", "BankNCUANumber", "BankStreet", "BankCity", "BankState", "BankZip",
    # Found by our leakage audit: the published term is rewritten for loans that go bad (non-standard terms
    # such as 38 or 70 months in ~90% of charged-off loans vs ~20% of others), so it partly encodes the time to
    # charge-off. `term_leakage_evidence` recomputes this on every run.
    "TermInMonths",
})
# The only raw fields features may be built from: all known on the approval date.
ORIGINATION_COLUMNS = frozenset({
    "GrossApproval", "SBAGuaranteedApproval", "ApprovalFY", "ProcessingMethod", "InitialInterestRate",
    "FixedorVariableInterestInd", "NaicsCode", "FranchiseCode", "ProjectState", "BusinessType",
    "BusinessAge", "RevolverStatus", "JobsSupported", "CollateralInd", "LocationID",
})
SBA_TRAIN_FY, SBA_VALID_FY, SBA_TEST_FROM_FY = 2016, 2017, 2018
SBA_NUMERIC = ["log_amount", "guarantee_pct", "interest_rate", "jobs_supported", "variable_rate",
               "revolver", "collateral", "franchise", "naics4_te", "state_te", "lender_volume"]
SBA_CATEGORICAL = ["business_age", "business_type", "processing_method"]
SBA_FEATURES = SBA_NUMERIC + SBA_CATEGORICAL
SBA_FEATURE_SOURCES = {  # feature → the raw fields it is built from (checked against the allow-list)
    "log_amount": {"GrossApproval"}, "guarantee_pct": {"SBAGuaranteedApproval", "GrossApproval"},
    "interest_rate": {"InitialInterestRate"},
    "jobs_supported": {"JobsSupported"}, "variable_rate": {"FixedorVariableInterestInd"},
    "revolver": {"RevolverStatus"}, "collateral": {"CollateralInd"}, "franchise": {"FranchiseCode"},
    "naics4_te": {"NaicsCode"}, "state_te": {"ProjectState"}, "lender_volume": {"LocationID", "ApprovalFY"},
    "business_age": {"BusinessAge"}, "business_type": {"BusinessType"}, "processing_method": {"ProcessingMethod"},
}
LGB_PARAMS = {"objective": "binary", "learning_rate": 0.03, "num_leaves": 7, "max_depth": 4,
              "min_child_samples": 300, "feature_fraction": 0.7, "bagging_fraction": 0.8, "bagging_freq": 1,
              "lambda_l2": 30.0, "cat_smooth": 50, "min_data_per_group": 200, "verbose": -1, "seed": 42}


HORIZON_MONTHS = 60  # SBA charges off a median 58 months after approval, well after the borrower stops paying
DESIGNS = {
    "horizon": f"Charged off within {HORIZON_MONTHS} months of approval; every disbursed loan approved at least "
               f"{HORIZON_MONTHS} months before the data date (active and paid-off loans count as 0)",
    "resolved": "Charged off vs paid in full, loans with a final outcome only (the addendum's design; biased for "
                "recent cohorts, shown for comparison)",
}


def load_sba(path: Path = SBA_FILE, design: str = "horizon",
             audit_cols: tuple[str, ...] = ()) -> tuple[pd.DataFrame, dict]:
    """Manufacturing loans approved FY2010+, labelled by `design`, plus the counts of what was excluded and why.

    `horizon` (headline): a fixed-horizon default label, as credit models define PD, on every disbursed loan
    old enough to have a full horizon. Nothing is selected on the outcome, so there is no resolution bias.
    `resolved`: paid in full vs charged off only. Recent cohorts are mostly still active, so their resolved
    loans are early payoffs and early charge-offs: a selection effect that flatters some features."""
    import duckdb

    con = duckdb.connect()
    base = (f"FROM read_parquet('{path}') WHERE substr(NaicsCode, 1, 2) IN ('31', '32', '33') "  # nosec B608
            "AND TRY_CAST(ApprovalFY AS INTEGER) >= 2010")
    status = dict(con.execute(f"SELECT replace(LoanStatus, ' ', ''), count(*) {base} GROUP BY 1").fetchall())  # nosec B608
    as_of = con.execute(f"SELECT max(TRY_CAST(AsOfDate AS DATE)) {base}").fetchone()[0]  # nosec B608
    # `audit_cols` (leakage audit only) adds named post-origination fields; they never reach build_sba_features.
    cols = ", ".join(sorted(ORIGINATION_COLUMNS) + list(audit_cols))
    st = "replace(LoanStatus, ' ', '')"
    if design == "horizon":
        cutoff = f"DATE '{as_of}' - INTERVAL {HORIZON_MONTHS} MONTH"
        label = (f"CASE WHEN {st} = 'CHGOFF' AND date_diff('month', TRY_CAST(ApprovalDate AS DATE), "
                 f"TRY_CAST(ChargeOffDate AS DATE)) <= {HORIZON_MONTHS} THEN 1 ELSE 0 END")
        where = f"AND {st} IN ('PIF', 'CHGOFF', 'EXEMPT') AND TRY_CAST(ApprovalDate AS DATE) <= {cutoff}"
        excluded = {k: v for k, v in status.items() if k in ("CANCLD", "COMMIT")}
        excluded["approved_within_horizon_of_data_date"] = con.execute(
            f"SELECT count(*) {base} AND {st} IN ('PIF', 'CHGOFF', 'EXEMPT') "  # nosec B608
            f"AND TRY_CAST(ApprovalDate AS DATE) > {cutoff}").fetchone()[0]
    elif design == "resolved":
        label = f"CASE WHEN {st} = 'CHGOFF' THEN 1 ELSE 0 END"
        where = f"AND {st} IN ('PIF', 'CHGOFF')"
        excluded = {k: v for k, v in status.items() if k not in ("PIF", "CHGOFF")}
    else:
        raise ValueError(design)
    # The label is computed in SQL from post-origination fields; only origination fields leave this query.
    df = con.execute(f"SELECT {cols}, {label} AS charged_off {base} {where}").df()  # nosec B608
    return df, {"status_counts": status, "excluded": excluded, "as_of": str(as_of)}


def _target_encode(train_key: pd.Series, train_y: pd.Series, apply_key: pd.Series, smoothing: float = 50.0) -> np.ndarray:
    prior = train_y.mean()
    stats = train_y.groupby(train_key).agg(["sum", "count"])
    enc = (stats["sum"] + smoothing * prior) / (stats["count"] + smoothing)
    return apply_key.map(enc).fillna(prior).to_numpy(float)


def _oof_target_encode(key: pd.Series, y: pd.Series, folds: int = 5, seed: int = 0) -> np.ndarray:
    """Out-of-fold encoding for training rows, so no row's own label leaks into its feature."""
    out = np.zeros(len(key))
    fold = np.random.default_rng(seed).integers(0, folds, len(key))
    for k in range(folds):
        m = fold == k
        out[m] = _target_encode(key[~m], y[~m], key[m])
    return out


def build_sba_features(df: pd.DataFrame, train_mask: np.ndarray, lender_counts: pd.Series | None = None) -> pd.DataFrame:
    """Features from approval-time fields only. Target encodings are learned on `train_mask` rows only."""
    used = set().union(*SBA_FEATURE_SOURCES.values())
    if used & LEAKAGE_COLUMNS or not used <= ORIGINATION_COLUMNS:
        raise AssertionError(f"post-origination field in features: {sorted(used & LEAKAGE_COLUMNS)}")
    num = lambda c: pd.to_numeric(df[c], errors="coerce")  # noqa: E731
    amount = num("GrossApproval")
    out = pd.DataFrame(index=df.index)
    out["log_amount"] = np.log1p(amount)
    out["guarantee_pct"] = (num("SBAGuaranteedApproval") / amount.replace(0, np.nan)).clip(0, 1)
    out["interest_rate"] = num("InitialInterestRate")
    out["jobs_supported"] = num("JobsSupported").clip(upper=500)
    out["variable_rate"] = (df["FixedorVariableInterestInd"].str.upper() == "V").astype(int)
    out["revolver"] = (df["RevolverStatus"].astype(str).str.strip() == "1").astype(int)
    out["collateral"] = (df["CollateralInd"].str.upper() == "Y").astype(int)
    franchise = df["FranchiseCode"].fillna("").astype(str).str.strip()
    out["franchise"] = (~franchise.isin(["", "0", "00000", "nan"])).astype(int)
    y = df["charged_off"]
    naics4 = df["NaicsCode"].astype(str).str[:4]
    state = df["ProjectState"].fillna("NA").astype(str)
    tm = np.asarray(train_mask, bool)
    for name, key in (("naics4_te", naics4), ("state_te", state)):
        col = np.empty(len(df))
        col[tm] = _oof_target_encode(key[tm].reset_index(drop=True), y[tm].reset_index(drop=True))
        col[~tm] = _target_encode(key[tm], y[tm], key[~tm])
        out[name] = col
    counts = lender_counts if lender_counts is not None else df.loc[tm, "LocationID"].value_counts()
    out["lender_volume"] = np.log1p(df["LocationID"].map(counts).fillna(0).to_numpy(float))
    for c, src in (("business_age", "BusinessAge"), ("business_type", "BusinessType"),
                   ("processing_method", "ProcessingMethod")):
        out[c] = df[src].fillna("Unknown").astype(str).str.strip().astype("category")
    if list(out.columns) != SBA_FEATURES:
        raise AssertionError("feature order changed")
    return out


def _align_categories(frames: list[pd.DataFrame]) -> None:
    for c in SBA_CATEGORICAL:
        cats = sorted(set().union(*(set(f[c].astype(str)) for f in frames)))
        for f in frames:
            f[c] = pd.Categorical(f[c].astype(str), categories=cats)


def _fit(X_tr, y_tr, X_va, y_va, params=LGB_PARAMS, rounds: int = 2000) -> lgb.Booster:
    dtr = lgb.Dataset(X_tr, y_tr, categorical_feature=[c for c in SBA_CATEGORICAL if c in X_tr], free_raw_data=False)
    dva = lgb.Dataset(X_va, y_va, reference=dtr)
    return lgb.train(params, dtr, rounds, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(0)])


def _shap_top(model: lgb.Booster, X: pd.DataFrame, k: int = 10) -> list[dict]:
    sample = X.sample(min(5000, len(X)), random_state=1)
    contrib = model.predict(sample, pred_contrib=True)[:, :-1]
    imp = np.abs(contrib).mean(axis=0)
    order = np.argsort(-imp)[:k]
    return [{"feature": X.columns[i], "mean_abs_shap": round(float(imp[i]), 4)} for i in order]


STANDARD_TERMS = (12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 180, 240, 300)


def term_leakage_evidence(path: Path = SBA_FILE) -> dict:
    """Why TermInMonths is excluded: share of non-standard terms among loans that defaulted vs the rest."""
    import duckdb

    con = duckdb.connect()
    loans = con.execute(
        f"SELECT TRY_CAST(TermInMonths AS DOUBLE) AS t, replace(LoanStatus, ' ', '') AS st FROM read_parquet('{path}') "  # nosec B608
        "WHERE substr(NaicsCode, 1, 2) IN ('31', '32', '33') AND TRY_CAST(ApprovalFY AS INTEGER) >= 2010 "
        "AND replace(LoanStatus, ' ', '') IN ('PIF', 'CHGOFF')").df()
    odd = ~loans["t"].isin(STANDARD_TERMS)
    co = loans["st"] == "CHGOFF"
    return {"non_standard_term_share_charged_off": round(float(odd[co].mean()), 3),
            "non_standard_term_share_paid_in_full": round(float(odd[~co].mean()), 3),
            "standard_terms": list(STANDARD_TERMS),
            "conclusion": "TermInMonths is revised for loans that go bad, so it is excluded as a post-origination field."}


def term_leak_auc(path: Path, lenders: pd.Series, n_boot: int) -> dict:
    """What the headline AUC would read if the leaking TermInMonths were kept as a feature (audit only).

    Same design, split, model and calibration as the headline; the only change is one extra column. The result is
    stored so the "inflated" figure we quote is reproducible, and it is never used as a reported benchmark."""
    df, _ = load_sba(path, "horizon", audit_cols=("TermInMonths",))
    fy = df["ApprovalFY"].astype(int).to_numpy()
    train_m, valid_m, test_m = fy <= SBA_TRAIN_FY, fy == SBA_VALID_FY, fy >= SBA_TEST_FROM_FY
    X = build_sba_features(df.drop(columns=["TermInMonths"]), train_m, lenders)
    X["term_months"] = pd.to_numeric(df["TermInMonths"], errors="coerce").to_numpy()
    y = df["charged_off"].to_numpy()
    parts = [X[train_m].copy(), X[valid_m].copy(), X[test_m].copy()]
    _align_categories(parts)
    model = _fit(parts[0], y[train_m], parts[1], y[valid_m])
    p_te = Calibrator.fit(model.predict(parts[1]), y[valid_m])(model.predict(parts[2]))
    m = metrics_with_ci(y[test_m], p_te, n_boot)
    return {"auc": m["auc"], "auc_ci95": m["auc_ci95"], "n_test": int(test_m.sum()),
            "note": "Audit only: the headline model with TermInMonths added. Inflated by leakage; never reported "
                    "as a benchmark."}


def _lender_counts(path: Path) -> pd.Series:
    """Loans per originating lender ID in the training years, across all industries (volume, no outcomes)."""
    import duckdb

    rows = duckdb.connect().execute(
        f"SELECT LocationID, count(*) FROM read_parquet('{path}') "  # nosec B608
        f"WHERE TRY_CAST(ApprovalFY AS INTEGER) BETWEEN 2010 AND {SBA_TRAIN_FY} GROUP BY 1").fetchall()
    return pd.Series(dict(rows), dtype=float)


def _sba_design(path: Path, design: str, lenders: pd.Series, n_boot: int, state_holdout: int) -> dict:
    df, counts = load_sba(path, design)
    fy = df["ApprovalFY"].astype(int).to_numpy()
    train_m, valid_m, test_m = fy <= SBA_TRAIN_FY, fy == SBA_VALID_FY, fy >= SBA_TEST_FROM_FY
    X = build_sba_features(df, train_m, lenders)
    y = df["charged_off"].to_numpy()
    X_tr, X_va, X_te = X[train_m].copy(), X[valid_m].copy(), X[test_m].copy()
    _align_categories([X_tr, X_va, X_te])
    model = _fit(X_tr, y[train_m], X_va, y[valid_m])
    raw_tr, raw_va, raw_te = model.predict(X_tr), model.predict(X_va), model.predict(X_te)
    cal = Calibrator.fit(raw_va, y[valid_m])
    p_te, y_te = cal(raw_te), y[test_m]
    naics3 = df["NaicsCode"].astype(str).str[:3].to_numpy()
    out = {
        "design": DESIGNS[design],
        "selection": {"rows_used": int(len(df)), "defaults": int(y.sum()), "default_rate": round(float(y.mean()), 4),
                      "excluded": counts["excluded"], "data_as_of": counts["as_of"]},
        "split": {"train": f"FY2010-FY{SBA_TRAIN_FY}", "validation": f"FY{SBA_VALID_FY} (early stopping, isotonic "
                  "calibration)", "test": f"FY{SBA_TEST_FROM_FY}-FY{int(fy[test_m].max())}",
                  "n_train": int(train_m.sum()), "n_valid": int(valid_m.sum()), "n_test": int(test_m.sum())},
        "test": metrics_with_ci(y_te, p_te, n_boot),
        "train_auc": round(float(metrics_with_ci(y[train_m], raw_tr, 0)["auc"]), 4),
        "test_uncalibrated_brier": round(float(np.mean((raw_te - y_te) ** 2)), 4),
        "expected_calibration_error": expected_calibration_error(y_te, p_te),
        "calibration": calibration_table(y_te, p_te),
        "precision_at_k": precision_at_k(y_te, p_te),
        "by_year": group_metrics(y_te, p_te, fy[test_m], min_n=150, min_pos=10),
        "by_sector_naics3": group_metrics(y_te, p_te, naics3[test_m], min_n=300, min_pos=15),
        "top_features_shap": _shap_top(model, X_te),
        "score_psi_train_vs_test": round(psi(raw_tr, raw_te), 4),
    }
    if state_holdout:  # whole states never seen in training, scored in the test years
        states = df["ProjectState"].fillna("NA").astype(str).to_numpy()
        big = pd.Series(states[train_m]).value_counts()
        held = sorted(np.random.default_rng(3).choice(big[big >= 300].index.to_numpy(), size=state_holdout,
                                                      replace=False).tolist())
        in_held = np.isin(states, held)
        tr2, va2, te2 = train_m & ~in_held, valid_m & ~in_held, test_m & in_held
        X2 = build_sba_features(df, tr2, lenders)
        parts = [X2[tr2].copy(), X2[va2].copy(), X2[te2].copy()]
        _align_categories(parts)
        m2 = _fit(parts[0], y[tr2], parts[1], y[va2])
        p2 = Calibrator.fit(m2.predict(parts[1]), y[va2])(m2.predict(parts[2]))
        out["state_holdout"] = {"held_out_states": held, **metrics_with_ci(y[te2], p2, n_boot)}
    return out


def run_sba(path: Path = SBA_FILE, n_boot: int = 1000, state_holdout: int = 8) -> dict:
    t0 = time.perf_counter()
    lenders = _lender_counts(path)
    headline = _sba_design(path, "horizon", lenders, n_boot, state_holdout)
    resolved = _sba_design(path, "resolved", lenders, n_boot, 0)
    leak = term_leak_auc(path, lenders, n_boot)
    report = {
        "dataset": "U.S. SBA 7(a) loans, manufacturing (NAICS 31-33), approved FY2010+",
        "provenance": "Real public data",
        "purpose": "Methodology benchmark on real small-business loan outcomes. Not the Indian MSME score.",
        "source": _source("FOIA_7a_FY2010_FY2019_asof_260930.csv", "FOIA_7a_FY2020_Present_asof_260930.csv"),
        "label": headline["design"],
        **headline,
        "features": SBA_FEATURES,
        "leakage_guard": {"excluded_columns": sorted(LEAKAGE_COLUMNS),
                          "allowed_source_columns": sorted(ORIGINATION_COLUMNS),
                          "target_encoding": "NAICS-4 and state encoded out-of-fold on training rows; "
                                             "validation and test rows use training statistics only",
                          "label_fields": "LoanStatus, ApprovalDate and ChargeOffDate build the label inside the "
                                          "query and never leave it",
                          "term_leakage_evidence": term_leakage_evidence(path),
                          "auc_if_term_included": leak},
        "comparison_resolved_only": {k: resolved[k] for k in ("design", "selection", "split", "test", "train_auc",
                                                               "by_year", "top_features_shap")},
        "limitations": [
            f"SBA records a charge-off a median 58 months after approval, so the {HORIZON_MONTHS}-month label "
            "captures roughly the defaults of the first three years; later defaults count as performing.",
            "The resolved-only design (paid in full vs charged off) scores higher on recent cohorts because their "
            "resolved loans are early payoffs and early charge-offs; its AUC falls cohort by cohort, which is why "
            "it is not the headline.",
            "U.S. loans with SBA guarantees differ from Indian MSME credit; only the methodology transfers.",
            "Lender volume uses the originating lender ID (LocationID); current-servicer fields are excluded.",
            "Loan term, normally a strong approval-time predictor, is excluded because the published value is "
            "revised for loans that go bad (see leakage_guard.term_leakage_evidence). With it the test AUC would read "
            f"{leak['auc']:.3f} (leakage_guard.auc_if_term_included), an inflated figure we do not report.",
        ],
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    report["runtime_seconds"] = round(time.perf_counter() - t0, 1)
    return report


# ---------------------------------------------------------------- UCI Polish bankruptcy

POLISH_FILE = CACHE / "polish_bankruptcy.parquet"
POLISH_VARIABLES = DATA_REAL / "samples" / "polish_variables.json"
RATIO_FAMILIES = {  # by the ratio's definition (UCI variable list), for the pillar view
    "profitability": ("profit", "ebit", "ebitda", "retained earnings"),
    "leverage": ("liabilities / total assets", "equity", "total assets / total liabilities", "long-term liabilities"),
    "liquidity": ("current assets", "working capital", "cash", "short-term liabilities"),
    "activity": ("sales /", "/ sales", "inventory", "receivables", "rotation", "turnover", "costs"),
}


def _family(desc: str) -> str:
    d = desc.lower()
    for fam, keys in RATIO_FAMILIES.items():
        if any(k in d for k in keys):
            return fam
    return "size"


def run_polish(path: Path = POLISH_FILE, n_boot: int = 1000) -> dict:
    t0 = time.perf_counter()
    df = pd.read_parquet(path)
    y = df["class"].astype(int).to_numpy()
    year = df["year"].astype(int).to_numpy()
    feats = [c for c in df.columns if c.startswith("A")]
    X = df[feats].astype(float)
    train_all, test_m = year <= 3, year >= 4
    rng = np.random.default_rng(5)
    valid_pick = rng.random(len(df)) < 0.2
    tr, va = train_all & ~valid_pick, train_all & valid_pick
    params = {**LGB_PARAMS, "num_leaves": 31, "min_child_samples": 40}
    model = _fit(X[tr], y[tr], X[va], y[va], params)
    cal = Calibrator.fit(model.predict(X[va]), y[va])
    p_te = cal(model.predict(X[test_m]))
    y_te = y[test_m]
    names = json.loads(POLISH_VARIABLES.read_text()) if POLISH_VARIABLES.exists() else {}
    top = _shap_top(model, X[test_m], k=12)
    for row in top:
        row["definition"] = names.get(row["feature"], "")
        row["family"] = _family(row["definition"]) if row["definition"] else None
    sample = X[test_m].sample(min(5000, int(test_m.sum())), random_state=1)
    contrib = np.abs(model.predict(sample, pred_contrib=True)[:, :-1]).mean(axis=0)
    fam_share: dict[str, float] = {}
    for f, v in zip(feats, contrib, strict=True):
        fam = _family(names.get(f, "")) if names.get(f) else "unknown"
        fam_share[fam] = fam_share.get(fam, 0.0) + float(v)
    total = sum(fam_share.values()) or 1.0
    return {
        "dataset": "UCI Polish companies bankruptcy (43,405 firm-years, 64 financial ratios)",
        "provenance": "Real public data",
        "purpose": "Validates the financial-health pillar's approach (cash-flow, liquidity, leverage ratios) on "
                   "real firms. Not the Indian MSME score.",
        "source": _source("polish_bankruptcy.parquet"),
        "citation": "Tomczak, S. (2016). Polish Companies Bankruptcy [Dataset]. UCI Machine Learning Repository. "
                    "https://doi.org/10.24432/C5F600",
        "licence": "CC BY 4.0",
        "label": "bankrupt within the dataset's forecasting horizon (class = 1)",
        "split": {"train": "forecasting years 1-3 (80%), validation 20% of the same years", "test": "years 4-5",
                  "n_train": int(tr.sum()), "n_valid": int(va.sum()), "n_test": int(test_m.sum()),
                  "note": "'Year' is the forecasting horizon (year 1 = status after 5 years ... year 5 = after 1 "
                          "year), so this tests generalisation across horizons, not across calendar time."},
        "test": metrics_with_ci(y_te, p_te, n_boot),
        "expected_calibration_error": expected_calibration_error(y_te, p_te),
        "calibration": calibration_table(y_te, p_te),
        "precision_at_k": precision_at_k(y_te, p_te),
        "by_year": group_metrics(y_te, p_te, year[test_m], min_n=100, min_pos=10),
        "top_features_shap": top,
        "importance_by_ratio_family": {k: round(v / total, 3) for k, v in sorted(fam_share.items(), key=lambda kv: -kv[1])},
        "limitations": ["Polish firms 2000-2013 with audited statements; Indian MSMEs often lack audited accounts, "
                        "which is why UdyamPulse relies on GST, bank and operating signals instead.",
                        "The dataset has no company identifier, so the same firm can appear in a training year and "
                        "a test year; that overlap can flatter the AUC.",
                        "Bankrupt firms are 4.8% of rows across a 1-5 year horizon; published studies on this "
                        "dataset report AUCs of a similar order with gradient boosting."],
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------- reports

def _source(*files: str) -> list[dict]:
    known = load_checksums()
    return [{"file": f, **{k: known[f][k] for k in ("url", "licence", "source", "retrieved_at", "sha256") if k in known[f]}}
            for f in files if f in known]


def _fmt_ci(m: dict, k: str) -> str:
    lo, hi = m[f"{k}_ci95"]
    return f"{m[k]:.3f} ({lo:.3f}–{hi:.3f})"


def to_markdown(name: str, r: dict) -> str:
    t = r["test"]
    lines = [f"# {name}", "", f"**Provenance: {r['provenance']}.** {r['purpose']}", "",
             f"Dataset: {r['dataset']}.", "",
             "| Test metric | Value (95% bootstrap CI, 1,000 resamples) |", "|---|---|",
             f"| AUC | {_fmt_ci(t, 'auc')} |", f"| KS | {_fmt_ci(t, 'ks')} |", f"| Brier score | {_fmt_ci(t, 'brier')} |",
             f"| Test accounts / defaults | {t['n']:,} / {t['positives']:,} ({t['event_rate']:.1%}) |",
             f"| Expected calibration error | {r['expected_calibration_error']:.4f} |", "",
             "## Precision in the riskiest accounts", "", "| Top | n | Precision | Recall | Lift |", "|---|---|---|---|---|"]
    lines += [f"| {x['top_pct']}% | {x['n']:,} | {x['precision']:.3f} | {x['recall']:.3f} | {x['lift']} |"
              for x in r["precision_at_k"]]
    lines += ["", "## By year", "", "| Year | n | Defaults | Rate | AUC (95% CI) |", "|---|---|---|---|---|"]
    for g in r["by_year"]:
        ci = f" ({g['auc_ci95'][0]:.3f}–{g['auc_ci95'][1]:.3f})" if "auc_ci95" in g else ""
        lines.append(f"| {g['group']} | {g['n']:,} | {g['positives']} | {g['event_rate']:.1%} | "
                     f"{(str(g['auc']) + ci) if 'auc' in g else 'too few defaults'} |")
    if "comparison_resolved_only" in r:
        c = r["comparison_resolved_only"]
        lines += ["", "## Why the fixed-horizon label is the headline", "",
                  f"Headline design: {r['design']}.", "",
                  f"For comparison, the resolved-only design ({c['design']}) gives test AUC {_fmt_ci(c['test'], 'auc')} "
                  f"on {c['test']['n']:,} loans, but its AUC falls cohort by cohort:", "",
                  "| Year | n | Defaults | AUC |", "|---|---|---|---|"]
        lines += [f"| {g['group']} | {g['n']:,} | {g['positives']} | {g.get('auc', 'too few defaults')} |"
                  for g in c["by_year"]]
    if "state_holdout" in r:
        sh = r["state_holdout"]
        lines += ["", "## Hold-out of whole states", "",
                  f"Never-seen states {', '.join(sh['held_out_states'])}, test years: AUC {_fmt_ci(sh, 'auc')}, "
                  f"n = {sh['n']:,}, defaults = {sh['positives']}."]
    lines += ["", "## Calibration (test, after isotonic calibration on validation)", "",
              "| Decile | n | Mean predicted | Observed |", "|---|---|---|---|"]
    lines += [f"| {c['bin']} | {c['n']:,} | {c['mean_predicted']:.4f} | {c['observed']:.4f} |" for c in r["calibration"]]
    lines += ["", "## Strongest features (mean |SHAP|, test)", ""]
    lines += [f"- `{f['feature']}` {f['mean_abs_shap']}" + (f" — {f['definition']}" if f.get("definition") else "")
              for f in r["top_features_shap"]]
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in r["limitations"]]
    src = r.get("source") or []
    if src:
        lines += ["", "## Source", ""] + [f"- {s.get('source', '')} · {s.get('licence', '')} · retrieved "
                                          f"{s.get('retrieved_at', '')} · `{s['file']}` sha256 {s.get('sha256', '')[:16]}…"
                                          for s in src]
    if r.get("citation"):
        lines += ["", f"Citation: {r['citation']}"]
    return "\n".join(lines) + "\n"


def write(name: str, slug: str, report: dict) -> None:
    out = get_settings().reports
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slug}.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    (out / f"{slug}.md").write_text(to_markdown(name, report))
    log.info("wrote %s (.json, .md)", slug)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["sba", "polish"])
    ap.add_argument("--boot", type=int, default=1000)
    args = ap.parse_args()
    if args.only in (None, "sba"):
        if not SBA_FILE.exists():
            raise SystemExit("SBA data missing: run `make data-real` first")
        r = run_sba(n_boot=args.boot)
        write("Real-data benchmark: U.S. SBA 7(a) manufacturing loans", "real_sba_benchmark", r)
        print(json.dumps({"sba_test": r["test"], "state_holdout_auc": r["state_holdout"]["auc"]}, indent=1))
    if args.only in (None, "polish"):
        if not POLISH_FILE.exists():
            raise SystemExit("Polish data missing: run `make data-real` first")
        r = run_polish(n_boot=args.boot)
        write("Real-data benchmark: UCI Polish companies bankruptcy", "real_polish_benchmark", r)
        print(json.dumps({"polish_test": r["test"]}, indent=1))


if __name__ == "__main__":
    main()
