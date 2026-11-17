"""OpenTelemetry tracing. Off unless `UP_OTEL_ENDPOINT` names an OTLP/HTTP collector (Jaeger, Tempo,
Azure Monitor's collector...). When off, the OTel API hands out no-op spans, so call sites never branch.

One trace follows a request from the HTTP edge through its SQL statements and into the background job it
enqueued: the job row carries the W3C `traceparent` of the request that created it."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from opentelemetry import context, propagate, trace

from core.settings import get_settings

log = logging.getLogger("udyampulse.telemetry")
tracer = trace.get_tracer("udyampulse")
_configured = False


def configure_tracing(service: str) -> bool:
    """Install an exporting tracer provider once per process. Returns True when spans are exported."""
    global _configured
    endpoint = get_settings().otel_endpoint
    if _configured or not endpoint:
        return _configured
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    s = get_settings()
    provider = TracerProvider(resource=Resource.create({
        "service.name": service, "service.namespace": "udyampulse", "deployment.environment": s.env}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
    trace.set_tracer_provider(provider)
    _configured = True
    log.info("tracing on", extra={"otlp_endpoint": endpoint, "service": service})
    return True


def instrument_engine(engine: Any) -> None:
    """One client span per SQL statement (statement text without parameter values)."""
    from sqlalchemy import event

    if getattr(engine, "_otel_instrumented", False):
        return
    engine._otel_instrumented = True

    @event.listens_for(engine, "before_cursor_execute")
    def _start(conn, cursor, statement, parameters, ctx, executemany):  # noqa: ARG001
        if not trace.get_current_span().get_span_context().is_valid:
            return  # only trace SQL that belongs to a traced request or job
        span = tracer.start_span(statement.split(None, 1)[0].upper() if statement else "SQL",
                                 kind=trace.SpanKind.CLIENT,
                                 attributes={"db.system.name": engine.dialect.name, "db.query.text": statement[:2000]})
        ctx._otel_span = span

    @event.listens_for(engine, "after_cursor_execute")
    def _end(conn, cursor, statement, parameters, ctx, executemany):  # noqa: ARG001
        span = getattr(ctx, "_otel_span", None)
        if span is not None:
            span.end()

    @event.listens_for(engine, "handle_error")
    def _error(exc_ctx):
        span = getattr(exc_ctx.execution_context, "_otel_span", None) if exc_ctx.execution_context else None
        if span is not None:
            span.record_exception(exc_ctx.original_exception)
            span.set_status(trace.StatusCode.ERROR)
            span.end()


def carrier() -> dict[str, str]:
    """The current trace context as W3C headers, to store with work that continues elsewhere."""
    out: dict[str, str] = {}
    propagate.inject(out)
    return out


@contextmanager
def continue_trace(headers: dict[str, str] | None, name: str, **attributes: Any):
    """Start a span that is a child of the trace described by `headers` (from `carrier()`)."""
    token = context.attach(propagate.extract(headers or {}))
    try:
        with tracer.start_as_current_span(name, kind=trace.SpanKind.CONSUMER, attributes=attributes) as span:
            yield span
    finally:
        context.detach(token)
