"""Structured logging. One JSON object per line with the request id, the trace id and the tenant, and
with PII masked in the message and every extra field. `UP_LOG_FORMAT=text` gives readable lines instead."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

from core.pii import mask_pii, mask_str

_tenant: ContextVar[str | None] = ContextVar("log_tenant", default=None)
_STD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime", "taskName"}


def set_log_tenant(tenant: str | None) -> None:
    _tenant.set(tenant)


def _request_id() -> str | None:
    try:
        from api.request_context import request_id
    except Exception:  # the worker can log before the API package is importable
        return None
    rid = request_id()
    return None if rid == "-" else rid


def _trace() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace
    except Exception:
        return None, None
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": mask_str(record.getMessage()),
        }
        rid = _request_id()
        if rid:
            out["request_id"] = rid
        trace_id, span_id = _trace()
        if trace_id:
            out["trace_id"], out["span_id"] = trace_id, span_id
        tenant = _tenant.get()
        if tenant:
            out["tenant"] = tenant
        extras = {k: v for k, v in record.__dict__.items() if k not in _STD and not k.startswith("_")}
        if extras:
            out.update(mask_pii(json.loads(json.dumps(extras, default=str))))
        if record.exc_info:
            out["exc"] = mask_str(self.formatException(record.exc_info))
        return json.dumps(out, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        return mask_str(super().format(record))


def configure_logging(fmt: str | None = None, level: str | None = None) -> None:
    """Idempotent: replaces the root handlers. uvicorn's own loggers propagate to the root."""
    from core.settings import get_settings

    s = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(TextFormatter() if (fmt or s.log_format) == "text" else JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level or s.log_level)
    for name in ("uvicorn", "uvicorn.error", "dramatiq"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
    # Our access log line replaces uvicorn's, which would print paths without the request id.
    logging.getLogger("uvicorn.access").disabled = True
