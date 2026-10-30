# UdyamPulse — one-command local demo. No cloud credentials or API keys needed.
SHELL := /bin/bash
PY_BOOT ?= $(shell command -v python3.11 || command -v python3.12 || command -v python3)
VENV := .venv
PY := $(VENV)/bin/python
export MLFLOW_DISABLE_AGENT_HINT := 1

.PHONY: help setup data lake train backtest seed pipeline api web demo test lint openapi clean

help:  ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

$(VENV)/.installed: requirements.txt
	$(PY_BOOT) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt
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

test: $(VENV)/.installed  ## Run pytest
	$(PY) -m pytest -q

lint: $(VENV)/.installed  ## Ruff + TypeScript checks
	$(VENV)/bin/ruff check .
	cd web && npx tsc -b --noEmit

openapi: $(VENV)/.installed  ## Export the OpenAPI spec to docs/openapi.json
	$(PY) -c "import json; from api.main import app; print(json.dumps(app.openapi(), indent=2))" > docs/openapi.json

clean:  ## Remove generated data, models and DB
	rm -rf lake/bronze lake/silver lake/gold var ml/artifacts ml/mlruns
