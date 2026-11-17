"""Data & Models: where every dataset comes from, what is real and what is synthetic, and how each model
performs with confidence intervals. Built only from committed report files, so it works offline."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends

from api.auth import CurrentUser, require_roles
from core.settings import DATASETS, ROOT, get_settings

router = APIRouter(tags=["governance"])
REPORTS = ROOT / "ml" / "reports"
REAL = "Real public data"
SYNTH = "Synthetic (calibrated)"
BENCHMARK_CAPTION = ("Same pipeline validated on real small-business loan outcomes (U.S. SBA, public domain) and real "
                     "company bankruptcies (UCI, CC BY 4.0). Indian MSME accuracy will be proven in a lender pilot on "
                     "consented data.")


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _metric(m: dict | None, keys: tuple[str, ...] = ("auc", "ks", "brier")) -> dict | None:
    if not m:
        return None
    out = {k: m.get(k) for k in ("n", "positives", "event_rate", "factories")}
    for k in keys:
        out[k] = m.get(k)
        out[f"{k}_ci95"] = m.get(f"{k}_ci95")
    return out


@lru_cache(maxsize=1)
def _checksums() -> dict:
    return _load(ROOT / "data_real" / "checksums.json") or {}


def _calibration_yaml() -> dict:
    import yaml

    p = ROOT / "data_gen" / "calibration.yaml"
    return yaml.safe_load(p.read_text()) if p.exists() else {"source": "fallback"}


def provenance() -> list[dict]:
    s = get_settings()
    sums = _checksums()
    full_build = _load(REPORTS / "full" / "build_stats.json") or {}
    sba = _load(REPORTS / "real_sba_benchmark.json") or {}
    polish = _load(REPORTS / "real_polish_benchmark.json") or {}
    cal = _calibration_yaml()
    cal_use = "fallback in use" if cal.get("source") == "fallback" else "seasonality, growth, shock shape"
    sba_file = sums.get("FOIA_7a_FY2020_Present_asof_260930.csv", {})
    rows = [
        {"dataset": "Demo panel (live walkthrough)", "provenance": "Synthetic", "source": "data_gen/generate.py, seed "
         f"{s.seed}", "licence": "Project code (synthetic, no real entities)", "rows": DATASETS["demo"]["factories"] * 24,
         "unit": "factory-months", "date_range": "Nov 2024 – Oct 2026 (simulated)", "retrieved_at": None,
         "used_for": "Demo model, cockpit and every screen of the walkthrough"},
        {"dataset": "Full calibrated panel", "provenance": SYNTH, "source": "data_gen/engine.py, calibrated to MoSPI IIP",
         "licence": "Project code (synthetic, no real entities)", "rows": full_build.get("silver_rows"),
         "unit": "factory-months", "date_range": "36 simulated months", "retrieved_at": None,
         "used_for": "Product model training and evaluation", "build_seconds": full_build.get("total_seconds"),
         "defaults": (full_build.get("generate") or {}).get("defaults")},
        {"dataset": "MoSPI Index of Industrial Production (NIC divisions)", "provenance": REAL,
         "source": "api.mospi.gov.in (Ministry of Statistics and Programme Implementation)",
         "licence": "MoSPI dissemination guidelines; GODL-India likely, unconfirmed for the API",
         "rows": sums.get("iip_monthly.parquet", {}).get("rows"), "unit": "monthly index values",
         "date_range": "1994 – 2026 (fit on base 2011-12 series)", "retrieved_at": sums.get("iip_monthly.parquet", {}).get("retrieved_at"),
         "used_for": f"Generator calibration ({cal_use})"},
        {"dataset": "U.S. SBA 7(a) FOIA loans, manufacturing FY2010+", "provenance": REAL,
         "source": "data.sba.gov (U.S. Small Business Administration)", "licence": "Public domain (U.S. Government Work)",
         "rows": (sba.get("selection") or {}).get("rows_used"), "unit": "loans",
         "date_range": "FY2010 – FY2021 approvals (60-month outcome window)", "retrieved_at": sba_file.get("retrieved_at"),
         "used_for": "Methodology benchmark on real loan defaults"},
        {"dataset": "UCI Polish companies bankruptcy", "provenance": REAL,
         "source": "UCI ML Repository, dataset 365 (Tomczak 2016, doi:10.24432/C5F600)", "licence": "CC BY 4.0",
         "rows": 43405, "unit": "firm-years", "date_range": "2000 – 2013",
         "retrieved_at": sums.get("polish_bankruptcy.parquet", {}).get("retrieved_at"),
         "used_for": "Financial-health pillar methodology check"},
    ]
    if not polish:
        rows[-1]["rows"] = None
    return rows


@router.get("/data-models")
def data_models(user: CurrentUser = Depends(require_roles("risk", "credit_officer", "rm"))) -> dict:
    """Provenance of every dataset, product and demo model metrics with CIs, and the real-world benchmarks."""
    s = get_settings()
    full = _load(REPORTS / "full" / "metrics.json")
    demo = _load(REPORTS / "metrics.json")
    sba = _load(REPORTS / "real_sba_benchmark.json")
    polish = _load(REPORTS / "real_polish_benchmark.json")
    product = None
    if full:
        product = {
            "provenance": SYNTH, "dataset": full["dataset"], "design": full["design"], "test": _metric(full["test"]),
            "fold_auc_mean": full["fold_auc_mean"], "fold_auc_sd": full["fold_auc_sd"],
            "expected_calibration_error": full["expected_calibration_error"], "calibration": full["calibration"],
            "operating_point": full["operating_point"], "band_default_rate": full["band_default_rate"],
            "sector_holdout": [{"group": h["held_out"], **_metric(h, ("auc",))} for h in full["sector_holdout"]],
            "cluster_holdout": [{"group": h["held_out"], **_metric(h, ("auc",))} for h in full["cluster_holdout"]],
            "shock": [{"group": h["period"], **_metric(h, ("auc",))} for h in full["shock"]],
            "ablation": full["ablation"],
            "leakage_audit": {k: full["leakage_audit"].get(k) for k in (
                "passed", "factory_months_checked", "shuffled_label_auc", "shuffled_label_runs", "shuffled_label_passed",
                "domain_prior_auc")},
            "ews": {"chosen": full["ews"]["chosen"], "rule": full["ews"]["rule"],
                    "operating_points": full["ews"]["operating_points"]},
        }
    benchmarks = []
    for key, r in (("sba", sba), ("polish", polish)):
        if r:
            benchmarks.append({"key": key, "dataset": r["dataset"], "provenance": REAL, "purpose": r["purpose"],
                               "licence": r.get("licence") or "Public domain", "test": _metric(r["test"]),
                               "label": r.get("label"), "calibration": r.get("calibration"),
                               "state_holdout": _metric(r.get("state_holdout"), ("auc",)) if r.get("state_holdout") else None})
    return {
        "dataset_in_use": {"name": s.dataset, "factories": s.n_factories, "months": s.n_months},
        "provenance": provenance(),
        "product_model": product,
        "demo_model": {"provenance": "Synthetic", "test": demo["test"], "train": demo["train"],
                       "note": "Live walkthrough model: 500 factories, 121 test defaults, so wide intervals."} if demo else None,
        "real_benchmarks": benchmarks,
        "benchmark_caption": BENCHMARK_CAPTION,
        "never_blended": True,
    }
