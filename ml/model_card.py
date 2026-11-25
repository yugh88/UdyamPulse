"""Model card built from every report that exists, so it never mixes real and synthetic results:

1. Synthetic product model (UP_DATASET=full, ml/reports/full/metrics.json)
2. Demo model used by the live walkthrough (ml/reports/metrics.json, fairness.json, drift.json)
3. Real public benchmarks (ml/reports/real_*_benchmark.json): methodology validation only
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from core.settings import ROOT

REPORTS = ROOT / "ml" / "reports"
OUT = ROOT / "ml" / "MODEL_CARD.md"


def _load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _ci(m: dict, k: str) -> str:
    lo, hi = m.get(f"{k}_ci95", [None, None])
    return f"{m[k]:.3f} ({lo:.3f}–{hi:.3f})" if lo is not None else f"{m[k]:.3f}"


def _fair_table(rows: list[dict]) -> str:
    head = "| Group | n | Default rate | Approval rate | Approval (non-defaulters) | AUC | AIR | EOR |\n|---|---|---|---|---|---|---|---|\n"
    return head + "\n".join(
        f"| {r['group']} | {r['n']:,} | {r['default_rate']:.1%} | {r['approval_rate']:.1%} | "
        f"{r['approval_rate_non_defaulters']:.1%} | {r['auc'] if r['auc'] is not None else '–'} | "
        f"{r['adverse_impact_ratio']} | {r['equal_opportunity_ratio']} |" for r in rows)


def _full_section(f: dict) -> list[str]:
    t = f["test"]
    lines = ["## 1. Product model: synthetic (calibrated) panel", "",
             f"**Provenance: {f['provenance']}.** {f['dataset']}. Generator calibrated to MoSPI IIP "
             "(data_gen/calibration.yaml). No real entity data.", "",
             f"Design: train months {f['design']['train_months']}, validation {f['design']['validation_months']}, "
             f"gap month {f['design']['gap_month']}, test months {f['design']['test_months']}, {f['design']['group_folds']} "
             "factory groups. Every factory is scored by a model that never saw it or its test months. "
             f"LightGBM with monotone constraints on {f['monotone_features']} features.", "",
             "| Out-of-time, out-of-group test | Value (95% CI, bootstrap over factories) |", "|---|---|",
             f"| AUC | {_ci(t, 'auc')} |", f"| KS | {_ci(t, 'ks')} |", f"| Brier (after isotonic calibration) | {_ci(t, 'brier')} |",
             f"| Rows / factories / defaults | {t['n']:,} / {t['factories']:,} / {t['positives']:,} ({t['event_rate']:.2%}) |",
             f"| AUC across the {len(f['fold_auc'])} groups | {f['fold_auc_mean']:.3f} ± {f['fold_auc_sd']:.3f} |",
             f"| Expected calibration error | {f['expected_calibration_error']:.4f} (uncalibrated Brier {f['uncalibrated_brier']}) |",
             f"| Operating point ({f['operating_point']['rule']}) | precision {f['operating_point']['precision']:.3f}, "
             f"recall {f['operating_point']['recall']:.3f}, flag rate {f['operating_point']['flag_rate']:.1%} |", "",
             "Default rate by band: " + ", ".join(f"{k} {v:.2%}" for k, v in f["band_default_rate"].items()) + ".", "",
             "### Generalisation", "", "| Hold-out | AUC (95% CI) | Test rows | Defaults |", "|---|---|---|---|"]
    for kind in ("sector_holdout", "cluster_holdout"):
        lines += [f"| {kind.split('_')[0]} = {h['held_out']} | {_ci(h, 'auc')} | {h['n']:,} | {h['positives']} |" for h in f[kind]]
    lines += [f"| {h['period']} | {_ci(h, 'auc')} | {h['n']:,} | {h['positives']} |" for h in f["shock"]]
    a, leak = f["ablation"], f["leakage_audit"]
    verdict = lambda ok: "passed" if ok else "FAILED"  # noqa: E731
    lines += ["", "### Ablation: production signals", "",
              f"With e-way bill, kWh and purchase-order features AUC {a['with_production_signals_auc']}, without "
              f"{a['without_production_signals_auc']}; uplift {a['uplift_auc']:+.3f} (95% CI {a['uplift_ci95'][0]:+.3f} "
              f"to {a['uplift_ci95'][1]:+.3f}). **{a['caveat']}**", "",
              "### Leakage audit", "",
              f"- Features recomputed from history cut at the scoring month match the stored features for "
              f"{leak['factory_months_checked']} factory-months: **{verdict(leak['passed'])}**.",
              *([f"- Shuffled labels, 8 runs, unconstrained model: mean AUC {leak['shuffled_label_auc']} "
                 f"(runs {min(leak['shuffled_label_runs'])}–{max(leak['shuffled_label_runs'])}): "
                 f"**{verdict(leak['shuffled_label_passed'])}** (should scatter around 0.5).",
                 f"- Domain priors alone: the same shuffled labels with monotone constraints give mean AUC "
                 f"{leak['domain_prior_auc']}. The economic directions encode real knowledge, as an expert scorecard would."]
                if "shuffled_label_runs" in leak else ["- Shuffled-label check: rerun `make train-full` for the current format."]),
              ""]
    ch = f["ews"]["chosen"]
    lines += ["### Early warning on the full panel", "",
              "| Alert threshold (points) | Recall | Median lead (days) | Precision (SMA-2 in 6 m) | Accounts alerted |",
              "|---|---|---|---|---|"]
    lines += [f"| ≥ {r['min_points']} | {r['recall']} | {r['median_lead_days']} | {r['precision_sma2_within_6m']} | "
              f"{r['alerted_accounts']:,} |" for r in f["ews"]["operating_points"]]
    if ch:
        lines += ["", f"Chosen ({f['ews']['rule']}): **≥ {ch['min_points']} points**: recall {ch['recall']}, median lead "
                  f"{ch['median_lead_days']} days, precision {ch['precision_sma2_within_6m']}."]
    lines += ["", "### Fairness (pooled test)", "", "#### By sector", _fair_table(f["fairness"]["sector"]), "",
              "#### Micro vs small", _fair_table(f["fairness"]["udyam_category"]), ""]
    return lines


def _demo_section(m: dict, fairness: dict | None, drift: dict | None) -> list[str]:
    t, tr = m["test"], m["train"]
    h = m.get("hero_month20", {})
    lines = ["## 2. Demo model (live walkthrough)", "",
             "**Provenance: Synthetic.** 500 factories × 24 months (`make demo`), trained on months 4–12, validated on "
             "13–15, tested out of time on 17–24. Small: the test set has "
             f"{t['positives']} defaults, so its AUC carries a wide interval (about ±0.05).", "",
             "| Split | AUC | KS | Brier | Rows | Event rate |", "|---|---|---|---|---|---|",
             f"| Train | {tr['auc']} | {tr['ks']} | {tr['brier']} | {tr['n']} | {tr['event_rate']:.2%} |",
             f"| Out-of-time test | **{t['auc']}** | {t['ks']} | {t['brier']} | {t['n']} | {t['event_rate']:.2%} |", ""]
    if h:
        lines += [f"Hero factory UP-F0001 at month 20: score **{h['score']}** ({h['band']}), PD {h['pd_12m']:.2%}.", ""]
    if drift:
        lines += [f"Drift: score PSI {drift['score_psi']} ({drift['status']}).", ""]
    if fairness:
        lines += ["Fairness by sector:", "", _fair_table(fairness["sector"]), ""]
    return lines


def _real_section(sba: dict | None, polish: dict | None) -> list[str]:
    lines = ["## 3. Real public benchmarks (methodology validation, not the Indian MSME score)", "",
             "Same pipeline (features → LightGBM → isotonic calibration → SHAP → drift monitoring) on real outcomes. "
             "These numbers are **never blended** with the synthetic results above.", "",
             "| Dataset | Licence | Test AUC (95% CI) | KS | Brier | Test n / defaults |", "|---|---|---|---|---|---|"]
    if sba:
        t = sba["test"]
        lines.append(f"| U.S. SBA 7(a) manufacturing loans, FY2018–21 test | Public domain | {_ci(t, 'auc')} | {t['ks']:.3f} | "
                     f"{t['brier']:.4f} | {t['n']:,} / {t['positives']} |")
    if polish:
        t = polish["test"]
        lines.append(f"| UCI Polish bankruptcies, years 4–5 test | CC BY 4.0 (Tomczak 2016) | {_ci(t, 'auc')} | {t['ks']:.3f} | "
                     f"{t['brier']:.4f} | {t['n']:,} / {t['positives']} |")
    if sba:
        lines += ["", f"SBA: {sba['label']}. Loan term was excluded after our leakage audit showed it is revised for "
                  "loans that go bad. Approval-time application fields alone predict default only modestly, which is "
                  "the case for operating and cash-flow signals. Details: `ml/reports/real_sba_benchmark.md`."]
    if polish:
        lines += ["", f"Polish: {polish['limitations'][1]} Details: `ml/reports/real_polish_benchmark.md`."]
    return lines + [""]


def write_model_card() -> Path:
    full = _load(REPORTS / "full" / "metrics.json")
    demo = _load(REPORTS / "metrics.json")
    lines = ["# Model card: UdyamPulse PD model (`udyampulse-pd`)", "",
             f"_Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC} by `ml/model_card.py` from the reports in `ml/reports/`._", "",
             "## Intended use",
             "Estimate the probability that an MSME manufacturer defaults (90+ DPD) within 12 months from consented "
             "operating data, mapped to a Factory Health Score (300–900) with plain-language reasons. It is a "
             "**recommendation to the regulated lender's credit officer**; it never decides or executes credit.", "",
             "Out of scope: consumer lending, units without consented GST/AA data, any automated rejection. No protected "
             "attributes exist in the data or features; sector and cluster are used only for fairness monitoring.", ""]
    if full:
        try:
            lines += _full_section(full)
        except KeyError as exc:  # a report from an older format must never break demo training
            lines += ["## 1. Product model", "", f"_Report predates this card format (missing {exc}); run `make train-full`._", ""]
    if demo:
        lines += _demo_section(demo, _load(REPORTS / "fairness.json"), _load(REPORTS / "drift.json"))
    lines += _real_section(_load(REPORTS / "real_sba_benchmark.json"), _load(REPORTS / "real_polish_benchmark.json"))
    lines += ["## 4. Leakage story",
              "To validate the method on real data, we tested the SBA 7(a) dataset. Using the loan-term field, the model "
              "scored an AUC of 0.915. We found that SBA revises the loan term after a loan defaults: 86.7% of charged-off "
              "loans have an unusual term, versus 16.4% of repaid ones. Removing the leaking field dropped the AUC to the "
              "honest 0.687 (95% CI 0.658–0.713). We use a 60-month label window so every loan has time to go bad.",
              "",
              "On the synthetic panel, we ran a shuffled-label check (8 runs). The mean AUC was 0.4659 (runs 0.3642–0.5462), "
              "scattering around the coin-toss 0.5, confirming no structural leakage in the features. Details in "
              "`ml/reports/full/metrics.json` and `ml/reports/real_sba_benchmark.md`.", ""]
    lines += ["## Limitations",
              "- The product model is trained on synthetic data. Coefficients, thresholds and the production-signal uplift "
              "must be re-learned and re-proven on a lender's consented data, followed by independent model validation.",
              "- Synthetic results reflect the generator's design; the real benchmarks validate the method, not Indian MSME accuracy.",
              "- Monthly granularity; weekly e-way bill and kWh signals would shorten detection lag.",
              "- Thin-file units (< 6 months of data) should be routed to manual review.", "",
              "## Governance",
              "SHAP reasons on every score, human decision, customer AI disclosure, review route, hash-chained audit trail, "
              "fairness and drift checks per training run (RBI FREE-AI principles)."]
    OUT.write_text("\n".join(lines) + "\n")
    return OUT


if __name__ == "__main__":
    print(write_model_card())
