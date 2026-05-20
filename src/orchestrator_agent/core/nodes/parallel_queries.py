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
from datetime import datetime
from typing import Any

from google.adk import Context, Event

from src.schemas import CapacityGapRequest, SystemQueryResults
from src.utils.skill_imports import (
    query_fdp_customer_config,
    query_intouch_specs,
    query_maximo_availability,
    query_sap_workforce,
)

from ...events.canvas_events import (
    MCPCallCompletedEvent,
    MCPCallStartedEvent,
    NodeCompletedEvent,
    NodeStartedEvent,
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


# ---------------------------------------------------------------------------
# Canvas-event emission helpers
# ---------------------------------------------------------------------------


class _CanvasEmitter:
    """Accumulates canvas events emitted during the parallel queries node.

    We can't repeatedly call :func:`src.orchestrator_agent.events.emit.emit`
    because it re-reads ``ctx.state`` on each call — the state delta from a
    previous emit isn't visible yet within the same node execution. Instead
    we accumulate in-memory and produce a final state delta at the end.
    """

    def __init__(self, ctx: Context | None) -> None:
        self._ctx = ctx
        # Seed with any pre-existing canvas_events from session state.
        existing: list[Any] = []
        if ctx is not None and hasattr(ctx, "state"):
            try:
                existing = list(ctx.state.get("canvas_events", []) or [])
            except Exception:
                existing = []
        self._events: list[dict[str, Any]] = existing

    def add(self, event: Any) -> None:
        self._events.append(event.model_dump(mode="json"))

    def workflow_id(self) -> str:
        if self._ctx is None or not hasattr(self._ctx, "state"):
            return ""
        try:
            return self._ctx.state.get("workflow_id", "") or ""
        except Exception:
            return ""

    def session_id(self) -> str:
        if self._ctx is None or not hasattr(self._ctx, "state"):
            return ""
        try:
            return self._ctx.state.get("session_id", "") or ""
        except Exception:
            return ""

    def state_delta(self) -> dict[str, Any]:
        return {"canvas_events": list(self._events)}


async def _call_with_emit(
    coro_factory: Any,
    *,
    emitter: _CanvasEmitter,
    server: str,
    tool: str,
    via_gateway: bool,
) -> Any:
    """Run a single MCP call, emitting started/completed canvas events.

    ``coro_factory`` is a zero-arg callable that returns the awaitable for
    the underlying call. We construct the awaitable inside this helper so
    the timer brackets the actual await rather than the coroutine creation.
    """
    emitter.add(
        MCPCallStartedEvent(
            workflow_id=emitter.workflow_id(),
            session_id=emitter.session_id(),
            server=server,
            tool=tool,
            via_gateway=via_gateway,
        )
    )
    started = datetime.utcnow()
    result = await coro_factory()
    duration_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    emitter.add(
        MCPCallCompletedEvent(
            workflow_id=emitter.workflow_id(),
            session_id=emitter.session_id(),
            server=server,
            tool=tool,
            duration_ms=duration_ms,
            result_summary=_summarize_for_canvas(result),
        )
    )
    return result


def _summarize_for_canvas(value: Any) -> dict[str, Any]:
    """Strip heavy fields so SSE chunks stay small.

    Mirrors the spec's ``_summarize`` helper. Drops ``raw_response``-style
    keys and bounds list lengths.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in ("raw_response", "full_response"):
                continue
            if isinstance(v, list) and len(v) > 5:
                out[k] = {"count": len(v), "first": v[:5]}
            else:
                out[k] = v
        return out
    if isinstance(value, list):
        return {"count": len(value), "first": value[:5]}
    return {"value": value}


# DEMO NARRATION: "Notice the MCP toolsets are pointed at Agent Gateway —
# not at the SAP / Maximo / FDP Cloud Run URLs directly. Every call goes
# through Gateway: IAM authorization on the Orchestrator's Agent Identity,
# Model Armor scan against prompt injection, audit log line, then routed
# to the registered MCP server. Our code reasons about WHAT to ask; the
# platform handles WHO is asking and whether it's safe."
async def _via_agent_gateway(
    request: CapacityGapRequest, emitter: _CanvasEmitter
) -> SystemQueryResults:
    """Run the four parallel queries through Agent Gateway.

    Each call is wrapped in canvas-event emission so the canvas can light
    up MCP-call pills in parallel while the four awaits race.
    """
    toolsets = _gateway_toolsets()
    canonical_id = request.canonical_asset_id or ""
    region = request.target_region
    customer_id = request.customer_id or ""

    maximo_task = _call_with_emit(
        lambda: _gateway_call_tool(
            toolsets["maximo-mcp-server"],
            "maximo_query_availability",
            canonical_id=canonical_id,
            region_filter=region,
        ),
        emitter=emitter,
        server="maximo-mcp-server",
        tool="maximo_query_availability",
        via_gateway=True,
    )
    sap_task = _call_with_emit(
        lambda: _gateway_call_tool(
            toolsets["sap-mcp-server"],
            "sap_workforce_by_basin",
            basin=_basin_for_region(region),
        ),
        emitter=emitter,
        server="sap-mcp-server",
        tool="sap_workforce_by_basin",
        via_gateway=True,
    )
    fdp_task = _call_with_emit(
        lambda: _gateway_call_tool(
            toolsets["fdp-mcp-server"],
            "fdp_get_customer_config",
            customer_id=customer_id,
            canonical_id=canonical_id,
        ),
        emitter=emitter,
        server="fdp-mcp-server",
        tool="fdp_get_customer_config",
        via_gateway=True,
    )
    # InTouch / Knowledge Catalog spec lookup uses the platform-managed
    # KC MCP server's `lookup_context` prebuilt tool. The argument shape
    # is the KC tool's (entry_name + aspect_types), not our internal
    # `query_intouch_specs` signature — the wrapper here normalizes it.
    intouch_task = _call_with_emit(
        lambda: _gateway_call_tool(
            toolsets["knowledge-catalog-mcp"],
            "lookup_context",
            entry_name=canonical_id,
            aspect_types=["intouch_spec"],
        ),
        emitter=emitter,
        server="knowledge-catalog-mcp",
        tool="lookup_context",
        via_gateway=True,
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


async def _via_in_process_skills(
    request: CapacityGapRequest, emitter: _CanvasEmitter
) -> SystemQueryResults:
    """Local-dev fallback — call skill functions directly.

    Identical contract to ``_via_agent_gateway`` so the workflow doesn't
    care which path ran. Still emits canvas MCP-call events so Replay
    mode (recorded local runs) produces the same canvas behavior as Live
    mode (Agent-Gateway recorded runs).
    """
    canonical_id = request.canonical_asset_id or ""

    maximo_task = _call_with_emit(
        lambda: asyncio.to_thread(
            query_maximo_availability,
            canonical_id=canonical_id,
            region_filter=request.target_region,
        ),
        emitter=emitter,
        server="maximo-mcp-server",
        tool="maximo_query_availability",
        via_gateway=False,
    )
    sap_task = _call_with_emit(
        lambda: asyncio.to_thread(
            query_sap_workforce,
            basin=_basin_for_region(request.target_region),
        ),
        emitter=emitter,
        server="sap-mcp-server",
        tool="sap_workforce_by_basin",
        via_gateway=False,
    )
    fdp_task = _call_with_emit(
        lambda: asyncio.to_thread(
            query_fdp_customer_config,
            customer_id=request.customer_id or "",
            canonical_id=canonical_id,
        ),
        emitter=emitter,
        server="fdp-mcp-server",
        tool="fdp_get_customer_config",
        via_gateway=False,
    )
    intouch_task = _call_with_emit(
        lambda: asyncio.to_thread(
            query_intouch_specs,
            canonical_id=canonical_id,
        ),
        emitter=emitter,
        server="knowledge-catalog-mcp",
        tool="query_intouch_specs",
        via_gateway=False,
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
async def parallel_system_queries(node_input: dict, ctx: Context) -> Event:
    """Fan out parallel queries to all four enterprise systems.

    Selects the Agent-Gateway path when ``AGENT_GATEWAY_ENDPOINT`` is set,
    otherwise falls back to the in-process skill calls. Emits canvas
    events for the node lifecycle and one started/completed pair per
    MCP call so the canvas can render the four-pill fan-out animation.
    """
    request = CapacityGapRequest(**node_input)
    emitter = _CanvasEmitter(ctx)
    node_started = datetime.utcnow()

    # DEMO NARRATION: "Notice the trace — and the canvas. Four parallel MCP
    # calls light up as pills, one per system. The canvas is consuming
    # events from the Workflow via the A2A SSE stream. This isn't polling;
    # it's the agent broadcasting its state."
    emitter.add(
        NodeStartedEvent(
            workflow_id=emitter.workflow_id(),
            session_id=emitter.session_id(),
            node_name="parallel_system_queries",
            node_kind="function",
        )
    )

    if not request.canonical_asset_id:
        # Should never happen — resolve_canonical_asset_node ran upstream.
        return Event(
            message="parallel_system_queries: missing canonical_asset_id",
            output=SystemQueryResults().model_dump(),
            state=emitter.state_delta(),
        )

    use_gateway = bool(os.environ.get(_GATEWAY_ENDPOINT_ENV))
    if use_gateway:
        try:
            aggregated = await _via_agent_gateway(request, emitter)
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
        aggregated = await _via_in_process_skills(request, emitter)
        path_label = "in-process"

    node_duration_ms = int((datetime.utcnow() - node_started).total_seconds() * 1000)
    emitter.add(
        NodeCompletedEvent(
            workflow_id=emitter.workflow_id(),
            session_id=emitter.session_id(),
            node_name="parallel_system_queries",
            duration_ms=node_duration_ms,
            output_summary=(
                f"4 systems queried via {path_label}: "
                f"maximo={aggregated.maximo['count']} instances, "
                f"intouch={aggregated.intouch['count']} specs"
            ),
        )
    )

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
        state=emitter.state_delta(),
    )
