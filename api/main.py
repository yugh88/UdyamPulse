"""UdyamPulse API (FastAPI). Run: uvicorn api.main:app --reload"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agents.orchestrator import InvalidTransition
from agents.providers.consent import ConsentError
from api.models.db import init_db
from api.routers import applications, auth, governance, msme, portfolio
from core.settings import assert_data_residency


@asynccontextmanager
async def lifespan(_: FastAPI):
    assert_data_residency()
    init_db()
    yield


app = FastAPI(
    title="UdyamPulse API",
    version="0.1.0",
    description="Decision intelligence for MSME manufacturing credit: consented operating data → explainable "
                "Factory Health Score → credit memo → human decision → continuous early warning. "
                "All AI outputs are recommendations; the credit officer decides.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConsentError)
async def consent_error(_: Request, exc: ConsentError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc), "code": "CONSENT_REQUIRED"})


@app.exception_handler(InvalidTransition)
async def invalid_transition(_: Request, exc: InvalidTransition) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc), "code": "INVALID_STATE"})


@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


for r in (auth.router, applications.router, portfolio.router, msme.router, governance.router):
    app.include_router(r)
