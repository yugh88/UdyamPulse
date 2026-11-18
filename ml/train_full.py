"""Train and evaluate the product model on the large calibrated panel (UP_DATASET=full).

    UP_DATASET=full python -m ml.train_full          # make train-full

Design (all results go to ml/reports/full/, the model to ml/artifacts_full/):
- **Group + time split.** Factories are split into 5 groups. For each group, a model is trained on the other
  four groups' months 4-20 (early stopping and isotonic calibration on their months 21-23) and tested on the
  held-out group's months 25-36. Every factory is scored once by a model that never saw it nor its time
  period; the pooled predictions give the headline metrics, with a **factory-level (cluster) bootstrap** CI.
- **Generalisation:** leave-one-sector-out, leave-one-cluster-out, and the macro shock at month 26 (all
  training data precedes it; the test is reported before, during and after it).
- **Ablation:** with and without the production signals (e-way bills, kWh, purchase orders). On synthetic
  data the uplift reflects how the generator was built; it must be re-proven in a pilot.
- **Leakage audit:** features recomputed from history truncated at the scoring month must equal the stored
  features; a shuffled-label model must score AUC ~ 0.5.
- **EWS:** the precision / recall / lead-time trade-off for every alert threshold, and the chosen operating point.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from core.settings import get_settings
from ml.evaluate import Calibrator, calibration_table, expected_calibration_error, precision_at_k, psi
from ml.features import FEATURE_NAMES, MONOTONE, _factory_features
from ml.scoring import band_for, pd_to_score
from ml.train import PARAMS, fairness_report

log = logging.getLogger("udyampulse.train_full")
TRAIN, VALID, TEST = range(4, 21), range(21, 24), range(25, 37)  # month 24 is a gap
FOLDS = 5
Y = "default_within_12m"
FULL_PARAMS = {**PARAMS, "learning_rate": 0.06, "num_leaves": 15, "max_depth": 5, "min_child_samples": 400,
               "lambda_l2": 10.0}
PRODUCTION_SIGNALS = ("eway", "kwh", "po_cover")  # e-way bills, electricity, purchase orders
N_BOOT = 1000


def load() -> pd.DataFrame:
    s = get_settings()
    feats = pd.read_parquet(s.gold / "features.parquet")
    labels = pd.read_parquet(s.gold / "labels.parquet")[["factory_id", "month", Y, "is_post_default"]]
    prof = pd.read_parquet(s.silver / "factories.parquet")[["factory_id", "sector", "cluster", "udyam_category"]]
    df = feats.merge(labels, on=["factory_id", "month"]).merge(prof, on="factory_id")
    df = df[df["is_post_default"] == 0].reset_index(drop=True)
    ids = np.sort(df["factory_id"].unique())
    fold = pd.Series(np.random.default_rng(42).integers(0, FOLDS, len(ids)), index=ids)
    df["fold"] = df["factory_id"].map(fold).to_numpy()
    return df


def fit(train: pd.DataFrame, valid: pd.DataFrame, features: list[str], params: dict | None = None,
        label: str = Y) -> tuple[lgb.Booster, Calibrator]:
    p = {**(params or FULL_PARAMS), "monotone_constraints": [MONOTONE[f] for f in features]}
    dtr = lgb.Dataset(train[features], train[label], free_raw_data=True)
    dva = lgb.Dataset(valid[features], valid[label], reference=dtr)
    b = lgb.train(p, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
    return b, Calibrator.fit(b.predict(valid[features]), valid[label].to_numpy())


def cluster_ci(y: np.ndarray, p: np.ndarray, groups: np.ndarray, n_boot: int = N_BOOT, seed: int = 7) -> dict:
    """AUC/KS/Brier with a bootstrap over factories (rows of one factory move together)."""
    from ml.evaluate import _point

    y, p = np.asarray(y, int), np.asarray(p, float)
    codes, uniq = pd.factorize(groups)
    rows_of = pd.Series(np.arange(len(y))).groupby(codes).apply(np.array).to_numpy()
    rng = np.random.default_rng(seed)
    point = _point(y, p)
    boots: dict[str, list[float]] = {k: [] for k in point}
    for _ in range(n_boot):
        pick = np.concatenate(rows_of[rng.integers(0, len(uniq), len(uniq))])
        if y[pick].min() == y[pick].max():
            continue
        for k, v in _point(y[pick], p[pick]).items():
            boots[k].append(v)
    out = {"n": int(len(y)), "positives": int(y.sum()), "event_rate": round(float(y.mean()), 4),
           "factories": int(len(uniq)), "bootstrap": f"{n_boot} resamples of factories"}
    for k, v in point.items():
        out[k] = round(v, 4)
        out[f"{k}_ci95"] = [round(float(x), 4) for x in np.percentile(boots[k], [2.5, 97.5])]
    return out


def sample_train(df: pd.DataFrame, max_rows: int = 450_000, seed: int = 1) -> pd.DataFrame:
    """Hold-out experiments train on a factory sample to keep `make train-full` within minutes."""
    if len(df) <= max_rows:
        return df
    ids = df["factory_id"].unique()
    keep = np.random.default_rng(seed).choice(ids, int(len(ids) * max_rows / len(df)), replace=False)
    return df[df["factory_id"].isin(set(keep))]


def holdout(df: pd.DataFrame, column: str, value: str, features: list[str]) -> dict:
    inside = df[column] != value
    tr = sample_train(df[inside & df.month.isin(TRAIN)])
    va = df[inside & df.month.isin(VALID)]
    te = df[~inside & df.month.isin(TEST)]
    b, cal = fit(tr, va, features)
    p = cal(b.predict(te[features]))
    return {"held_out": value, **cluster_ci(te[Y].to_numpy(), p, te["factory_id"].to_numpy(), n_boot=200)}


def leakage_audit(df: pd.DataFrame, n_factories: int = 150) -> dict:
    """Recompute features from history cut at the scoring month; any difference means look-ahead."""
    s = get_settings()
    silver = pd.read_parquet(s.silver / "factory_month.parquet")
    prof = pd.read_parquet(s.silver / "factories.parquet")
    stored = pd.read_parquet(s.gold / "features.parquet")
    ids = np.random.default_rng(3).choice(df["factory_id"].unique(), n_factories, replace=False)
    checked, mismatches = 0, []
    for fid in ids:
        hist = silver[silver.factory_id == fid].merge(
            prof[["factory_id", "sector", "n_buyers", "vintage_years", "loan_requested_inr"]], on="factory_id")
        for t in (12, 24, 30):
            cut = _factory_features(hist[hist.month <= t]).iloc[-1]
            ref = stored[(stored.factory_id == fid) & (stored.month == t)].iloc[0]
            # vintage_years is anchored to the panel's last month by design (age at the end of the panel)
            cols = [c for c in FEATURE_NAMES if c not in ("vintage_years", "kwh_vs_sector")]
            a, b = cut[cols].astype(float).to_numpy(), ref[cols].astype(float).to_numpy()
            bad = [c for c, x, y in zip(cols, a, b, strict=True) if not (np.isclose(x, y, equal_nan=True))]
            checked += 1
            if bad:
                mismatches.append({"factory_id": fid, "month": t, "features": bad[:5]})
    return {"factory_months_checked": checked, "features_checked": len(FEATURE_NAMES) - 2,
            "mismatches": mismatches[:10], "passed": not mismatches,
            "excluded_by_design": {"vintage_years": "age at the panel end, constant offset per factory",
                                   "kwh_vs_sector": "cross-sectional peer median of the same month"}}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = get_settings()
    if s.dataset == "demo":
        raise SystemExit("Run with UP_DATASET=full (or scale): the demo panel is trained by `python -m ml.train`")
    t0 = time.perf_counter()
    df = load()
    feats = FEATURE_NAMES
    log.info("training table: %s rows, %s factories, %s positives", len(df), df.factory_id.nunique(), int(df[Y].sum()))

    # ---- group + time cross-validation (headline) ----
    oof = []
    fold_metrics = []
    for k in range(FOLDS):
        tr = df[(df.fold != k) & df.month.isin(TRAIN)]
        va = df[(df.fold != k) & df.month.isin(VALID)]
        te = df[(df.fold == k) & df.month.isin(TEST)].copy()
        b, cal = fit(tr, va, feats)
        te["raw"] = b.predict(te[feats])
        te["pd_cal"] = cal(te["raw"].to_numpy())
        oof.append(te[["factory_id", "month", "sector", "cluster", "udyam_category", Y, "raw", "pd_cal"]])
        fold_metrics.append({"fold": k, "auc": round(float(roc_auc_score(te[Y], te["pd_cal"])), 4),
                             "train_auc": round(float(roc_auc_score(tr[Y], b.predict(tr[feats]))), 4),
                             "best_iteration": b.best_iteration, "test_rows": int(len(te))})
        log.info("fold %s: %s (%.0fs)", k, fold_metrics[-1], time.perf_counter() - t0)
    pooled = pd.concat(oof, ignore_index=True)
    y, p = pooled[Y].to_numpy(), pooled["pd_cal"].to_numpy()
    headline = cluster_ci(y, p, pooled["factory_id"].to_numpy())
    pooled["score"] = pd_to_score(p)
    pooled["band"] = pooled["score"].map(band_for)
    flagged = pooled["score"] < 650
    operating = {"rule": "flag when score < 650 (Watch or High risk)",
                 "precision": round(float(pooled.loc[flagged, Y].mean()), 4),
                 "recall": round(float(flagged[pooled[Y] == 1].mean()), 4),
                 "flag_rate": round(float(flagged.mean()), 4)}

    # ---- production model: all factories, months 4-20 ----
    tr, va = df[df.month.isin(TRAIN)], df[df.month.isin(VALID)]
    final, final_cal = fit(tr, va, feats)
    s.artifacts.mkdir(parents=True, exist_ok=True)
    final.save_model(str(s.artifacts / "model.txt"), num_iteration=final.best_iteration)
    (s.artifacts / "model_meta.json").write_text(json.dumps({
        "features": feats, "best_iteration": final.best_iteration, "dataset": s.dataset,
        "trained_at": datetime.now(UTC).isoformat()}, indent=2))
    contrib = final.predict(pooled.sample(20000, random_state=0).merge(df, on=["factory_id", "month"])[feats],
                            pred_contrib=True)[:, :-1]
    importance = sorted(zip(feats, np.abs(contrib).mean(axis=0), strict=True), key=lambda x: -x[1])

    # ---- generalisation ----
    sectors = [holdout(df, "sector", v, feats) for v in sorted(df.sector.unique())]
    log.info("sector hold-outs done (%.0fs)", time.perf_counter() - t0)
    clusters = [holdout(df, "cluster", v, feats) for v in sorted(df.cluster.unique())]
    log.info("cluster hold-outs done (%.0fs)", time.perf_counter() - t0)
    shock = []
    for name, months in (("before shock (month 25)", [25]), ("shock (26-30)", range(26, 31)),
                         ("recovery (31-36)", range(31, 37))):
        part = pooled[pooled.month.isin(months)]
        shock.append({"period": name, **cluster_ci(part[Y].to_numpy(), part["pd_cal"].to_numpy(),
                                                   part["factory_id"].to_numpy(), n_boot=200)})

    # ---- ablation (one group split, same test rows, paired bootstrap) ----
    no_prod = [f for f in feats if not any(k in f for k in PRODUCTION_SIGNALS)]
    tr0 = sample_train(df[(df.fold != 0) & df.month.isin(TRAIN)])
    va0 = df[(df.fold != 0) & df.month.isin(VALID)]
    te0 = df[(df.fold == 0) & df.month.isin(TEST)]
    b_all, c_all = fit(tr0, va0, feats)
    b_np, c_np = fit(tr0, va0, no_prod)
    p_all, p_np = c_all(b_all.predict(te0[feats])), c_np(b_np.predict(te0[no_prod]))
    y0 = te0[Y].to_numpy()
    rng = np.random.default_rng(9)
    codes, uniq = pd.factorize(te0["factory_id"])
    rows_of = pd.Series(np.arange(len(y0))).groupby(codes).apply(np.array).to_numpy()
    diffs = []
    for _ in range(300):
        pick = np.concatenate(rows_of[rng.integers(0, len(uniq), len(uniq))])
        if y0[pick].min() != y0[pick].max():
            diffs.append(roc_auc_score(y0[pick], p_all[pick]) - roc_auc_score(y0[pick], p_np[pick]))
    ablation = {
        "with_production_signals_auc": round(float(roc_auc_score(y0, p_all)), 4),
        "without_production_signals_auc": round(float(roc_auc_score(y0, p_np)), 4),
        "uplift_auc": round(float(np.mean(diffs)), 4), "uplift_ci95": [round(float(x), 4) for x in np.percentile(diffs, [2.5, 97.5])],
        "removed_features": [f for f in feats if f not in no_prod],
        "caveat": "On synthetic data this uplift reflects how the generator links production signals to stress. "
                  "It is a hypothesis to re-prove on a lender's consented data in a pilot, not evidence.",
    }
    log.info("ablation done (%.0fs)", time.perf_counter() - t0)

    # ---- leakage audit + shuffled labels ----
    leakage = leakage_audit(df)
    # Shuffled labels, several seeds. Unconstrained: any pipeline leak would push every run above 0.5.
    # Constrained: the monotone directions alone encode domain knowledge, so they are reported separately.
    unconstrained = {k: v for k, v in FULL_PARAMS.items() if not k.startswith("monotone")}
    noise_auc: dict[str, list[float]] = {"unconstrained": [], "monotone": []}
    for seed in range(8):
        ys = np.random.default_rng(100 + seed).permutation(tr0[Y].to_numpy())
        yv = np.random.default_rng(200 + seed).permutation(va0[Y].to_numpy())
        for name, params in (("unconstrained", unconstrained),
                             ("monotone", {**unconstrained, "monotone_constraints": [MONOTONE[f] for f in feats]})):
            b_sh = lgb.train({**params, "seed": seed}, lgb.Dataset(tr0[feats], ys), 3000,
                             valid_sets=[lgb.Dataset(va0[feats], yv)], callbacks=[lgb.early_stopping(100, verbose=False)])
            noise_auc[name].append(round(float(roc_auc_score(y0, b_sh.predict(te0[feats]))), 4))
    mean_u = float(np.mean(noise_auc["unconstrained"]))
    leakage["shuffled_label_auc"] = round(mean_u, 4)
    leakage["shuffled_label_runs"] = noise_auc["unconstrained"]
    leakage["shuffled_label_passed"] = bool(0.4 <= mean_u <= 0.6 and min(noise_auc["unconstrained"]) < 0.5)
    leakage["shuffled_label_note"] = ("8 shuffles, unconstrained model: AUCs scatter around 0.5 in both directions, "
                                      "as they must without leakage")
    leakage["domain_prior_auc"] = round(float(np.mean(noise_auc["monotone"])), 4)
    leakage["domain_prior_runs"] = noise_auc["monotone"]
    leakage["domain_prior_note"] = ("A monotone-constrained model trained on shuffled labels still ranks real defaults: "
                                    "the economic directions alone carry this much signal, like an expert scorecard")

    # ---- EWS operating point on the full panel ----
    from ml import ews

    hits = pd.read_parquet(s.gold / "ews_hits.parquet")
    truth = pd.read_parquet(s.bronze / "_truth_factory.parquet")
    points = ews.operating_points(hits, truth, s.n_months)
    eligible = [r for r in points if r["median_lead_days"] and r["median_lead_days"] >= 60 and r["recall"] >= 0.5]
    chosen = max(eligible, key=lambda r: r["precision_sma2_within_6m"]) if eligible else None

    train_rows = df[df.month.isin(TRAIN)]
    report = {
        "dataset": f"Synthetic (calibrated): {df.factory_id.nunique():,} factories x {s.n_months} months",
        "provenance": "Synthetic (calibrated)",
        "design": {"train_months": "4-20", "validation_months": "21-23 (early stopping, isotonic calibration)",
                   "gap_month": 24, "test_months": "25-36", "group_folds": FOLDS,
                   "note": "Each factory is tested by a model that never saw it or its test months."},
        "test": headline,
        "fold_auc": fold_metrics,
        "fold_auc_mean": round(float(np.mean([f["auc"] for f in fold_metrics])), 4),
        "fold_auc_sd": round(float(np.std([f["auc"] for f in fold_metrics])), 4),
        "uncalibrated_brier": round(float(np.mean((pooled["raw"] - y) ** 2)), 4),
        "expected_calibration_error": expected_calibration_error(y, p),
        "calibration": calibration_table(y, p),
        "operating_point": operating,
        "precision_at_k": precision_at_k(y, p),
        "band_default_rate": pooled.groupby("band")[Y].mean().round(4).to_dict(),
        "band_share": pooled["band"].value_counts(normalize=True).round(4).to_dict(),
        "sector_holdout": sectors, "cluster_holdout": clusters, "shock": shock,
        "ablation": ablation, "leakage_audit": leakage,
        "fairness": fairness_report(pooled.rename(columns={"pd_cal": "pd_12m"})),
        "score_psi_train_vs_test": round(psi(final.predict(sample_train(train_rows, 200_000)[feats]), pooled["raw"].to_numpy()), 4),
        "top_features_shap": [{"feature": n, "mean_abs_shap": round(float(v), 5)} for n, v in importance[:15]],
        "ews": {"operating_points": points, "chosen": chosen,
                "rule": "highest precision with median lead >= 60 days and recall >= 0.5"},
        "monotone_features": sum(1 for v in MONOTONE.values() if v),
        "runtime_seconds": round(time.perf_counter() - t0, 1),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    s.reports.mkdir(parents=True, exist_ok=True)
    (s.reports / "metrics.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    from ml.model_card import write_model_card

    write_model_card()
    t = headline
    print(json.dumps({"test_auc": t["auc"], "ci": t["auc_ci95"], "ks": t["ks"], "brier": t["brier"],
                      "folds": report["fold_auc_mean"], "ablation": ablation["uplift_auc"],
                      "leakage": leakage["passed"], "shuffled_auc": leakage["shuffled_label_auc"],
                      "ews_chosen": chosen and {k: chosen[k] for k in ("min_points", "recall", "median_lead_days",
                                                                     "precision_sma2_within_6m")},
                      "seconds": report["runtime_seconds"]}, indent=1))


if __name__ == "__main__":
    main()
