# TASK-05: MCP servers via genai-toolbox

**Prerequisites:** TASK-04 complete. ADK 2.0 installed, Capacity Orchestrator running as Workflow, cargo-plane scenario passing.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Backend

---

## Context

Until now, the Orchestrator's enterprise-systems skill queries in-memory synthetic data directly. That's fine for demonstrating reasoning but bypasses the Model Context Protocol (MCP) — which is the actual mechanism Gemini Enterprise Agent Platform uses for tool integration. This task replaces the direct synthetic-data calls with MCP server calls, using the **genai-toolbox** framework that ships with the platform.

Two things happen here. First, we set up **MCP servers for SAP, Maximo, and FDP** — mocked backends that conform to MCP protocol and look indistinguishable from real enterprise systems to the agent. The platform-visibility win is significant: the demo trace shows MCP calls happening, which is what the customer will see in production. Second, we wire in the **prebuilt Knowledge Catalog MCP tools** that genai-toolbox provides out of the box (`search_entries`, `lookup_entry`, `search_aspect_types`, `lookup_context`). Knowledge Catalog itself will be populated in TASK-06; this task makes its MCP interface available to the agent.

The genai-toolbox project is open source at `github.com/googleapis/genai-toolbox`. It is the same framework Google uses internally for Knowledge Catalog's MCP integration. Building on it means we get the production pattern, not a one-off mock.

---

## Inputs

- TASK-04 complete (Workflow Orchestrator on ADK 2.0)
- genai-toolbox: `https://github.com/googleapis/genai-toolbox`
- Knowledge Catalog MCP integration: `https://docs.cloud.google.com/dataplex/docs/pre-built-tools-with-mcp-toolbox`
- MCP protocol: `https://modelcontextprotocol.io/introduction`
- ADK MCP tools docs: `https://adk.dev/tools-custom/mcp-tools/`

---

## Deliverables

When this task is complete:

1. Three mocked MCP servers exist, deployed as Cloud Run services or local processes:
   - **SAP MCP server** — exposes material master, workforce, plant maintenance tools
   - **Maximo MCP server** — exposes equipment status, location, availability tools
   - **FDP MCP server** — exposes customer configuration tools
2. Each server is built using the genai-toolbox pattern (configuration file + binary launch)
3. The Orchestrator's `enterprise-systems` skill is refactored to call MCP servers instead of querying synthetic data directly
4. The prebuilt **Knowledge Catalog MCP tools** are wired into the Orchestrator (the actual catalog content arrives in TASK-06)
5. Apigee proxies in front of each MCP server (or a documented path for adding them post-v1)
6. Cargo-plane integration test passes against the new MCP-backed setup
7. Cloud Trace shows MCP tool calls as distinct spans, with full request/response payloads visible
8. Documentation in `docs/architecture.md` describes the MCP architecture clearly

---

## Step-by-step instructions

### Step 1 — Understand genai-toolbox

Spend 30-60 minutes reading the genai-toolbox repo before writing code:

```bash
git clone https://github.com/googleapis/genai-toolbox.git /tmp/genai-toolbox
cd /tmp/genai-toolbox
ls docs/en/integrations/   # see the integration patterns
cat README.md
```

Key concepts:
- **Sources** — backend data systems the toolbox connects to (databases, APIs, etc.)
- **Tools** — operations exposed to agents (each tool maps to a SQL query, HTTP request, or function)
- **Toolsets** — groups of tools that get loaded together
- **MCP server mode** — the toolbox runs as an MCP server, exposing configured tools over MCP protocol

For our build, we need custom Sources for SAP, Maximo, and FDP (since they're not databases in v1 — they're synthetic JSON-backed mocks). The toolbox supports custom HTTP sources, which is the right primitive.

### Step 2 — Set up the MCP server scaffolding

Create the directory structure for our three MCP servers:

```bash
mkdir -p mcp_servers/{sap,maximo,fdp}/{config,backend,Dockerfile}
```

Each MCP server has:
- `config.yaml` — genai-toolbox configuration declaring sources, tools, toolsets
- `backend/` — Python module implementing the synthetic data backend (FastAPI service)
- `Dockerfile` — for Cloud Run deployment

### Step 3 — Build the SAP MCP server backend

The SAP backend serves synthetic SAP-shaped responses over HTTP. Think of it as the API a real SAP S/4HANA system would expose, with realistic latency and response structure.

`mcp_servers/sap/backend/main.py`:

```python
"""Synthetic SAP backend for MCP server consumption.

In production this would be replaced with calls to a real SAP S/4HANA instance,
but the MCP interface stays identical — that's the point.
"""

from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ....src.utils.synthetic_data import (
    load_canonical_assets,
    load_cross_system_aliases,
    load_customers,
)

app = FastAPI(title="SAP S/4HANA (Synthetic)", version="1.0.0")


# DEMO NARRATION: "This is the SAP MCP server. In production it sits in front
# of the customer's actual SAP S/4HANA system — typically via Apigee for security
# and observability. For demo purposes we mock the responses, but the interface
# is identical to what we'd connect to a real RISE-on-Google-Cloud SAP instance."


class MaterialMasterResponse(BaseModel):
    material_number: str
    canonical_id: str
    description: str
    plant: str
    storage_location: str
    quantity_available: int


@app.get("/material_master/{material_number}", response_model=MaterialMasterResponse)
async def get_material_master(material_number: str) -> MaterialMasterResponse:
    """Lookup material master record."""
    aliases = load_cross_system_aliases()
    assets = {a["canonical_id"]: a for a in load_canonical_assets()}

    for canonical_id, alias in aliases.items():
        if alias.get("sap_material_number") == material_number:
            asset = assets[canonical_id]
            return MaterialMasterResponse(
                material_number=material_number,
                canonical_id=canonical_id,
                description=asset["canonical_label"],
                plant="PT01",
                storage_location="LAG01",
                quantity_available=1,
            )
    raise HTTPException(status_code=404, detail=f"Material {material_number} not found")


class WorkforceQuery(BaseModel):
    basin: str
    date_window_start: date
    date_window_end: date


@app.post("/workforce/availability")
async def get_workforce_availability(query: WorkforceQuery) -> dict:
    """Workforce availability lookup for a basin and date range."""
    return {
        "basin": query.basin,
        "available_technicians": 4,
        "certifications": ["Tool-X-cert", "HazMat-2"],
        "next_available": query.date_window_start.isoformat(),
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "sap-synthetic"}
```

`mcp_servers/sap/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

`mcp_servers/sap/backend/requirements.txt`:

```
fastapi==0.110.0
uvicorn==0.27.0
pydantic==2.5.0
```

### Step 4 — Configure genai-toolbox to expose SAP backend as MCP

`mcp_servers/sap/config/config.yaml`:

```yaml
sources:
  sap_synthetic:
    kind: http
    base_url: ${SAP_BACKEND_URL}     # populated at deploy time
    timeout: 5s

tools:
  sap_get_material_master:
    kind: http
    source: sap_synthetic
    description: |
      Retrieve SAP material master record by SAP material number.
      Returns canonical asset ID, description, plant, storage location, and available quantity.
      Use this when you have a SAP material number (e.g. MAT-67890) and need to resolve to canonical asset.
    method: GET
    path: /material_master/{material_number}
    parameters:
      - name: material_number
        type: string
        description: SAP material number (e.g. MAT-67890)

  sap_get_workforce_availability:
    kind: http
    source: sap_synthetic
    description: |
      Check workforce availability for a basin and date window.
      Returns available technicians, certifications, next available date.
    method: POST
    path: /workforce/availability
    parameters:
      - name: basin
        type: string
        description: Basin name (e.g. "Permian", "West_Africa")
      - name: date_window_start
        type: string
        description: ISO date for window start
      - name: date_window_end
        type: string
        description: ISO date for window end

toolsets:
  sap_oilfield:
    - sap_get_material_master
    - sap_get_workforce_availability
```

### Step 5 — Repeat for Maximo and FDP

Build `mcp_servers/maximo/` and `mcp_servers/fdp/` following the same pattern. Key tool surfaces:

**Maximo** (equipment management):
- `maximo_query_availability` — find assets matching a canonical_id, optionally filtered by region
- `maximo_get_equipment` — full equipment record by Maximo equipment ID
- `maximo_get_repair_status` — repair shop status for an equipment

**FDP** (customer configurations):
- `fdp_get_customer_config` — customer's configuration for a specific asset class
- `fdp_check_compatibility` — check if a substitute asset is accepted by a customer's config

Use the same Pydantic schemas, the same FastAPI pattern, the same genai-toolbox config structure.

### Step 6 — Deploy the MCP servers

Two deployment paths. Pick based on whether you have time for Apigee setup or want the fastest path.

**Path A — Direct Cloud Run (fast, no Apigee).**

```bash
# Build and deploy each backend
cd mcp_servers/sap/backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/sap-mcp-backend
gcloud run deploy sap-mcp-backend \
    --image gcr.io/$PROJECT_ID/sap-mcp-backend \
    --region us-central1 \
    --no-allow-unauthenticated \
    --service-account agent-runtime-sa@$PROJECT_ID.iam.gserviceaccount.com

# Capture the URL into .env
SAP_BACKEND_URL=$(gcloud run services describe sap-mcp-backend --region us-central1 --format='value(status.url)')
echo "SAP_BACKEND_URL=$SAP_BACKEND_URL" >> .env
```

Repeat for Maximo and FDP.

Run the genai-toolbox MCP server locally (for development) or deploy as a separate Cloud Run service (for the demo):

```bash
# Local development: run toolbox pointing at each config
toolbox --tools-file=mcp_servers/sap/config/config.yaml --port=8101 &
toolbox --tools-file=mcp_servers/maximo/config/config.yaml --port=8102 &
toolbox --tools-file=mcp_servers/fdp/config/config.yaml --port=8103 &
```

**Path B — Apigee-managed (production pattern, recommended for the demo).**

Apigee adds an authenticated, observable, rate-limited layer in front of each MCP server. For tier-one services majors, this is the right pattern — they'll want to put real SAP behind Apigee.

```bash
# Create Apigee proxies for each MCP server
gcloud apigee apis create sap-mcp-proxy --source-uri=$SAP_BACKEND_URL
gcloud apigee apis create maximo-mcp-proxy --source-uri=$MAXIMO_BACKEND_URL
gcloud apigee apis create fdp-mcp-proxy --source-uri=$FDP_BACKEND_URL
```

Add Apigee API keys to `.env` and update the genai-toolbox configs to point at Apigee endpoints rather than direct Cloud Run URLs.

**For TASK-05, choose Path A.** Path B is documented for v2 / customer-specific deployments where Apigee is part of the customer's existing API gateway estate.

### Step 7 — Wire MCP into ADK Orchestrator

ADK 2.0 has first-class MCP tool support. The Orchestrator's workflow nodes that previously called synthetic data directly now call MCP tools.

Update `src/orchestrator_agent/core/nodes/parallel_queries.py`:

```python
"""Parallel system queries via MCP."""

import asyncio
from google.adk import Event
from google.adk.tools.mcp import MCPClient

from ....schemas import CapacityGapRequest, SystemQueryResults


# MCP clients for each enterprise system
sap_mcp = MCPClient(server_url="http://localhost:8101")    # or production Cloud Run URL
maximo_mcp = MCPClient(server_url="http://localhost:8102")
fdp_mcp = MCPClient(server_url="http://localhost:8103")


# DEMO NARRATION: "Now look at the trace — four parallel MCP calls. Maximo, SAP,
# FDP, and Knowledge Catalog, all hit concurrently. MCP is the standard protocol
# the Gemini Enterprise Agent Platform uses for tool integration. In production
# these would be the customer's actual SAP S/4HANA via Apigee, their Maximo
# instance, their FDP. The interface stays the same."
async def parallel_system_queries(node_input: dict) -> Event:
    """Fan out parallel MCP queries to all enterprise systems."""
    request = CapacityGapRequest(**node_input["payload"])

    sap_task = sap_mcp.call_tool(
        "sap_get_material_master",
        material_number=request.sap_material_number,
    )
    maximo_task = maximo_mcp.call_tool(
        "maximo_query_availability",
        canonical_id=request.canonical_asset_id,
        region_filter=request.target_region,
    )
    fdp_task = fdp_mcp.call_tool(
        "fdp_get_customer_config",
        customer_id=request.customer_id,
        asset_canonical_id=request.canonical_asset_id,
    )

    results = await asyncio.gather(sap_task, maximo_task, fdp_task)

    aggregated = SystemQueryResults(
        sap=results[0],
        maximo=results[1],
        fdp=results[2],
    )
    return Event(
        message="Parallel system queries complete",
        payload=aggregated.model_dump(),
    )
```

### Step 8 — Wire in Knowledge Catalog MCP

Knowledge Catalog comes with prebuilt MCP tools that don't require building anything new. Just add the toolbox to the agent's available tools:

```python
# In src/orchestrator_agent/core/tools.py — add Knowledge Catalog MCP

from google.adk.tools.mcp import MCPClient

# Knowledge Catalog MCP via genai-toolbox prebuilt dataplex integration
knowledge_catalog_mcp = MCPClient(
    server_url="http://localhost:8100",  # toolbox running --prebuilt dataplex
)

def create_knowledge_catalog_tools() -> list:
    """Return the prebuilt Knowledge Catalog MCP tools."""
    return [
        knowledge_catalog_mcp.tool("search_entries"),
        knowledge_catalog_mcp.tool("lookup_entry"),
        knowledge_catalog_mcp.tool("search_aspect_types"),
        knowledge_catalog_mcp.tool("lookup_context"),
    ]
```

The `equivalence_lookup_agent` (an LLM node in the workflow) gets these tools, so when it reasons about functional equivalence, it calls `lookup_context` on Knowledge Catalog directly — exactly as the platform intends.

Update `mcp_servers/knowledge_catalog/launch.sh`:

```bash
#!/usr/bin/env bash
# Launch the genai-toolbox in Knowledge Catalog prebuilt mode
toolbox --prebuilt dataplex --stdio --env DATAPLEX_PROJECT=$GOOGLE_CLOUD_PROJECT
```

(Knowledge Catalog content itself is set up in TASK-06.)

### Step 9 — Integration test

Update `tests/integration/test_cargo_plane_scenario.py` to verify MCP calls happen:

```python
async def test_cargo_plane_uses_mcp():
    """Cargo-plane scenario should call MCP servers, not synthetic data directly."""
    # Run the scenario and capture trace
    response = await root_agent.run_async(user_input="...", session_id="test-mcp")
    plan = SourcingPlan.model_validate(response.output)

    # Verify the trace contains MCP spans
    trace = response.cloud_trace
    mcp_spans = [s for s in trace.spans if s.name.startswith("mcp.")]
    assert any("sap_get_material_master" in s.name for s in mcp_spans)
    assert any("maximo_query_availability" in s.name for s in mcp_spans)
    assert any("fdp_get_customer_config" in s.name for s in mcp_spans)
    assert any("lookup_context" in s.name for s in mcp_spans)  # Knowledge Catalog

    # Verify the scenario still produces the right answer
    assert plan.primary_option.source_location.label == "Lagos, Nigeria"
    assert plan.avoided_cost_usd > 300_000
```

Run:

```bash
make deploy-mcp-servers   # add this Makefile target
uv run pytest tests/integration/test_cargo_plane_scenario.py::test_cargo_plane_uses_mcp -v
```

### Step 10 — Architecture documentation

Update `docs/architecture.md` (or create) with a clear diagram of the MCP architecture:

```
Capacity Orchestrator (Workflow on Agent Runtime)
        │
        │ MCP protocol calls
        ▼
genai-toolbox MCP layer
        │
        ├──────────────► SAP MCP (Cloud Run) ──► synthetic SAP backend
        │                  via Apigee (production)
        │
        ├──────────────► Maximo MCP (Cloud Run) ──► synthetic Maximo backend
        │                  via Apigee (production)
        │
        ├──────────────► FDP MCP (Cloud Run) ──► synthetic FDP backend
        │                  via Apigee (production)
        │
        └──────────────► Knowledge Catalog MCP (prebuilt)
                           via genai-toolbox --prebuilt dataplex
                           queries actual Knowledge Catalog (TASK-06)
```

### Step 11 — Commit

```bash
git add .
git commit -m "feat: MCP servers for SAP/Maximo/FDP + Knowledge Catalog MCP wiring (TASK-05)"
git push
```

---

## Acceptance criteria

- [ ] Three MCP server backends exist with FastAPI implementations
- [ ] Three genai-toolbox config files exist (one per server)
- [ ] All three backends deploy to Cloud Run successfully
- [ ] Knowledge Catalog MCP runs via `toolbox --prebuilt dataplex`
- [ ] Orchestrator's `parallel_system_queries` node calls MCP tools instead of synthetic data
- [ ] Cargo-plane integration test passes against MCP-backed setup
- [ ] Cloud Trace shows distinct MCP spans for each tool call
- [ ] `docs/architecture.md` updated with the MCP architecture diagram
- [ ] Every MCP call site has a `# DEMO NARRATION:` comment
- [ ] Commit pushed

---

## Common pitfalls

**MCP server health check.** Each Cloud Run MCP backend must expose `/health` returning 200. Without it, Cloud Run thinks the service is unhealthy and won't route traffic.

**Async context.** MCP calls in ADK 2.0 Workflow nodes must be `async`. Mixing sync and async will hang the workflow runner.

**Authentication between Orchestrator and MCP.** For Path A (direct Cloud Run), use service account auth — the Orchestrator's service account needs `roles/run.invoker` on each MCP backend service. For Path B (Apigee), use API keys provisioned by Apigee.

**Knowledge Catalog MCP needs DATAPLEX_PROJECT env var.** The prebuilt dataplex toolbox reads `DATAPLEX_PROJECT` to know which project's catalog to query. If unset, all `lookup_context` calls return empty results — which looks like "the agent is broken" until you trace it.

**Genai-toolbox version drift.** The toolbox is at v0.31+ at time of writing. Pin the version explicitly (`toolbox v0.31.0`) rather than running `latest`. Breaking changes between minor versions have happened.

**Local development vs. production URLs.** Hardcoding `localhost:8101` in the Orchestrator works for dev but breaks when deployed to Agent Runtime. Use environment variables for MCP server URLs.

**Apigee policy gotchas.** If you go with Path B, Apigee policies can rate-limit or reject requests in ways that look like MCP server failures from the agent's perspective. Trace through Apigee first before debugging the agent.

---

## References

- genai-toolbox: `https://github.com/googleapis/genai-toolbox`
- Knowledge Catalog MCP integration: `https://docs.cloud.google.com/dataplex/docs/pre-built-tools-with-mcp-toolbox`
- ADK MCP tools: `https://adk.dev/tools-custom/mcp-tools/`
- MCP protocol: `https://modelcontextprotocol.io/introduction`
- Apigee proxy setup: `https://cloud.google.com/apigee/docs/api-platform/get-started/create-proxy`

---

*When TASK-05 is complete, proceed to `TASK-06-knowledge-catalog.md`.*
