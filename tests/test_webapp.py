"""Single-container public demo: FastAPI serves the React build, strips /api, and keeps the site unindexed."""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import security, webapp
from core.settings import get_settings


def _app(tmp_path) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root>Waking up the demo…</div>")
    (dist / "assets" / "app-123.js").write_text("console.log(1)")
    (dist / "sw.js").write_text("self")
    (tmp_path / "secret.txt").write_text("not public")
    app = FastAPI()

    @app.get("/v1/ping")
    def ping() -> dict:
        return {"ok": True}

    webapp.install(app, dist)
    app.add_middleware(security.SecurityHeadersMiddleware)
    app.add_middleware(webapp.ApiPrefixMiddleware)
    return TestClient(app)


def test_spa_routes_assets_and_api_prefix(tmp_path):
    c = _app(tmp_path)
    assert "Waking up the demo" in c.get("/").text
    assert "Waking up the demo" in c.get("/console/141").text  # client-side route survives a reload
    assert c.get("/assets/app-123.js").text == "console.log(1)"
    assert c.get("/sw.js").headers["cache-control"] == "no-cache"
    assert c.get("/api/v1/ping").json() == {"ok": True}  # same paths the nginx front end proxies
    assert c.get("/v1/ping").json() == {"ok": True}


def test_no_path_traversal_and_noindex(tmp_path):
    c = _app(tmp_path)
    r = c.get("/..%2Fsecret.txt")
    assert "not public" not in r.text
    assert c.get("/robots.txt").text.startswith("User-agent: *\nDisallow: /")
    assert c.get("/").headers["x-robots-tag"] == "noindex, nofollow"


def test_framing_is_denied_unless_configured(tmp_path, monkeypatch):
    c = _app(tmp_path)
    page, api = c.get("/"), c.get("/api/v1/ping")
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert "frame-src 'self' blob:" in page.headers["content-security-policy"]  # the memo PDF preview frames a blob: URL
    assert page.headers["x-frame-options"] == "DENY"
    assert api.headers["content-security-policy"].startswith("default-src 'none'")
    s = replace(get_settings(), frame_ancestors="https://huggingface.co")
    monkeypatch.setattr("core.settings.get_settings", lambda: s)
    page = c.get("/")
    assert "frame-ancestors https://huggingface.co" in page.headers["content-security-policy"]
    assert "x-frame-options" not in page.headers  # the Space page may embed the app
    assert "frame-ancestors 'none'" in c.get("/api/v1/ping").headers["content-security-policy"]  # API never
