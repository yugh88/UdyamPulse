# Architecture

![UdyamPulse architecture](images/architecture.png)

Rendered images: [`images/architecture.png`](images/architecture.png) · [`images/loan_lifecycle.png`](images/loan_lifecycle.png)
(SVG versions alongside). Sources: [`diagrams/`](diagrams/) — regenerate with
`npx -p @mermaid-js/mermaid-cli mmdc -i docs/diagrams/<name>.mmd -o docs/images/<name>.png -c docs/diagrams/mermaid-config.json`.

## 1. System architecture

```mermaid
flowchart TB
    subgraph SRC["1 · DATA SOURCES (consent-based)"]
        GST["GST e-invoice<br/>& e-way bills"]
        AA["Account Aggregator<br/>bank statements"]
        ERP["Tally / D365<br/>Business Central"]
        PWR["Electricity bills<br/>(production proxy)"]
        PO["POs, invoices<br/>(IoT in v2)"]
    end

    subgraph ING["2 · INGEST & TRUST"]
        CON["AA + GST connectors<br/>(sandbox mocks, FIU-style consent)"]
        API["API gateway<br/>(FastAPI · Azure APIM in prod)"]
        OCR["Doc parser<br/>(Azure AI Document Intelligence adapter)"]
    end

    subgraph DML["3 · DATA & ML (Databricks-style medallion)"]
        BR["Bronze: raw events"]
        SV["Silver: cleaned, reconciled"]
        GD["Gold: monthly factory features (60+)"]
        MOD["LightGBM PD model<br/>+ SHAP reasons"]
        EWS["EWS rules + Isolation Forest"]
        FC["Cash-flow forecast (Prophet)"]
        REG["MLflow registry + drift check"]
    end

    subgraph AGT["4 · AGENT LAYER (Semantic Kernel · Azure OpenAI adapter)"]
        ORC["Orchestrator agent"]
        DA["Data agent"]
        CMA["Credit-memo agent<br/>(RAG over bank policy)"]
        EWA["Early-warning agent"]
        ADV["MSME advisor agent"]
    end

    subgraph EXP["5 · EXPERIENCE"]
        RM["RM / credit console<br/>(React · D365 CRM in prod)"]
        DASH["Portfolio risk cockpit<br/>(React charts · Power BI in prod)"]
        APP["MSME app (PWA)<br/>+ WhatsApp-style notifications"]
        LOS["LOS / core banking<br/>REST stubs"]
    end

    GOV["SECURITY & GOVERNANCE: auth (Entra ID in prod) · secrets (Key Vault) · consent ledger · audit log · data stays in India region"]

    SRC --> ING --> DML --> AGT --> EXP
    MOD --> CMA
    EWS --> EWA
    FC --> ADV
    GOV -.-> ING
    GOV -.-> DML
    GOV -.-> AGT
```

## 2. Loan-lifecycle flowchart (what the demo walks through)

![Loan lifecycle](images/loan_lifecycle.png)

```mermaid
flowchart TD
    A([MSME applies: app / WhatsApp / RM]) --> B[Consent via Account Aggregator + GST]
    B --> C[Data agent pulls, cleans, reconciles]
    C --> D[Factory Health Score 300–900 + top-5 reasons]
    D --> E{Score ≥ 650?}
    E -- NO --> F[Advisor agent: 90-day fix plan]
    F -. re-apply .-> A
    E -- YES --> G[Credit-memo agent: limit, pricing, risks, policy citations]
    G --> H[Credit officer reviews & approves: human-in-loop]
    H --> I[Disburse via LOS / core banking stub]
    I --> J[Early-warning agent: daily monitoring]
    J --> K{Stress signal?}
    K -- NO --> J
    K -- YES --> L[Alert RM + next-best action: call · visit · limit review · restructure]
```

## 3. How the layers map to code

| Layer | Prototype (local default) | Code | Production adapter (behind a Protocol) |
|---|---|---|---|
| Data sources | Synthetic generator, 500 factories × 24 months, fixed seed | `data_gen/generate.py` | AA (ReBIT FIU APIs), GSTN/IRP, e-way bill, DISCOM, Tally/BC connectors |
| Ingest & trust | Mock AA consent artefacts + ledger; regex doc parser | `agents/providers/consent.py`, `docparser.py` | `SahamatiAAConsentProvider`, `AzureDocIntelParser` |
| Bronze → silver | Parquet + DuckDB SQL (dedupe, calendar spine, reconciliation) | `data_gen/lake.py` | Azure Databricks + Delta Lake + Unity Catalog (`DatabricksLakeStore`) |
| Gold features | 67 features, 1/3/6/12-month windows, five pillars | `ml/features.py` | Databricks feature tables |
| PD model | LightGBM + TreeSHAP, time split, score 300–900 | `ml/train.py`, `ml/scoring.py` | Databricks MLflow registry |
| Early warning | YAML rules + IsolationForest + lead-time back-test | `ml/ews.py`, `ml/rules.yaml` | Same code on Databricks Jobs |
| Forecast | Prophet (offline fallback) | `ml/forecast.py` | — |
| Agents | Typed classes; every tool call audited | `agents/*.py` | Semantic Kernel + Azure OpenAI / Foundry Agent Service |
| LLM | Deterministic template writer (no keys needed) | `agents/providers/llm.py` | `SemanticKernelLLM` (Azure OpenAI), guarded by `agents/guard.py` |
| RAG | TF-IDF (or sentence-transformers) + FAISS over `policy/*.md` | `agents/providers/search.py` | Azure AI Search hybrid (`AzureAISearch`) |
| API | FastAPI + Pydantic v2, JWT roles | `api/` | Azure API Management + Entra ID |
| OLTP | SQLite via SQLAlchemy | `api/models/db.py` | Azure Database for PostgreSQL |
| Experience | React + Vite + Tailwind + Recharts; PWA | `web/` | Dynamics 365 CRM embed, Power BI Embedded |

Every provider is selected by an environment variable (`UP_LLM_PROVIDER`, `UP_SEARCH_PROVIDER`,
`UP_DOC_PARSER`, `UP_CONSENT_PROVIDER`, `UP_LAKE_STORE`, `UP_EMBEDDINGS`); the default is always local.

## 4. Loan-journey state machine

`APPLIED → CONSENTED → SCORED → MEMO_DRAFTED → DECIDED → DISBURSED → MONITORING`
(`agents/orchestrator.py`). Invalid transitions return **409**; actions without active consent return **403**.

## 5. Simulated clock

The panel covers Nov 2024 – Oct 2026. The demo starts on **30 Jun 2026** with data visible through month 20.
`POST /sim/advance?days=N` moves the clock; the early-warning agent then processes every newly visible month
for monitored accounts (only those with active consent).

## 6. Guardrails that are enforced in code

- **No invented numbers:** memo and briefing numbers come from `build_facts` / the scoring engine; LLM output
  containing any number absent from the facts is rejected (`agents/guard.py`, `tests/test_memo.py`).
- **Human decision:** only `credit_officer` can call `/decision`; a comment is mandatory.
- **Consent gate:** every data pull goes through `authorise_pull`; revocation blocks pulls and runs a deletion job.
- **Audit:** every tool call writes agent, tool, PII-masked inputs, output SHA-256, user and timestamp.
- **Residency:** the API refuses to start if `UP_DATA_REGION` is a non-India cloud region.
