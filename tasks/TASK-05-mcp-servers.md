# TASK-05: MCP servers via Agent Registry and Agent Gateway

**Prerequisites:** TASK-04 complete. ADK 2.0 installed, Capacity Orchestrator running as Workflow, cargo-plane scenario passing.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Backend

---

## Context

Gemini Enterprise Agent Platform provides **native MCP infrastructure**: Agent Registry as the central catalog of MCP servers, agents, and tools; Agent Gateway as the runtime policy and authorization layer; Agent Identity for cryptographic agent authentication; and Model Armor for prompt-injection and sensitive-data protection on tool calls. No third-party gateway (Apigee or otherwise) is needed — the platform handles it natively.

This task wires three custom MCP servers (synthetic SAP, Maximo, FDP) and the Knowledge Catalog MCP server into this native infrastructure. The Orchestrator's `parallel_system_queries` workflow node calls MCP tools through Agent Gateway, with Agent Registry providing discovery, Agent Identity providing authentication, and Model Armor protecting against prompt injection at the tool boundary.

The narration win is substantial. Previous architecture said *"Apigee-managed MCP servers in front of SAP, Maximo, FDP."* Corrected architecture says *"MCP servers registered with Agent Registry, governed by Agent Gateway, protected by Model Armor — all native platform components. This is what the customer deploys in production, with their real SAP behind it."* Every named component is something the customer buys as part of the platform.

---

## Inputs

- TASK-04 complete (Workflow Orchestrator on ADK 2.0)
- Platform MCP docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/use-agent-platform-mcp`
- Agent Registry docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry`
- Agent Gateway docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview`
- Custom MCP server setup: `https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server`
- Knowledge Catalog MCP: `https://docs.cloud.google.com/dataplex/docs/pre-built-tools-with-mcp-toolbox`
- MCP protocol: `https://modelcontextprotocol.io/introduction`
- ADK MCP tools: `https://adk.dev/tools-custom/mcp-tools/`

---

## Deliverables

When this task is complete:

1. Three custom MCP servers deployed as Cloud Run services, each implementing the MCP protocol over StreamableHTTP transport:
   - **SAP MCP server** — material master, workforce, plant maintenance
   - **Maximo MCP server** — equipment status, location, availability
   - **FDP MCP server** — customer configurations
2. Each server registered with **Agent Registry** so the Orchestrator can discover its tools
3. **Agent Gateway policies** configured to control which agents can call which tools, with read-only/read-write distinctions
4. **Agent Identity** issued for the Orchestrator and other agents, used as the principal in Gateway policies
5. **Model Armor** attached to the MCP servers for prompt-injection protection
6. **Knowledge Catalog's MCP server** registered with Agent Registry and accessible to the equivalence-lookup agent
7. The Orchestrator's `parallel_system_queries` node calls MCP tools through Agent Gateway (not direct HTTP)
8. Cloud Trace shows the full call chain: Agent → Agent Gateway → Model Armor scan → MCP server → response
9. Cargo-plane integration test passes against the new MCP infrastructure

---

## The platform's MCP architecture (read this carefully)

Before writing code, understand how the pieces fit together. This is what you are building toward.

```
                            ┌───────────────────────────────┐
                            │     Agent Registry            │
                            │   (catalog of MCP servers,    │
                            │    agents, tools)             │
                            └──────────────┬────────────────┘
                                           │ discovery
                                           ▼
  Capacity Orchestrator                 ┌──────────────────────┐
  Agent (Workflow)         ────────────►│   Agent Gateway      │
    │                                   │  - IAM authorization │
    │ workflow node calls               │  - Model Armor scan  │
    │ tool via MCP                      │  - audit logging     │
    │                                   └──────────┬───────────┘
    │                                              │
    │ MCP protocol (StreamableHTTP)                │ routed to registered MCP server
    │                                              ▼
    │                            ┌──────────────────────────────┐
    │                            │  SAP MCP server (Cloud Run)  │
    │                            │  Maximo MCP server           │
    │                            │  FDP MCP server              │
    │                            │  Knowledge Catalog MCP        │
    └─────────────────────────►  │  (platform-provided)         │
                                 └──────────────────────────────┘
```

Three things to know:

1. **The Orchestrator does not call MCP servers directly.** It calls Agent Gateway, which authenticates the call (via Agent Identity), authorizes it (against IAM policies on the registered tools), scans the input with Model Armor, then routes to the appropriate registered MCP server.

2. **By default, only registered MCP servers are reachable.** From the Agent Gateway docs: *"By default, access to any remote MCP servers, agents, or tools that have not been registered in the local Agent Registry is blocked."* This is a security default that protects against accidental data exfiltration.

3. **Knowledge Catalog MCP server is platform-provided.** You don't build it; you register Knowledge Catalog as a remote MCP server in Agent Registry and the platform handles the rest. Its prebuilt tools (`search_entries`, `lookup_entry`, `search_aspect_types`, `lookup_context`) become discoverable.

---

## Step-by-step instructions

### Step 1 — Build the custom MCP server backends

Each backend is a Cloud Run service implementing the MCP protocol over StreamableHTTP transport. The MCP protocol specification is at `modelcontextprotocol.io/specification`. Use the Python MCP SDK (`mcp` package) or the genai-toolbox framework — both produce a conformant MCP server.

For build speed, use the **genai-toolbox** approach. It lets you declare MCP tools in YAML against HTTP backends, with minimal Python code. Note the toolbox is just an implementation detail for hosting the MCP protocol — the platform integration happens via Agent Registry registration, not via the toolbox itself.

Create the directory structure:

```bash
mkdir -p mcp_servers/{sap,maximo,fdp}/{backend,Dockerfile,config}
```

#### SAP MCP server backend

`mcp_servers/sap/backend/main.py` — synthetic SAP HTTP service:

```python
"""Synthetic SAP backend that the SAP MCP server will expose as MCP tools.

In production this routes to the customer's real SAP S/4HANA via the customer's
own ingress (typically inside their VPC). For demo, we mock responses.
"""

from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ....src.utils.synthetic_data import (
    load_canonical_assets,
    load_cross_system_aliases,
)

app = FastAPI(title="SAP S/4HANA (Synthetic)", version="1.0.0")


class MaterialMasterResponse(BaseModel):
    material_number: str
    canonical_id: str
    description: str
    plant: str
    storage_location: str
    quantity_available: int


# DEMO NARRATION: "This backend is what the MCP server fronts. In production
# this is the customer's real SAP S/4HANA — typically deployed in their
# project's VPC. The agent never sees this URL directly; it goes through
# Agent Gateway, which routes to the registered SAP MCP server, which calls
# this backend."
@app.get("/material_master/{material_number}", response_model=MaterialMasterResponse)
async def get_material_master(material_number: str) -> MaterialMasterResponse:
    """SAP material master lookup."""
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
    """SAP workforce availability check."""
    return {
        "basin": query.basin,
        "available_technicians": 4,
        "certifications": ["Tool-X-cert", "HazMat-2"],
        "next_available": query.date_window_start.isoformat(),
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

`mcp_servers/sap/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY config/ ./config/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PORT=8080
EXPOSE 8080
CMD ["/entrypoint.sh"]
```

`mcp_servers/sap/entrypoint.sh` — runs the backend and the MCP toolbox in the same container:

```bash
#!/usr/bin/env bash
# Start the synthetic SAP backend in the background
uvicorn backend.main:app --host 127.0.0.1 --port 8090 &

# Start the MCP toolbox exposing the configured tools on $PORT
toolbox --tools-file=/app/config/config.yaml --port=$PORT --transport=streamable-http
```

`mcp_servers/sap/config/config.yaml` — declare MCP tools against the local backend:

```yaml
sources:
  sap_local:
    kind: http
    base_url: http://127.0.0.1:8090
    timeout: 5s

tools:
  sap_get_material_master:
    kind: http
    source: sap_local
    description: |
      Retrieve SAP material master record by SAP material number.
      Returns canonical asset ID, description, plant, storage location, and available quantity.
      Use when you have a SAP material number (e.g. MAT-67890) and need to resolve to canonical asset.
    method: GET
    path: /material_master/{material_number}
    parameters:
      - name: material_number
        type: string
        description: SAP material number (e.g. MAT-67890)

  sap_get_workforce_availability:
    kind: http
    source: sap_local
    description: |
      Check workforce availability for a basin and date window.
    method: POST
    path: /workforce/availability
    parameters:
      - name: basin
        type: string
        description: Basin name
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

Repeat for Maximo and FDP using the same pattern.

#### Deploy to Cloud Run

```bash
# Build container
cd mcp_servers/sap
gcloud builds submit --tag gcr.io/$PROJECT_ID/sap-mcp-server

# Deploy
gcloud run deploy sap-mcp-server \
    --image gcr.io/$PROJECT_ID/sap-mcp-server \
    --region us-central1 \
    --no-allow-unauthenticated \
    --service-account sap-mcp-sa@$PROJECT_ID.iam.gserviceaccount.com

# Capture URL
SAP_MCP_URL=$(gcloud run services describe sap-mcp-server --region us-central1 --format='value(status.url)')
echo "SAP_MCP_URL=$SAP_MCP_URL" >> .env
```

### Step 2 — Register MCP servers with Agent Registry

Once the Cloud Run services are deployed, register them as remote MCP servers in Agent Registry. This makes their tools discoverable to agents and enforces the default-deny security posture.

The Agent Registry API (`projects.locations.mcpServers` or similar — verify against the current Agent Registry docs) accepts a registration with the MCP server URL, description, and optional metadata.

`scripts/register_mcp_servers.py`:

```python
"""Register MCP servers and tools with Agent Registry.

This script is idempotent — re-running it updates existing registrations.
"""

import os
from google.cloud import aiplatform   # check exact module for Agent Registry

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


# DEMO NARRATION: "Step one of the production deployment: register every MCP
# server with Agent Registry. This is the central catalog — your audit team
# can pull a list of every tool every agent can call, every external system
# being touched, every endpoint. By default, the platform blocks calls to
# unregistered servers. That's the security posture out of the box."
def register_sap_mcp_server():
    sap_url = os.environ["SAP_MCP_URL"]
    # Agent Registry API call to register the SAP MCP server
    # Verify exact API surface against:
    # https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry/register-mcp-servers
    print(f"Registering SAP MCP server at {sap_url}")
    # implementation: client.create_mcp_server(parent=..., mcp_server={...})


def register_maximo_mcp_server():
    maximo_url = os.environ["MAXIMO_MCP_URL"]
    print(f"Registering Maximo MCP server at {maximo_url}")


def register_fdp_mcp_server():
    fdp_url = os.environ["FDP_MCP_URL"]
    print(f"Registering FDP MCP server at {fdp_url}")


def register_knowledge_catalog_mcp_server():
    """Knowledge Catalog has a managed remote MCP server hosted by Google Cloud.

    Endpoint: https://dataplex.googleapis.com/mcp
    Auto-enabled when the Dataplex API is enabled in the project.

    We register this managed endpoint with Agent Registry so:
    - Agent Gateway can apply policies on calls to it
    - Model Armor floor settings (project-level) cover it
    - Audit logs flow through the same path as our custom MCP servers

    See: https://docs.cloud.google.com/dataplex/docs/use-remote-mcp
    """
    kc_mcp_url = "https://dataplex.googleapis.com/mcp"
    print(f"Registering Knowledge Catalog managed MCP at {kc_mcp_url}")


if __name__ == "__main__":
    register_sap_mcp_server()
    register_maximo_mcp_server()
    register_fdp_mcp_server()
    register_knowledge_catalog_mcp_server()
```

Add to the Makefile:

```makefile
register-mcp-servers:
	uv run python scripts/register_mcp_servers.py
```

### Step 3 — Configure Agent Gateway policies

Agent Gateway uses Google Cloud authorization policies to control which agents can call which tools. The policies live in IAM and are attached to the registered MCP servers.

For our build, define policies that:
- Allow the Capacity Orchestrator to call all four MCP servers
- Allow Plan Evaluator to call read-only Knowledge Catalog tools only (it doesn't need SAP/Maximo write access)
- Deny everything else by default

`infra/gateway_policies.yaml` (or use Terraform):

```yaml
policies:
  - name: orchestrator_full_mcp_access
    principal: serviceAccount:orchestrator-agent@${PROJECT}.iam.gserviceaccount.com
    permissions:
      - mcp.tools.call
    resources:
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/sap-mcp-server/*
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/maximo-mcp-server/*
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/fdp-mcp-server/*
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/knowledge-catalog-mcp/*

  - name: plan_evaluator_readonly_kc
    principal: serviceAccount:plan-evaluator-agent@${PROJECT}.iam.gserviceaccount.com
    permissions:
      - mcp.tools.call
    resources:
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/knowledge-catalog-mcp/tools/search_entries
      - projects/${PROJECT}/locations/${LOCATION}/mcpServers/knowledge-catalog-mcp/tools/lookup_context
```

Verify exact policy syntax against:
`https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/configure-policies`

### Step 4 — Attach Model Armor to MCP servers

Model Armor protects against prompt-injection at the tool boundary. Enable it on each registered MCP server.

In the Agent Gateway configuration:

```yaml
gateway_config:
  model_armor:
    enabled: true
    template: oilfield-services-mcp-template
    apply_to:
      - mcpServers/sap-mcp-server
      - mcpServers/maximo-mcp-server
      - mcpServers/fdp-mcp-server
      - mcpServers/knowledge-catalog-mcp
    actions:
      - block_on_prompt_injection
      - block_on_sensitive_data_leak
      - log_all_scans
```

This becomes a demo moment in Persona 6 (Ayesha, the audit director): when she asks "show me an example of a blocked attack," the Model Armor log shows a prompt-injection attempt against the SAP MCP that was caught and blocked.

### Step 5 — Wire MCP into the Orchestrator's Workflow

ADK 2.0 has first-class support for calling MCP tools that have been registered with Agent Registry. The pattern is to use `MCPClient` or the `mcp` tools module pointed at Agent Gateway, not the raw MCP server URL.

Update `src/orchestrator_agent/core/nodes/parallel_queries.py`:

```python
"""Parallel system queries via Agent Gateway → registered MCP servers."""

import asyncio
import os

from google.adk import Event
from google.adk.tools.mcp import MCPClient

from ....schemas import CapacityGapRequest, SystemQueryResults


# DEMO NARRATION: "Notice the MCP client is pointed at Agent Gateway —
# not at the MCP servers directly. Every call goes through Gateway: IAM
# authorization, Model Armor scan, audit logging, then routed to the
# registered server. The agent's reasoning is in our code; the security
# enforcement is platform infrastructure."
GATEWAY_ENDPOINT = os.environ["AGENT_GATEWAY_ENDPOINT"]
gateway_client = MCPClient(
    server_url=GATEWAY_ENDPOINT,
    auth="agent-identity",   # uses Agent Identity for authentication
)


async def parallel_system_queries(node_input: dict) -> Event:
    """Fan out parallel MCP queries to all enterprise systems via Agent Gateway."""
    request = CapacityGapRequest(**node_input["payload"])

    sap_task = gateway_client.call_tool(
        server="sap-mcp-server",
        tool="sap_get_material_master",
        material_number=request.sap_material_number,
    )
    maximo_task = gateway_client.call_tool(
        server="maximo-mcp-server",
        tool="maximo_query_availability",
        canonical_id=request.canonical_asset_id,
        region_filter=request.target_region,
    )
    fdp_task = gateway_client.call_tool(
        server="fdp-mcp-server",
        tool="fdp_get_customer_config",
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

### Step 6 — Wire Knowledge Catalog MCP into the equivalence-lookup node

The Knowledge Catalog content itself arrives in TASK-06. For now, configure the Orchestrator's `equivalence_lookup_agent` to call the Knowledge Catalog MCP server through Agent Gateway, using the prebuilt tools.

```python
# In src/orchestrator_agent/core/nodes/equivalence_lookup.py
from google.adk import Agent
from google.adk.tools.mcp import MCPClient

gateway = MCPClient(server_url=os.environ["AGENT_GATEWAY_ENDPOINT"], auth="agent-identity")

# DEMO NARRATION: "The equivalence lookup uses prebuilt Knowledge Catalog MCP
# tools. We didn't build search_entries or lookup_context — they ship with the
# platform. Agent Gateway routes the call to Knowledge Catalog MCP, returns
# the canonical entity with all aliases."
equivalence_lookup_agent = Agent(
    name="equivalence_lookup",
    model="gemini-3-1-pro-preview",
    instruction="""...""",
    tools=[
        gateway.tool(server="knowledge-catalog-mcp", tool="lookup_context"),
        gateway.tool(server="knowledge-catalog-mcp", tool="search_entries"),
    ],
)
```

### Step 7 — Integration test

`tests/integration/test_cargo_plane_via_gateway.py`:

```python
async def test_cargo_plane_calls_through_gateway():
    """Verify the cargo-plane scenario routes through Agent Gateway."""
    response = await root_agent.run_async(user_input="...", session_id="test-gw")
    plan = SourcingPlan.model_validate(response.output)

    # Verify trace shows Agent Gateway spans
    trace = response.cloud_trace
    gateway_spans = [s for s in trace.spans if "agent_gateway" in s.name]
    assert len(gateway_spans) >= 4, "Expected at least 4 Gateway calls (SAP, Maximo, FDP, KC)"

    # Verify Model Armor scans occurred
    armor_spans = [s for s in trace.spans if "model_armor" in s.name]
    assert len(armor_spans) > 0, "Expected Model Armor scan spans"

    # Scenario still works
    assert plan.primary_option.source_location.label == "Lagos, Nigeria"
    assert plan.avoided_cost_usd > 300_000
```

### Step 8 — Architecture documentation

Update `docs/architecture.md`:

```markdown
## MCP Architecture

Capacity Orchestrator (Workflow on Agent Runtime)
        │
        │ MCP protocol calls
        ▼
Agent Gateway (regional, native platform component)
   ├── Agent Identity verification
   ├── IAM authorization policies
   ├── Model Armor scan
   └── audit logging to Cloud Logging
        │
        │ routed to registered MCP servers
        ▼
        ├── SAP MCP server (Cloud Run, registered in Agent Registry)
        ├── Maximo MCP server (Cloud Run, registered in Agent Registry)
        ├── FDP MCP server (Cloud Run, registered in Agent Registry)
        └── Knowledge Catalog MCP server (platform-provided, registered)

No third-party gateway needed. No Apigee. Agent Registry catalogs every server;
Agent Gateway enforces policies on every call.
```

### Step 9 — Commit

```bash
git add .
git commit -m "feat: MCP servers via Agent Registry and Agent Gateway (TASK-05)"
git push
```

---

## Acceptance criteria

- [ ] Three MCP server Cloud Run services deployed (SAP, Maximo, FDP)
- [ ] Each registered with Agent Registry; visible in `gcloud ai mcp-servers list` (verify exact CLI)
- [ ] Knowledge Catalog MCP registered with Agent Registry
- [ ] Agent Gateway policies created and attached to each registered server
- [ ] Agent Identity provisioned for the Orchestrator and Plan Evaluator agents
- [ ] Model Armor template configured and attached to MCP servers
- [ ] Orchestrator's `parallel_system_queries` node calls through Agent Gateway, not direct URLs
- [ ] Cargo-plane integration test passes against the new architecture
- [ ] Cloud Trace shows distinct spans for Agent Gateway, Model Armor scan, and routed MCP calls
- [ ] Unregistered MCP server test: attempting to call an unregistered URL fails with the default-deny behavior
- [ ] `docs/architecture.md` updated with corrected MCP architecture
- [ ] Every code path that calls MCP has a `# DEMO NARRATION:` comment
- [ ] Commit pushed

---

## Common pitfalls

**Pointing the MCP client at the wrong endpoint.** The agent should call Agent Gateway, not the raw Cloud Run URL of the MCP server. Direct calls bypass Gateway policies and won't show in audit logs — and may fail outright if the MCP server denies traffic that doesn't come from Gateway.

**Forgetting to register the MCP server.** Default-deny means unregistered servers are unreachable. If `mcp_client.call_tool(...)` returns a permission error, check Agent Registry first.

**Agent Identity not provisioned.** Each agent that calls MCP needs an Agent Identity. Without it, Agent Gateway has no principal to authorize. Provision Identities for the Orchestrator and any sub-agent that calls MCP directly.

**Policy granularity wrong.** Gateway policies can be granular per tool (e.g., Plan Evaluator can call `lookup_context` but not `search_entries`). Get the granularity right early — overly broad policies invite the audit team's concern.

**Model Armor template misconfigured.** Model Armor needs a template that defines what to block. Use a permissive template during development (log-only) and tighten before customer demos.

**Knowledge Catalog MCP not enabled at the project level.** Knowledge Catalog's MCP server is platform-provided but must be enabled. Check the Dataplex API is enabled and the catalog has content (TASK-06 populates the content; TASK-05 just registers and verifies the MCP endpoint is reachable).

**MCP protocol transport mismatch.** Use StreamableHTTP transport (the new standard). The older SSE transport is not supported for custom MCP server data stores. Verify your genai-toolbox config specifies `--transport=streamable-http`.

**Cloud Run cold starts.** Agent Gateway routes have a timeout. If a Cloud Run MCP server has a cold start that exceeds the timeout, the call fails. Configure minimum instances on the MCP server Cloud Run services if cold-start latency is a concern in the demo.

---

## References

- Agent Registry overview: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry`
- Register MCP servers: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry/register-mcp-servers`
- Agent Gateway overview: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview`
- Agent Identity: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/identity`
- Model Armor: `https://docs.cloud.google.com/security-command-center/docs/model-armor-overview`
- Custom MCP server setup (Gemini Enterprise side): `https://docs.cloud.google.com/gemini/enterprise/docs/connectors/custom-mcp-server/set-up-custom-mcp-server`
- Knowledge Catalog MCP: `https://docs.cloud.google.com/dataplex/docs/pre-built-tools-with-mcp-toolbox`
- MCP protocol: `https://modelcontextprotocol.io/introduction`
- genai-toolbox: `https://github.com/googleapis/genai-toolbox`

---

*When TASK-05 is complete, proceed to `TASK-06-knowledge-catalog.md`. Knowledge Catalog content gets created and the prebuilt MCP tools become useful queries.*
