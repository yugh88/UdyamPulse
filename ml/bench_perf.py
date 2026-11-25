"""Performance benchmarks whose numbers are quoted in the README and the deck, stored so they can be checked.

    python -m ml.bench_perf                    # demo panel: ml/reports/perf.json and perf.md
    UP_DATASET=full python -m ml.bench_perf    # 50,000 factories, batch only: ml/reports/full/perf.*

Measures, on the demo panel and a fresh throwaway SQLite database (nothing else is touched):
- **Nightly batch throughput**: `ml.batch.run_batch` over every live account, one process; median of 5 runs.
- **Portfolio read**: `GET /v1/portfolio` as the risk head with the read cache off; median of 15 requests.
- **Credit memo**: `generated_in_ms` recorded by the memo agent for the hero application; median of 5 fresh runs.
- **Demo reset**: `POST /v1/demo/reset`; median of 5.

Timings depend on the machine, so the report records it. Extrapolations (for example to 10 lakh accounts) are
derived from these numbers in the docs and labelled as estimates there.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="udyampulse-bench-"))
os.environ["UP_DB_URL"] = f"sqlite:///{_TMP / 'bench.db'}"
os.environ["UP_LLM_PROVIDER"] = "template"
os.environ["UP_CACHE"] = "off"
for _k in ("UP_RATE_LIMIT_USER_PER_MIN", "UP_RATE_LIMIT_TENANT_PER_MIN", "UP_RATE_LIMIT_LOGIN_PER_MIN"):
    os.environ.setdefault(_k, "100000")

from core.settings import get_settings  # noqa: E402

RUNS_BATCH, RUNS_PORTFOLIO, RUNS_MEMO, RUNS_RESET = 5, 15, 5, 5


def _machine() -> dict:
    return {"cpu": os.environ.get("UP_BENCH_CPU") or platform.processor() or platform.machine(), "cores": os.cpu_count(),
            "os": f"{platform.system()} {platform.release()}", "python": platform.python_version()}


def _commit() -> str | None:
    """The checked-out commit, read from .git without running a process."""
    git = Path(__file__).resolve().parent.parent / ".git"
    try:
        if git.is_file():  # a worktree: .git points at the real git dir
            git = Path(git.read_text().split(":", 1)[1].strip())
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            common = Path((git / "commondir").read_text().strip()) if (git / "commondir").exists() else None
            for base in (git, (git / common) if common else None):
                if base and (base / ref).exists():
                    return (base / ref).read_text().strip()[:7]
            return None
        return head[:7]
    except OSError:
        return None


def bench_batch(workers: int = 1, runs: int = RUNS_BATCH) -> dict:
    from ml.batch import run_batch

    month = get_settings().n_months
    out = [run_batch(month, workers=workers) for _ in range(runs)]
    rates = [r["accounts_per_second"] for r in out]
    return {"month": month, "accounts": out[0]["accounts"], "workers": workers, "runs": runs,
            "accounts_per_second_runs": rates, "accounts_per_second_median": statistics.median(rates),
            "wall_seconds_median": statistics.median(r["wall_seconds"] for r in out)}


def _ok(response, expected: int = 200):
    if response.status_code != expected:
        raise RuntimeError(f"{response.request.method} {response.request.url} -> {response.status_code}: {response.text}")
    return response


def _login(client, username: str) -> dict:
    from api.seed import DEMO_PASSWORD

    r = client.post("/auth/login", json={"username": username, "password": DEMO_PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def bench_api() -> dict:
    from fastapi.testclient import TestClient

    from api import seed
    from api.main import app

    seed.main()
    with TestClient(app, base_url="http://testserver/v1") as c:
        risk = _login(c, "risk1")
        portfolio_ms = []
        for _ in range(RUNS_PORTFOLIO):
            t0 = time.perf_counter()
            _ok(c.get("/portfolio", headers=risk))
            portfolio_ms.append((time.perf_counter() - t0) * 1000)
        body = c.get("/portfolio", headers=risk).json()
        accounts = body.get("kpis", {}).get("accounts") if isinstance(body.get("kpis"), dict) else None

        memo_ms = []
        for _ in range(RUNS_MEMO):
            seed.main()
            rm = _login(c, "rm1")
            app_id = next(a["id"] for a in c.get("/applications", headers=rm).json() if a["factory_id"] == "UP-F0001")
            _ok(c.post(f"/applications/{app_id}/consent", headers=rm))
            _ok(c.post(f"/applications/{app_id}/score", headers=rm))
            memo = _ok(c.post(f"/applications/{app_id}/memo", headers=rm))
            memo_ms.append(memo.json()["generated_in_ms"])

        reset_ms = []
        for _ in range(RUNS_RESET):
            t0 = time.perf_counter()
            _ok(c.post("/demo/reset"))
            reset_ms.append((time.perf_counter() - t0) * 1000)

    r1 = lambda xs: [round(x, 1) for x in xs]  # noqa: E731
    return {
        "portfolio_read": {"endpoint": "GET /v1/portfolio", "role": "risk1", "cache": "off", "runs": RUNS_PORTFOLIO,
                           "accounts_in_scope": accounts or None, "ms_runs": r1(portfolio_ms),
                           "ms_median": round(statistics.median(portfolio_ms), 1)},
        "credit_memo": {"application": "UP-F0001 (hero)", "llm_provider": "template", "runs": RUNS_MEMO,
                        "generated_in_ms_runs": memo_ms, "generated_in_ms_median": statistics.median(memo_ms)},
        "demo_reset": {"endpoint": "POST /v1/demo/reset", "runs": RUNS_RESET, "ms_runs": r1(reset_ms),
                       "ms_median": round(statistics.median(reset_ms), 1)},
    }


def to_markdown(r: dict) -> str:
    b, p, m, d = r["batch"], r["api"]["portfolio_read"], r["api"]["credit_memo"], r["api"]["demo_reset"]
    mc = r["machine"]
    return "\n".join([
        "# Performance benchmarks (demo panel, synthetic data)", "",
        f"Measured {r['generated_at']} on {mc['cpu']}, {mc['cores']} cores, {mc['os']}, Python {mc['python']}"
        f"{', commit ' + r['commit'] if r.get('commit') else ''}. Re-run with `python -m ml.bench_perf`.", "",
        "| What | Median | Runs | Notes |", "|---|---|---|---|",
        f"| Nightly batch, accounts scored per second (one process) | {b['accounts_per_second_median']:,.0f} | "
        f"{b['runs']} | {b['accounts']} accounts, month {b['month']}, wall {b['wall_seconds_median']} s |",
        f"| Portfolio read, `GET /v1/portfolio` | {p['ms_median']} ms | {p['runs']} | SQLite, read cache off |",
        f"| Credit memo drafted (template writer) | {m['generated_in_ms_median']:,} ms | {m['runs']} | "
        "hero application, including the PDF |",
        f"| Demo reset, `POST /v1/demo/reset` | {d['ms_median']:,.0f} ms | {d['runs']} | |", "",
        "Estimates derived from these numbers (for example the 10 lakh-account nightly run) are labelled as estimates "
        "where they are quoted.", ""])


def full_markdown(r: dict) -> str:
    mc = r["machine"]
    rows = [f"| {b['workers']} | {b['accounts']:,} | {b['accounts_per_second_median']:,.0f} | {b['wall_seconds_median']} s | "
            f"{b['runs']} |" for b in r["batch"]]
    return "\n".join([
        "# Nightly batch throughput (50,000-factory panel, synthetic data)", "",
        f"Measured {r['generated_at']} on {mc['cpu']}, {mc['cores']} cores, {mc['os']}, Python {mc['python']}"
        f"{', commit ' + r['commit'] if r.get('commit') else ''}. Re-run with `UP_DATASET=full python -m ml.bench_perf`.",
        "", "| Processes | Accounts | Accounts per second (median) | Wall time (median) | Runs |", "|---|---|---|---|---|",
        *rows, "", "The 10 lakh-account nightly run quoted in the docs is extrapolated from these rates (an estimate).", ""])


def main() -> None:
    s = get_settings()
    report = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "commit": _commit(),
              "machine": _machine(), "dataset": s.dataset, "provenance": f"Synthetic data ({s.dataset} panel)"}
    if s.dataset == "demo":
        report |= {"batch": bench_batch(), "api": bench_api()}
        md = to_markdown(report)
    else:  # the larger panels measure only the batch, the number that is extrapolated to bank scale
        report["batch"] = [bench_batch(workers=1, runs=3), bench_batch(workers=4, runs=3)]
        md = full_markdown(report)
    (s.reports / "perf.json").write_text(json.dumps(report, indent=2) + "\n")
    (s.reports / "perf.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
