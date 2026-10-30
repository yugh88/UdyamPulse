"""3-month cash-flow forecast per factory (Prophet), used by the MSME advisor agent.

Falls back to a seasonal-naive + damped-trend forecast if Prophet is unavailable or fails, so the
offline demo never breaks.
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd

from core.timeline import month_start

logging.getLogger("cmdstanpy").disabled = True
logging.getLogger("prophet").setLevel(logging.ERROR)


def _history_frame(history: pd.DataFrame) -> pd.DataFrame:
    h = history.sort_values("month")
    return pd.DataFrame({
        "ds": [pd.Timestamp(month_start(int(m))) for m in h["month"]],
        "y": (h["aa_credits"] - h["aa_debits"]).astype(float).to_numpy(),
        "credits": h["aa_credits"].astype(float).to_numpy(),
    }).dropna()


def _fallback(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    y = df["y"].to_numpy()
    recent = y[-3:].mean() if len(y) >= 3 else y.mean()
    trend = (y[-3:].mean() - y[-6:-3].mean()) / 3 if len(y) >= 6 else 0.0
    sigma = float(np.std(y[-12:])) if len(y) >= 4 else abs(recent) * 0.2
    rows = []
    for k in range(1, periods + 1):
        yhat = recent + trend * k * 0.7**k
        rows.append({"yhat": yhat, "yhat_lower": yhat - 1.28 * sigma, "yhat_upper": yhat + 1.28 * sigma})
    return pd.DataFrame(rows)


def forecast_cashflow(history: pd.DataFrame, periods: int = 3) -> dict:
    """Forecast monthly net cash inflow (AA credits - debits). `history` needs month, aa_credits, aa_debits."""
    df = _history_frame(history)
    last = df["ds"].max()
    future_ds = [last + pd.DateOffset(months=k) for k in range(1, periods + 1)]
    method = "prophet"
    try:
        from prophet import Prophet

        logging.getLogger("cmdstanpy").disabled = True
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # < 3 years of monthly points: yearly seasonality overfits, so keep trend + changepoints only.
            m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False,
                        interval_width=0.8, changepoint_prior_scale=0.5, n_changepoints=min(8, len(df) // 3))
            m.fit(df[["ds", "y"]])
            fc = m.predict(pd.DataFrame({"ds": future_ds}))[["yhat", "yhat_lower", "yhat_upper"]]
    except Exception:
        method = "seasonal_naive_fallback"
        fc = _fallback(df, periods)

    points = [
        {"month": ds.strftime("%Y-%m"), "yhat": round(float(r.yhat)), "lo": round(float(r.yhat_lower)),
         "hi": round(float(r.yhat_upper))}
        for ds, r in zip(future_ds, fc.itertuples(), strict=False)
    ]
    hist = [{"month": d.strftime("%Y-%m"), "actual": round(float(v))} for d, v in zip(df["ds"], df["y"], strict=False)]
    negative = [p["month"] for p in points if p["yhat"] < 0]
    return {"method": method, "history": hist, "forecast": points, "negative_months": negative,
            "avg_monthly_credits": round(float(df["credits"].tail(3).mean()))}
