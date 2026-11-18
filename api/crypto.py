"""Field-level encryption for personal data and free text (Fernet: AES-128-CBC + HMAC-SHA256).

Columns typed `EncryptedText` / `EncryptedJSON` are encrypted before they reach the database and decrypted when
read, so a database dump, a replica or a backup shows ciphertext only. Keys come from `UP_FIELD_KEYS`
(comma separated, newest first): new values use the first key, every listed key still decrypts, and
`python -m api.crypto rotate` re-encrypts every row with the newest key so an old key can then be dropped.
In production the keys come from Azure Key Vault through the pod's environment.

Values written before encryption was switched on (no `enc:v1:` prefix) are read as they are and encrypted the
next time they are written, or all at once by `rotate`.

The local demo falls back to a fixed, public key so `make demo` needs no setup; the production start-up guard
refuses to run with it."""

from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from core.settings import get_settings

PREFIX = "enc:v1:"
DEMO_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"udyampulse-public-demo-field-key").digest()).decode()


def _keys() -> list[str]:
    raw = get_settings().field_keys_raw
    keys = [k.strip() for k in raw.split(",") if k.strip()] if raw else []
    return keys or [DEMO_KEY]


@lru_cache
def _cipher_for(keys: tuple[str, ...]) -> MultiFernet:
    return MultiFernet([Fernet(k.encode()) for k in keys])


def cipher() -> MultiFernet:
    return _cipher_for(tuple(_keys()))


def encrypt(plain: str) -> str:
    return PREFIX + cipher().encrypt(plain.encode()).decode()


def decrypt(stored: str) -> str:
    if not stored.startswith(PREFIX):
        return stored  # written before encryption was enabled
    try:
        return cipher().decrypt(stored[len(PREFIX):].encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Field cannot be decrypted with any configured key (UP_FIELD_KEYS)") from exc


def is_encrypted(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(PREFIX)


def new_key() -> str:
    return Fernet.generate_key().decode()


class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        return None if value is None else encrypt(str(value))

    def process_result_value(self, value: Any, dialect) -> str | None:
        return None if value is None else decrypt(value)


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        return None if value is None else encrypt(json.dumps(value, default=str, ensure_ascii=False))

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, dict | list):  # a driver that already parsed legacy JSON
            return value
        return json.loads(decrypt(value))


def encrypted_columns() -> list[tuple[type, str]]:
    from api.models.db import Base

    out = []
    for mapper in Base.registry.mappers:
        for col in mapper.columns:
            if isinstance(col.type, EncryptedText | EncryptedJSON):
                out.append((mapper.class_, col.key))
    return out


def rotate(batch: int = 500) -> dict[str, int]:
    """Re-encrypt every encrypted column with the newest key (also encrypts legacy plaintext)."""
    from sqlalchemy import literal, select, update

    from api.models.db import SessionLocal

    counts: dict[str, int] = {}
    newest = cipher()
    for model, attr in encrypted_columns():
        table = model.__table__
        col = table.c[attr]
        pk = list(table.primary_key.columns)
        name = f"{table.name}.{attr}"
        counts[name] = 0
        with SessionLocal() as db:  # platform maintenance: no tenant bound, so RLS bypass applies
            raw_rows = db.execute(select(*pk, col.cast(Text)).where(col.is_not(None))).all()
            for row in raw_rows:
                *keys, stored = row
                if stored.startswith(PREFIX):
                    token = newest.rotate(stored[len(PREFIX):].encode()).decode()
                    fresh = PREFIX + token
                else:
                    fresh = PREFIX + newest.encrypt(stored.encode()).decode()
                cond = [c == k for c, k in zip(pk, keys, strict=True)]
                # Bound as plain Text, so the column's type decorator does not encrypt the ciphertext again.
                db.execute(update(table).where(*cond).values({attr: literal(fresh, Text())}))
                counts[name] += 1
                if counts[name] % batch == 0:
                    db.commit()
            db.commit()
    return counts


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Field encryption keys")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new-key", help="Print a new Fernet key to put first in UP_FIELD_KEYS")
    sub.add_parser("rotate", help="Re-encrypt every encrypted field with the first key in UP_FIELD_KEYS")
    args = parser.parse_args()
    if args.cmd == "new-key":
        print(new_key())
    else:
        print(json.dumps(rotate(), indent=2))


if __name__ == "__main__":
    main()
