"""Early-Warning System: configurable rules (rules.yaml) + IsolationForest anomaly detection,
severity, next-best action, and a lead-time back-test against SMA-2.

Usage: python -m ml.ews   (fits the anomaly model, scores every factory-month, writes the back-test)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import IsolationForest

from core.settings import get_settings
from core.timeline import month_end

RULES_PATH = Path(__file__).with_name("rules.yaml")
DELTA_COLS = ["eway_value", "einvoice_value", "kwh", "aa_credits", "avg_balance", "rm_purchases", "epfo_headcount"]
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}


@lru_cache
def load_rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text())


@dataclass
class EwsResult:
    factory_id: str
    month: int
    rules: list[str]
    reasons: list[str]
    anomaly: bool
    severity: str | None
    next_best_action: str | None


def rule_inputs(silver: pd.DataFrame) -> pd.DataFrame:
    """Per factory-month inputs for the rules, using only current and past months."""
    cfg = load_rules()
    b = cfg["baseline_months"]
    df = silver.sort_values(["factory_id", "month"]).copy()
    g = df.groupby("factory_id")

    def base(col: str, w: int) -> pd.Series:
        prev = g[col].shift(1)
        return (prev.groupby(df["factory_id"]).rolling(w, min_periods=1).mean()
                .reset_index(level=0, drop=True).reindex(df.index))

    out = df[["factory_id", "month"]].copy()
    out["eway_chg"] = df["eway_value"] / base("eway_value", b) - 1
    out["kwh_chg"] = df["kwh"] / base("kwh", b) - 1
    out["bounces"] = df["bounces"]
    out["balance_chg_30d"] = df["avg_balance"] / g["avg_balance"].shift(1) - 1
    out["top_buyer_share"] = df["top_buyer_share"]
    out["dtp_increase"] = df["avg_days_to_pay"] - base("avg_days_to_pay", 3)
    out["gst_bank_mismatch"] = df["gst_bank_mismatch"]
    late = (df["gst_filing_delay_days"] > 0).astype(int)
    out["consecutive_late"] = late.groupby([df["factory_id"], (late == 0).cumsum()]).cumsum()
    for c in DELTA_COLS:
        out[f"d_{c}"] = g[c].pct_change(fill_method=None)
    out["d_bounces"] = g["bounces"].diff()
    out["d_dtp"] = g["avg_days_to_pay"].diff()
    return out.replace([np.inf, -np.inf], np.nan)


def delta_matrix(inputs: pd.DataFrame) -> pd.DataFrame:
    cols = [f"d_{c}" for c in DELTA_COLS] + ["d_bounces", "d_dtp"]
    return inputs[cols].fillna(0.0).clip(-3, 3)


def fit_anomaly(inputs: pd.DataFrame, train_months: range = range(2, 13)) -> IsolationForest:
    cfg = load_rules()["anomaly"]
    X = delta_matrix(inputs[inputs.month.isin(train_months)])
    model = IsolationForest(n_estimators=200, contamination=cfg["contamination"], random_state=42)
    model.fit(X)
    return model


def _fmt_pct(x: float) -> str:
    return f"{'↓' if x < 0 else '↑'}{abs(x) * 100:.0f}%"


def evaluate(inputs: pd.DataFrame, anomaly_model: IsolationForest | None) -> pd.DataFrame:
    """Vectorised rule evaluation for every row of `inputs`."""
    cfg = load_rules()
    r = cfg["rules"]
    res = inputs[["factory_id", "month"]].copy()
    res["order_loss"] = (inputs.eway_chg <= -r["order_loss"]["eway_drop"]) & (inputs.kwh_chg <= -r["order_loss"]["kwh_drop"])
    res["cash_squeeze"] = (inputs.bounces >= r["cash_squeeze"]["bounces_min"]) | (
        inputs.balance_chg_30d <= -r["cash_squeeze"]["balance_drop"]
    )
    res["buyer_risk"] = (inputs.top_buyer_share > r["buyer_risk"]["top_share_min"]) & (
        inputs.dtp_increase >= r["buyer_risk"]["dtp_increase_days"]
    )
    res["diversion"] = inputs.gst_bank_mismatch > r["diversion"]["mismatch_min"]
    res["compliance_slip"] = inputs.consecutive_late >= r["compliance_slip"]["consecutive_late"]
    res["anomaly"] = (
        anomaly_model.predict(delta_matrix(inputs)) == -1 if anomaly_model is not None else False
    )
    weights = {k: v["weight"] for k, v in r.items()} | {"anomaly": cfg["anomaly"]["weight"]}
    res["severity_points"] = sum(res[k].astype(int) * w for k, w in weights.items())
    sev = cfg["severity"]
    labels = np.select(
        [res.severity_points >= sev["high"], res.severity_points >= sev["medium"], res.severity_points >= sev["low"]],
        ["high", "medium", "low"],
        default="",
    )
    res["severity"] = pd.Series(labels, index=res.index, dtype=object).replace("", None)
    return res.join(inputs.drop(columns=["factory_id", "month"]))


def next_best_action(row: pd.Series) -> str | None:
    if not isinstance(row.get("severity"), str):
        return None
    if row["severity"] == "high" and row["order_loss"]:
        return "visit + limit review"
    if row["cash_squeeze"] and row.get("bounces", 0) >= 3:
        return "restructure"
    if row["severity"] == "high":
        return "visit + limit review" if row["diversion"] else "visit"
    if row["diversion"]:
        return "visit"
    if row["severity"] == "medium":
        return "visit" if row["cash_squeeze"] else "call"
    return "call"


def next_best_actions(hits: pd.DataFrame) -> pd.Series:
    """Vectorised `next_best_action` for a whole frame (same rules, same order)."""
    sev = hits["severity"]
    has = sev.map(lambda x: isinstance(x, str)).to_numpy()
    high, medium = (sev == "high").to_numpy(), (sev == "medium").to_numpy()
    ol, cs, dv = hits["order_loss"].to_numpy(bool), hits["cash_squeeze"].to_numpy(bool), hits["diversion"].to_numpy(bool)
    b3 = (hits["bounces"].fillna(0) >= 3).to_numpy()
    out = np.select(
        [~has, high & ol, cs & b3, high & dv, high, dv, medium & cs, medium],
        [None, "visit + limit review", "restructure", "visit + limit review", "visit", "visit", "visit", "call"],
        default="call")
    return pd.Series(out, index=hits.index, dtype=object)


def explain(row: pd.Series) -> list[str]:
    r = load_rules()["rules"]
    out = []
    if row["order_loss"]:
        out.append(f"Order loss: e-way bills {_fmt_pct(row.eway_chg)} and kWh {_fmt_pct(row.kwh_chg)} vs 8-week baseline")
    if row["cash_squeeze"]:
        parts = []
        if row.bounces >= r["cash_squeeze"]["bounces_min"]:
            parts.append(f"{int(row.bounces)} cheque/NACH bounces")
        if pd.notna(row.balance_chg_30d) and row.balance_chg_30d <= -r["cash_squeeze"]["balance_drop"]:
            parts.append(f"average balance {_fmt_pct(row.balance_chg_30d)} in 30 days")
        out.append("Cash squeeze: " + " and ".join(parts))
    if row["buyer_risk"]:
        out.append(f"Buyer risk: top buyer at {row.top_buyer_share * 100:.0f}% of sales, days-to-pay +{row.dtp_increase:.0f} days")
    if row["diversion"]:
        out.append(f"Possible diversion: GST turnover vs bank credits mismatch {row.gst_bank_mismatch * 100:.0f}%")
    if row["compliance_slip"]:
        out.append(f"Compliance slip: GSTR-3B late {int(row.consecutive_late)} months in a row")
    if row["anomaly"]:
        out.append("Unusual month-over-month pattern across signals (anomaly model)")
    return out


def to_result(row: pd.Series) -> EwsResult:
    rules = [k for k in ("order_loss", "cash_squeeze", "buyer_risk", "diversion", "compliance_slip") if row[k]]
    return EwsResult(
        factory_id=row.factory_id, month=int(row.month), rules=rules, reasons=explain(row),
        anomaly=bool(row["anomaly"]), severity=row["severity"], next_best_action=next_best_action(row),
    )


def backtest(hits: pd.DataFrame, truth: pd.DataFrame, n_months: int, min_severity: str | None = None,
             min_points: int | None = None) -> dict:
    """Lead time, recall and precision of the alerts against SMA-2 events. Vectorised (joins, no row loops),
    so it runs on the 50,000-factory panel. `min_points` overrides the severity cut for operating-point sweeps."""
    cfg = load_rules()["backtest"]
    lookback, horizon = cfg["lookback_months"], cfg["precision_horizon_months"]
    min_sev = min_severity or cfg["min_severity"]
    if min_points is not None:
        alerts = hits[hits.severity_points >= min_points][["factory_id", "month"]]
    else:
        alerts = hits[hits.severity.map(lambda x: SEVERITY_ORDER.get(x, 0)) >= SEVERITY_ORDER[min_sev]][["factory_id", "month"]]

    sma2 = truth[truth.sma2_month.notna() & (truth.sma2_month <= n_months)][["factory_id", "sma2_month"]]
    j = alerts.merge(sma2, on="factory_id")
    j = j[(j.month < j.sma2_month) & (j.month >= j.sma2_month - lookback)]
    first = j.groupby("factory_id").agg(first=("month", "min"), s2=("sma2_month", "first")).reset_index()
    ends = {m: month_end(m) for m in range(0, n_months + lookback + 2)}
    first["lead"] = [(ends[int(s2)] - ends[int(f)]).days for f, s2 in zip(first["first"], first["s2"], strict=True)]
    leads = first.loc[first["lead"] >= 30, "lead"].to_numpy()

    fa = alerts[alerts.month <= n_months - horizon].groupby("factory_id").month.min().rename("m").reset_index()
    fa = fa.merge(truth[["factory_id", "sma2_month", "stress_month"]], on="factory_id", how="left")
    tp = int(((fa.sma2_month > fa.m) & (fa.sma2_month <= fa.m + horizon)).sum())
    tp_stress = int(((fa.m >= fa.stress_month - 5) & (fa.m <= fa.stress_month + 6)).sum())
    n_alerted = len(fa)
    detected = len(leads)
    return {
        "sma2_events_in_window": int(len(sma2)),
        "detected_30d_ahead": detected,
        "recall": round(detected / len(sma2), 3) if len(sma2) else None,
        "median_lead_days": float(np.median(leads)) if detected else None,
        "mean_lead_days": round(float(np.mean(leads)), 1) if detected else None,
        "p25_lead_days": float(np.percentile(leads, 25)) if detected else None,
        "alerted_accounts": n_alerted,
        "precision_sma2_within_6m": round(tp / n_alerted, 3) if n_alerted else None,
        "precision_true_stress": round(tp_stress / n_alerted, 3) if n_alerted else None,
        "alert_rate_per_account_month": round(len(alerts) / len(hits), 4),
        "min_severity": min_sev if min_points is None else f"points>={min_points}",
        "target_median_lead_days_met": bool(detected and np.median(leads) >= 60),
    }


def operating_points(hits: pd.DataFrame, truth: pd.DataFrame, n_months: int) -> list[dict]:
    """The precision / recall / lead-time trade-off for every severity cut."""
    max_pts = int(hits.severity_points.max()) if len(hits) else 1
    return [{"min_points": k, **backtest(hits, truth, n_months, min_points=k)} for k in range(1, max_pts + 1)]


def main() -> None:
    s = get_settings()
    silver = pd.read_parquet(s.silver / "factory_month.parquet")
    truth = pd.read_parquet(s.bronze / "_truth_factory.parquet")
    labels = pd.read_parquet(s.gold / "labels.parquet")

    inputs = rule_inputs(silver)
    model = fit_anomaly(inputs)
    s.artifacts.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, s.artifacts / "ews_iforest.joblib")

    hits = evaluate(inputs, model)
    hits = hits.merge(labels[["factory_id", "month", "is_post_default"]], on=["factory_id", "month"])
    hits = hits[(hits.is_post_default == 0) & (hits.month >= 3)].drop(columns="is_post_default")
    hits["next_best_action"] = next_best_actions(hits)
    hits.to_parquet(s.gold / "ews_hits.parquet", index=False)

    report = backtest(hits, truth, s.n_months)
    hero = hits[(hits.factory_id == "UP-F0001") & hits.month.between(19, 23)]
    report["hero_alerts"] = [
        {"month": int(r.month), "severity": r.severity, "rules": to_result(r).rules,
         "action": r.next_best_action if isinstance(r.next_best_action, str) else None}
        for _, r in hero.iterrows()
    ]
    s.reports.mkdir(parents=True, exist_ok=True)
    (s.reports / "ews_backtest.json").write_text(json.dumps(report, indent=2))
    md = ["# EWS back-test", "", "| Metric | Value |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in report.items() if k != "hero_alerts"]
    md += ["", "## Hero factory (UP-F0001)", "", "| Month | Severity | Rules | Action |", "|---|---|---|---|"]
    md += [f"| {h['month']} | {h['severity']} | {', '.join(h['rules']) or '–'} | {h['action'] or '–'} |" for h in report["hero_alerts"]]
    (s.reports / "ews_backtest.md").write_text("\n".join(md) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
