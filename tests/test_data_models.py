"""Governance "Data & Models": provenance of every dataset and separately reported real vs synthetic results."""

from __future__ import annotations

from core.settings import ROOT
from tests.conftest import login


def test_data_models_lists_provenance_and_keeps_real_and_synthetic_apart(client):
    r = client.get("/data-models", headers=login(client, "risk1"))
    assert r.status_code == 200, r.text
    d = r.json()
    kinds = {p["provenance"] for p in d["provenance"]}
    assert {"Real public data", "Synthetic (calibrated)", "Synthetic"} <= kinds
    assert all(p["licence"] and p["source"] for p in d["provenance"])
    assert d["never_blended"] is True and "pilot" in d["benchmark_caption"]
    assert d["dataset_in_use"]["name"] == "demo"
    keys = {b["key"] for b in d["real_benchmarks"]}
    assert keys == {"sba", "polish"}
    for b in d["real_benchmarks"]:
        assert b["provenance"] == "Real public data" and b["test"]["auc_ci95"][0] <= b["test"]["auc"]
    if (ROOT / "ml" / "reports" / "full" / "metrics.json").exists():
        pm = d["product_model"]
        assert pm["provenance"] == "Synthetic (calibrated)"
        lo, hi = pm["test"]["auc_ci95"]
        assert lo <= pm["test"]["auc"] <= hi
        assert len(pm["sector_holdout"]) == 5 and pm["leakage_audit"]["passed"]


def test_data_models_is_staff_only(client):
    assert client.get("/data-models", headers=login(client, "sharma")).status_code == 403
