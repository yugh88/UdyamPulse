"""Request id: taken from `X-Request-ID` or generated, exposed to logs through a context variable and
returned on every response so a user-reported error can be traced."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_SAFE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
HEADER = "x-request-id"


def request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class RequestIdMiddleware:
    """Pure ASGI middleware (no response buffering, so it is safe for streaming and SSE)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(HEADER.encode(), b"").decode("latin-1")
        rid = incoming if _SAFE.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid  # survives into the last-resort 500 handler
        token = _request_id.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                if not any(k.lower() == HEADER.encode() for k, _ in headers):
                    headers.append((HEADER.encode(), rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _request_id.reset(token)
