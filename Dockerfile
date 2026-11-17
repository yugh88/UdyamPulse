# syntax=docker/dockerfile:1
# API and worker image. The synthetic lake, the trained model and the EWS back-test are built here, at image
# build time, so every API pod and worker runs the same model version and starts in seconds.

FROM python:3.11-slim AS deps
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# REQUIREMENTS=requirements-cloud.txt adds the hosted-LLM SDK (UP_LLM_PROVIDER=azure_openai | openai).
ARG REQUIREMENTS=requirements.txt
COPY requirements*.txt ./
RUN pip install -r ${REQUIREMENTS}

FROM deps AS build
COPY requirements-train.txt .
RUN pip install -r requirements-train.txt
WORKDIR /app
COPY core core
COPY data_gen data_gen
COPY ml ml
ENV MLFLOW_DISABLE_AGENT_HINT=1
RUN python -m data_gen.generate && python -m data_gen.lake && python -m ml.train && python -m ml.ews \
    && rm -rf ml/mlruns

# Runtime virtualenv without pip and without the bundled test suites of the large scientific packages.
FROM deps AS venv
RUN pip uninstall -y pip setuptools wheel >/dev/null 2>&1; \
    for pkg in pandas scipy sklearn numpy pyarrow matplotlib; do \
      find /opt/venv/lib/python3.11/site-packages/$pkg -type d \( -name tests -o -name testing_data \) -prune -exec rm -rf {} + ; \
    done; \
    find /opt/venv -name '*.pyx' -delete -o -name '*.pxd' -delete

FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
ENV PATH=/opt/venv/bin:$PATH MLFLOW_DISABLE_AGENT_HINT=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UP_DB_URL=sqlite:////app/var/udyampulse.db
WORKDIR /app
COPY --from=venv /opt/venv /opt/venv
COPY --chown=app:app . .
COPY --from=build --chown=app:app /app/lake lake
COPY --from=build --chown=app:app /app/ml ml
RUN mkdir -p var && chown app:app var
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=30 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz')"
# Two uvicorn processes share one metrics view through PROMETHEUS_MULTIPROC_DIR. prometheus_client switches mode
# whenever the variable exists (even empty), so it is set here for the API only, never for the worker.
CMD ["sh", "-c", "export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus && rm -rf $PROMETHEUS_MULTIPROC_DIR && mkdir -p $PROMETHEUS_MULTIPROC_DIR && python -m api.seed --if-empty && exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers"]
