"""Security response headers for every API response (pure ASGI, so SSE streams are untouched).

The API only ever returns JSON, PDFs and event streams, so its Content-Security-Policy forbids everything.
The interactive docs (`/docs`, `/redoc`) load Swagger UI from a CDN and get a narrower relaxed policy.
HSTS is sent only on HTTPS (directly or behind a proxy that sets `X-Forwarded-Proto`), because browsers
ignore it on plain HTTP and it would pin `localhost` to HTTPS for every other local project.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.webapp import is_api_path

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# The web app's policy (same as web/nginx.conf), used when FastAPI serves the React build itself.
SPA_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
           "font-src 'self' data:; connect-src 'self'; worker-src 'self'; frame-src 'self' blob:; manifest-src 'self'; object-src 'none'; "
           "base-uri 'self'; form-action 'self'; frame-ancestors {ancestors}")


def spa_csp() -> tuple[str, bool]:
    """(policy, framing allowed). Framing is denied unless UP_FRAME_ANCESTORS names who may embed the app."""
    from core.settings import get_settings

    ancestors = get_settings().frame_ancestors.strip()
    return SPA_CSP.format(ancestors=ancestors or "'none'"), bool(ancestors)
DOCS_CSP = ("default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
HSTS = "max-age=31536000; includeSubDomains"
DOCS_PATHS = ("/docs", "/redoc")

BASE_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
)


def is_https(scope: Scope) -> bool:
    """True for TLS requests. uvicorn `--proxy-headers` already rewrites `scheme` from a trusted proxy."""
    if scope.get("scheme") == "https":
        return True
    for k, v in scope.get("headers", []):
        if k == b"x-forwarded-proto":
            return v.split(b",")[0].strip().lower() == b"https"
    return False


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        web = not is_api_path(path) and not path.startswith(DOCS_PATHS)
        framable = False
        if path.startswith(DOCS_PATHS):
            csp = DOCS_CSP
        elif web:
            csp, framable = spa_csp()
        else:
            csp = API_CSP
        https = is_https(scope)
        api_data = path.startswith("/v1/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                base = [h for h in BASE_HEADERS if not (framable and h[0] == b"x-frame-options")]
                extra = [*base, (b"content-security-policy", csp.encode())]
                if https:
                    extra.append((b"strict-transport-security", HSTS.encode()))
                extra.append((b"x-robots-tag", b"noindex, nofollow"))  # prototype on synthetic data
                # Credit data must never sit in a shared or browser cache.
                if api_data:
                    extra.append((b"cache-control", b"no-store"))
                headers.extend((k, v) for k, v in extra if k not in present)
            await send(message)

        await self.app(scope, receive, send_with_headers)
