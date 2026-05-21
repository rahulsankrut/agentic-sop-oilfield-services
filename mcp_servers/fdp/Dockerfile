# Multi-stage build for the FDP MCP server.
# Mirrors the SAP / Maximo server pattern.

FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.31.0 AS toolbox

FROM python:3.10-slim AS runtime

COPY --from=toolbox /toolbox /usr/local/bin/toolbox

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
# Shared agent schemas (staged by cloudbuild.yaml). Without this COPY the
# backend's `from agents.schemas import (...)` crashes uvicorn at startup.
COPY agents /app/agents
COPY config.yaml /app/config.yaml

ENV DATA_DIR=/data \
    FDP_BACKEND_URL=http://127.0.0.1:8003 \
    PORT=8080 \
    LATENCY_MIN_MS=50 \
    LATENCY_MAX_MS=200 \
    PYTHONPATH=/app

EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.main:app --host 127.0.0.1 --port 8003 & exec toolbox --tools-file /app/config.yaml --address 0.0.0.0 --port ${PORT}"]
