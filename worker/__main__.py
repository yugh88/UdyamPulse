"""Standalone worker: `python -m worker`. Needs UP_REDIS_URL (the queue is shared with the API pods).

Runs the outbox relay and UP_WORKER_THREADS Dramatiq worker threads; stops cleanly on SIGTERM/SIGINT."""

from __future__ import annotations

import logging
import signal
import threading

from core.settings import assert_data_residency, get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    assert_data_residency(s)
    if not s.redis_url:
        raise SystemExit("python -m worker needs UP_REDIS_URL. Without Redis the API runs the worker in-process.")
    from api.models.db import init_db
    from worker.runtime import WorkerRuntime

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
