"""Prometheus metrics shared by the API and the worker.

With several uvicorn workers in one container, set `PROMETHEUS_MULTIPROC_DIR` (the image's API command does)
so every process writes to shared files and one scrape sees the whole container. Leave it unset everywhere
else: prometheus_client switches to file mode whenever the variable exists, even when it is empty.

Labels are low-cardinality on purpose: the route template, never the raw path; the job kind, never the job
id; no tenant or user labels.
"""

from __future__ import annotations

import os

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily

MULTIPROC = "PROMETHEUS_MULTIPROC_DIR" in os.environ  # same test prometheus_client itself uses
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

HTTP_REQUESTS = Counter("udyam_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("udyam_http_request_duration_seconds", "HTTP request latency", ["method", "route"],
                         buckets=LATENCY_BUCKETS)
HTTP_IN_FLIGHT = Gauge("udyam_http_requests_in_flight", "HTTP requests being served",
                       multiprocess_mode="livesum")
JOBS = Counter("udyam_jobs_total", "Background jobs finished, by outcome", ["kind", "status"])
JOB_LATENCY = Histogram("udyam_job_duration_seconds", "Background job run time", ["kind"],
                        buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600))
CACHE = Counter("udyam_cache_requests_total", "Read-model cache lookups", ["name", "result"])
RATE_LIMITED = Counter("udyam_rate_limited_total", "Requests refused by a rate limit", ["scope"])
LLM_CALLS = Counter("udyam_llm_calls_total", "LLM writer calls", ["provider", "outcome"])
LLM_BREAKER_OPEN = Gauge("udyam_llm_breaker_open", "1 while the LLM circuit breaker is open",
                         multiprocess_mode="max")
BATCH_ACCOUNTS = Counter("udyam_batch_accounts_total", "Accounts scored by the nightly batch")
AUTH_EVENTS = Counter("udyam_auth_events_total", "Authentication events", ["event"])


class QueueCollector:
    """Queue depth and outbox backlog, read from the database at scrape time (so every replica agrees)."""

    def collect(self):
        depth = GaugeMetricFamily("udyam_job_queue_depth", "Jobs waiting or running", labels=["status"])
        backlog = GaugeMetricFamily("udyam_outbox_pending", "Outbox events not yet published")
        try:
            from sqlalchemy import func, select

            from api.models.db import Job, OutboxEvent, SessionLocal

            with SessionLocal() as db:  # no tenant bound and not request-enforced: platform-wide counts
                rows = db.execute(select(Job.status, func.count()).where(
                    Job.status.in_(("queued", "running", "retrying"))).group_by(Job.status)).all()
                pending = db.execute(select(func.count()).select_from(OutboxEvent)
                                     .where(OutboxEvent.published_at.is_(None))).scalar_one()
        except Exception:  # a scrape must never fail because the database is busy
            return
        counts = dict(rows)
        for status in ("queued", "running", "retrying"):
            depth.add_metric([status], counts.get(status, 0))
        backlog.add_metric([], pending)
        yield depth
        yield backlog


def render(include_queue: bool = True) -> tuple[bytes, str]:
    if MULTIPROC:
        from prometheus_client import multiprocess

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        from prometheus_client import REGISTRY as registry
    body = generate_latest(registry)
    if include_queue:
        queue = CollectorRegistry()
        queue.register(QueueCollector())
        body += generate_latest(queue)
    return body, CONTENT_TYPE_LATEST
