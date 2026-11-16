"""Shared agent plumbing: every tool call goes through `Agent.tool`, which writes the audit log
(agent, tool, inputs, SHA-256 of the output, user, timestamp)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

import pandas as pd
from sqlalchemy.orm import Session

from agents.providers.llm import get_llm
from api.audit import Actor, log_event
from api.models.db import AiUsage, SimClock
from core.settings import get_settings
from core.timeline import last_visible_month, month_end

T = TypeVar("T")


class Agent:
    name = "agent"

    def __init__(self, db: Session, actor: Actor) -> None:
        self.db = db
        self.actor = actor

    def tool(self, tool: str, fn: Callable[..., T], *, audit_app: int | None = None,
             audit_output: Callable[[T], Any] | None = None, **inputs: Any) -> T:
        result = fn(**inputs)
        out = audit_output(result) if audit_output else result
        logged_inputs = {
            k: f"<{type(v).__name__} {len(v)} rows>" if isinstance(v, (pd.DataFrame, pd.Series)) else v
            for k, v in inputs.items()
        }
        log_event(self.db, self.actor, agent=self.name, tool=tool, action="tool_call", inputs=logged_inputs,
                  output=_jsonable(out), application_id=audit_app)
        return result

    def write(self, template_id: str, task: str, facts: dict, draft: str, *, audit_app: int | None = None) -> str:
        """Prose from the LLM writer (template by default). Audited like any tool call and recorded in the
        AI usage log with the prompt template id, provider, latency and a token estimate."""
        llm = get_llm()
        t0 = time.perf_counter()
        text = self.tool("llm.write", llm.write, audit_app=audit_app, **{"task": task, "facts": facts, "draft": draft})
        chars = len(task) + len(json.dumps(facts, ensure_ascii=False, default=str)) + len(draft) + len(text)
        self.db.add(AiUsage(
            agent=self.name, template_id=template_id, provider=llm.name,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2), tokens_est=chars // 4,
            fallback=llm.name != "template" and text == draft, user=self.actor.username, application_id=audit_app,
        ))
        return text


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except TypeError:
            pass
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


# ---- simulated clock -------------------------------------------------------------------------

def sim_date(db: Session) -> date:
    clock = db.get(SimClock, 1)
    if clock is None:
        clock = SimClock(id=1, current_date=get_settings().sim_start)
        db.add(clock)
        db.commit()
    return clock.current_date


def set_sim_date(db: Session, new_date: date) -> date:
    cap = month_end(get_settings().n_months)
    clock = db.get(SimClock, 1) or SimClock(id=1, current_date=get_settings().sim_start)
    clock.current_date = min(new_date, cap)
    db.add(clock)
    db.commit()
    return clock.current_date


def visible_month(db: Session) -> int:
    return last_visible_month(sim_date(db))
