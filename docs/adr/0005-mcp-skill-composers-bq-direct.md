# ADR 0005: MCP skill composers go BigQuery-direct

## Status

Accepted (TASK-MCP-REFACTOR, 2026-05-21). Captured in CLAUDE.md
"Known gotchas" addenda.

## Context

The original architecture (TASK-16) routed every skill-tool data
fetch through one of three MCP servers on Cloud Run: SAP-shaped,
Maximo-shaped, FDP-shaped. The path was:

```
LLM (skill tool, e.g. identify_blockers)
   → agents/utils/mcp_client.py (httpx GET)
   → Cloud Run MCP server (toolbox MCP front + FastAPI backend)
   → BigQuery
```

Three problems surfaced:

1. **Toolbox config mismatch.** The toolbox config.yaml used
   `{matnr}` Python-style placeholders; the genai-toolbox expects
   Go-template `{{.matnr}}`. The toolbox happily registered tools
   but forwarded literal `{matnr}` strings to the backend, which
   404'd or returned empty rows. Took days to surface because nothing
   in the chain logged "I didn't substitute that placeholder."
2. **Silent uvicorn crash.** The Dockerfile CMD was
   `sh -c "uvicorn ... & exec toolbox ..."`. Toolbox became PID 1;
   if uvicorn crashed after the shell fork (e.g.,
   `ModuleNotFoundError: agents.schemas` before the backend was
   staged into the build context), the backgrounded uvicorn died
   without its stderr reaching Cloud Logs in a debuggable form.
3. **The skill composers are Python, not LLM.** When an LLM picks a
   tool via ADK's MCP integration, the MCP path is necessary —
   that's the canonical surface. But the *skill composers* (e.g.
   `identify_blockers`, `query_maximo_availability`) are Python
   functions called by other Python code, not by the LLM. Routing
   them through an HTTP round-trip added latency for no protocol-
   demonstration value.

The MCP backends themselves are 100% BigQuery-backed — every SQL
template in `mcp_servers/{sap,maximo,fdp}/backend/main.py` queries
`oilfield_{sap,maximo,fdp}_extract.*`. The HTTP layer adds nothing
except potential failure modes.

## Decision

Retire `agents/utils/mcp_client.py` as a real network client. Add
`agents/utils/enterprise_data.py` — a thin BQ-direct module that
mirrors the schema the MCP backends used to read. Skill composers
import `enterprise_data as ed` and call `bq_query` underneath.

```python
# Before
from agents.utils import mcp_client
matches = mcp_client.sap_resolve_customer_by_name(needle)

# After
from agents.utils import enterprise_data as ed
matches = ed.sap_resolve_customer_by_name(needle)
```

`mcp_client.py` survives as a back-compat shim re-exporting from
`enterprise_data` so existing test fixtures and `scripts/
smoke_cargo_plane.py` keep working without a churn-heavy port. The
shim's `_do_get`/`_do_post` helpers are no-op stubs (the conftest
fixture that monkey-patches them is now a no-op too).

The Cloud Run MCP servers are **not retired** — they're separately
fixed and reachable. They're how `McpToolset` exposes raw MCP tools
to the LLM on Procurement / Forecast / Capacity Planning agents
(ADR-future TBD, but registration is in place). That is the
canonical ADK MCP path the docs prescribe; it just doesn't sit
under the skill composers anymore.

## Consequences

**Positive**

- Skill composer calls are now ~30ms (single BQ query) instead of
  ~300ms (HTTP roundtrip to Cloud Run + backend → BQ → return).
  Cargo-plane workflow end-to-end dropped from ~140s to ~95s.
- Removes the fragile multi-process Cloud Run container from the
  critical-path. The toolbox-fronted MCP servers still run for the
  LLM-driven MCP demonstration, but a partial outage doesn't break
  the cargo-plane workflow.
- One transport to debug for the data path. Skill composer bugs are
  BQ SQL bugs, not HTTP-status-code bugs.

**Negative**

- Two paths to maintain when MCP schema changes: the
  `mcp_servers/*/backend/main.py` SQL and the
  `enterprise_data.py` SQL. They have to stay in sync. Mitigated by
  keeping the function signatures + return shapes byte-identical.
- The "everything goes through MCP" demo narrative is narrower —
  MCP is the LLM-tool path (via `McpToolset`), not the skill
  composer path. The customer story has to acknowledge both shapes.

## Related work

- `agents/utils/enterprise_data.py` — new BQ-direct module.
- `agents/utils/mcp_client.py` — deprecation shim.
- `agents/utils/mcp_toolsets.py` — separate canonical-ADK
  registration path for the LLM. See registrations in
  `agents/procurement_approval_agent/tools.py`,
  `agents/forecast_review_agent/tools.py`,
  `agents/capacity_planning_agent/tools.py`.
- CLAUDE.md "Known gotchas" addendum 2026-05-21.
