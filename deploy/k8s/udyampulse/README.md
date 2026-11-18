# Kubernetes (AKS, Central India)

```bash
# Secrets come from Azure Key Vault (CSI driver or External Secrets) into one Kubernetes Secret:
#   UP_DB_URL, UP_REDIS_URL, UP_JWT_SECRET, UP_FIELD_KEYS, UP_METRICS_TOKEN
helm upgrade --install udyampulse deploy/k8s/udyampulse -f deploy/k8s/udyampulse/values-prod.yaml -n udyampulse
```

What the chart sets up:

| Piece | Behaviour |
|---|---|
| Migrations | `pre-install` / `pre-upgrade` hook runs Alembic before new pods start |
| API | 3–20 pods, HPA on CPU (65 %), PDB `minAvailable: 2`, zone spread, `/healthz` liveness, `/readyz` readiness, 5 s pre-stop drain |
| Workers | KEDA scales 2–30 pods on `udyam_job_queue_depth{status="queued"}` (20 queued jobs per worker), PDB, 120 s grace so running jobs finish |
| Web | nginx SPA + `/api` proxy to the release's API service, PDB |
| Security | non-root, read-only root filesystem, all capabilities dropped, seccomp `RuntimeDefault`, default-deny ingress network policies, no service-account token unless workload identity needs it |
| Observability | Prometheus scrape annotations (API :8000/metrics, worker :9191), optional ServiceMonitor with the metrics token, OTLP endpoint in values |

The application refuses to start if `UP_ENV=production` is combined with demo secrets, SQLite, a missing
Redis or field key, or a non-India `UP_DATA_REGION` (`core/settings.py`).

Validated in CI-like fashion with `helm lint`, `helm template` and `kubeconform -strict` (Kubernetes 1.30 schemas).
