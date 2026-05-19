"""Parallel system queries — fan out to Maximo, SAP, FDP, InTouch.

Two execution paths, picked at runtime based on env:

* **Agent-Gateway path (production / cloud).** When ``AGENT_GATEWAY_ENDPOINT``
  is set, the node calls registered MCP servers through Agent Gateway using
  ADK 2.0's :class:`McpToolset` machinery. Every call gets:

  - Agent Identity verification (the Orchestrator's SA),
  - IAM authorization against the policies in
    ``infra/gateway_policies.yaml``,
  - Model Armor scan per ``infra/model_armor.yaml``,
  - audit log line in Cloud Logging.

  This is the architecture TASK-05 builds toward.

* **In-process fallback (local dev).** When ``AGENT_GATEWAY_ENDPOINT`` is
  unset, the node calls the same skill functions directly via
  ``asyncio.to_thread``. No Cloud Run, no Agent Gateway, no Model Armor —
  enabling fast local iteration (``scripts/local_run_orchestrator.py``)
  without standing up the platform infra.

The two paths return the same :class:`SystemQueryResults` shape so
downstream nodes can't tell which one ran.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from google.adk import Event

from src.schemas import CapacityGapRequest, SystemQueryResults
from src.utils.skill_imports import (
    query_fdp_customer_config,
    query_intouch_specs,
    query_maximo_availability,
    query_sap_workforce,
)

logger = logging.getLogger("orchestrator.parallel_queries")


# ---------------------------------------------------------------------------
# Region → basin mapping (shared by both paths)
# ---------------------------------------------------------------------------


def _basin_for_region(region: str | None) -> str:
    """Map our Maximo region tag to the SAP workforce-table basin name.

    The SAP synthetic data uses long basin names ("West Africa OCC"); our
    region tags are short slugs. Keep this mapping narrow — TASK-06 will
    replace it with a Knowledge-Catalog-driven lookup.
    """
    return {
        "west_africa": "West Africa OCC",
        "north_america": "Permian",
        "europe": "North Sea",
        "asia_pacific": "Bohai",
    }.get(region or "", region or "")


# ---------------------------------------------------------------------------
# Agent-Gateway path
# ---------------------------------------------------------------------------


_GATEWAY_ENDPOINT_ENV = "AGENT_GATEWAY_ENDPOINT"

_GATEWAY_TOOLSETS: dict[str, Any] | None = None


def _gateway_toolsets() -> dict[str, Any]:
    """Lazily build one ADK McpToolset per registered MCP server.

    Each toolset is pointed at the same Agent Gateway endpoint but with a
    distinct logical-server prefix in the URL path — Gateway routes to the
    correct registered MCP server based on the prefix. The auth header is
    populated with the Orchestrator's Agent Identity (ADC at runtime).

    Cached on first build; ADK Toolsets are stateful (session manager
    inside) and not safe to instantiate per-call.

    The import is local so unit tests that exercise only the in-process
    fallback path don't need ADK MCP plumbing imported.
    """
    global _GATEWAY_TOOLSETS  # noqa: PLW0603
    if _GATEWAY_TOOLSETS is not None:
        return _GATEWAY_TOOLSETS

    # ADK 2.0 import path. See https://adk.dev/tools-custom/mcp-tools/
    # (StreamableHTTPConnectionParams is the supported transport; SSE is
    # deprecated upstream).
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    gateway_endpoint = os.environ[_GATEWAY_ENDPOINT_ENV].rstrip("/")
    auth_token = _gateway_auth_token()

    def _toolset(server_id: str) -> McpToolset:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                # Agent Gateway routes path-prefix `/mcpServers/<id>` to
                # the registered server. Verify the exact path convention
                # against the live Agent Gateway docs once published.
                url=f"{gateway_endpoint}/mcpServers/{server_id}",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        )

    _GATEWAY_TOOLSETS = {
        "sap-mcp-server": _toolset("sap-mcp-server"),
        "maximo-mcp-server": _toolset("maximo-mcp-server"),
        "fdp-mcp-server": _toolset("fdp-mcp-server"),
        "knowledge-catalog-mcp": _toolset("knowledge-catalog-mcp"),
    }
    return _GATEWAY_TOOLSETS


def _gateway_auth_token() -> str:
    """Mint an OAuth access token for the Orchestrator's Agent Identity.

    In Cloud Run / Agent Engine the runtime SA's identity is picked up
    automatically by Application Default Credentials. Gateway then maps the
    SA to the Agent Identity it has on file for that agent.

    Returns the raw bearer token; the caller wraps it in
    ``Authorization: Bearer ...``.
    """
    from google.auth import default as google_auth_default
    from google.auth.transport.requests import Request

    creds, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())
    return creds.token  # type: ignore[no-any-return]


async def _gateway_call_tool(toolset: Any, tool_name: str, **arguments: Any) -> Any:
    """Invoke one tool on an ADK MCP toolset.

    ADK 2.0's McpToolset exposes tools via ``get_tools()`` (returns a list
    of FunctionTool-like objects). We look up the named tool and call it.
    The actual ADK call signature is ``await tool.run_async(args=...)`` —
    if the live API differs we surface the error at runtime rather than
    crash all four queries silently.
    """
    tools = await toolset.get_tools()
    by_name = {t.name: t for t in tools}
    tool = by_name.get(tool_name)
    if tool is None:
        raise RuntimeError(
            f"Tool '{tool_name}' not found in toolset (available: {sorted(by_name)})"
        )
    return await tool.run_async(args=arguments)


# DEMO NARRATION: "Notice the MCP toolsets are pointed at Agent Gateway —
# not at the SAP / Maximo / FDP Cloud Run URLs directly. Every call goes
# through Gateway: IAM authorization on the Orchestrator's Agent Identity,
# Model Armor scan against prompt injection, audit log line, then routed
# to the registered MCP server. Our code reasons about WHAT to ask; the
# platform handles WHO is asking and whether it's safe."
async def _via_agent_gateway(request: CapacityGapRequest) -> SystemQueryResults:
    """Run the four parallel queries through Agent Gateway."""
    toolsets = _gateway_toolsets()
    canonical_id = request.canonical_asset_id or ""
    region = request.target_region
    customer_id = request.customer_id or ""

    maximo_task = _gateway_call_tool(
        toolsets["maximo-mcp-server"],
        "maximo_query_availability",
        canonical_id=canonical_id,
        region_filter=region,
    )
    sap_task = _gateway_call_tool(
        toolsets["sap-mcp-server"],
        "sap_workforce_by_basin",
        basin=_basin_for_region(region),
    )
    fdp_task = _gateway_call_tool(
        toolsets["fdp-mcp-server"],
        "fdp_get_customer_config",
        customer_id=customer_id,
        canonical_id=canonical_id,
    )
    # InTouch / Knowledge Catalog spec lookup uses the platform-managed
    # KC MCP server's `lookup_context` prebuilt tool. The argument shape
    # is the KC tool's (entry_name + aspect_types), not our internal
    # `query_intouch_specs` signature — the wrapper here normalizes it.
    intouch_task = _gateway_call_tool(
        toolsets["knowledge-catalog-mcp"],
        "lookup_context",
        entry_name=canonical_id,
        aspect_types=["intouch_spec"],
    )

    maximo, sap, fdp, intouch = await asyncio.gather(
        maximo_task, sap_task, fdp_task, intouch_task, return_exceptions=False
    )

    # The Gateway tool responses are plain dicts (the toolbox / MCP server
    # serializes pydantic models on the way out). Normalize into the same
    # shape the in-process path returns so downstream nodes can't tell.
    maximo_list = _coerce_list(maximo, key="instances")
    intouch_list = _coerce_list(intouch, key="specs")
    return SystemQueryResults(
        maximo={"instances": maximo_list, "count": len(maximo_list)},
        sap=_coerce_dict(sap),
        fdp=_coerce_dict(fdp),
        intouch={"specs": intouch_list, "count": len(intouch_list)},
    )


def _coerce_list(value: Any, *, key: str) -> list[Any]:
    """Pull a list out of a Gateway response in a forgiving way."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        inner = value.get(key)
        if isinstance(inner, list):
            return inner
    return []


def _coerce_dict(value: Any) -> dict[str, Any] | None:
    """Return value if it's a dict, else None."""
    return value if isinstance(value, dict) else None


# ---------------------------------------------------------------------------
# In-process fallback path
# ---------------------------------------------------------------------------


async def _via_in_process_skills(request: CapacityGapRequest) -> SystemQueryResults:
    """Local-dev fallback — call skill functions directly.

    Identical contract to ``_via_agent_gateway`` so the workflow doesn't
    care which path ran.
    """
    canonical_id = request.canonical_asset_id or ""

    maximo_task = asyncio.to_thread(
        query_maximo_availability,
        canonical_id=canonical_id,
        region_filter=request.target_region,
    )
    sap_task = asyncio.to_thread(
        query_sap_workforce,
        basin=_basin_for_region(request.target_region),
    )
    fdp_task = asyncio.to_thread(
        query_fdp_customer_config,
        customer_id=request.customer_id or "",
        canonical_id=canonical_id,
    )
    intouch_task = asyncio.to_thread(
        query_intouch_specs,
        canonical_id=canonical_id,
    )

    maximo, sap, fdp, intouch = await asyncio.gather(
        maximo_task, sap_task, fdp_task, intouch_task, return_exceptions=False
    )

    return SystemQueryResults(
        maximo={"instances": maximo, "count": len(maximo)},
        sap=sap or None,
        fdp=fdp or None,
        intouch={"specs": intouch, "count": len(intouch)},
    )


# ---------------------------------------------------------------------------
# Workflow node entrypoint
# ---------------------------------------------------------------------------


# DEMO NARRATION: "Now the workflow fans out — four parallel queries against
# Maximo, SAP, FDP, and Knowledge Catalog. All running concurrently, all
# through MCP. In production every call routes via Agent Gateway with
# Model Armor in the path; locally we short-circuit to in-process skill
# calls for fast iteration. No LLM in this step; the agent isn't deciding
# what to do, the workflow is. This is what makes agentic AI defensible to
# procurement audit — predictable steps, parallel execution, full trace."
async def parallel_system_queries(node_input: dict) -> Event:
    """Fan out parallel queries to all four enterprise systems.

    Selects the Agent-Gateway path when ``AGENT_GATEWAY_ENDPOINT`` is set,
    otherwise falls back to the in-process skill calls.
    """
    request = CapacityGapRequest(**node_input)

    if not request.canonical_asset_id:
        # Should never happen — resolve_canonical_asset_node ran upstream.
        return Event(
            message="parallel_system_queries: missing canonical_asset_id",
            output=SystemQueryResults().model_dump(),
        )

    use_gateway = bool(os.environ.get(_GATEWAY_ENDPOINT_ENV))
    if use_gateway:
        try:
            aggregated = await _via_agent_gateway(request)
            path_label = "agent-gateway"
        except Exception as exc:  # noqa: BLE001
            # Surface gateway failures loudly in logs, but DON'T silently
            # fall back to in-process — the demo's whole point is that the
            # call went through Gateway. A fallback here would mask a
            # broken Gateway policy as a successful run.
            logger.exception(
                "Agent Gateway call failed; re-raising to fail the node: %s",
                exc,
            )
            raise
    else:
        aggregated = await _via_in_process_skills(request)
        path_label = "in-process"

    return Event(
        message=(
            f"Parallel system queries complete via {path_label}: "
            f"maximo={aggregated.maximo['count']} instances, "
            f"intouch={aggregated.intouch['count']} specs"
        ),
        # Pass the original request alongside the results so downstream
        # nodes don't have to re-thread it through every payload.
        output={
            "request": request.model_dump(),
            "results": aggregated.model_dump(),
            "transport": path_label,
        },
    )
