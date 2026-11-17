"""Key-value store for the cache, rate limits and idempotency keys.

Redis when `UP_REDIS_URL` is set (shared by every API pod), otherwise a thread-safe in-memory store
(single process, for the lite demo). Redis errors never fail a request: the store logs and behaves as
empty, so the API degrades to "no cache, no limit" instead of going down with Redis."""

from __future__ import annotations

import logging
import threading
import time
from functools import lru_cache
from typing import Protocol

from core.settings import get_settings

log = logging.getLogger("udyampulse.kv")


class KV(Protocol):
    backend: str

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int) -> None: ...
    def set_nx(self, key: str, value: str, ttl: int) -> bool: ...
    def incr(self, key: str, ttl: int | None = None) -> int: ...
    def delete(self, key: str) -> None: ...
    def ping(self) -> bool: ...


class MemoryKV:
    backend = "memory"

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.Lock()
        self._ops = 0

    def _live(self, key: str) -> tuple[str, float | None] | None:
        item = self._data.get(key)
        if item and item[1] is not None and item[1] <= time.monotonic():
            del self._data[key]
            return None
        return item

    def _sweep(self) -> None:
        self._ops += 1
        if self._ops % 1000 == 0:
            now = time.monotonic()
            for k in [k for k, (_, exp) in self._data.items() if exp is not None and exp <= now]:
                del self._data[k]

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._live(key)
            return item[0] if item else None

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._sweep()
            self._data[key] = (value, time.monotonic() + ttl)

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        with self._lock:
            if self._live(key):
                return False
            self._data[key] = (value, time.monotonic() + ttl)
            return True

    def incr(self, key: str, ttl: int | None = None) -> int:
        with self._lock:
            self._sweep()
            item = self._live(key)
            value = int(item[0]) + 1 if item else 1
            expires = item[1] if item else (time.monotonic() + ttl if ttl else None)
            self._data[key] = (str(value), expires)
            return value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def ping(self) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisKV:
    backend = "redis"

    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5,
                                       health_check_interval=30)

    def _safe(self, op: str, fn, default):
        try:
            return fn()
        except Exception as exc:  # Redis down or slow: degrade, never fail the request
            log.warning("redis %s failed: %s", op, type(exc).__name__)
            return default

    def get(self, key: str) -> str | None:
        return self._safe("get", lambda: self._r.get(key), None)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._safe("set", lambda: self._r.set(key, value, ex=ttl), None)

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        return bool(self._safe("set_nx", lambda: self._r.set(key, value, ex=ttl, nx=True), True))

    def incr(self, key: str, ttl: int | None = None) -> int:
        def run() -> int:
            pipe = self._r.pipeline()
            pipe.incr(key)
            if ttl:
                pipe.expire(key, ttl, nx=True)
            return int(pipe.execute()[0])

        return self._safe("incr", run, 0)

    def delete(self, key: str) -> None:
        self._safe("delete", lambda: self._r.delete(key), None)

    def ping(self) -> bool:
        return bool(self._r.ping())


@lru_cache
def get_kv() -> KV:
    url = get_settings().redis_url
    return RedisKV(url) if url else MemoryKV()
