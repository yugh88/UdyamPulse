"""Single-container mode for the free public demo: FastAPI also serves the built React app.

Enabled when `UP_WEB_DIST` points at `web/dist`. One URL, no CORS, no second service to keep awake.
- `/api/...` is the same API the nginx front end proxies (the prefix is stripped here instead);
- hashed `/assets/*` are cached for a year, everything else revalidates;
- any other path returns `index.html` so client-side routes survive a reload;
- the whole site is `noindex`: it is a prototype on synthetic data, not a lending product.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

API_PREFIXES = ("/v1/", "/healthz", "/readyz", "/health", "/metrics", "/docs", "/openapi.json", "/redoc")
ROBOTS = "User-agent: *\nDisallow: /\n"


class ApiPrefixMiddleware:
    """`/api/v1/...` → `/v1/...`, matching the nginx `location /api/ { proxy_pass http://api:8000/; }`."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api/"):
            scope = dict(scope)
            scope["path"] = scope["path"][4:]
            scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


def is_api_path(path: str) -> bool:
    return path.startswith(API_PREFIXES)


def install(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.exists():
        raise RuntimeError(f"UP_WEB_DIST={dist} has no index.html; run `npm run build` in web/")
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/robots.txt", include_in_schema=False)
    def robots() -> PlainTextResponse:
        return PlainTextResponse(ROBOTS)

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            no_cache = {"Cache-Control": "no-cache"} if path in ("sw.js", "theme-init.js", "manifest.webmanifest") else {}
            return FileResponse(candidate, headers=no_cache)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
