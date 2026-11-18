"""Evaluation helpers shared by the product model and the real-data benchmarks, so both are judged the same way.

- `metrics_with_ci`: AUC, KS and Brier score with percentile bootstrap 95% confidence intervals
- `calibration_table`: predicted vs observed default rate by score decile
- `precision_at_k`: precision, recall and lift in the riskiest k% of accounts
- `group_metrics`: AUC per group, with a CI only where the group has enough defaults to support one
- `Calibrator`: isotonic calibration fitted on a validation split, never on the test split
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

N_BOOT = 1000
MIN_POSITIVES_FOR_CI = 30


def ks_stat(y: np.ndarray, p: np.ndarray) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def _point(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    return {"auc": float(roc_auc_score(y, p)), "ks": ks_stat(y, p), "brier": float(brier_score_loss(y, p))}


def bootstrap(y: np.ndarray, p: np.ndarray, n_boot: int = N_BOOT, seed: int = 7) -> dict[str, list[float]]:
    """Percentile bootstrap: resample accounts with replacement, recompute every metric."""
    rng = np.random.default_rng(seed)
    n = len(y)
    out: dict[str, list[float]] = {"auc": [], "ks": [], "brier": []}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yy = y[idx]
        if yy.min() == yy.max():  # a resample with one class has no AUC
            continue
        for k, v in _point(yy, p[idx]).items():
            out[k].append(v)
    return out


def metrics_with_ci(y: np.ndarray, p: np.ndarray, n_boot: int = N_BOOT, seed: int = 7) -> dict:
    y, p = np.asarray(y, int), np.asarray(p, float)
    point = _point(y, p)
    boots = bootstrap(y, p, n_boot, seed)
    out = {"n": int(len(y)), "positives": int(y.sum()), "event_rate": round(float(y.mean()), 4),
           "bootstrap_resamples": n_boot}
    for k, v in point.items():
        lo, hi = np.percentile(boots[k], [2.5, 97.5]) if boots[k] else (np.nan, np.nan)
        out[k] = round(v, 4)
        out[f"{k}_ci95"] = [round(float(lo), 4), round(float(hi), 4)]
    return out


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict]:
    """Deciles of predicted PD: mean predicted vs observed default rate."""
    y, p = np.asarray(y, int), np.asarray(p, float)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = which == b
        if m.any():
            rows.append({"bin": b + 1, "n": int(m.sum()), "mean_predicted": round(float(p[m].mean()), 4),
                         "observed": round(float(y[m].mean()), 4)})
    return rows


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    table = calibration_table(y, p, bins)
    n = sum(r["n"] for r in table)
    return round(sum(r["n"] / n * abs(r["mean_predicted"] - r["observed"]) for r in table), 4)


def precision_at_k(y: np.ndarray, p: np.ndarray, ks: tuple[float, ...] = (0.01, 0.05, 0.10, 0.20)) -> list[dict]:
    y, p = np.asarray(y, int), np.asarray(p, float)
    order = np.argsort(-p, kind="stable")
    base = y.mean()
    rows = []
    for k in ks:
        top = order[: max(1, int(round(k * len(y))))]
        prec = float(y[top].mean())
        rows.append({"top_pct": round(k * 100, 1), "n": int(len(top)), "precision": round(prec, 4),
                     "recall": round(float(y[top].sum() / max(1, y.sum())), 4),
                     "lift": round(prec / base, 2) if base else None})
    return rows


def group_metrics(y: np.ndarray, p: np.ndarray, groups: np.ndarray, min_n: int = 200, min_pos: int = 10,
                  n_boot: int = 300) -> list[dict]:
    """AUC per group. Groups too small for a meaningful AUC are reported with counts only."""
    y, p, groups = np.asarray(y, int), np.asarray(p, float), np.asarray(groups)
    rows = []
    for g in sorted(set(groups.tolist()), key=str):
        m = groups == g
        yy, pp = y[m], p[m]
        row = {"group": str(g), "n": int(m.sum()), "positives": int(yy.sum()),
               "event_rate": round(float(yy.mean()), 4) if m.any() else None}
        if m.sum() >= min_n and yy.sum() >= min_pos and yy.min() != yy.max():
            row["auc"] = round(float(roc_auc_score(yy, pp)), 4)
            if yy.sum() >= MIN_POSITIVES_FOR_CI:
                boots = bootstrap(yy, pp, n_boot, seed=11)["auc"]
                row["auc_ci95"] = [round(float(x), 4) for x in np.percentile(boots, [2.5, 97.5])]
        rows.append(row)
    return rows


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected, actual = np.asarray(expected, float), np.asarray(actual, float)
    expected, actual = expected[~np.isnan(expected)], actual[~np.isnan(actual)]
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    e = np.histogram(np.clip(expected, edges[0], edges[-1]), edges)[0] / len(expected)
    a = np.histogram(np.clip(actual, edges[0], edges[-1]), edges)[0] / len(actual)
    e, a = np.clip(e, 1e-4, None), np.clip(a, 1e-4, None)
    return float(np.sum((a - e) * np.log(a / e)))


@dataclass
class Calibrator:
    """Isotonic map from raw model output to a calibrated PD, fitted on validation data only."""

    model: IsotonicRegression

    @classmethod
    def fit(cls, p_valid: np.ndarray, y_valid: np.ndarray) -> Calibrator:
        iso = IsotonicRegression(y_min=1e-4, y_max=1 - 1e-4, out_of_bounds="clip")
        iso.fit(np.asarray(p_valid, float), np.asarray(y_valid, int))
        return cls(iso)

    def __call__(self, p: np.ndarray) -> np.ndarray:
        return self.model.predict(np.asarray(p, float))
