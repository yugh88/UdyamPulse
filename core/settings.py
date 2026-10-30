"""Central configuration. Every value comes from the environment (or `.env`) with a local default."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INDIA_REGIONS = {"centralindia", "southindia", "westindia", "jioindiacentral", "jioindiawest"}


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so we do not need python-dotenv. Existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(ROOT / ".env")


def _env(key: str, default: str) -> str:
    value = os.environ.get(key, "")
    return value if value else default


@dataclass(frozen=True)
class Settings:
    seed: int = field(default_factory=lambda: int(_env("UP_SEED", "42")))
    n_factories: int = field(default_factory=lambda: int(_env("UP_N_FACTORIES", "500")))
    n_months: int = 24
    # Month 1 of the synthetic panel. Month 24 = Oct 2026.
    panel_start: date = date(2024, 11, 1)
    # The demo starts with data visible up to the end of month 20 (Jun 2026).
    sim_start: date = date(2026, 6, 30)

    lake_dir: Path = field(default_factory=lambda: ROOT / _env("UP_LAKE_DIR", "lake"))
    var_dir: Path = ROOT / "var"
    ml_dir: Path = ROOT / "ml"
    policy_dir: Path = ROOT / "policy"

    db_url: str = field(default_factory=lambda: _env("UP_DB_URL", f"sqlite:///{ROOT / 'var' / 'udyampulse.db'}"))
    jwt_secret: str = field(default_factory=lambda: _env("UP_JWT_SECRET", "change-me-local-demo-secret"))
    jwt_ttl_minutes: int = field(default_factory=lambda: int(_env("UP_JWT_TTL_MINUTES", "480")))

    llm_provider: str = field(default_factory=lambda: _env("UP_LLM_PROVIDER", "template"))
    search_provider: str = field(default_factory=lambda: _env("UP_SEARCH_PROVIDER", "local"))
    doc_parser: str = field(default_factory=lambda: _env("UP_DOC_PARSER", "stub"))
    consent_provider: str = field(default_factory=lambda: _env("UP_CONSENT_PROVIDER", "mock_aa"))
    lake_store: str = field(default_factory=lambda: _env("UP_LAKE_STORE", "duckdb"))
    embeddings: str = field(default_factory=lambda: _env("UP_EMBEDDINGS", "tfidf"))
    data_region: str = field(default_factory=lambda: _env("UP_DATA_REGION", "local"))

    @property
    def bronze(self) -> Path:
        return self.lake_dir / "bronze"

    @property
    def silver(self) -> Path:
        return self.lake_dir / "silver"

    @property
    def gold(self) -> Path:
        return self.lake_dir / "gold"

    @property
    def artifacts(self) -> Path:
        return self.ml_dir / "artifacts"

    @property
    def reports(self) -> Path:
        return self.ml_dir / "reports"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def assert_data_residency(settings: Settings | None = None) -> None:
    """Refuse to start against a cloud region outside India (RBI digital lending / DPDP)."""
    s = settings or get_settings()
    region = s.data_region.lower().replace(" ", "")
    if region != "local" and region not in INDIA_REGIONS:
        raise RuntimeError(f"Data residency violation: region '{s.data_region}' is not an India region")
