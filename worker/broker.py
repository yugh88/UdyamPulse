"""Dramatiq broker: Redis when configured, otherwise the in-process stub broker.

Retries use exponential backoff with jitter (Dramatiq's `Retries` middleware). A message that exhausts its
retries is moved to the dead-letter queue (`<queue>.XQ` on Redis, `dead_letters` on the stub broker)."""

from __future__ import annotations

import dramatiq
from dramatiq.middleware import AgeLimit, Callbacks, CurrentMessage, Pipelines, Retries, ShutdownNotifications, TimeLimit

from core.settings import get_settings


def build_broker() -> dramatiq.Broker:
    s = get_settings()
    middleware = [
        AgeLimit(),
        TimeLimit(time_limit=s.job_time_limit_ms),
        ShutdownNotifications(),
        Callbacks(),
        Pipelines(),
        Retries(max_retries=s.job_max_retries, min_backoff=s.job_min_backoff_ms, max_backoff=s.job_max_backoff_ms),
        CurrentMessage(),
    ]
    if s.redis_url:
        from dramatiq.brokers.redis import RedisBroker

        broker: dramatiq.Broker = RedisBroker(url=s.redis_url, namespace="udyampulse", middleware=middleware)
    else:
        from dramatiq.brokers.stub import StubBroker

        broker = StubBroker(middleware=middleware)
        broker.emit_after("process_boot")
    dramatiq.set_broker(broker)
    return broker


broker = build_broker()
