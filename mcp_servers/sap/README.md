# SAP MCP server

Synthetic SAP S/4HANA backend wrapped by `genai-toolbox` as an MCP server.

## What's exposed

`config.yaml` declares the `sap_oilfield` toolset with two tools:

| Tool | Method | Backend path | Purpose |
| --- | --- | --- | --- |
| `sap_workforce_by_basin` | POST | `/sap/workforce/by_basin` | Crew / specialist / on-call counts for a basin |
| `sap_resolve_material_number` | GET | `/sap/material/{sap_material_number}` | SAP material number → canonical asset |

Mirrors `query_sap_workforce` and (new) material-master resolution from
`src/orchestrator_agent/skills/enterprise-systems/scripts/tools.py`.

## Local test

```bash
# 1. Backend (FastAPI, port 8001)
cd mcp_servers/sap
DATA_DIR=$(pwd)/../../data \
  uvicorn backend.main:app --host 127.0.0.1 --port 8001

# 2. Toolbox MCP front-end (port 8101) — in a second shell
SAP_BACKEND_URL=http://127.0.0.1:8001 \
  toolbox --tools-file=config.yaml --address 0.0.0.0 --port 8101

# 3. Quick sanity check
curl http://127.0.0.1:8001/health
curl -X POST http://127.0.0.1:8001/sap/workforce/by_basin \
  -H 'Content-Type: application/json' -d '{"basin":"permian"}'
curl http://127.0.0.1:8001/sap/material/MAT-67890
```

Or use the repo-level convenience script `mcp_servers/local_run.sh`, which
starts all three backends + their toolbox front-ends.

## Env vars

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATA_DIR` | `<repo>/data` | Where the `*.json` synthetic fixtures live |
| `SAP_BACKEND_URL` | (required) | URL of the FastAPI backend the toolbox calls |
| `PORT` | `8080` | Toolbox listen port (Cloud Run convention) |
| `LATENCY_MIN_MS` / `LATENCY_MAX_MS` | `50` / `200` | Artificial-latency window |

## Deploy notes

1. Build the multi-stage image:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/sap-mcp-server mcp_servers/sap
   ```
2. Deploy to Cloud Run, mounting the synthetic data as a GCS-backed volume
   or baked into the image at `/data`. The repo's `data/*.json` are small —
   simplest is to `COPY ../../data /data` from the Dockerfile (left as a
   v2 task, since multi-stage `COPY` from a parent directory needs build
   context tweaking).
3. Set `SAP_BACKEND_URL=http://127.0.0.1:8001` (the in-container backend);
   Cloud Run's invoker sees only the toolbox port `8080`.
4. Register the deployed service with Agent Registry
   (`scripts/register_mcp_servers.py`) and apply the Agent Gateway
   policies in `infra/gateway_policies.yaml`. From that point the
   Orchestrator can only reach the SAP MCP server through Gateway, with
   Model Armor in the path.

## In production

The synthetic FastAPI backend goes away; the toolbox config's `baseUrl`
points to the real SAP S/4HANA endpoint. The MCP layer above stays
identical, the Agent Registry record stays identical, the Gateway
policy stays identical — only the backend URL changes. The Orchestrator
never sees the swap.
