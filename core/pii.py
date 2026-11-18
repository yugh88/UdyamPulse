"""PII masking shared by the audit trail and the structured logs: nothing personal reaches either."""

from __future__ import annotations

import re
from typing import Any

PII_KEYS = {"name", "display_name", "phone", "mobile", "email", "pan", "aadhaar", "gstin", "account_number", "address",
            "password", "token", "access_token", "refresh_token", "authorization", "cookie"}
SECRET_KEYS = {"password", "token", "access_token", "refresh_token", "authorization", "cookie"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(?<!\d)(\+91[\s-]?)?[6-9]\d{9}(?!\d)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_AADHAAR = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def mask_str(value: str) -> str:
    value = _BEARER.sub("Bearer ***", value)
    value = _EMAIL.sub("***@***", value)
    value = _PHONE.sub("**********", value)
    value = _AADHAAR.sub("XXXX XXXX ####", value)
    return _PAN.sub("*****####*", value)


def mask_pii(obj: Any) -> Any:
    """Recursively mask PII-bearing keys and patterns. Secrets are removed entirely, names keep 2 letters."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k).lower()
            if key in SECRET_KEYS:
                out[k] = "***"
            elif key in PII_KEYS and isinstance(v, str):
                out[k] = (v[:2] + "***") if v else v
            else:
                out[k] = mask_pii(v)
        return out
    if isinstance(obj, list | tuple):
        return [mask_pii(v) for v in obj]
    if isinstance(obj, str):
        return mask_str(obj)
    return obj
