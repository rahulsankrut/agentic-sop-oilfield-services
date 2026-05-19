# Maximo MCP server

Synthetic IBM Maximo backend wrapped by `genai-toolbox` as an MCP server.

## What's exposed

`config.yaml` declares the `maximo_oilfield` toolset:

| Tool | Method | Backend path | Purpose |
| --- | --- | --- | --- |
| `maximo_query_availability` | POST | `/maximo/availability` | Equipment instances of a canonical asset, optionally region-filtered |
| `maximo_get_equipment_instance` | GET | `/maximo/equipment/{equipment_instance_id}` | Single equipment record by instance id |

Mirrors `query_maximo_availability` from
`src/orchestrator_agent/skills/enterprise-systems/scripts/tools.py`.

## Local test

```bash
cd mcp_servers/maximo
DATA_DIR=$(pwd)/../../data \
  uvicorn backend.main:app --host 127.0.0.1 --port 8002

# In a second shell
MAXIMO_BACKEND_URL=http://127.0.0.1:8002 \
  toolbox --tools-file=config.yaml --address 0.0.0.0 --port 8102

curl http://127.0.0.1:8002/health
curl -X POST http://127.0.0.1:8002/maximo/availability \
  -H 'Content-Type: application/json' \
  -d '{"canonical_id":"TX-001","region_filter":"north_america"}'
curl http://127.0.0.1:8002/maximo/equipment/TX-007-LGS-001
```

Or `mcp_servers/local_run.sh` from the repo root.

## Env vars

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `<repo>/data` | Where the JSON fixtures live |
| `MAXIMO_BACKEND_URL` | (required) | URL of the FastAPI backend the toolbox calls |
| `PORT` | `8080` | Toolbox listen port |
| `LATENCY_MIN_MS` / `LATENCY_MAX_MS` | `50` / `200` | Artificial-latency window |

## Deploy notes

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/maximo-mcp-server mcp_servers/maximo
gcloud run deploy maximo-mcp-server \
    --image gcr.io/$PROJECT_ID/maximo-mcp-server \
    --region us-central1 \
    --no-allow-unauthenticated
```

In production the synthetic FastAPI backend is replaced by the real
Maximo endpoint. The MCP layer, Agent Registry registration, and Agent
Gateway policy stay unchanged — only the backend URL moves.
