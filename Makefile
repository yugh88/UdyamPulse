# UdyamPulse — one-command local demo. No cloud credentials or API keys needed.
SHELL := /bin/bash
PY_BOOT ?= $(shell command -v python3.11 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
export MLFLOW_DISABLE_AGENT_HINT := 1

.PHONY: help setup data lake train backtest seed pipeline api web demo demo-lite test test-web test-pg test-full pg-up pg-down redis-up redis-down up down e2e lint openapi clean security deploy-check data-real bench-real data-full train-full

help:  ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

$(VENV)/.installed: requirements.txt requirements-train.txt
	$(PY_BOOT) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-train.txt
	touch $@

web/node_modules/.installed: web/package.json
	cd web && npm ci --no-audit --no-fund
	touch $@

setup: $(VENV)/.installed web/node_modules/.installed  ## Install Python + web dependencies

data: $(VENV)/.installed  ## 1. Generate synthetic bronze data (500 factories x 24 months)
	$(PY) -m data_gen.generate

lake: $(VENV)/.installed  ## 2. Build silver (DuckDB) and gold (60+ features)
	$(PY) -m data_gen.lake

train: $(VENV)/.installed  ## 3. Train LightGBM PD model, SHAP, fairness, drift, model card
	$(PY) -m ml.train

backtest: $(VENV)/.installed  ## 4. EWS rules + IsolationForest + lead-time back-test
	$(PY) -m ml.ews

seed: $(VENV)/.installed  ## 5. Seed the demo database
	$(PY) -m api.seed

pipeline: data lake train backtest seed  ## Steps 1-5

data-real: $(VENV)/.installed  ## Fetch real public datasets (SBA 7(a), UCI Polish, MoSPI IIP): resumable, checksummed
	$(PY) -m data_real.fetch_sba
	$(PY) -m data_real.fetch_uci
	$(PY) -m data_real.fetch_india
	$(PY) -m data_gen.calibrate

data-full: $(VENV)/.installed  ## Build the 50,000-factory x 36-month calibrated panel into lake_full/ (~2-3 min)
	UP_DATASET=full $(PY) -m data_gen.build

train-full: $(VENV)/.installed  ## Product model on the full panel: group+time CV, hold-outs, ablation, leakage audit, EWS
	UP_DATASET=full $(PY) -m ml.ews
	UP_DATASET=full $(PY) -m ml.train_full

bench-real: $(VENV)/.installed  ## Real-data methodology benchmarks with bootstrap CIs (needs data-real)
	$(PY) -m ml.benchmark_real

api: $(VENV)/.installed  ## Run the API on :8000
	$(VENV)/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000

web: web/node_modules/.installed  ## Run the web app on :5173
	cd web && npm run dev

demo: setup pipeline  ## Everything: build data/model, seed, start API + web at http://localhost:5173
	@echo ""
	@echo "  UdyamPulse → http://localhost:5173   (API docs: http://localhost:8000/docs)"
	@echo "  Logins (password demo123): rm1 · co1 · risk1 · sharma"
	@echo ""
	@trap 'kill 0' EXIT INT TERM; \
	  $(VENV)/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 & \
	  (cd web && npm run dev -- --strictPort) & \
	  wait

demo-lite: demo  ## Same as demo: SQLite, no Docker, no services

test: $(VENV)/.installed  ## Run pytest (SQLite)
	$(PY) -m pytest -q

pg-up:  ## Start a project-local PostgreSQL on :55432 (data in var/pg, non-superuser app role)
	@bash ops/postgres/local.sh up

pg-down:  ## Stop the project-local PostgreSQL
	@bash ops/postgres/local.sh down

redis-up:  ## Start a project-local Redis on :56379 (no persistence)
	@redis-cli -p 56379 ping >/dev/null 2>&1 || redis-server --port 56379 --bind 127.0.0.1 --save "" --appendonly no --daemonize yes --dir $(CURDIR)/var --logfile $(CURDIR)/var/redis.log
	@echo "Redis ready: redis://127.0.0.1:56379/0"

redis-down:  ## Stop the project-local Redis
	@redis-cli -p 56379 shutdown nosave >/dev/null 2>&1 || true

test-full: $(VENV)/.installed pg-up redis-up  ## Run pytest against PostgreSQL and Redis
	UP_TEST_DB_URL=postgresql+psycopg://udyam_app@127.0.0.1:55432/udyampulse_test UP_TEST_REDIS_URL=redis://127.0.0.1:56379/15 $(PY) -m pytest -q

test-pg: $(VENV)/.installed pg-up  ## Run pytest against PostgreSQL (migrations, partitions, row-level security)
	UP_TEST_DB_URL=postgresql+psycopg://udyam_app@127.0.0.1:55432/udyampulse_test $(PY) -m pytest -q

up:  ## Full stack in Docker: PostgreSQL, Redis, API, worker, web on http://localhost:5173 (UP_WEB_PORT to change)
	docker compose up -d --build
	@echo "  UdyamPulse (full stack) → http://localhost:$${UP_WEB_PORT:-5173}"

down:  ## Stop the Docker stack (add -v by hand to also delete its database volume)
	docker compose down

lint: $(VENV)/.installed web/node_modules/.installed  ## Ruff, ESLint, Prettier, TypeScript and contrast checks
	$(VENV)/bin/ruff check .
	cd web && npx tsc -b --noEmit && npm run lint && npm run format:check && npm run check:contrast

security: $(VENV)/.installed web/node_modules/.installed  ## Secret scan, dependency audits and bandit (as CI)
	docker run --rm -v "$(CURDIR):/repo" zricethezav/gitleaks:v8.28.0 git /repo --redact --no-banner
	$(VENV)/bin/pip install -q pip-audit==2.10.1 bandit==1.9.4
	$(VENV)/bin/pip-audit -r requirements.txt --progress-spinner off --strict
	$(VENV)/bin/bandit -q -r api agents core worker ml data_gen
	cd web && npm audit --audit-level=moderate

deploy-check:  ## Validate the Helm chart (kubeconform) and Terraform, using Docker images
	docker run --rm -v "$(CURDIR)/deploy/k8s/udyampulse:/chart" alpine/helm:3.18.4 lint /chart
	docker run --rm -v "$(CURDIR)/deploy/k8s/udyampulse:/chart" alpine/helm:3.18.4 template up /chart -f /chart/values-prod.yaml > var/rendered.yaml
	docker run --rm -v "$(CURDIR)/var:/w" ghcr.io/yannh/kubeconform:v0.7.0 -strict -summary -ignore-missing-schemas -kubernetes-version 1.30.0 /w/rendered.yaml
	docker run --rm -v "$(CURDIR)/deploy/terraform:/tf" -w /tf -e TF_DATA_DIR=/tmp/tf --entrypoint sh hashicorp/terraform:1.12.2 -c "terraform fmt -check && terraform init -backend=false -input=false >/dev/null && terraform validate"

test-web: web/node_modules/.installed  ## Web unit tests (Vitest)
	cd web && npm test

e2e: $(VENV)/.installed web/node_modules/.installed  ## Browser tests on an isolated stack (Playwright + axe)
	cd web && npx playwright install chromium && npm run e2e

openapi: $(VENV)/.installed  ## Export the OpenAPI spec to docs/openapi.json
	$(PY) -c "import json; from api.main import app; print(json.dumps(app.openapi(), indent=2))" > docs/openapi.json

clean:  ## Remove generated data, models and DB
	rm -rf lake/bronze lake/silver lake/gold var ml/artifacts ml/mlruns
