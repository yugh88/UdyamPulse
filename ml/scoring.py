"""Scoring engine: PD -> Factory Health Score (300-900), bands, SHAP reasons and pillar breakdown.

Score mapping is monotonic in PD (log-odds scaling with "points to double the odds"), so the
SHAP contributions (which are additive in log-odds) translate exactly into score points.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache

import lightgbm as lgb
import numpy as np
import pandas as pd

from core.settings import get_settings
from ml.features import FEATURES, PILLARS, describe

SCORE_MIN, SCORE_MAX = 300, 900
# Anchor: a 3.5% 12-month PD maps to 650 (approve cut-off); every halving of the odds adds 30 points.
BASE_SCORE, PD_AT_BASE, PDO = 650.0, 0.035, 30.0
FACTOR = PDO / math.log(2)
Z0 = math.log(PD_AT_BASE / (1 - PD_AT_BASE))

BANDS = [(650, "APPROVE"), (550, "WATCH"), (300, "HIGH_RISK")]


def pd_to_score(pd_: np.ndarray | float) -> np.ndarray | float:
    p = np.clip(pd_, 1e-6, 1 - 1e-6)
    z = np.log(p / (1 - p))
    return np.clip(np.round(BASE_SCORE - FACTOR * (z - Z0)), SCORE_MIN, SCORE_MAX)


def band_for(score: float) -> str:
    for cut, name in BANDS:
        if score >= cut:
            return name
    return "HIGH_RISK"


@dataclass
class Reason:
    feature: str
    pillar: str
    text: str
    value: float | None
    points: float  # score points contributed (+ helps, - hurts)
    direction: str  # "risk_up" | "risk_down"


@dataclass
class ScoreResult:
    factory_id: str
    month: int
    pd_12m: float
    score: int
    band: str
    reasons: list[Reason]
    pillars: list[dict]
    base_points: float
    features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "factory_id": self.factory_id,
            "month": self.month,
            "pd_12m": round(self.pd_12m, 4),
            "score": self.score,
            "band": self.band,
            "reasons": [r.__dict__ for r in self.reasons],
            "pillars": self.pillars,
            "base_points": round(self.base_points, 1),
        }


class Scorer:
    def __init__(self, booster: lgb.Booster, feature_names: list[str]) -> None:
        self.booster = booster
        self.feature_names = feature_names

    @classmethod
    def load(cls) -> Scorer:
        art = get_settings().artifacts
        booster = lgb.Booster(model_file=str(art / "model.txt"))
        meta = json.loads((art / "model_meta.json").read_text())
        return cls(booster, meta["features"])

    def predict_pd(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(X[self.feature_names])

    def score_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        pd_ = self.predict_pd(df)
        scores = pd_to_score(pd_)
        return pd.DataFrame({
            "factory_id": df["factory_id"].values,
            "month": df["month"].values,
            "pd_12m": pd_,
            "score": scores.astype(int),
            "band": [band_for(s) for s in scores],
        })

    def explain_row(self, row: pd.Series, top_k: int = 5) -> ScoreResult:
        X = row[self.feature_names].to_frame().T.astype(float)
        contrib = self.booster.predict(X, pred_contrib=True)[0]
        shap_vals, bias = contrib[:-1], contrib[-1]
        z = float(shap_vals.sum() + bias)
        pd_ = 1 / (1 + math.exp(-z))
        score = int(pd_to_score(pd_))
        points = -FACTOR * shap_vals

        order = np.argsort(-np.abs(shap_vals))[:top_k]
        reasons = []
        for i in order:
            name = self.feature_names[i]
            val = X.iloc[0, i]
            val = None if pd.isna(val) else float(val)
            reasons.append(Reason(
                feature=name,
                pillar=FEATURES[name].pillar,
                text=describe(name, val) if val is not None else f"{name} unavailable",
                value=val,
                points=round(float(points[i]), 1),
                direction="risk_up" if shap_vals[i] > 0 else "risk_down",
            ))

        pillars = []
        for key, meta in PILLARS.items():
            idx = [i for i, n in enumerate(self.feature_names) if FEATURES[n].pillar == key]
            s = float(shap_vals[idx].sum())
            pillars.append({
                "pillar": key,
                "label": meta["label"],
                "prior_weight": meta["weight"],
                "points": round(-FACTOR * s, 1),
                "health": round(100 / (1 + math.exp(s * 2)), 0),
            })
        return ScoreResult(
            factory_id=str(row["factory_id"]),
            month=int(row["month"]),
            pd_12m=pd_,
            score=score,
            band=band_for(score),
            reasons=reasons,
            pillars=pillars,
            base_points=BASE_SCORE - FACTOR * (bias - Z0),
            features={n: (None if pd.isna(row[n]) else float(row[n])) for n in self.feature_names},
        )


@lru_cache
def get_scorer() -> Scorer:
    return Scorer.load()
