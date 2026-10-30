"""Shared agent plumbing: every tool call goes through `Agent.tool`, which writes the audit log
(agent, tool, inputs, SHA-256 of the output, user, timestamp)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

import pandas as pd
from sqlalchemy.orm import Session

from api.audit import Actor, log_event
from api.models.db import SimClock
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
