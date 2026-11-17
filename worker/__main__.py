"""Standalone worker: `python -m worker`. Needs UP_REDIS_URL (the queue is shared with the API pods).

Runs the outbox relay and UP_WORKER_THREADS Dramatiq worker threads; stops cleanly on SIGTERM/SIGINT."""

from __future__ import annotations

import logging
import os
import signal
import threading

from core.logs import configure_logging
from core.settings import assert_startup_safe, get_settings


def main() -> None:
    configure_logging()
    s = get_settings()
    assert_startup_safe(s)
    if not s.redis_url:
        raise SystemExit("python -m worker needs UP_REDIS_URL. Without Redis the API runs the worker in-process.")
    from api.models.db import get_engine, init_db
    from core.telemetry import configure_tracing, instrument_engine
    from worker.runtime import WorkerRuntime

    if configure_tracing("udyampulse-worker"):
        instrument_engine(get_engine())
    if s.metrics_enabled:
        from prometheus_client import start_http_server

        # Job counters and latencies for Prometheus (queue depth is served by the API's /metrics).
        start_http_server(int(os.environ.get("UP_WORKER_METRICS_PORT", "9191")))
    init_db()
    runtime = WorkerRuntime(threads=s.worker_threads).start()
    logging.getLogger("udyampulse.worker").info("worker up: %s threads, relay on", s.worker_threads)
    done = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: done.set())
    done.wait()
    runtime.stop()


if __name__ == "__main__":
    main()
