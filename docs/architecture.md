# Architecture

Live architectural reference for the Agentic S&OP for Oilfield Services
demo. Sections grow as tasks land; this file is the single source of
truth for what's currently wired together.

## MCP Architecture (TASK-05)

The Capacity Orchestrator's `parallel_system_queries` workflow node calls
four MCP servers concurrently. None of the calls go directly to the
backing services — every one routes through Gemini Enterprise Agent
Platform's native MCP infrastructure.

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
    │                                   │  - Agent Identity    │
    │ workflow node calls               │  - IAM authorization │
    │ tools via MCP                     │  - Model Armor scan  │
    │                                   │  - audit logging     │
    │ (StreamableHTTP transport)        └──────────┬───────────┘
    │                                              │
    │                                              │ routed to registered MCP server
    │                                              ▼
    │                            ┌──────────────────────────────┐
    │                            │  SAP MCP server (Cloud Run)  │
    │                            │  Maximo MCP server           │
    │                            │  FDP MCP server              │
    │                            │  Knowledge Catalog MCP        │
    └─────────────────────────►  │  (platform-provided)         │
                                 └──────────────────────────────┘
```

### Component-by-component

| Component | What it does | File / artifact |
| --- | --- | --- |
| **Agent Registry** | Catalogs the four MCP servers. Default-deny: an unregistered URL is unreachable. | `scripts/register_mcp_servers.py` |
| **Agent Gateway** | Single ingress for every MCP call. Verifies Agent Identity, evaluates IAM policies, runs Model Armor, audits. | `infra/gateway_policies.yaml` |
| **Agent Identity** | Cryptographic identity bound to each agent's service account. Used as the principal in Gateway policies. | Provisioned per-SA in terraform (TASK-13). |
| **Model Armor** | Prompt-injection + sensitive-data scanner. Applied to all four MCP servers. Logs every scan. | `infra/model_armor.yaml` |
| **SAP MCP server** | Custom Cloud Run service. FastAPI synthetic backend + genai-toolbox MCP layer. | `mcp_servers/sap/` |
| **Maximo MCP server** | Same shape. Equipment availability. | `mcp_servers/maximo/` |
| **FDP MCP server** | Same shape. Customer configurations. | `mcp_servers/fdp/` |
| **Knowledge Catalog MCP** | Platform-provided MCP server at `https://dataplex.googleapis.com/mcp`. Prebuilt tools: `search_entries`, `lookup_entry`, `lookup_context`, `search_aspect_types`. | (no source — managed) |

### What this replaces

Previous architecture said *"Apigee-managed MCP servers in front of SAP,
Maximo, FDP."* That was the v0 framing — a third-party gateway tier in
front of custom MCP servers, with Apigee carrying the auth / quota /
trace concerns.

The corrected architecture uses **no Apigee**. Agent Registry, Agent
Gateway, Agent Identity, and Model Armor are native Gemini Enterprise
Agent Platform components. Every named piece is something the customer
pays for as part of the platform — there's no extra licensing line item,
no separate ops surface, and the audit story is uniform across all four
MCP servers (including the platform-managed Knowledge Catalog one).

### Local-dev fallback

`src/orchestrator_agent/core/nodes/parallel_queries.py` keeps an
in-process fallback that calls the underlying skill functions directly.
The fallback engages when `AGENT_GATEWAY_ENDPOINT` is unset (the local
runner sets nothing). Behaviour:

| Env state | Path taken | Used by |
| --- | --- | --- |
| `AGENT_GATEWAY_ENDPOINT` set | Agent Gateway → registered MCP server | Cloud Run / Agent Engine production |
| `AGENT_GATEWAY_ENDPOINT` unset | In-process skill functions | `scripts/local_run_orchestrator.py` |

The in-process path is **strictly a dev affordance**. In any deployment
that claims to demonstrate platform-grade governance, the Gateway
endpoint MUST be set — a missing variable is a misconfiguration, not a
graceful degradation. The workflow node intentionally does NOT silently
fall back from a failed Gateway call to in-process; a Gateway exception
re-raises and fails the node so a broken policy can't masquerade as a
green run.

### Acceptance checklist (status mirrors `tasks/TASK-05-mcp-servers.md`)

- [x] Three MCP server Cloud Build configs + Cloud Run descriptors (`mcp_servers/{sap,maximo,fdp}/cloudbuild.yaml`, `infra/cloud_run/*.yaml`).
- [x] Idempotent registration script for all four MCP servers (`scripts/register_mcp_servers.py`).
- [x] Agent Gateway authorization policies (`infra/gateway_policies.yaml`) — Orchestrator full access, Plan Evaluator read-only KC.
- [x] Model Armor template (`infra/model_armor.yaml`) with prompt-injection + sensitive-data blocking and full scan logging.
- [x] Orchestrator workflow node routes through Agent Gateway via ADK 2.0 `McpToolset` with an in-process fallback for local dev (`src/orchestrator_agent/core/nodes/parallel_queries.py`).
- [x] Makefile targets (`deploy-mcp-servers`, `register-mcp-servers`, `apply-gateway-policies`, `enable-model-armor`).
- [ ] Agent Identity provisioning (deferred to TASK-13 / terraform — the per-agent SAs already exist; Agent Identity bindings land with the rest of the IAM apply).
- [ ] Cargo-plane integration test against the deployed Gateway endpoint (deferred to TASK-11 once the full stack is up).
