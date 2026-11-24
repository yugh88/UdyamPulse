erDiagram
    %% Core Relationships
    tenants ||--o{ users : "tenant_id"
    tenants ||--o{ applications : "tenant_id"
    tenants ||--o{ consents : "tenant_id"
    tenants ||--o{ consent_ledger : "tenant_id"
    tenants ||--o{ data_snapshots : "tenant_id"
    tenants ||--o{ alerts : "tenant_id"
    tenants ||--o{ notifications : "tenant_id"
    tenants ||--o{ audit_log : "tenant_id"
    tenants ||--o{ ai_usage : "tenant_id"
    tenants ||--o{ plan_progress : "tenant_id"
    tenants ||--o{ jobs : "tenant_id"
    tenants ||--o{ outbox : "tenant_id"
    tenants ||--o{ change_events : "tenant_id"
    tenants ||--o{ user_seen : "tenant_id"
    tenants ||--o{ refresh_tokens : "tenant_id"

    applications ||--o{ consents : "application_id"
    applications ||--o{ data_snapshots : "application_id"
    applications ||--o{ alerts : "application_id"
    applications ||--o{ jobs : "application_id"
    applications ||--o{ change_events : "application_id"

    batch_runs ||--o{ batch_chunks : "run_id"

    %% Table Definitions
    tenants {
        string id PK
        string name
        timestamp change_baseline_at
    }

    users {
        int id PK
        string username UK
        string display_name
        string role
        string password_hash
        string factory_id
        string branch
        string tenant_id FK
    }

    applications {
        int id PK
        string factory_id
        string state
        string channel
        float requested_amount
        int score
        string band
        float pd_12m
        int score_month
        json score_detail
        json data_checks
        json memo
        string memo_pdf
        float recommended_limit
        string pricing_band
        string decision
        text decision_comment
        string decided_by
        timestamp decided_at
        json kfs
        float sanctioned_limit
        string disbursement_ref
        date disbursed_on
        int last_ews_month
        boolean review_requested
        text review_note
        json plan_cache
        timestamp created_at
        timestamp updated_at
        string tenant_id FK
        string cluster
    }

    account_scores {
        string tenant_id PK
        string factory_id PK
        date month_date PK
        int month
        int application_id
        int score
        string band
        float pd_12m
    }

    alerts {
        int id PK
        int application_id FK
        string factory_id
        int month
        string severity
        json rules
        json reasons
        string next_best_action
        text briefing
        string status
        string action_taken
        text action_note
        string actioned_by
        string outcome
        string owner
        string acknowledged_by
        timestamp acknowledged_at
        date raised_on
        timestamp created_at
        string tenant_id FK
    }

    consents {
        string id PK
        int application_id FK
        string factory_id
        string purpose
        json fi_types
        date data_from
        date data_to
        date expires_on
        string frequency
        string status
        timestamp granted_at
        timestamp revoked_at
        string tenant_id FK
    }

    consent_ledger {
        int id PK
        string consent_id
        string factory_id
        string event
        json detail
        string actor
        timestamp ts
        string tenant_id FK
    }

    data_snapshots {
        int id PK
        int application_id FK
        string factory_id
        int upto_month
        text payload
        timestamp pulled_at
        string tenant_id FK
    }

    notifications {
        int id PK
        string factory_id
        string channel
        text text
        text text_hi
        date sim_date
        timestamp created_at
        string tenant_id FK
    }

    audit_log {
        int id PK
        timestamp ts
        string user
        string role
        string agent
        string tool
        string action
        int application_id
        json inputs
        string output_hash
        string tenant_id FK
        int chain_seq
        string prev_hash
        string row_hash
    }

    ai_usage {
        int id PK
        timestamp ts
        string agent
        string template_id
        string provider
        float latency_ms
        int tokens_est
        boolean fallback
        string user
        int application_id
        string tenant_id FK
        string outcome
    }

    plan_progress {
        int id PK
        string factory_id
        string step_key
        timestamp done_at
        string tenant_id FK
    }

    jobs {
        string id PK
        string kind
        string status
        int progress
        string message
        json params
        json result
        text error
        int attempts
        string created_by
        string role
        int application_id
        timestamp created_at
        timestamp started_at
        timestamp finished_at
        timestamp updated_at
        string tenant_id FK
    }

    outbox {
        int id PK
        string topic
        json payload
        timestamp created_at
        timestamp published_at
        int attempts
        text last_error
        string tenant_id FK
    }

    batch_runs {
        string id PK
        string kind
        int month
        int shards
        int chunk_size
        string status
        int total_accounts
        int total_chunks
        json stats
        text error
        timestamp started_at
        timestamp finished_at
    }

    batch_chunks {
        string run_id FK
        int chunk_no PK
        int shard
        int accounts
        int alerts
        float seconds
        string worker
        timestamp finished_at
    }

    refresh_tokens {
        string id PK
        string family_id
        string username
        string token_hash
        timestamp issued_at
        timestamp expires_at
        timestamp used_at
        timestamp revoked_at
        string replaced_by
        string tenant_id FK
    }

    change_events {
        int id PK
        string entity_type
        string entity_id
        int application_id
        string event_type
        json before
        json after
        string summary
        string actor
        timestamp created_at
        string tenant_id FK
    }

    user_seen {
        int id PK
        string username
        string entity_type
        string entity_id
        timestamp last_seen_at
        string tenant_id FK
    }

    sim_clock {
        int id PK
        date current_date
    }