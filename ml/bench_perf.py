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
import subprocess
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
    cpu = platform.processor() or platform.machine()
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True,
                             check=True).stdout.strip() or cpu
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"cpu": cpu, "cores": os.cpu_count(), "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version()}


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def bench_batch(workers: int = 1, runs: int = RUNS_BATCH) -> dict:
    from ml.batch import run_batch

    month = get_settings().n_months
    out = [run_batch(month, workers=workers) for _ in range(runs)]
    rates = [r["accounts_per_second"] for r in out]
    return {"month": month, "accounts": out[0]["accounts"], "workers": workers, "runs": runs,
            "accounts_per_second_runs": rates, "accounts_per_second_median": statistics.median(rates),
            "wall_seconds_median": statistics.median(r["wall_seconds"] for r in out)}


def _login(client, username: str) -> dict:
    r = client.post("/auth/login", json={"username": username, "password": "demo123"})
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
            assert c.get("/portfolio", headers=risk).status_code == 200
            portfolio_ms.append((time.perf_counter() - t0) * 1000)
        body = c.get("/portfolio", headers=risk).json()
        accounts = body.get("kpis", {}).get("accounts") if isinstance(body.get("kpis"), dict) else None

        memo_ms = []
        for _ in range(RUNS_MEMO):
            seed.main()
            rm = _login(c, "rm1")
            app_id = next(a["id"] for a in c.get("/applications", headers=rm).json() if a["factory_id"] == "UP-F0001")
            assert c.post(f"/applications/{app_id}/consent", headers=rm).status_code == 200
            assert c.post(f"/applications/{app_id}/score", headers=rm).status_code == 200
            memo = c.post(f"/applications/{app_id}/memo", headers=rm)
            assert memo.status_code == 200, memo.text
            memo_ms.append(memo.json()["generated_in_ms"])

        reset_ms = []
        for _ in range(RUNS_RESET):
            t0 = time.perf_counter()
            assert c.post("/demo/reset").status_code == 200
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
