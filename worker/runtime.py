"""Start and stop the relay and the Dramatiq worker threads, in the API (lite) or in `python -m worker`."""

from __future__ import annotations

import threading

import dramatiq

from worker.broker import broker
from worker.relay import run_relay


class WorkerRuntime:
    def __init__(self, threads: int = 1, relay: bool = True) -> None:
        self.threads, self.relay = threads, relay
        self._stop = threading.Event()
        self._relay_thread: threading.Thread | None = None
        self._worker: dramatiq.Worker | None = None

    def start(self) -> WorkerRuntime:
        import worker.tasks  # noqa: F401  (registers the actors)

        self._worker = dramatiq.Worker(broker, worker_threads=self.threads, worker_timeout=200)
        self._worker.start()
        if self.relay:
            self._relay_thread = threading.Thread(target=run_relay, args=(self._stop,), name="outbox-relay", daemon=True)
            self._relay_thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._relay_thread:
            self._relay_thread.join(timeout=5)
        if self._worker:
            self._worker.stop(timeout=10_000)
