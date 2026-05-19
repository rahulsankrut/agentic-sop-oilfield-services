#!/usr/bin/env bash
# Launch all three MCP server pairs (FastAPI backend + genai-toolbox front-end)
# locally for development. Ctrl+C tears everything down.
#
# Prerequisites:
#   - `toolbox` binary on PATH (https://github.com/googleapis/genai-toolbox/releases)
#   - Python venv at repo root (venv/) with fastapi, uvicorn, pydantic installed
#       (mirrors what each backend's requirements.txt declares)
#
# Ports:
#   SAP    backend 8001   toolbox 8101
#   Maximo backend 8002   toolbox 8102
#   FDP    backend 8003   toolbox 8103
#
# Usage:
#   ./mcp_servers/local_run.sh            # blocks; Ctrl+C stops everything
#   SKIP_TOOLBOX=1 ./mcp_servers/local_run.sh   # backends only (handy when toolbox isn't installed)

set -euo pipefail

# Resolve repo root (this script lives at mcp_servers/local_run.sh).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${DATA_DIR:-${REPO_ROOT}/data}"

# Prefer the repo's venv if present.
if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/venv/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

SKIP_TOOLBOX="${SKIP_TOOLBOX:-0}"
TOOLBOX_BIN="${TOOLBOX_BIN:-toolbox}"

PIDS=()

cleanup() {
  echo
  echo "[local_run] stopping ${#PIDS[@]} processes..."
  for pid in "${PIDS[@]}"; do
    kill "${pid}" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "[local_run] bye."
}
trap cleanup INT TERM EXIT

start_backend() {
  local name="$1"
  local port="$2"
  echo "[local_run] starting ${name} backend on 127.0.0.1:${port}"
  (
    cd "${SCRIPT_DIR}/${name}"
    DATA_DIR="${DATA_DIR}" \
      "${PYTHON}" -m uvicorn backend.main:app \
        --host 127.0.0.1 --port "${port}" --log-level info
  ) &
  PIDS+=("$!")
}

start_toolbox() {
  # Args: name backend_port toolbox_port env_var_name
  # We export ${env_var_name}=http://127.0.0.1:${backend_port} inside the
  # subshell before launching toolbox, so the toolbox config.yaml's
  # ${SAP_BACKEND_URL} / ${MAXIMO_BACKEND_URL} / ${FDP_BACKEND_URL}
  # substitution resolves to the right local port.
  local name="$1"
  local backend_port="$2"
  local toolbox_port="$3"
  local env_var="$4"
  if [[ "${SKIP_TOOLBOX}" == "1" ]]; then
    echo "[local_run] SKIP_TOOLBOX=1, skipping toolbox front-end for ${name}"
    return
  fi
  if ! command -v "${TOOLBOX_BIN}" >/dev/null 2>&1; then
    echo "[local_run] WARN: '${TOOLBOX_BIN}' not found on PATH; skipping ${name} toolbox front-end."
    echo "          install from https://github.com/googleapis/genai-toolbox/releases"
    return
  fi
  echo "[local_run] starting ${name} toolbox on 0.0.0.0:${toolbox_port}  (-> 127.0.0.1:${backend_port})"
  (
    cd "${SCRIPT_DIR}/${name}"
    export "${env_var}=http://127.0.0.1:${backend_port}"
    "${TOOLBOX_BIN}" --tools-file config.yaml \
      --address 0.0.0.0 --port "${toolbox_port}"
  ) &
  PIDS+=("$!")
}

echo "[local_run] DATA_DIR=${DATA_DIR}"
echo "[local_run] PYTHON=${PYTHON}"
echo

start_backend sap 8001
start_backend maximo 8002
start_backend fdp 8003

# Give the backends a beat to bind their sockets before toolbox starts probing.
sleep 1

# start_toolbox: name backend_port toolbox_port env_var_name
# Each toolbox process talks to exactly one backend via its own *_BACKEND_URL.
start_toolbox sap    8001 8101 SAP_BACKEND_URL
start_toolbox maximo 8002 8102 MAXIMO_BACKEND_URL
start_toolbox fdp    8003 8103 FDP_BACKEND_URL

cat <<EOF

[local_run] All processes started. URLs:

  SAP    backend  http://127.0.0.1:8001    health: /health
  SAP    MCP      http://127.0.0.1:8101    (genai-toolbox)

  Maximo backend  http://127.0.0.1:8002    health: /health
  Maximo MCP      http://127.0.0.1:8102    (genai-toolbox)

  FDP    backend  http://127.0.0.1:8003    health: /health
  FDP    MCP      http://127.0.0.1:8103    (genai-toolbox)

[local_run] Ctrl+C to stop.
EOF

wait
