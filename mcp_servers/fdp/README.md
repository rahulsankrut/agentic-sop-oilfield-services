# FDP MCP server

Synthetic FDP customer-configuration backend wrapped by `genai-toolbox` as
an MCP server.

## What's exposed

`config.yaml` declares the `fdp_oilfield` toolset:

| Tool | Method | Backend path | Purpose |
| --- | --- | --- | --- |
| `fdp_get_customer_config` | POST | `/fdp/customer_config` | (customer, canonical_id) → approval + substitution flags |

Mirrors `query_fdp_customer_config` from
`src/orchestrator_agent/skills/enterprise-systems/scripts/tools.py`, including
the `normalize_customer_id` slug-or-display-name pattern from
`src/utils/synthetic_data.py` (re-implemented inline to keep the MCP server
free of `src/` package dependencies).

## Local test

```bash
cd mcp_servers/fdp
DATA_DIR=$(pwd)/../../data \
  uvicorn backend.main:app --host 127.0.0.1 --port 8003

# Second shell
FDP_BACKEND_URL=http://127.0.0.1:8003 \
  toolbox --tools-file=config.yaml --address 0.0.0.0 --port 8103

curl http://127.0.0.1:8003/health
curl -X POST http://127.0.0.1:8003/fdp/customer_config \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"Gulf Petroleum","canonical_id":"TX-001"}'
```

Both `gulf-petroleum` and `Gulf Petroleum` (and the full
`Gulf Petroleum Services`) resolve to the same record — the
`normalize_customer_id` helper takes care of it.

## Env vars

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `<repo>/data` | Where the JSON fixtures live |
| `FDP_BACKEND_URL` | (required) | URL of the FastAPI backend the toolbox calls |
| `PORT` | `8080` | Toolbox listen port |
| `LATENCY_MIN_MS` / `LATENCY_MAX_MS` | `50` / `200` | Artificial-latency window |

## Deploy notes

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/fdp-mcp-server mcp_servers/fdp
gcloud run deploy fdp-mcp-server \
    --image gcr.io/$PROJECT_ID/fdp-mcp-server \
    --region us-central1 \
    --no-allow-unauthenticated
```

In production: real FDP behind this MCP server, registered with Agent
Registry, fronted by Agent Gateway. Same MCP interface, no agent-side
change.
