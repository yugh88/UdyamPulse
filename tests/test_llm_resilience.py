"""LLM resilience: timeout, circuit breaker, per-bank concurrency cap, prompt cache, number guard."""

from __future__ import annotations

import threading
import time

import pytest

from agents.providers.llm import CircuitBreaker, ResilientWriter, TemplateLLM
from api.kv import MemoryKV

FACTS = {"score": 723, "limit": "₹3.00 Cr"}
DRAFT = "The unit scores 723 with a ₹3.00 Cr limit."


class Fake:
    def __init__(self, name="fake", reply="Polished: the unit scores 723.", delay=0.0, fail=False):
        self.name, self.reply, self.delay, self.fail = name, reply, delay, fail
        self.calls, self.active, self.peak = 0, 0, 0
        self._lock = threading.Lock()

    def complete(self, task, facts, draft):
        with self._lock:
            self.calls += 1
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(self.delay)
            if self.fail:
                raise ConnectionError("provider down")
            return self.reply
        finally:
            with self._lock:
                self.active -= 1


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    kv = MemoryKV()
    monkeypatch.setattr("api.kv.get_kv", lambda: kv)
    return kv


def writer(provider, **kw):
    kw.setdefault("timeout_s", 1.0)
    kw.setdefault("concurrency", 4)
    kw.setdefault("cache_ttl_s", 60)
    kw.setdefault("breaker", CircuitBreaker(3, 30))
    return ResilientWriter(provider, **kw)


def test_template_provider_returns_draft():
    r = writer(TemplateLLM()).write_result("t", FACTS, DRAFT)
    assert r.text == DRAFT and r.outcome == "template" and not r.fallback


def test_good_output_is_used_and_cached():
    fake = Fake()
    w = writer(fake)
    first = w.write_result("summary", FACTS, DRAFT, tenant="bank-a")
    second = w.write_result("summary", FACTS, DRAFT, tenant="bank-a")
    assert first.outcome == "ok" and first.text.startswith("Polished")
    assert second.outcome == "cached" and second.text == first.text
    assert fake.calls == 1  # the second identical prompt never reached the model
    assert w.write_result("summary", {**FACTS, "score": 724}, DRAFT).outcome == "ok"  # different facts, new call


def test_invented_numbers_fall_back_to_template():
    r = writer(Fake(reply="The unit scores 723 and deserves ₹5.5 Cr.")).write_result("summary", FACTS, DRAFT)
    assert r.outcome == "guard_rejected" and r.text == DRAFT and r.fallback


def test_slow_provider_times_out_quickly():
    w = writer(Fake(delay=2.0), timeout_s=0.2)
    t0 = time.perf_counter()
    r = w.write_result("summary", FACTS, DRAFT)
    assert r.outcome == "timeout" and r.text == DRAFT
    assert time.perf_counter() - t0 < 1.0


def test_breaker_opens_after_failures_then_recovers():
    now = [0.0]
    breaker = CircuitBreaker(3, 30, clock=lambda: now[0])
    down = Fake(fail=True)
    w = writer(down, breaker=breaker)
    assert [w.write_result("t", FACTS, DRAFT).outcome for _ in range(3)] == ["error"] * 3
    assert breaker.state == "open"
    assert w.write_result("t", FACTS, DRAFT).outcome == "breaker_open"
    assert down.calls == 3  # skipped while open: no load on a struggling provider
    now[0] = 31  # reset period over: one trial call
    down.fail = False
    assert breaker.state == "half_open"
    assert w.write_result("t2", FACTS, DRAFT).outcome == "ok"
    assert breaker.state == "closed"


def test_failed_trial_reopens_the_breaker():
    now = [0.0]
    breaker = CircuitBreaker(2, 10, clock=lambda: now[0])
    w = writer(Fake(fail=True), breaker=breaker)
    w.write_result("a", FACTS, DRAFT)
    w.write_result("b", FACTS, DRAFT)
    now[0] = 11
    assert w.write_result("c", FACTS, DRAFT).outcome == "error"
    assert breaker.state == "open"


def test_per_bank_concurrency_cap():
    fake = Fake(delay=0.15)
    w = writer(fake, concurrency=2, timeout_s=2.0)
    threads = [threading.Thread(target=w.write_result, args=(f"t{i}", FACTS, DRAFT, "bank-a")) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert fake.calls == 6 and fake.peak <= 2


def test_one_bank_cannot_starve_another():
    fake = Fake(delay=0.3)
    w = writer(fake, concurrency=1, timeout_s=0.1)
    busy = threading.Thread(target=w.write_result, args=("a", FACTS, DRAFT, "bank-a"))
    busy.start()
    time.sleep(0.02)
    assert w.write_result("b", FACTS, DRAFT, "bank-a").outcome == "busy"  # bank A is at its cap
    fake.delay = 0.0
    assert w.write_result("c", FACTS, DRAFT, "bank-b").outcome == "ok"  # bank B is not affected
    busy.join()
