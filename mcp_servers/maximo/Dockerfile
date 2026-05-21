# Multi-stage build for the Maximo MCP server.
# Mirrors the SAP server pattern; see mcp_servers/sap/Dockerfile for notes.

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

# Shared entrypoint — see mcp_servers/sap/Dockerfile.
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV DATA_DIR=/data \
    MAXIMO_BACKEND_URL=http://127.0.0.1:8002 \
    BACKEND_PORT=8002 \
    PORT=8080 \
    LATENCY_MIN_MS=50 \
    LATENCY_MAX_MS=200 \
    PYTHONPATH=/app

EXPOSE 8080

CMD ["/app/entrypoint.sh"]
