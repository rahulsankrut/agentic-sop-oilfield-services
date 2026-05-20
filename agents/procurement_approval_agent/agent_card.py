"""A2A Agent Card for the Procurement Approval Agent.

Describes the agent for A2A discovery. Used by ``runtime/deploy.py`` when
wrapping the root_agent in ``A2aAgent`` for Agent Engine deployment.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card


def create_procurement_approval_card() -> AgentCard:
    """Create an A2A AgentCard for the Procurement Approval Agent."""
    skill = AgentSkill(
        id="approve_sourcing_plan",
        name="Approve Sourcing Plan",
        description=(
            "Review a SourcingPlan for procurement readiness: budget threshold "
            "(default $500K), customer authorization, equipment certification, "
            "regulatory clearance. Returns a structured ProcurementApproval."
        ),
        tags=["procurement", "approval", "oilfield", "gate"],
        examples=[
            "Approve sourcing $40K Tool X-V7 from Lagos to Luanda",
            "Approve sourcing $420K cargo charter from Darwin to Luanda",
            "Approve sourcing $750K MWD tool from Bohai to Houston",
        ],
    )

    card = create_agent_card(
        agent_name="procurement_approval_agent",
        description=(
            "Procurement Approval Agent — fast deterministic approval gate for "
            "oilfield-service sourcing plans. Powered by Gemini 3 Flash."
        ),
        skills=[skill],
    )

    if card.capabilities is None:
        card.capabilities = AgentCapabilities(streaming=False)
    else:
        card.capabilities.streaming = False

    return card
