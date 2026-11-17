# syntax=docker/dockerfile:1
# Free public demo: ONE container on a Hugging Face Docker Space (or Render / Koyeb / any Docker host).
# FastAPI serves the API and the built React app on one port. Lite profile: SQLite, in-process cache and
# worker, the 500-factory demo dataset, and the deterministic template writer, so no keys or services.
# The lake and model are built at image build time; startup only seeds the demo database (~5 s).

FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS deps
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt requirements-train.txt ./
RUN pip install -r requirements.txt

FROM deps AS build
RUN pip install -r requirements-train.txt
WORKDIR /app
COPY core core
COPY data_gen data_gen
COPY data_real data_real
COPY ml ml
ENV MLFLOW_DISABLE_AGENT_HINT=1
RUN python -m data_gen.generate && python -m data_gen.lake && python -m ml.train && python -m ml.ews && rm -rf ml/mlruns

FROM deps AS venv
RUN pip uninstall -y pip setuptools wheel >/dev/null 2>&1; \
    for pkg in pandas scipy sklearn numpy pyarrow matplotlib; do \
      find /opt/venv/lib/python3.11/site-packages/$pkg -type d \( -name tests -o -name testing_data \) -prune -exec rm -rf {} + ; \
    done

FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 user
# Hugging Face runs Spaces as uid 1000 and serves port 7860.
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1 \
    PORT=7860 UP_WEB_DIST=/app/web/dist UP_DB_URL=sqlite:////tmp/udyampulse.db UP_DATASET=demo \
    UP_DEMO_MODE=on UP_DATA_REGION=local UP_LLM_PROVIDER=template UP_COOKIE_SECURE=on \
    UP_FRAME_ANCESTORS="https://huggingface.co" UP_LOG_FORMAT=json
WORKDIR /app
COPY --from=venv /opt/venv /opt/venv
COPY --chown=user:user api api
COPY --chown=user:user agents agents
COPY --chown=user:user core core
COPY --chown=user:user worker worker
COPY --chown=user:user policy policy
COPY --chown=user:user migrations migrations
COPY --chown=user:user alembic.ini ./
COPY --chown=user:user data_gen data_gen
COPY --chown=user:user data_real/__init__.py data_real/common.py data_real/
COPY --chown=user:user data_real/checksums.json data_real/
COPY --from=build --chown=user:user /app/lake lake
COPY --from=build --chown=user:user /app/ml ml
COPY --from=web --chown=user:user /web/dist web/dist
RUN mkdir -p var && chown user:user var
USER user
EXPOSE 7860
HEALTHCHECK --interval=15s --timeout=3s --retries=20 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"7860\")}/healthz')"
# A fresh demo on every start: the free tier's disk is ephemeral anyway.
CMD ["sh", "-c", "python -m api.seed && exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
