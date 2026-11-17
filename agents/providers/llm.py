"""LLM providers behind one resilient writer. The default is a deterministic template writer, so the demo
works with no API keys; Azure OpenAI / OpenAI are wired through Semantic Kernel.

`ResilientWriter` wraps any provider and guarantees that a slow, failing or misbehaving model can never break
or stall a credit workflow:

- **number guard**: any output containing a number that is not in the structured facts is rejected;
- **timeout** (`UP_LLM_TIMEOUT_S`): a call that takes longer is abandoned;
- **circuit breaker**: after `UP_LLM_BREAKER_FAILURES` consecutive failures the provider is skipped for
  `UP_LLM_BREAKER_RESET_S` seconds, then one trial call decides whether it is healthy again;
- **per-bank concurrency cap** (`UP_LLM_CONCURRENCY_PER_TENANT`): one bank's batch cannot starve another's;
- **cache**: the same facts and draft give the same prose, keyed by a SHA-256 of the prompt, for
  `UP_LLM_CACHE_TTL_S` seconds (Redis when configured).

Every one of those paths falls back to the template text, which is always a complete, correct answer. The
outcome is recorded per call (ai_usage.outcome) and counted in `udyam_llm_calls_total`."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from agents.guard import unsupported_numbers
from core import metrics
from core.settings import get_settings

log = logging.getLogger(__name__)
PROMPT_VERSION = "v1"  # part of the cache key: changing the system prompt invalidates cached prose

SYSTEM_PROMPT = (
    "You are a credit analyst assistant at an Indian bank writing for a credit officer. "
    "Rewrite the DRAFT into clear, concise professional prose. Rules: use ONLY numbers that appear in FACTS "
    "or DRAFT, verbatim; never compute, round or invent numbers; keep every policy citation like [§4.1]; "
    "do not add recommendations beyond the draft; the final decision belongs to the credit officer."
)


class Provider(Protocol):
    name: str

    def complete(self, task: str, facts: dict, draft: str) -> str: ...


class TemplateLLM:
    """Deterministic writer: returns the agent's template draft unchanged."""

    name = "template"

    def complete(self, task: str, facts: dict, draft: str) -> str:
        return draft


class SemanticKernelLLM:
    """Azure OpenAI (or OpenAI) chat completion through Semantic Kernel, guarded against invented numbers."""

    def __init__(self, provider: str) -> None:
        from semantic_kernel import Kernel

        self.name = provider
        self.kernel = Kernel()
        if provider == "azure_openai":
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

            self.service = AzureChatCompletion(
                deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
        else:
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

            self.service = OpenAIChatCompletion(
                ai_model_id=os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
                api_key=os.environ["OPENAI_API_KEY"],
            )
        self.kernel.add_service(self.service)

    async def _complete(self, task: str, facts: dict, draft: str) -> str:
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        from semantic_kernel.contents import ChatHistory

        history = ChatHistory()
        history.add_system_message(SYSTEM_PROMPT)
        history.add_user_message(
            f"TASK: {task}\n\nFACTS (JSON):\n{json.dumps(facts, ensure_ascii=False, default=str)}\n\nDRAFT:\n{draft}"
        )
        settings = OpenAIChatPromptExecutionSettings(temperature=0.2, max_tokens=600)
        result = await self.service.get_chat_message_content(history, settings=settings)
        return str(result).strip()

    def complete(self, task: str, facts: dict, draft: str) -> str:
        return asyncio.run(self._complete(task, facts, draft))


@dataclass(frozen=True)
class WriteResult:
    text: str
    outcome: str  # template | ok | cached | timeout | error | guard_rejected | breaker_open | busy

    @property
    def fallback(self) -> bool:
        return self.outcome not in ("template", "ok", "cached")


class CircuitBreaker:
    """Closed → open after N consecutive failures → half-open after the reset period (one trial call)."""

    def __init__(self, failures: int, reset_s: float, clock=time.monotonic) -> None:
        self.threshold, self.reset_s, self.clock = failures, reset_s, clock
        self._failures, self._opened_at, self._trial = 0, None, False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state()

    def _state(self) -> str:
        if self._opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self._opened_at >= self.reset_s else "open"

    def allow(self) -> bool:
        with self._lock:
            state = self._state()
            if state == "closed":
                return True
            if state == "half_open" and not self._trial:
                self._trial = True  # exactly one caller probes the provider
                return True
            return False

    def release_trial(self) -> None:
        """A half-open trial that never reached the provider must not block the next one."""
        with self._lock:
            self._trial = False

    def success(self) -> None:
        with self._lock:
            self._failures, self._opened_at, self._trial = 0, None, False
        metrics.LLM_BREAKER_OPEN.set(0)

    def failure(self) -> None:
        with self._lock:
            self._failures += 1
            self._trial = False
            if self._failures >= self.threshold or self._opened_at is not None:
                self._opened_at = self.clock()
                opened = True
            else:
                opened = False
        if opened:
            metrics.LLM_BREAKER_OPEN.set(1)


class ResilientWriter:
    def __init__(self, provider: Provider, *, timeout_s: float | None = None, concurrency: int | None = None,
                 breaker: CircuitBreaker | None = None, cache_ttl_s: int | None = None) -> None:
        s = get_settings()
        self.provider = provider
        self.name = provider.name
        self.timeout_s = s.llm_timeout_s if timeout_s is None else timeout_s
        self.concurrency = s.llm_concurrency_per_tenant if concurrency is None else concurrency
        self.cache_ttl_s = s.llm_cache_ttl_s if cache_ttl_s is None else cache_ttl_s
        self.breaker = breaker or CircuitBreaker(s.llm_breaker_failures, s.llm_breaker_reset_s)
        self._pool = ThreadPoolExecutor(max_workers=max(4, self.concurrency * 4), thread_name_prefix="llm")
        self._slots: dict[str, threading.BoundedSemaphore] = {}
        self._slots_lock = threading.Lock()

    def _slot(self, tenant: str) -> threading.BoundedSemaphore:
        with self._slots_lock:
            return self._slots.setdefault(tenant, threading.BoundedSemaphore(self.concurrency))

    def cache_key(self, task: str, facts: dict, draft: str) -> str:
        blob = json.dumps([self.name, PROMPT_VERSION, task, facts, draft], sort_keys=True, ensure_ascii=False,
                          default=str)
        return "llm:" + hashlib.sha256(blob.encode()).hexdigest()

    def write(self, task: str, facts: dict, draft: str, tenant: str | None = None) -> str:
        return self.write_result(task, facts, draft, tenant).text

    def write_result(self, task: str, facts: dict, draft: str, tenant: str | None = None) -> WriteResult:
        result = self._write(task, facts, draft, tenant or "-")
        metrics.LLM_CALLS.labels(self.name, result.outcome).inc()
        return result

    def _write(self, task: str, facts: dict, draft: str, tenant: str) -> WriteResult:
        if isinstance(self.provider, TemplateLLM):
            return WriteResult(draft, "template")
        from api.kv import get_kv

        kv, key = get_kv(), self.cache_key(task, facts, draft)
        hit = kv.get(key)
        if hit is not None:
            return WriteResult(hit, "cached")
        if not self.breaker.allow():
            return WriteResult(draft, "breaker_open")
        slot = self._slot(tenant)
        if not slot.acquire(timeout=self.timeout_s):
            self.breaker.release_trial()
            return WriteResult(draft, "busy")
        future = self._pool.submit(self.provider.complete, task, facts, draft)
        future.add_done_callback(lambda _f: slot.release())  # the slot frees when the call really ends
        try:
            text = (future.result(timeout=self.timeout_s) or "").strip()
        except FutureTimeout:
            self.breaker.failure()
            log.warning("LLM call timed out after %ss; using template text", self.timeout_s,
                        extra={"provider": self.name})
            return WriteResult(draft, "timeout")
        except Exception as exc:  # network, quota, configuration
            self.breaker.failure()
            log.warning("LLM call failed (%s); using template text", type(exc).__name__, extra={"provider": self.name})
            return WriteResult(draft, "error")
        self.breaker.success()
        bad = unsupported_numbers(text, {"facts": facts, "draft": draft})
        if bad or not text:
            log.warning("LLM output rejected by number guard: %s", sorted(bad), extra={"provider": self.name})
            return WriteResult(draft, "guard_rejected")
        kv.set(key, text, self.cache_ttl_s)
        return WriteResult(text, "ok")


@lru_cache
def get_llm() -> ResilientWriter:
    provider = get_settings().llm_provider
    if provider in ("azure_openai", "openai"):
        try:
            return ResilientWriter(SemanticKernelLLM(provider))
        except Exception as exc:
            log.warning("LLM provider '%s' unavailable (%s); falling back to template writer", provider, exc)
    return ResilientWriter(TemplateLLM())
