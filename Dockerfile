# syntax=docker/dockerfile:1
# API and worker image. The synthetic lake, the trained model and the EWS back-test are built here, at image
# build time, so every API pod and worker runs the same model version and starts in seconds.

FROM python:3.11-slim AS deps
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM deps AS build
WORKDIR /app
COPY core core
COPY data_gen data_gen
COPY ml ml
ENV MLFLOW_DISABLE_AGENT_HINT=1
RUN python -m data_gen.generate && python -m data_gen.lake && python -m ml.train && python -m ml.ews \
    && rm -rf ml/mlruns

FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app
ENV PATH=/opt/venv/bin:$PATH MLFLOW_DISABLE_AGENT_HINT=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UP_DB_URL=sqlite:////app/var/udyampulse.db
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app . .
COPY --from=build --chown=app:app /app/lake lake
COPY --from=build --chown=app:app /app/ml ml
RUN mkdir -p var && chown app:app var
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=30 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz')"
CMD ["sh", "-c", "python -m api.seed --if-empty && exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers"]
