"""Keyset pagination: walking the pages returns every row exactly once, in the same order as one big page."""

from urllib.parse import urlsplit

from tests.conftest import advance, login


def _walk(client, path: str, headers: dict, key=lambda r: r["id"], body=lambda r: r) -> list:
    out, url, pages = [], path, 0
    while url:
        r = client.get(url, headers=headers)
        assert r.status_code == 200, r.text
        out += [key(x) for x in body(r.json())]
        pages += 1
        link = r.headers.get("link")
        if link:
            assert link.endswith('; rel="next"') and r.headers["x-next-cursor"]
            nxt = urlsplit(link[1:link.index(">")])
            url = f"{nxt.path.removeprefix('/v1')}?{nxt.query}"
        else:
            url = None
    return out, pages


def test_applications_and_alerts_page_without_gaps_or_repeats(client):
    rm = login(client, "rm1")
    advance(client, rm, 42)  # more alerts, several months, mixed severities
    for path, small in (("/applications?state=MONITORING", "/applications?state=MONITORING&limit=7"),
                        ("/alerts?status=ALL", "/alerts?status=ALL&limit=3")):
        whole = [x["id"] for x in client.get(path, headers=rm).json()]
        paged, pages = _walk(client, small, rm)
        assert paged == whole and len(set(paged)) == len(paged) and pages > 2, path
    sev = [x["severity"] for x in client.get("/alerts?status=ALL", headers=rm).json()]
    order = {"high": 0, "medium": 1, "low": 2}
    assert sev == sorted(sev, key=order.get), "severity order is kept across pages"


def test_governance_lists_page_by_cursor(client):
    risk = login(client, "risk1")
    whole = [x["id"] for x in client.get("/audit?limit=2000", headers=risk).json()]
    paged, _ = _walk(client, "/audit?limit=50", risk)
    assert paged == whole[: len(paged)] and len(paged) == len(whole)
    ledger, pages = _walk(client, "/consent-ledger?limit=40", risk, body=lambda b: b["events"])
    assert pages > 1 and len(set(ledger)) == len(ledger)
    first = client.get("/consent-ledger?limit=40", headers=risk).json()
    assert first["next_cursor"] and client.get("/consent-ledger?limit=100000", headers=risk).status_code == 422


def test_bad_cursors_are_rejected(client):
    rm = login(client, "rm1")
    for bad in ("not-base64!!", "W10", "eyJhIjoxfQ"):  # garbage, [] (wrong size), {"a":1} (not a list)
        r = client.get(f"/alerts?cursor={bad}", headers=rm)
        assert r.status_code == 400 and r.json()["code"] == "bad_request", bad
