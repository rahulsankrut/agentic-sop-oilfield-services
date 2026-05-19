# MCP servers

Three MCP server scaffolds for the Agentic S&OP for Oilfield Services
project. Each one mirrors one of the enterprise systems the Orchestrator
talks to, and is deployable as its own Cloud Run service.

## Layout

```
mcp_servers/
├── README.md                  ← this file
├── local_run.sh               ← spin up all 3 backends + 3 toolbox front-ends locally
├── sap/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py            ← FastAPI synthetic SAP backend
│   │   └── requirements.txt
│   ├── config.yaml            ← genai-toolbox MCP config (declares sources, tools, toolsets)
│   ├── Dockerfile             ← multi-stage: toolbox binary + backend
│   └── README.md
├── maximo/
│   ├── backend/{__init__,main}.py, requirements.txt
│   ├── config.yaml, Dockerfile, README.md
└── fdp/
    ├── backend/{__init__,main}.py, requirements.txt
    ├── config.yaml, Dockerfile, README.md
```

Each `backend/main.py` is a small FastAPI app that mocks the responses of
a real enterprise system. Each `config.yaml` configures
[genai-toolbox](https://github.com/googleapis/genai-toolbox) to expose
those endpoints as MCP tools.

## The three servers at a glance

| Server | Toolset | Tools | Backend endpoints |
| --- | --- | --- | --- |
| **SAP** | `sap_oilfield` | `sap_workforce_by_basin`, `sap_resolve_material_number` | `POST /sap/workforce/by_basin`, `GET /sap/material/{sap_material_number}` |
| **Maximo** | `maximo_oilfield` | `maximo_query_availability`, `maximo_get_equipment_instance` | `POST /maximo/availability`, `GET /maximo/equipment/{equipment_instance_id}` |
| **FDP** | `fdp_oilfield` | `fdp_get_customer_config` | `POST /fdp/customer_config` |

InTouch (the operations knowledge corpus) is **out of scope** for this
task — it's served by the prebuilt Knowledge Catalog MCP, wired up
separately in TASK-06.

## The genai-toolbox layer

Each MCP server is two processes:

```
                ┌──────────────────────────────┐
   MCP (HTTP)   │ genai-toolbox                │   HTTP   ┌────────────────────┐
   ◀──────────▶ │   --tools-file=config.yaml   │ ───────▶ │ FastAPI backend    │
                │   --port=${PORT}             │ ◀─────── │ (synthetic data)   │
                └──────────────────────────────┘          └────────────────────┘
```

The toolbox handles MCP protocol details (tool discovery, schema, MCP-over-
HTTP/SSE transport) so the FastAPI side only has to be a normal REST API.
This is the same shape Google's Knowledge Catalog MCP uses, and it's the
same shape we'd use against a real SAP / Maximo / FDP endpoint — only the
`baseUrl` in `config.yaml` changes.

## Local run

```bash
./mcp_servers/local_run.sh
```

Starts:
- SAP backend on `127.0.0.1:8001`, toolbox on `0.0.0.0:8101`
- Maximo backend on `127.0.0.1:8002`, toolbox on `0.0.0.0:8102`
- FDP backend on `127.0.0.1:8003`, toolbox on `0.0.0.0:8103`

Ctrl+C tears all six processes down.

Prerequisites: `toolbox` binary on `$PATH` (download from the
[genai-toolbox releases page](https://github.com/googleapis/genai-toolbox/releases))
and a Python venv at the repo root (`venv/`) with `fastapi`, `uvicorn`,
and `pydantic` installed.

## Cloud Run deploy

Each subdirectory ships a multi-stage Dockerfile that:
1. Pulls the `toolbox` binary from the upstream Google image.
2. Installs the FastAPI backend deps.
3. Bakes both into a `python:3.10-slim` runtime (matches the Reasoning
   Engine runtime version — see CLAUDE.md gotchas).
4. At container start, runs the FastAPI backend on `127.0.0.1` and the
   toolbox MCP front-end on `0.0.0.0:${PORT}` (Cloud Run convention).

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/sap-mcp-server     mcp_servers/sap
gcloud builds submit --tag gcr.io/$PROJECT_ID/maximo-mcp-server  mcp_servers/maximo
gcloud builds submit --tag gcr.io/$PROJECT_ID/fdp-mcp-server     mcp_servers/fdp

for s in sap maximo fdp; do
  gcloud run deploy ${s}-mcp-server \
    --image gcr.io/$PROJECT_ID/${s}-mcp-server \
    --region us-central1 \
    --no-allow-unauthenticated
done
```

The Orchestrator's service account needs `roles/run.invoker` on each
service. Endpoint URLs go into `.env` as `SAP_MCP_URL`, `MAXIMO_MCP_URL`,
`FDP_MCP_URL`.

## Agent Registry + Agent Gateway path (TASK-05)

In production we **do not** front these servers with Apigee. The Gemini
Enterprise Agent Platform ships native MCP infrastructure that supersedes
the v0 Apigee plan:

1. **Agent Registry** catalogs each MCP server. Registration happens via
   `scripts/register_mcp_servers.py` (REST against the Agent Registry
   API). The default-deny posture means unregistered URLs are
   unreachable from any agent on the platform.
2. **Agent Gateway** is the single ingress for every MCP call. It
   verifies the caller's Agent Identity, evaluates IAM authorization
   policies (`infra/gateway_policies.yaml`), runs Model Armor against
   the prompt (`infra/model_armor.yaml`), audits, then routes to the
   correct registered MCP server.
3. **Agent Identity** is provisioned per agent SA — the Orchestrator's
   SA gets an Identity, the Plan Evaluator's SA gets another, and
   Gateway uses these as the principals in policy decisions.
4. **Model Armor** scans every prompt and response. The template lives
   at `infra/model_armor.yaml` and is attached to all four registered
   MCP servers (including the platform-managed Knowledge Catalog MCP at
   `https://dataplex.googleapis.com/mcp`).

The Orchestrator's `parallel_system_queries` node calls Gateway via ADK
2.0's `McpToolset` pointed at `${AGENT_GATEWAY_ENDPOINT}`. See
`src/orchestrator_agent/core/nodes/parallel_queries.py`. A short
in-process fallback path exists for local dev when
`AGENT_GATEWAY_ENDPOINT` is unset — it calls the same skill functions
directly. The fallback is dev-only; production runs always carry a
Gateway endpoint.

The `config.yaml` files use env-var substitution (`${SAP_BACKEND_URL}`)
specifically so the toolbox front-end can sit either in front of the
synthetic FastAPI mock or in front of a real enterprise system — without
changes to the YAML structure.

### One-line deploy + register

```bash
make deploy-mcp-servers       # gcloud builds submit ×3
make register-mcp-servers     # scripts/register_mcp_servers.py
make apply-gateway-policies   # gateway IAM policies
make enable-model-armor       # Model Armor template + attach
```

See `docs/architecture.md` for the full component diagram.
