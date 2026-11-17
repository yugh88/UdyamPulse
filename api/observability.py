"""Per-request observability (pure ASGI, stream safe): a server span continuing any incoming `traceparent`,
RED metrics by route template, and one structured access-log line carrying the request id and trace id."""

from __future__ import annotations

import logging
import time

from opentelemetry import context, propagate, trace
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.middleware import principal
from core import metrics
from core.logs import set_log_tenant
from core.telemetry import tracer

access = logging.getLogger("udyampulse.access")
QUIET = ("/healthz", "/readyz", "/metrics", "/health")  # probes and scrapes: metrics yes, log lines no


def route_of(scope: Scope) -> str:
    """The matched route template with its router prefix, e.g. `/v1/applications/{app_id}`."""
    template = getattr(scope.get("route"), "path", None)
    if not template:
        return "unmatched"
    path = scope.get("path", "")
    literal = template.split("{", 1)[0]
    at = path.find(literal)
    return (path[:at] if at > 0 else "") + template


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope["method"]
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]
                   if k in (b"traceparent", b"tracestate")}
        token = context.attach(propagate.extract(headers))
        who = principal(scope)  # verified once per request and cached; tags every log line with the bank
        set_log_tenant(who[1] if who else None)
        status = {"code": 500}
        start = time.perf_counter()
        metrics.HTTP_IN_FLIGHT.inc()

        async def send_wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                span = trace.get_current_span()
                if span.get_span_context().is_valid:
                    tp: dict[str, str] = {}
                    propagate.inject(tp)
                    if "traceparent" in tp:  # lets a user-reported error be found in the tracing UI
                        message.setdefault("headers", []).append((b"traceparent", tp["traceparent"].encode()))
            await send(message)

        with tracer.start_as_current_span(f"{method} {scope.get('path', '')}", kind=trace.SpanKind.SERVER) as span:
            try:
                await self.app(scope, receive, send_wrapped)
            finally:
                elapsed = time.perf_counter() - start
                route = route_of(scope)
                code = status["code"]
                metrics.HTTP_IN_FLIGHT.dec()
                metrics.HTTP_REQUESTS.labels(method, route, str(code)).inc()
                metrics.HTTP_LATENCY.labels(method, route).observe(elapsed)
                span.update_name(f"{method} {route}")
                span.set_attribute("http.request.method", method)
                span.set_attribute("http.route", route)
                span.set_attribute("http.response.status_code", code)
                if code >= 500:
                    span.set_status(trace.StatusCode.ERROR)
                if not scope.get("path", "").startswith(QUIET):
                    access.info("%s %s %s", method, route, code, extra={
                        "http_method": method, "route": route, "status": code,
                        "duration_ms": round(elapsed * 1000, 1)})
                context.detach(token)
