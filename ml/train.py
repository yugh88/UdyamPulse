"""Train the LightGBM PD model with a time-based split, report AUC/KS/Brier, fairness and drift,
log to MLflow (local file store) and write the model card.

Usage: python -m ml.train
"""

from __future__ import annotations

import json
import os
import warnings
from datetime import UTC, datetime

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

from core.settings import get_settings
from ml.features import FEATURE_NAMES, MONOTONE
from ml.scoring import BASE_SCORE, PD_AT_BASE, PDO, Scorer, band_for, pd_to_score

TRAIN_MONTHS = range(4, 13)  # fit
VALID_MONTHS = range(13, 16)  # early stopping
TEST_MONTHS = range(17, 25)  # out-of-time hold-out (month 16 left as a gap)
PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 4,
    "min_child_samples": 250,
    "extra_trees": True,
    "feature_fraction": 0.5,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 30.0,
    "verbose": -1,
    "seed": 42,
    # Audit M10: features with a clear economic direction may only move the PD that way.
    "monotone_constraints": [MONOTONE[f] for f in FEATURE_NAMES],
    # "intermediate": the "advanced" method left one feature non-monotone (tests/test_monotone.py). Chosen on
    # validation with zero violations; it also keeps the smallest train/validation gap.
    "monotone_constraints_method": "intermediate",
}


def ks_stat(y: np.ndarray, p: np.ndarray) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected, actual = expected[~np.isnan(expected)], actual[~np.isnan(actual)]
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    e = np.histogram(np.clip(expected, edges[0], edges[-1]), edges)[0] / len(expected)
    a = np.histogram(np.clip(actual, edges[0], edges[-1]), edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


def load_training_table() -> pd.DataFrame:
    s = get_settings()
    feats = pd.read_parquet(s.gold / "features.parquet")
    labels = pd.read_parquet(s.gold / "labels.parquet")
    prof = pd.read_parquet(s.silver / "factories.parquet")[["factory_id", "sector", "udyam_category"]]
    df = feats.merge(labels, on=["factory_id", "month"]).merge(prof, on="factory_id")
    return df[df["is_post_default"] == 0].reset_index(drop=True)


def evaluate(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {
        "auc": round(float(roc_auc_score(y, p)), 4),
        "ks": round(ks_stat(y, p), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "n": int(len(y)),
        "positives": int(y.sum()),
        "event_rate": round(float(y.mean()), 4),
    }


def fairness_report(test: pd.DataFrame) -> dict:
    out: dict[str, list[dict]] = {}
    for attr in ("sector", "udyam_category"):
        rows = []
        for group, g in test.groupby(attr):
            approve = g["score"] >= 650
            goods = g["default_within_12m"] == 0
            rows.append({
                "group": group,
                "n": int(len(g)),
                "default_rate": round(float(g["default_within_12m"].mean()), 4),
                "mean_score": round(float(g["score"].mean()), 1),
                "approval_rate": round(float(approve.mean()), 4),
                "approval_rate_non_defaulters": round(float(approve[goods].mean()), 4),
                "auc": round(float(roc_auc_score(g["default_within_12m"], g["pd_12m"])), 4)
                if g["default_within_12m"].nunique() > 1 else None,
            })
        best = max(r["approval_rate"] for r in rows)
        best_goods = max(r["approval_rate_non_defaulters"] for r in rows)
        for r in rows:
            r["adverse_impact_ratio"] = round(r["approval_rate"] / best, 3) if best else None
            r["equal_opportunity_ratio"] = round(r["approval_rate_non_defaulters"] / best_goods, 3)
        out[attr] = rows
    return out


def drift_report(train: pd.DataFrame, test: pd.DataFrame, top_features: list[str]) -> dict:
    report = {
        "score_psi": round(psi(train["score"].to_numpy(float), test["score"].to_numpy(float)), 4),
        "features": {f: round(psi(train[f].to_numpy(float), test[f].to_numpy(float)), 4) for f in top_features},
    }
    worst = max([report["score_psi"], *report["features"].values()])
    report["status"] = "stable" if worst < 0.1 else ("monitor" if worst < 0.25 else "investigate")
    return report


def log_to_mlflow(metrics: dict, art_dir: str) -> str | None:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")  # local file store for the offline demo
    try:
        import mlflow

        s = get_settings()
        mlflow.set_tracking_uri((s.ml_dir / "mlruns").resolve().as_uri())
        mlflow.set_experiment("udyampulse-pd")
        with mlflow.start_run(run_name="lgbm-pd-12m") as run:
            mlflow.log_params({k: v for k, v in PARAMS.items() if k not in ("verbose", "monotone_constraints")})
            mlflow.log_param("monotone_features", sum(1 for v in MONOTONE.values() if v))
            mlflow.log_params({"n_features": len(FEATURE_NAMES), "train_months": "4-12", "test_months": "17-24"})
            for split in ("train", "test"):
                for k in ("auc", "ks", "brier"):
                    mlflow.log_metric(f"{split}_{k}", metrics[split][k])
            mlflow.log_artifacts(art_dir, artifact_path="model")
            mlflow.set_tags({"model_name": "udyampulse-pd", "stage": "candidate", "owner": "risk-analytics"})
            return run.info.run_id
    except Exception as exc:  # MLflow is optional for the offline demo
        warnings.warn(f"MLflow logging skipped: {exc}", stacklevel=2)
        return None


def main() -> None:
    s = get_settings()
    df = load_training_table()
    y = "default_within_12m"
    tr = df[df.month.isin(TRAIN_MONTHS)]
    va = df[df.month.isin(VALID_MONTHS)]
    te = df[df.month.isin(TEST_MONTHS)]

    dtrain = lgb.Dataset(tr[FEATURE_NAMES], tr[y])
    dvalid = lgb.Dataset(va[FEATURE_NAMES], va[y], reference=dtrain)
    booster = lgb.train(
        PARAMS, dtrain, num_boost_round=2000, valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(150, verbose=False)],
    )

    s.artifacts.mkdir(parents=True, exist_ok=True)
    s.reports.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(s.artifacts / "model.txt"), num_iteration=booster.best_iteration)
    (s.artifacts / "model_meta.json").write_text(json.dumps({
        "features": FEATURE_NAMES,
        "best_iteration": booster.best_iteration,
        "score_scale": {"base_score": BASE_SCORE, "pd_at_base": PD_AT_BASE, "pdo": PDO},
        "trained_at": datetime.now(UTC).isoformat(),
    }, indent=2))

    scorer = Scorer(lgb.Booster(model_file=str(s.artifacts / "model.txt")), FEATURE_NAMES)
    metrics = {}
    for name, part in (("train", tr), ("valid", va), ("test", te)):
        metrics[name] = evaluate(part[y].to_numpy(), scorer.predict_pd(part))

    te = te.copy()
    te["pd_12m"] = scorer.predict_pd(te)
    te["score"] = pd_to_score(te["pd_12m"].to_numpy())
    tr = tr.copy()
    tr["score"] = pd_to_score(scorer.predict_pd(tr))

    contrib = booster.predict(te[FEATURE_NAMES], pred_contrib=True, num_iteration=booster.best_iteration)[:, :-1]
    imp = sorted(zip(FEATURE_NAMES, np.abs(contrib).mean(axis=0), strict=False), key=lambda x: -x[1])
    fairness = fairness_report(te)
    drift = drift_report(tr, te, [n for n, _ in imp[:10]])

    # Batch-score every factory-month for the portfolio cockpit (gold/scores.parquet).
    feats = pd.read_parquet(s.gold / "features.parquet")
    scorer.score_frame(feats).to_parquet(s.gold / "scores.parquet", index=False)

    hero_row = feats[(feats.factory_id == "UP-F0001") & (feats.month == 20)].iloc[0]
    hero = scorer.explain_row(hero_row).to_dict()

    band_dist = te["score"].map(band_for).value_counts(normalize=True).round(4).to_dict()
    metrics["band_distribution_test"] = band_dist
    metrics["band_default_rate_test"] = (
        te.assign(band=te["score"].map(band_for)).groupby("band")[y].mean().round(4).to_dict()
    )
    metrics["hero_month20"] = {k: hero[k] for k in ("score", "band", "pd_12m")}
    metrics["target_auc_met"] = metrics["test"]["auc"] >= 0.80

    (s.reports / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (s.reports / "fairness.json").write_text(json.dumps(fairness, indent=2))
    (s.reports / "drift.json").write_text(json.dumps(drift, indent=2))
    (s.reports / "feature_importance.json").write_text(
        json.dumps([{"feature": n, "mean_abs_shap": round(float(v), 5)} for n, v in imp], indent=2)
    )
    log_to_mlflow(metrics, str(s.artifacts))
    from ml.model_card import write_model_card

    write_model_card()

    print(f"best_iteration={booster.best_iteration}")
    for k in ("train", "valid", "test"):
        print(f"{k:>5}: {metrics[k]}")
    print("band distribution (test):", band_dist)
    print("default rate by band (test):", metrics["band_default_rate_test"])
    print(f"hero UP-F0001 @ month 20: score={hero['score']} band={hero['band']} pd={hero['pd_12m']:.4f}")
    for r in hero["reasons"]:
        print(f"   {r['points']:+6.1f}  {r['text']}")
    print("drift:", drift["status"], "score PSI", drift["score_psi"])


if __name__ == "__main__":
    main()
