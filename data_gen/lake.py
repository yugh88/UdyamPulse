"""Medallion build: bronze (raw per-source events) -> silver (deduped, reconciled factory-month table).

Silver is built with DuckDB SQL; gaps are then forward-filled in Python (limit 1 month) and flagged.
Gold features are built by `ml.features.build_gold`.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from core.settings import get_settings
from data_gen.generate import SOURCE_COLUMNS

SIGNAL_COLUMNS = [c for cols in SOURCE_COLUMNS.values() for c in cols]


def _dedupe_sql(source: str) -> str:
    cols = ", ".join(SOURCE_COLUMNS[source])
    return f"""
        {source}_dedup AS (
            SELECT factory_id, month, {cols}
            FROM read_parquet('{{bronze}}/{source}.parquet')
            QUALIFY row_number() OVER (PARTITION BY factory_id, month ORDER BY _ingested_at DESC) = 1
        )"""


def build_silver() -> pd.DataFrame:
    s = get_settings()
    bronze = s.bronze.as_posix()
    ctes = ",".join(_dedupe_sql(src).replace("{bronze}", bronze) for src in SOURCE_COLUMNS)
    joins = "\n".join(
        f"LEFT JOIN {src}_dedup USING (factory_id, month)" for src in SOURCE_COLUMNS
    )
    # USING-joins drop the right-side key, so detect missing sources via each source's first column.
    missing_expr = " + ".join(
        f"CASE WHEN {SOURCE_COLUMNS[src][0]} IS NULL THEN 1 ELSE 0 END" for src in SOURCE_COLUMNS
    )
    sql = f"""
        WITH {ctes},
        spine AS (
            SELECT f.factory_id, m.month
            FROM read_parquet('{bronze}/factories.parquet') f
            CROSS JOIN range(1, {s.n_months + 1}) m(month)
        )
        SELECT spine.factory_id, spine.month,
               {", ".join(SIGNAL_COLUMNS)},
               {missing_expr} AS dq_missing_sources
        FROM spine
        {joins}
        ORDER BY factory_id, month
    """
    con = duckdb.connect()
    df = con.execute(sql).df()

    # Forward-fill single-month gaps per factory; keep the missing-source flag for data-quality features.
    df[SIGNAL_COLUMNS] = df.groupby("factory_id")[SIGNAL_COLUMNS].ffill(limit=1)
    df[SIGNAL_COLUMNS] = df.groupby("factory_id")[SIGNAL_COLUMNS].bfill(limit=1)

    # Reconciliation: bank credits (incl. ~12% GST, ~1.5 month collection lag) vs declared GST turnover.
    df = df.sort_values(["factory_id", "month"]).reset_index(drop=True)
    g = df.groupby("factory_id")
    bank_3 = g["aa_credits"].transform(lambda x: x.rolling(3, min_periods=2).mean()) / 1.12
    gst_lag_3 = g["gst_turnover"].transform(lambda x: x.shift(1).rolling(3, min_periods=2).mean())
    df["gst_bank_mismatch"] = ((bank_3 - gst_lag_3).abs() / gst_lag_3).fillna(0.0)
    df["einv_eway_gap"] = (1 - df["eway_value"] / df["einvoice_value"]).clip(-1, 1)

    con.register("silver_df", df)
    s.silver.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY silver_df TO '{(s.silver / 'factory_month.parquet').as_posix()}' (FORMAT parquet)")
    con.execute(
        f"COPY (SELECT * FROM read_parquet('{bronze}/factories.parquet')) "
        f"TO '{(s.silver / 'factories.parquet').as_posix()}' (FORMAT parquet)"
    )
    con.close()
    return df


def main() -> None:
    from ml.features import build_gold

    silver = build_silver()
    print(f"silver: {len(silver)} factory-months, {int((silver.dq_missing_sources > 0).sum())} with gaps")
    gold = build_gold()
    n_feats = len([c for c in gold.columns if c not in ("factory_id", "month")])
    print(f"gold: {len(gold)} rows x {n_feats} features")


if __name__ == "__main__":
    main()
