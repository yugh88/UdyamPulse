"""UdyamPulse API (FastAPI). Run: uvicorn api.main:app --reload

Business endpoints are versioned under `/v1`. Health probes live at the root:
`/healthz` (liveness: the process is up) and `/readyz` (readiness: dependencies answer)."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api import problems
from api.models.db import get_engine, init_db
from api.request_context import RequestIdMiddleware
from api.routers import applications, auth, governance, insights, msme, portfolio
from core.settings import assert_data_residency, get_settings

API_VERSION = "v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    assert_data_residency()
    init_db()
    yield


app = FastAPI(
    title="UdyamPulse API",
    version="1.0.0",
    description="Decision intelligence for MSME manufacturing credit: consented operating data → explainable "
                "Factory Health Score → credit memo → human decision → continuous early warning. "
                "All AI outputs are recommendations; the credit officer decides. "
                "Errors use RFC 9457 problem details (`application/problem+json`).",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
app.add_middleware(RequestIdMiddleware)
problems.install(app)

v1 = APIRouter(prefix=f"/{API_VERSION}")
for r in (auth.router, applications.router, insights.router, portfolio.router, msme.router, governance.router):
    v1.include_router(r)
app.include_router(v1)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    """Liveness: the process is running. Checks no dependency, so a slow database never restarts the pod."""
    return {"status": "ok"}


def _check(fn) -> dict:
    t0 = time.perf_counter()
    try:
        detail = fn()
        return {"ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1), **(detail or {})}
    except Exception as exc:  # a failed dependency is reported, never raised
        return {"ok": False, "ms": round((time.perf_counter() - t0) * 1000, 1), "error": type(exc).__name__}


def _db() -> dict:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"dialect": get_engine().dialect.name}


def _model() -> dict:
    s = get_settings()
    if not (s.artifacts / "model.txt").exists():
        raise FileNotFoundError("model artifact")
    return {}


def _lake() -> dict:
    s = get_settings()
    if not (s.gold / "scores.parquet").exists():
        raise FileNotFoundError("gold layer")
    return {}


@app.get("/readyz", tags=["meta"])
def readyz(response: Response) -> dict:
    """Readiness: database, model artifact and lake are reachable. 503 takes the pod out of rotation."""
    checks = {"database": _check(_db), "model": _check(_model), "lake": _check(_lake)}
    ready = all(c["ok"] for c in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not_ready", "version": app.version, "checks": checks}


@app.get("/health", tags=["meta"], include_in_schema=False)
def health() -> dict:
    return {"status": "ok"}
