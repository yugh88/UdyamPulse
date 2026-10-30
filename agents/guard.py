"""Number guard: the LLM must never invent numbers. Every number in generated prose must already
exist in the structured facts the scoring engine / database produced."""

from __future__ import annotations

import json
import re
from typing import Any

_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def _normalise(token: str) -> str:
    token = token.replace(",", "")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token


def numbers_in(text: str) -> set[str]:
    return {_normalise(m.group()) for m in _NUM.finditer(text)}


def allowed_numbers(facts: Any) -> set[str]:
    return numbers_in(json.dumps(facts, ensure_ascii=False, default=str))


def unsupported_numbers(text: str, facts: Any) -> set[str]:
    """Numbers in `text` that do not appear anywhere in `facts`."""
    return numbers_in(text) - allowed_numbers(facts)
