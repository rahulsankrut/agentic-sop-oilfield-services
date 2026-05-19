# Multi-stage build for the SAP MCP server.
#
# Stage 1 — toolbox: pull the genai-toolbox binary from the official image.
# Stage 2 — runtime: run the FastAPI synthetic backend and the toolbox MCP
#           server side-by-side. The toolbox MCP front-end speaks MCP to the
#           Orchestrator and forwards calls to the local FastAPI backend.
#
# For Cloud Run we expose port 8080 (the toolbox port). The FastAPI backend
# binds to 127.0.0.1:8001 inside the container; only toolbox is publicly
# reachable, which matches the production "MCP server in front of enterprise
# system" deployment shape.

# -- Stage 1: pull the toolbox binary -----------------------------------------
FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.31.0 AS toolbox

# -- Stage 2: assemble the runtime image --------------------------------------
FROM python:3.10-slim AS runtime

# Toolbox binary lives at /toolbox in the upstream image.
COPY --from=toolbox /toolbox /usr/local/bin/toolbox

WORKDIR /app

# Python deps for the FastAPI backend.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Backend source.
COPY backend /app/backend

# Toolbox config.
COPY config.yaml /app/config.yaml

# Synthetic data lives in /data inside the container; the Cloud Run / docker
# run command should mount the repo's data/ directory there. Locally you can
# also override with -e DATA_DIR=/some/other/path.
ENV DATA_DIR=/data \
    SAP_BACKEND_URL=http://127.0.0.1:8001 \
    PORT=8080 \
    LATENCY_MIN_MS=50 \
    LATENCY_MAX_MS=200

EXPOSE 8080

# Launch both processes. Backend in background, toolbox in foreground so the
# container exits cleanly when toolbox stops.
CMD ["sh", "-c", "uvicorn backend.main:app --host 127.0.0.1 --port 8001 & exec toolbox --tools-file /app/config.yaml --address 0.0.0.0 --port ${PORT}"]
