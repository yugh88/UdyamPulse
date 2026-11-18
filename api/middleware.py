"""Edge middleware (pure ASGI, so streaming responses pass through untouched):

- `RateLimitMiddleware`: fixed one-minute windows per user and per tenant, and per client IP on login.
  Over the limit → 429 problem+json with `Retry-After`.
- `IdempotencyMiddleware`: a POST/PUT/DELETE carrying `Idempotency-Key` runs at most once per user. A retry
  with the same key and body gets the stored response (`Idempotency-Replayed: true`); the same key with a
  different body is refused (422); a retry while the first request is still running gets 409.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from http import HTTPStatus

import jwt
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.kv import get_kv
from api.problems import MEDIA_TYPE, PROBLEM_BASE
from api.request_context import request_id
from core import metrics
from core.settings import get_settings

EXEMPT = ("/healthz", "/readyz", "/health", "/docs", "/openapi.json", "/redoc", "/v1/events", "/metrics")
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
IDEMPOTENCY_TTL = 24 * 3600
IN_FLIGHT_TTL = 120


def _header(scope: Scope, name: str) -> str:
    raw = name.lower().encode()
    for k, v in scope["headers"]:
        if k == raw:
            return v.decode("latin-1")
    return ""


def principal(scope: Scope) -> tuple[str, str] | None:
    """(user, tenant) from a valid bearer token, or None. Verified, so keys cannot be forged per user."""
    state = scope.setdefault("state", {})
    if "principal" in state:
        return state["principal"]
    auth = _header(scope, "authorization")
    result = None
    if auth.lower().startswith("bearer "):
        try:
            claims = jwt.decode(auth[7:], get_settings().jwt_secret, algorithms=["HS256"])
            if claims.get("sub") and claims.get("tid"):
                result = (str(claims["sub"]), str(claims["tid"]))
        except jwt.PyJWTError:
            result = None
    state["principal"] = result
    return result


async def send_problem(send: Send, scope: Scope, status: int, code: str, detail: str,
                       headers: dict[str, str] | None = None) -> None:
    rid = scope.get("state", {}).get("request_id") or request_id()
    body = json.dumps({"type": PROBLEM_BASE + code, "title": HTTPStatus(status).phrase, "status": status,
                       "detail": detail, "instance": scope["path"], "code": code, "request_id": rid}).encode()
    hdrs = [(b"content-type", MEDIA_TYPE.encode()), (b"content-length", str(len(body)).encode())]
    hdrs += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": status, "headers": hdrs})
    await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"].startswith(EXEMPT):
            await self.app(scope, receive, send)
            return
        s = get_settings()
        now = time.time()
        window = int(now // 60)
        retry_after = str(60 - int(now % 60))
        kv = get_kv()
        checks: list[tuple[str, int]] = []
        who = principal(scope)
        if who:
            checks = [(f"rl:u:{who[1]}:{who[0]}:{window}", s.rate_limit_user_per_min),
                      (f"rl:t:{who[1]}:{window}", s.rate_limit_tenant_per_min)]
        elif scope["path"].endswith(("/auth/login", "/auth/refresh")):
            ip = (scope.get("client") or ("unknown", 0))[0]
            checks = [(f"rl:ip:{ip}:{window}", s.rate_limit_login_per_min)]
        for key, limit in checks:
            if limit > 0 and kv.incr(key, ttl=61) > limit:
                scope_name = "sign-in attempts" if ":ip:" in key else ("your bank" if ":t:" in key else "you")
                metrics.RATE_LIMITED.labels(key.split(":")[1]).inc()
                await send_problem(send, scope, 429, "rate_limited",
                                   f"Too many requests for {scope_name}. Try again in {retry_after} seconds.",
                                   {"Retry-After": retry_after})
                return
        await self.app(scope, receive, send)


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        key = _header(scope, "idempotency-key") if scope["type"] == "http" else ""
        who = principal(scope) if key else None
        # Sign-in endpoints are never stored or replayed: their responses carry tokens and set cookies.
        if (not key or scope["method"] not in MUTATING or not scope["path"].startswith("/v1/") or who is None
                or scope["path"].startswith("/v1/auth/")):
            await self.app(scope, receive, send)
            return
        if not (1 <= len(key) <= 128) or not key.isprintable():
            await send_problem(send, scope, 400, "bad_request", "Idempotency-Key must be 1 to 128 printable characters")
            return

        body = b""
        more = True
        while more:
            message = await receive()
            body += message.get("body", b"")
            more = message.get("more_body", False)
        fingerprint = hashlib.sha256(
            b"\n".join([scope["method"].encode(), scope["path"].encode(), scope.get("query_string", b""), body])
        ).hexdigest()
        store_key = "idem:" + hashlib.sha256(f"{who[1]}|{who[0]}|{scope['method']}|{scope['path']}|{key}".encode()).hexdigest()
        kv = get_kv()

        if not kv.set_nx(store_key, json.dumps({"state": "pending", "fp": fingerprint}), IN_FLIGHT_TTL):
            stored = json.loads(kv.get(store_key) or "null")
            if stored is not None:
                if stored["fp"] != fingerprint:
                    await send_problem(send, scope, 422, "idempotency_key_reused",
                                       "This Idempotency-Key was already used for a different request")
                elif stored["state"] == "pending":
                    await send_problem(send, scope, 409, "idempotency_in_progress",
                                       "A request with this Idempotency-Key is still being processed", {"Retry-After": "1"})
                else:
                    headers = [(k.encode(), v.encode()) for k, v in stored["headers"]]
                    headers.append((b"idempotency-replayed", b"true"))
                    await send({"type": "http.response.start", "status": stored["status"], "headers": headers})
                    await send({"type": "http.response.body", "body": base64.b64decode(stored["body"])})
                return
            # The record expired between the two calls: fall through and process normally.

        sent_body = False

        async def replay() -> Message:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        start: Message | None = None
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False) and start is not None:
                    status = start["status"]
                    if status < 500:  # server errors are not stored, so the client can retry them
                        keep = [(k.decode(), v.decode()) for k, v in start.get("headers", [])
                                if k.lower() in (b"content-type", b"location")]
                        kv.set(store_key, json.dumps({"state": "done", "fp": fingerprint, "status": status, "headers": keep,
                                                      "body": base64.b64encode(b"".join(chunks)).decode()}), IDEMPOTENCY_TTL)
                    else:
                        kv.delete(store_key)
            await send(message)

        try:
            await self.app(scope, replay, capture)
        except BaseException:
            kv.delete(store_key)
            raise
