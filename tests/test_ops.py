"""Ops and security basics: security headers, metrics, structured logs, tracing, production start-up guard."""

from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest

from core.settings import DEFAULT_JWT_SECRET, assert_startup_safe, get_settings, production_problems
from tests.conftest import hero_app_id, login, wait_job


def test_security_headers_on_api_responses(client):
    r = client.get("/applications", headers=login(client, "rm1"))
    h = r.headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["referrer-policy"] == "no-referrer"
    assert h["cache-control"] == "no-store"  # credit data never cached
    assert "strict-transport-security" not in h  # plain HTTP: HSTS would be ignored and pin localhost


def test_hsts_only_over_https(client):
    r = client.get("http://testserver/healthz", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"].startswith("max-age=31536000")


def test_problem_responses_carry_headers_too(client):
    r = client.get("/applications")
    assert r.status_code == 401
    assert r.headers["x-content-type-options"] == "nosniff"


def test_metrics_endpoint_exposes_red_and_queue_metrics(client):
    rm = login(client, "rm1")
    client.get("/applications", headers=rm)
    body = client.get("http://testserver/metrics").text
    assert 'udyam_http_requests_total{method="GET",route="/v1/applications",status="200"}' in body
    assert "udyam_http_request_duration_seconds_bucket" in body
    assert 'udyam_job_queue_depth{status="queued"}' in body
    assert "udyam_outbox_pending" in body
    # Route templates, never raw ids: no label explosion.
    app_id = hero_app_id(client, rm)
    client.get(f"/applications/{app_id}", headers=rm)
    body = client.get("http://testserver/metrics").text
    assert 'route="/v1/applications/{app_id}"' in body
    assert f'route="/v1/applications/{app_id}"' not in body


def test_metrics_token(client, monkeypatch):
    import api.main as main

    s = replace(get_settings(), metrics_token="scrape-secret")
    monkeypatch.setattr(main, "get_settings", lambda: s)
    assert client.get("http://testserver/metrics").status_code == 401
    assert client.get("http://testserver/metrics", headers={"Authorization": "Bearer scrape-secret"}).status_code == 200


def test_json_logs_mask_pii_and_carry_request_id():
    from api.request_context import _request_id
    from core.logs import JsonFormatter, set_log_tenant

    token = _request_id.set("req-12345678")
    set_log_tenant("bank-a")
    try:
        record = logging.LogRecord("udyampulse.test", logging.INFO, __file__, 1,
                                   "owner phone 9876543210 mailed a@b.in with PAN ABCDE1234F", None, None)
        record.display_name = "Ramesh Sharma"
        record.password = "demo123"
        line = json.loads(JsonFormatter().format(record))
    finally:
        _request_id.reset(token)
        set_log_tenant(None)
    assert line["request_id"] == "req-12345678" and line["tenant"] == "bank-a"
    assert "9876543210" not in line["msg"] and "a@b.in" not in line["msg"] and "ABCDE1234F" not in line["msg"]
    assert line["display_name"] == "Ra***" and line["password"] == "***"


def test_access_log_line_is_structured(client, caplog):
    rm = login(client, "rm1")
    with caplog.at_level(logging.INFO, logger="udyampulse.access"):
        client.get("/applications", headers={**rm, "X-Request-ID": "trace-me-1234"})
    rec = next(r for r in caplog.records if r.name == "udyampulse.access" and getattr(r, "route", "") == "/v1/applications")
    assert rec.status == 200 and rec.duration_ms >= 0


@pytest.fixture(scope="module")
def spans():
    """Export spans to memory. The global tracer provider can be set once per process, so share it."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        current.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    return exporter


def test_trace_continues_from_request_into_background_job(client, spans):
    rm = login(client, "rm1")
    app_id = hero_app_id(client, rm)
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    spans.clear()
    r = client.post(f"/applications/{app_id}/score", headers={
        **rm, "Prefer": "respond-async", "traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"})
    assert r.status_code == 202
    assert r.headers["traceparent"].split("-")[1] == trace_id  # echoed so a user report can be found
    wait_job(client, rm, r.json()["job_id"])  # the outcome does not matter here, only that it ran
    finished = spans.get_finished_spans()
    server = [s for s in finished if s.name == "POST /v1/applications/{app_id}/score"]
    job = [s for s in finished if s.name == "job application.score"]
    assert server and job
    assert format(server[0].context.trace_id, "032x") == trace_id
    assert format(job[0].context.trace_id, "032x") == trace_id  # one trace across the queue


def test_production_guard_refuses_demo_configuration():
    demo = replace(get_settings(), env="production", data_region="centralindia")
    problems = production_problems(demo)
    assert any("UP_JWT_SECRET" in p for p in problems)
    assert any("SQLite" in p for p in problems)
    with pytest.raises(RuntimeError, match="Refusing to start in production"):
        assert_startup_safe(demo)


def test_production_requires_india_region():
    with pytest.raises(RuntimeError, match="India region"):
        assert_startup_safe(replace(get_settings(), env="production", data_region="local"))
    with pytest.raises(RuntimeError, match="not an India region"):
        assert_startup_safe(replace(get_settings(), data_region="eastus"))


def test_production_guard_accepts_hardened_configuration():
    hardened = replace(get_settings(), env="production", data_region="centralindia", jwt_secret="x" * 48,
                       field_keys_raw="k1", db_url="postgresql+psycopg://u@db/x", redis_url="redis://r:6379/0",
                       demo_mode_raw="auto", cookie_secure_raw="auto", jwt_ttl_minutes=15,
                       argon2_time_cost=3, argon2_memory_kib=65536)
    assert production_problems(hardened) == []
    assert hardened.cookie_secure and not hardened.demo_mode
    assert_startup_safe(hardened)
    assert DEFAULT_JWT_SECRET not in hardened.jwt_secret
