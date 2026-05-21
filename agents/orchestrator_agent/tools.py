"""Tools for the Capacity Orchestrator Agent.

Wiring:
- Plan Evaluator as an in-process ``AgentTool`` (no network hop)
- Procurement Approval Agent as a ``RemoteA2aAgent`` wrapped in ``AgentTool``
  (Agent Engine, A2A protocol)
- ``PreloadMemoryTool`` for cross-session memory

Mirrors the marathon-planner reference repo's ``planner_agent/tools.py`` pattern from
the reference repo (``next-26-keynotes/devkey/demo-2``). SkillToolset + MCP
tools are added in TASK-03/TASK-04.
"""

import logging
import os

import httpx
from a2a.client.client import ClientConfig as A2AClientConfig
from a2a.client.client_factory import ClientFactory as A2AClientFactory
from a2a.types import TransportProtocol as A2ATransport
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool

from .auth import GoogleAuthRefresh
from .plan_evaluator.agent import root_agent as plan_evaluator_agent

logger = logging.getLogger(__name__)

# Configurable timeout for Agent Engine A2A requests
AGENT_TIMEOUT_SECONDS = 120


# ============================================================================
# A2A INFRASTRUCTURE — preserved verbatim from the reference repo's pattern
# (SerializableRemoteA2aAgent fixes the Agent Engine "global URL returned in
# agent card, regional URL needed for message:send" issue).
# ============================================================================


def _get_agent_a2a_endpoint(resource_name: str, default_port: int = 8080) -> str:
    """Construct A2A card endpoint URL from Agent Engine resource name or local."""
    if resource_name.startswith("local"):
        port = resource_name.split(":")[1] if ":" in resource_name else default_port
        return f"http://127.0.0.1:{port}/.well-known/agent-card.json"

    parts = resource_name.split("/")
    try:
        location_idx = parts.index("locations") + 1
        location = parts[location_idx]
        api_endpoint = f"https://{location}-aiplatform.googleapis.com"
        return f"{api_endpoint}/v1beta1/{resource_name}/a2a/v1/card"
    except (ValueError, IndexError):
        return resource_name


def _get_agent_a2a_url(resource_name: str) -> str | None:
    """Construct the regional A2A message URL from an Agent Engine resource name."""
    if resource_name.startswith("local"):
        return None
    parts = resource_name.split("/")
    try:
        location_idx = parts.index("locations") + 1
        location = parts[location_idx]
        api_endpoint = f"https://{location}-aiplatform.googleapis.com"
        return f"{api_endpoint}/v1beta1/{resource_name}/a2a"
    except (ValueError, IndexError):
        return None


class SerializableRemoteA2aAgent(RemoteA2aAgent):
    """RemoteA2aAgent with Google Cloud authentication and Agent Engine URL fix.

    Two Agent Engine quirks handled here:
    1. Lazy auth client construction with Google Cloud ADC.
    2. Override the agent card URL — Agent Engine returns a global URL that
       404s on message:send; we override with the regional URL.
    """

    def __init__(self, *, a2a_url: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._a2a_url_override = a2a_url

    async def _ensure_httpx_client(self) -> httpx.AsyncClient:
        """Lazily build an httpx client with ADC auth + retry config."""
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=AGENT_TIMEOUT_SECONDS),
                headers={"Content-Type": "application/json"},
                auth=GoogleAuthRefresh(),
            )
            self._httpx_client_needs_cleanup = True

        if self._a2a_client_factory is None:
            client_config = A2AClientConfig(
                httpx_client=self._httpx_client,
                streaming=False,
                polling=False,
                supported_transports=[A2ATransport.http_json, A2ATransport.jsonrpc],
            )
            self._a2a_client_factory = A2AClientFactory(config=client_config)

        return self._httpx_client

    async def _resolve_agent_card_from_url(self, url: str):
        """Resolve agent card and fix URL for Agent Engine compatibility."""
        card = await super()._resolve_agent_card_from_url(url)
        if self._a2a_url_override:
            logger.info(f"Overriding agent card URL: {card.url} → {self._a2a_url_override}")
            card.url = self._a2a_url_override
        return card


# ============================================================================
# TOOL CONSTRUCTORS
# ============================================================================


def create_plan_evaluator_tool() -> AgentTool:
    """Plan Evaluator is bundled in-process — same deployment as Orchestrator."""
    # DEMO NARRATION: "The Plan Evaluator is bundled in-process via AgentTool —
    # no network hop, sub-second response. Seven weighted criteria specific to
    # oilfield services sourcing decisions."
    return AgentTool(agent=plan_evaluator_agent)


def create_procurement_approval_tool() -> AgentTool:
    """Procurement Gate is remote — Agent Engine, called via A2A."""
    resource_name = os.environ.get("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME")
    if not resource_name:
        raise ValueError("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set")

    endpoint = _get_agent_a2a_endpoint(resource_name, default_port=8089)
    # DEMO NARRATION: "The Procurement Approval Agent runs on Agent Engine,
    # called via A2A protocol — the open standard that bridges to SAP Joule
    # agents. Cryptographically signed agent cards, runtime policy enforcement
    # via Agent Gateway."
    remote = SerializableRemoteA2aAgent(
        name="procurement_approval_agent",
        description=(
            "Procurement Approval Agent. Reviews sourcing plans for procurement "
            "readiness: budget threshold, customer authorization, certification "
            "chain, regulatory clearance."
        ),
        agent_card=endpoint,
        a2a_url=_get_agent_a2a_url(resource_name),
    )
    return AgentTool(agent=remote)


# NOTE: this file used to define `_load_skills()` + `get_tools()` mirroring
# the marathon-planner reference pattern, but the Orchestrator is a
# `Workflow` agent — root_agent in `agent.py` doesn't consume a flat tool
# list, it composes nodes via edges. Workflow LLM nodes (equivalence_lookup,
# sourcing_logistics, revise_plan, plan_evaluator) each manage their own
# `tools=` list, so `get_tools()` had no caller. Removed (code-review MED #15).
# The two AgentTool constructors above stay because the Plan Evaluator is
# called as an AgentTool from the Workflow's plan_evaluator_tool edge.
