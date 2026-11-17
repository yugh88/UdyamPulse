"""Keyset (cursor) pagination.

A cursor is the opaque, URL-safe encoding of the last row's sort key. The next page starts strictly after it,
so pages stay correct while rows are inserted, and each page is an index range scan instead of an OFFSET that
gets slower the deeper you go. The next page is advertised with an RFC 8288 `Link: <…>; rel="next"` header and
`X-Next-Cursor`, so list bodies stay plain arrays."""

from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import HTTPException, Request, Response, status


def encode(key: list[Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(key, separators=(",", ":")).encode()).decode().rstrip("=")


def decode(cursor: str | None, size: int) -> list[Any] | None:
    if not cursor:
        return None
    try:
        key = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The cursor is not valid") from exc
    if not isinstance(key, list) or len(key) != size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The cursor is not valid")
    return key


def link_next(request: Request, response: Response, next_key: list[Any] | None) -> str | None:
    """Set the next-page headers. Returns the cursor (or None on the last page)."""
    if next_key is None:
        return None
    cursor = encode(next_key)
    url = request.url.include_query_params(cursor=cursor)
    response.headers["Link"] = f'<{url.path}?{url.query}>; rel="next"'
    response.headers["X-Next-Cursor"] = cursor
    return cursor
