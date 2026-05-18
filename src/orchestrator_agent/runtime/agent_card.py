"""A2A Agent Card for the Capacity Orchestrator Agent.

Describes the agent's capabilities for A2A protocol discovery. Uses the
vertexai create_agent_card utility for proper Agent Engine integration.

Pattern preserved verbatim from
github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-2/src/planner_agent/runtime/agent_card.py.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card


def create_orchestrator_card() -> AgentCard:
    """Create an A2A AgentCard for the Capacity Orchestrator Agent."""
    skill = AgentSkill(
        id="resolve_capacity_gap",
        name="Resolve Service Capacity Gap",
        description=(
            "Design a SourcingPlan that resolves an oilfield service capacity gap. "
            "Decomposes the request across SAP, Maximo, FDP, and InTouch via MCP, "
            "coordinates with the Plan Evaluator and Procurement Approval Agent, "
            "and returns a scored, approved plan."
        ),
        tags=["sourcing", "capacity", "orchestration", "multi-agent", "oilfield"],
        examples=[
            "Tool X variant needed in Luanda by Friday — what are my options?",
            "We have a capacity gap on completions equipment in West Texas next week",
            "Find the cheapest functionally-equivalent asset for our Bohai operation",
        ],
    )

    card = create_agent_card(
        agent_name="orchestrator_agent",
        description=(
            "Capacity Orchestrator Agent — lead architect for service capacity gap "
            "resolution. Coordinates Plan Evaluator (in-process AgentTool) and "
            "Procurement Approval Agent (Agent Engine, A2A). Grounded by Knowledge "
            "Catalog. Powered by Gemini 3.1 Pro."
        ),
        skills=[skill],
    )

    if card.capabilities is None:
        card.capabilities = AgentCapabilities(streaming=True)
    else:
        card.capabilities.streaming = True

    return card
