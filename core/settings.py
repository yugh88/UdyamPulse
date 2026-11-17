"""Central configuration. Every value comes from the environment (or `.env`) with a local default."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INDIA_REGIONS = {"centralindia", "southindia", "westindia", "jioindiacentral", "jioindiawest"}
# Public demo default; the production start-up guard refuses it.
DEFAULT_JWT_SECRET = "change-me-local-demo-secret-please-rotate-0001"  # nosec B105


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

    # local (demo defaults allowed) | production (refuses to start on demo secrets, SQLite or a non-India region)
    env: str = field(default_factory=lambda: _env("UP_ENV", "local").lower())
    db_url: str = field(default_factory=lambda: _env("UP_DB_URL", f"sqlite:///{ROOT / 'var' / 'udyampulse.db'}"))
    jwt_secret: str = field(default_factory=lambda: _env("UP_JWT_SECRET", DEFAULT_JWT_SECRET))
    # Access tokens are short-lived; the browser renews them with a rotating httpOnly refresh cookie.
    jwt_ttl_minutes: int = field(default_factory=lambda: int(_env("UP_JWT_TTL_MINUTES", "15")))
    refresh_ttl_hours: int = field(default_factory=lambda: int(_env("UP_REFRESH_TTL_HOURS", "12")))
    cookie_secure_raw: str = field(default_factory=lambda: _env("UP_COOKIE_SECURE", "auto"))
    # argon2id cost (RFC 9106 second recommended option by default: 3 passes, 64 MiB, 4 lanes)
    argon2_time_cost: int = field(default_factory=lambda: int(_env("UP_ARGON2_TIME_COST", "3")))
    argon2_memory_kib: int = field(default_factory=lambda: int(_env("UP_ARGON2_MEMORY_KIB", "65536")))
    argon2_parallelism: int = field(default_factory=lambda: int(_env("UP_ARGON2_PARALLELISM", "4")))
    # Fernet keys for field-level PII encryption, comma separated, newest first (older keys still decrypt).
    field_keys_raw: str = field(default_factory=lambda: _env("UP_FIELD_KEYS", ""))

    # Observability
    log_format: str = field(default_factory=lambda: _env("UP_LOG_FORMAT", "json").lower())  # json | text
    log_level: str = field(default_factory=lambda: _env("UP_LOG_LEVEL", "INFO").upper())
    otel_endpoint: str = field(default_factory=lambda: _env("UP_OTEL_ENDPOINT", ""))  # OTLP/HTTP, empty = off
    metrics_enabled: bool = field(default_factory=lambda: _env("UP_METRICS", "on").lower() not in ("0", "off", "false"))
    metrics_token: str = field(default_factory=lambda: _env("UP_METRICS_TOKEN", ""))  # if set, /metrics needs it

    # LLM resilience (only matters when a hosted LLM provider is configured)
    llm_timeout_s: float = field(default_factory=lambda: float(_env("UP_LLM_TIMEOUT_S", "20")))
    llm_concurrency_per_tenant: int = field(default_factory=lambda: int(_env("UP_LLM_CONCURRENCY_PER_TENANT", "4")))
    llm_breaker_failures: int = field(default_factory=lambda: int(_env("UP_LLM_BREAKER_FAILURES", "5")))
    llm_breaker_reset_s: float = field(default_factory=lambda: float(_env("UP_LLM_BREAKER_RESET_S", "60")))
    llm_cache_ttl_s: int = field(default_factory=lambda: int(_env("UP_LLM_CACHE_TTL_S", "86400")))

    llm_provider: str = field(default_factory=lambda: _env("UP_LLM_PROVIDER", "template"))
    search_provider: str = field(default_factory=lambda: _env("UP_SEARCH_PROVIDER", "local"))
    doc_parser: str = field(default_factory=lambda: _env("UP_DOC_PARSER", "stub"))
    consent_provider: str = field(default_factory=lambda: _env("UP_CONSENT_PROVIDER", "mock_aa"))
    lake_store: str = field(default_factory=lambda: _env("UP_LAKE_STORE", "duckdb"))
    embeddings: str = field(default_factory=lambda: _env("UP_EMBEDDINGS", "tfidf"))
    data_region: str = field(default_factory=lambda: _env("UP_DATA_REGION", "local"))
    # Redis: cache, rate limits, idempotency keys and the job queue. Empty = in-process fallbacks (lite demo).
    redis_url: str = field(default_factory=lambda: _env("UP_REDIS_URL", ""))
    cache_enabled: bool = field(default_factory=lambda: _env("UP_CACHE", "on").lower() not in ("0", "off", "false"))
    cache_ttl_seconds: int = field(default_factory=lambda: int(_env("UP_CACHE_TTL_SECONDS", "30")))
    rate_limit_user_per_min: int = field(default_factory=lambda: int(_env("UP_RATE_LIMIT_USER_PER_MIN", "600")))
    rate_limit_tenant_per_min: int = field(default_factory=lambda: int(_env("UP_RATE_LIMIT_TENANT_PER_MIN", "6000")))
    rate_limit_login_per_min: int = field(default_factory=lambda: int(_env("UP_RATE_LIMIT_LOGIN_PER_MIN", "30")))
    # Background jobs (Dramatiq). The in-process worker runs inside the API when Redis is not configured.
    inprocess_worker_raw: str = field(default_factory=lambda: _env("UP_INPROCESS_WORKER", "auto"))
    worker_threads: int = field(default_factory=lambda: int(_env("UP_WORKER_THREADS", "4")))
    job_max_retries: int = field(default_factory=lambda: int(_env("UP_JOB_MAX_RETRIES", "3")))
    job_min_backoff_ms: int = field(default_factory=lambda: int(_env("UP_JOB_MIN_BACKOFF_MS", "1000")))
    job_max_backoff_ms: int = field(default_factory=lambda: int(_env("UP_JOB_MAX_BACKOFF_MS", "60000")))
    job_time_limit_ms: int = field(default_factory=lambda: int(_env("UP_JOB_TIME_LIMIT_MS", "600000")))

    @property
    def inprocess_worker(self) -> bool:
        raw = self.inprocess_worker_raw.lower()
        return raw in ("1", "on", "true") or (raw == "auto" and not self.redis_url)

    # Demo conveniences (one-click reset). On by default only for the local, synthetic-data deployment.
    demo_mode_raw: str = field(default_factory=lambda: _env("UP_DEMO_MODE", "auto"))

    @property
    def demo_mode(self) -> bool:
        if self.demo_mode_raw.lower() in ("1", "true", "on"):
            return True
        if self.demo_mode_raw.lower() in ("0", "false", "off"):
            return False
        return self.data_region.lower() == "local" and not self.production

    @property
    def production(self) -> bool:
        return self.env in ("prod", "production")

    @property
    def cookie_secure(self) -> bool:
        raw = self.cookie_secure_raw.lower()
        if raw in ("1", "on", "true"):
            return True
        if raw in ("0", "off", "false"):
            return False
        return self.production

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
    if s.production and region not in INDIA_REGIONS:
        raise RuntimeError("Data residency violation: production needs UP_DATA_REGION set to an India region")


def production_problems(settings: Settings | None = None) -> list[str]:
    """Everything that makes this configuration unsafe for production. Empty means it may start."""
    s = settings or get_settings()
    problems = []
    if s.jwt_secret == DEFAULT_JWT_SECRET or len(s.jwt_secret) < 32:
        problems.append("UP_JWT_SECRET is the demo default or shorter than 32 characters")
    if not s.field_keys_raw:
        problems.append("UP_FIELD_KEYS is empty, so PII would be encrypted with the public demo key")
    if s.db_url.startswith("sqlite"):
        problems.append("UP_DB_URL points at SQLite; production needs PostgreSQL")
    if not s.redis_url:
        problems.append("UP_REDIS_URL is empty; production needs Redis for limits, cache and the job queue")
    if s.demo_mode_raw.lower() in ("1", "true", "on"):
        problems.append("UP_DEMO_MODE is on; demo reset must never be reachable in production")
    if not s.cookie_secure:
        problems.append("UP_COOKIE_SECURE is off; refresh cookies must be HTTPS-only")
    if s.argon2_memory_kib < 19456 or s.argon2_time_cost < 2:
        problems.append("argon2 cost is below the OWASP minimum (19 MiB, 2 passes)")
    if s.jwt_ttl_minutes > 60:
        problems.append("UP_JWT_TTL_MINUTES is above 60; access tokens must be short-lived")
    return problems


def assert_startup_safe(settings: Settings | None = None) -> None:
    """Fail fast at boot: data residency always, and the production checklist when UP_ENV=production."""
    s = settings or get_settings()
    assert_data_residency(s)
    if s.production:
        problems = production_problems(s)
        if problems:
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
