#!/bin/sh
# Shared MCP container entrypoint — starts the FastAPI backend in the
# background, waits for it to be reachable, then starts the toolbox
# MCP front-end in the foreground.
#
# Replaces the original
#   sh -c "uvicorn ... & exec toolbox ..."
# which silently swallowed uvicorn crashes (backend's stderr never made
# it into Cloud Logs because PID 1 was toolbox, and a backgrounded
# uvicorn that died at startup looked indistinguishable from one that
# was happily listening).
#
# Per-container env:
#   BACKEND_PORT  — port the FastAPI backend listens on (8001/8002/8003)
#   PORT          — port the toolbox front-end listens on (Cloud Run = 8080)
#   CONFIG_PATH   — toolbox config file (default /app/config.yaml)

set -e

PORT_BACKEND="${BACKEND_PORT:-8001}"
PORT_TOOLBOX="${PORT:-8080}"
CONFIG="${CONFIG_PATH:-/app/config.yaml}"

echo "[mcp-entrypoint] starting uvicorn on 127.0.0.1:${PORT_BACKEND}"
uvicorn backend.main:app \
    --host 127.0.0.1 \
    --port "${PORT_BACKEND}" \
    --log-level info &
UVICORN_PID=$!
echo "[mcp-entrypoint] uvicorn pid=${UVICORN_PID}"

# Poll the backend port until it accepts connections, capped at 30s.
# Bail loudly if uvicorn dies before that.
ATTEMPTS=0
while true; do
    if python3 -c "import socket,sys;
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', ${PORT_BACKEND}))
except Exception:
    sys.exit(1)
s.close()" 2>/dev/null; then
        echo "[mcp-entrypoint] uvicorn listening on 127.0.0.1:${PORT_BACKEND}"
        break
    fi
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -gt 30 ]; then
        echo "[mcp-entrypoint] FATAL: uvicorn never started listening on port ${PORT_BACKEND}"
        exit 1
    fi
    if ! kill -0 "${UVICORN_PID}" 2>/dev/null; then
        echo "[mcp-entrypoint] FATAL: uvicorn pid ${UVICORN_PID} exited (check logs above)"
        exit 1
    fi
    sleep 1
done

echo "[mcp-entrypoint] starting toolbox on 0.0.0.0:${PORT_TOOLBOX}"
exec toolbox --tools-file "${CONFIG}" --address 0.0.0.0 --port "${PORT_TOOLBOX}"
