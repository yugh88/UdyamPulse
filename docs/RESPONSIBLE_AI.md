# Responsible AI

UdyamPulse recommends; a person decides. This page lists how each responsible-AI principle shows up in the
code, with the file or test that proves it. ✅ Done · 🟡 Partial · 🔭 Future.

| Principle | What we do | Evidence | Status |
|---|---|---|---|
| **Explainability** | Every score comes with its top 5 reasons (TreeSHAP), written in plain language, plus points per pillar. The MSME owner sees the same reasons in English or Hindi. | `ml/scoring.py: explain_row`, `ml/i18n_hi.py` | ✅ |
| **Sensible behaviour** | Monotone constraints: more bounces, slower payments or falling dispatches can only lower a score. Checked on every constrained feature and on the simulator. | `ml/features.py: MONOTONE`, `tests/test_monotone.py` | ✅ |
| **Human in the loop** | Only the credit officer can approve or reject, with a written comment. The RM cannot decide; agents never decide. | `agents/orchestrator.py` state machine, `tests/test_api_roles_consent.py` | ✅ |
| **No protected attributes** | No gender, religion, caste or age anywhere in the data or features. Sector and cluster are used only to monitor fairness, never as inputs. | `data_gen/*`, `ml/features.py`, `tests/test_engine.py::test_no_protected_attributes` | ✅ |
| **Fairness testing** | Approval rate, adverse impact ratio and equal-opportunity ratio by sector and by micro/small, on every training run. | `ml/train.py: fairness_report`, model card | ✅ (synthetic) |
| **Drift monitoring** | PSI of the score and the top features between training and recent periods. | `ml/reports/drift.json` | ✅ |
| **Calibration and honest metrics** | Isotonic calibration; bootstrap 95% CIs (resampling factories); a leakage audit and a shuffled-label test; real and synthetic results never blended. | `ml/evaluate.py`, `ml/train_full.py`, `ml/benchmark_real.py` | ✅ |
| **LLM guardrails** | The LLM only rewrites prose. Numbers come from the scoring and policy engines, and any number not in the facts is rejected. Citations come from policy retrieval and are checked against the clause store. A deterministic template is the fallback for every failure. | `agents/guard.py`, `agents/providers/llm.py`, `tests/test_memo.py`, `tests/test_llm_resilience.py` | ✅ |
| **Disclosure** | Every AI-written text carries the label "AI-generated recommendation · final decision by credit officer". The AI usage log records the template, provider, outcome and latency of every LLM call. | `agents/memo_agent.py: AI_LABEL`, Governance → AI usage | ✅ |
| **Right to review** | The MSME owner can request a review of a decision; the request is recorded for the officer. | `POST /v1/applications/{id}/review-request`, `tests/test_p2_endpoints.py` | ✅ |
| **Consent and data minimisation** | Data is pulled only under an active consent; revocation blocks pulls and deletes snapshots. Public benchmarks drop borrower names and addresses. | `agents/providers/consent.py`, `data_real/fetch_sba.py` | ✅ |
| **Accountability** | A hash-chained audit trail records every API action and agent tool call, with inputs masked and outputs hashed. | `api/audit_chain.py`, `tests/test_audit_chain.py` | ✅ |
| **Model governance at scale** | Champion/challenger, scheduled retraining and independent model validation. | Described in `docs/DATA_STRATEGY.md` (pilot path) | 🔭 |

## Mapping to the RBI FREE-AI principles

The RBI's Framework for Responsible and Ethical Enablement of AI (FREE-AI) sets out seven "sutras". How the
prototype answers each:

| Sutra | How UdyamPulse answers it |
|---|---|
| Trust is the foundation | Synthetic-data and prototype banner on every screen; provenance badges; no overclaiming |
| People first | The officer decides; plain-language reasons; Hindi for MSME owners; review route |
| Innovation over restraint | Operating-signal credit for underserved manufacturers, with controls built in rather than bolted on |
| Fairness and equity | No protected attributes; fairness ratios per run; monotone, explainable behaviour |
| Accountability | Hash-chained audit; AI usage log; model card; human sign-off |
| Understandable by design | SHAP reasons on every score; cited memos; a what-if simulator labelled as a simulation |
| Safety, resilience and sustainability | LLM fallbacks and circuit breaker; drift and leakage checks; offline demo with no external dependency |

The sutra names above follow the published framework. Before using this table in a submission, check the
wording against the RBI's final text.
