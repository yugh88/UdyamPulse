"""Shared download helpers: resumable HTTP downloads, SHA-256 checksums and a provenance record per file.

Raw files land in `data_real/raw/` (gitignored). `data_real/checksums.json` (committed) records the URL, size,
SHA-256, licence and retrieval time of every file, so a rerun skips what it already has and anyone can verify
they are working from the same bytes."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
CACHE = ROOT / "cache"
CHECKSUMS = ROOT / "checksums.json"
USER_AGENT = "udyampulse-research/1.0 (open-data benchmark; python-urllib)"
log = logging.getLogger("udyampulse.data_real")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_checksums() -> dict:
    return json.loads(CHECKSUMS.read_text()) if CHECKSUMS.exists() else {}


def save_checksum(name: str, record: dict) -> None:
    data = load_checksums()
    data[name] = record
    CHECKSUMS.write_text(json.dumps(dict(sorted(data.items())), indent=2) + "\n")


def http_json(url: str, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 - fixed https URLs of public portals
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dest: Path, *, licence: str, source: str, retries: int = 5) -> Path:
    """Resumable download with HTTP Range. Skips the file when it is complete and its checksum matches."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    known = load_checksums().get(dest.name)
    if dest.exists() and known and known.get("bytes") == dest.stat().st_size and known.get("sha256") == sha256(dest):
        log.info("have %s (%s bytes, checksum ok)", dest.name, dest.stat().st_size)
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        have = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120) as r:  # nosec B310 - fixed https URLs of public portals
                mode = "ab" if have and r.status == 206 else "wb"
                total = int(r.headers.get("Content-Length", 0)) + (have if mode == "ab" else 0)
                with part.open(mode) as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
            if total and part.stat().st_size != total:
                raise OSError(f"short read: {part.stat().st_size} of {total} bytes")
            part.rename(dest)
            break
        except OSError as exc:
            if attempt == retries:
                raise
            wait = 2 ** attempt
            log.warning("download %s failed (%s); retry %s in %ss", dest.name, exc, attempt, wait)
            time.sleep(wait)
    save_checksum(dest.name, {"url": url, "bytes": dest.stat().st_size, "sha256": sha256(dest), "licence": licence,
                              "source": source, "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds")})
    log.info("downloaded %s (%s bytes)", dest.name, dest.stat().st_size)
    return dest
