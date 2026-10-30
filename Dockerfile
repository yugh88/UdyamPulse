# API + data/ML pipeline image (Azure: push to ACR, run on AKS / Container Apps in Central India)
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 make && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV MLFLOW_DISABLE_AGENT_HINT=1 UP_DB_URL=sqlite:////app/var/udyampulse.db
EXPOSE 8000
# Build the synthetic lake, train, back-test and seed on start, then serve.
CMD ["sh", "-c", "python -m data_gen.generate && python -m data_gen.lake && python -m ml.train && python -m ml.ews && python -m api.seed && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
