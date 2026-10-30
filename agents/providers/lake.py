"""LakeStore adapters: DuckDB over local Parquet (default) and an Azure Databricks stub."""

from __future__ import annotations

from functools import lru_cache

import duckdb
import pandas as pd

from core.settings import get_settings


class DuckDBLakeStore:
    """Reads the medallion layers with DuckDB; tables are small so results are cached in memory."""

    def __init__(self) -> None:
        s = get_settings()
        con = duckdb.connect()

        def q(path: str) -> pd.DataFrame:
            return con.execute(f"SELECT * FROM read_parquet('{path}')").df()

        self._profiles = q((s.silver / "factories.parquet").as_posix()).set_index("factory_id", drop=False)
        self._silver = q((s.silver / "factory_month.parquet").as_posix())
        self._gold = q((s.gold / "features.parquet").as_posix())
        self._scores = q((s.gold / "scores.parquet").as_posix())
        self._ews = q((s.gold / "ews_hits.parquet").as_posix())
        con.close()

    def profile(self, factory_id: str) -> dict:
        if factory_id not in self._profiles.index:
            raise KeyError(factory_id)
        return self._profiles.loc[factory_id].to_dict()

    def profiles(self) -> pd.DataFrame:
        return self._profiles.reset_index(drop=True)

    def history(self, factory_id: str, upto_month: int) -> pd.DataFrame:
        df = self._silver
        return df[(df.factory_id == factory_id) & (df.month <= upto_month)].sort_values("month")

    def features(self, factory_id: str, month: int) -> pd.Series:
        df = self._gold
        rows = df[(df.factory_id == factory_id) & (df.month == month)]
        if rows.empty:
            raise KeyError(f"{factory_id}@{month}")
        return rows.iloc[0]

    def scores(self, upto_month: int) -> pd.DataFrame:
        return self._scores[self._scores.month <= upto_month]

    def ews_hits(self, factory_id: str, months: list[int]) -> pd.DataFrame:
        df = self._ews
        return df[(df.factory_id == factory_id) & (df.month.isin(months))].sort_values("month")


class DatabricksLakeStore:  # pragma: no cover - production adapter
    """Azure Databricks + Delta Lake + Unity Catalog. Same contract; queries the gold schema via
    `databricks-sql-connector` using a service principal from Key Vault."""

    def __init__(self) -> None:
        raise NotImplementedError("Set UP_LAKE_STORE=duckdb for the local prototype")


@lru_cache
def get_lake() -> DuckDBLakeStore:
    if get_settings().lake_store == "databricks":
        return DatabricksLakeStore()  # type: ignore[return-value]
    return DuckDBLakeStore()
