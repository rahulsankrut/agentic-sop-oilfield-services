"""LLM node: reason about functional equivalence using Knowledge Catalog MCP.

Scoped to ONE decision: given a canonical asset that's not directly available,
pick the best functional substitute with a confidence score and a Knowledge
Catalog (InTouch) grounding reference. Structured output via
``EquivalentAssetCandidate``.

TASK-06 Step 5 refactor: the canonical asset model lives in Knowledge Catalog
as Entries + Aspects (see ``knowledge_catalog/``). This node calls the managed
remote MCP server at ``https://dataplex.googleapis.com/mcp`` *through Agent
Gateway*, using the prebuilt MCP tools. The MCP server itself is operated by
Google Cloud and auto-enabled when the Dataplex API is enabled — we do not
host any Knowledge Catalog MCP infrastructure ourselves. Authentication is
OAuth 2.0 with IAM, using the Orchestrator's Agent Identity; required roles
on the agent's service account are ``roles/mcp.toolUser`` plus
``roles/dataplex.catalogViewer`` (read-only is sufficient for equivalence
lookup; the ``dataplex.readonly`` OAuth scope covers it).

Tool surface (verified against
``https://docs.cloud.google.com/dataplex/docs/reference/mcp`` on 2026-05-19):

- ``search_entries`` — searches the catalog for entries matching a query
- ``lookup_context`` — fetches rich metadata + relationships for one or more
  entries (this is how we pull the cross-system aliases + functional
  equivalence Aspect data on the canonical Tool X entry)

Note: the reference MCP doc does NOT currently list ``lookup_entry`` or
``search_aspect_types`` as exposed MCP tools (despite their presence in the
REST API). We wire ``search_entries`` + ``lookup_context`` only.

Local-dev fallback
------------------
When ``AGENT_GATEWAY_ENDPOINT`` is unset (unit tests, local skeleton runs),
this module falls back to the pre-TASK-06 shape: a bare ``Agent`` with no MCP
tools, reasoning purely against the JSON payload passed in via the workflow.
The instruction in ``EQUIVALENCE_LOOKUP_INSTRUCTION`` already mentions
"Knowledge Catalog" and a "ranked list of functional-equivalence candidates"
that the upstream parallel-queries node hands it, so the prompt is unchanged
between modes. See ``EQUIVALENCE_LOOKUP_USING_MCP`` below for the flag the
rest of the workflow can inspect.

ADK 2.0 MCP API used here (verified against ``https://adk.dev/tools-custom/
mcp-tools/`` on 2026-05-19):

    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=os.environ["AGENT_GATEWAY_ENDPOINT"],
            headers={...},  # Agent Identity / gateway routing
        ),
        tool_filter=["search_entries", "lookup_context"],
    )

The toolset auto-discovers tools from the MCP server; the ``tool_filter``
restricts the surface area to just the two tools this node needs.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import EquivalentAssetCandidate
from agents.utils.global_gemini import GlobalGemini

from ..events.canvas_events import (
    EquivalentAssetFoundEvent,
    KnowledgeCatalogLookupEvent,
)
from ..prompts import EQUIVALENCE_LOOKUP_INSTRUCTION
from ..services.memory_manager import auto_save_memories

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("EQUIVALENCE_LOOKUP_MODEL", "gemini-3.1-pro-preview")

# Knowledge Catalog MCP tool surface — keep the list narrow so the LLM doesn't
# get a 10-tool buffet. ``search_entries`` is the entry-point query;
# ``lookup_context`` returns the canonical entity + all its Aspects (the
# cross-system aliases + functional_equivalence rows the agent reasons over).
_KC_MCP_TOOLS = ("search_entries", "lookup_context")

# Identifier the gateway uses to route to the Knowledge-Catalog-managed MCP
# server registered in Agent Registry (TASK-05 Step 6). Carried as a header on
# the gateway-fronted MCP connection. If/when the gateway exposes a per-server
# query parameter, the routing convention may shift — keep it in one place.
_KC_GATEWAY_SERVER_ID = "knowledge-catalog-mcp"


def _build_mcp_toolset() -> list:
    """Construct the McpToolset list when ``AGENT_GATEWAY_ENDPOINT`` is set.

    Returns an empty list in local-dev / unit-test mode (env var unset) so the
    agent definition falls back to the pre-MCP shape (output_schema only).

    Raises ImportError back to the caller only if the env var IS set but the
    ADK MCP imports fail — that's a deploy-config problem, not a local-dev
    one, and silent fallback would hide it.
    """
    gateway_url = os.getenv("AGENT_GATEWAY_ENDPOINT")
    if not gateway_url:
        logger.info(
            "AGENT_GATEWAY_ENDPOINT not set; equivalence_lookup running in "
            "local-dev mode (no Knowledge Catalog MCP tools). Set the env var "
            "to route through Agent Gateway to the managed Dataplex MCP server."
        )
        return []

    # Imports are lazy so local-dev / 3.10-runtime deploys don't pay the cost
    # of resolving the MCP toolset module unless they're going to use it.
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    # Agent Gateway accepts the agent's identity token plus a routing header
    # naming the registered MCP server. The exact header name is governed by
    # the gateway config from TASK-05; ``X-Agent-Mcp-Server`` is the working
    # convention until/unless the gateway team locks a different name.
    headers = {
        "X-Agent-Mcp-Server": _KC_GATEWAY_SERVER_ID,
    }
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=gateway_url,
                headers=headers,
            ),
            tool_filter=list(_KC_MCP_TOOLS),
        ),
    ]


# Exposed for the rest of the workflow (and tests) to introspect which mode
# this node is running in without re-reading the env var.
EQUIVALENCE_LOOKUP_USING_MCP: bool = bool(os.getenv("AGENT_GATEWAY_ENDPOINT"))


def _emit_kc_drawer_a2ui(ctx, candidate_dict: dict) -> None:
    """TASK-45 Phase 2 — emit a KC drawer A2UI surface.

    Called inside the after-agent callback once the equivalence decision
    has produced a candidate. The canvas's A2UIProvider drains
    ``a2ui_envelopes`` from the SSE state_delta and renders the surface
    client-side. Failures are swallowed — A2UI is best-effort, and the
    bespoke drawer remains the fallback.
    """
    if not candidate_dict:
        return
    try:
        from agents.utils import a2ui  # noqa: PLC0415

        aspects = {
            "cross_system_aliases": candidate_dict.get("aliases", {}) or {},
            "functional_equivalences": [candidate_dict] if candidate_dict else [],
            "asset_specification": {
                "manufacturer": candidate_dict.get("manufacturer", ""),
                "introduced_year": candidate_dict.get("introduced_year", ""),
            },
        }
        a2ui_msgs = a2ui.kc_drawer(
            str(candidate_dict.get("canonical_id", "")),
            str(candidate_dict.get("canonical_label", "")),
            aspects=aspects,
        )
        ctx.state["a2ui_envelopes"] = [
            *(ctx.state.get("a2ui_envelopes") or []),
            *a2ui_msgs,
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("equivalence_lookup a2ui emit failed: %s", exc)


async def _emit_equivalence_events(callback_context: CallbackContext) -> None:
    """Surface the equivalence decision to the canvas as two events.

    Runs after the LLM produces a structured ``EquivalentAssetCandidate``.
    We mutate ``ctx.state['canvas_events']`` directly here — the framework
    propagates the state delta on the next emitted event. After emitting,
    we chain to :func:`auto_save_memories` to preserve Memory Bank
    persistence.
    """
    try:
        ctx = callback_context
        workflow_id = ""
        session_id = ""
        try:
            workflow_id = ctx.state.get("workflow_id", "") or ""
            session_id = ctx.state.get("session_id", "") or ""
        except Exception:
            pass

        # Pull the LLM's structured output. ADK stores the most recent
        # node output on ``ctx.output`` (Workflow API) when the agent ran
        # as a workflow node.
        output: Any = None
        try:
            output = ctx.output
        except Exception:
            output = None

        candidate_dict: dict[str, Any] | None = None
        if isinstance(output, dict):
            candidate_dict = output
        elif hasattr(output, "model_dump"):
            try:
                candidate_dict = output.model_dump(mode="json")
            except Exception:
                candidate_dict = None

        new_events: list[dict[str, Any]] = []
        try:
            existing = list(ctx.state.get("canvas_events", []) or [])
        except Exception:
            existing = []

        if candidate_dict:
            equiv = candidate_dict.get("equivalent_asset") or {}
            original = candidate_dict.get("original_asset") or {}
            kc_event = KnowledgeCatalogLookupEvent(
                workflow_id=workflow_id,
                session_id=session_id,
                canonical_id=str(equiv.get("canonical_id") or original.get("canonical_id") or ""),
                canonical_label=str(
                    equiv.get("canonical_label") or original.get("canonical_label") or ""
                ),
                aspects=candidate_dict,
            )
            new_events.append(kc_event.model_dump(mode="json"))

            location = candidate_dict.get("source_location") or {}
            confidence = candidate_dict.get("confidence")
            try:
                confidence_f = float(confidence) if confidence is not None else 0.0
            except (TypeError, ValueError):
                confidence_f = 0.0
            found_event = EquivalentAssetFoundEvent(
                workflow_id=workflow_id,
                session_id=session_id,
                original_asset=original,
                equivalent_asset=equiv,
                confidence=confidence_f,
                rationale_source=str(candidate_dict.get("rationale_source") or ""),
                location=location if isinstance(location, dict) else {},
            )
            new_events.append(found_event.model_dump(mode="json"))

        if new_events:
            try:
                ctx.state["canvas_events"] = [*existing, *new_events]
            except Exception as exc:
                logger.warning("Failed to write canvas_events to state: %s", exc)

        _emit_kc_drawer_a2ui(ctx, candidate_dict)
    except Exception as exc:  # noqa: BLE001
        # Never let canvas-event emission fail the agent turn.
        logger.warning("equivalence_lookup canvas-event emit failed: %s", exc)

    # Chain to the original Memory Bank callback so persistence still runs.
    await auto_save_memories(callback_context)


# DEMO NARRATION: "First AI node in the workflow — and this is where Issue 4
# dissolves visibly. The equivalence agent is calling Knowledge Catalog
# through Agent Gateway. The MCP server itself is managed by Google Cloud —
# we don't host it, we don't run it. When the Dataplex API is enabled the
# remote MCP server at dataplex.googleapis.com/mcp is enabled automatically.
# The catalog returns the canonical Tool X entry with all its aliases — SAP
# material number, Maximo equipment ID, FDP config ID — and the functional
# equivalence Aspect listing Tool X-V7 as a substitute per InTouch spec §3.2.
# One call. One canonical entity. No taxonomic chaos. No infrastructure we
# own. Gemini reasons against that canonical entity and returns a structured
# candidate with confidence score and rationale source. One job. Predictable
# input, structured output, no instruction sprawl."
equivalence_lookup_agent = Agent(
    name="equivalence_lookup",
    model=GlobalGemini(model=_MODEL_NAME),
    description=(
        "Decision node: given a canonical asset that's unavailable in the target "
        "region, return the best functional equivalent with confidence + spec "
        "rationale. Sources its evidence from Knowledge Catalog via the managed "
        "Dataplex MCP server, routed through Agent Gateway."
    ),
    instruction=EQUIVALENCE_LOOKUP_INSTRUCTION,
    output_schema=EquivalentAssetCandidate,
    tools=[*_build_mcp_toolset(), preload_memory],
    after_agent_callback=_emit_equivalence_events,
    generate_content_config=GenerateContentConfig(
        temperature=0.0,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
