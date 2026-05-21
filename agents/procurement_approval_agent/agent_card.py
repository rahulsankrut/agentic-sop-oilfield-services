"""A2A Agent Card for the Procurement Approval Agent.

Describes the agent for A2A discovery. Used by ``runtime/deploy.py`` when
wrapping the root_agent in ``A2aAgent`` for Agent Engine deployment.
"""

from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card


def _build_examples() -> list[str]:
    """Skin-derived A2A AgentCard examples (TASK-13 Step 5).

    Reads the active customer skin's cargo-plane scenario to produce
    examples that match the customer the agent is currently skinned to.
    Falls back to in-house defaults if the skin loader can't be reached
    (e.g., during agent_card import at deploy-script-load time).
    """
    try:
        from agents.utils.skin_loader import get_active_skin  # noqa: PLC0415

        sc = get_active_skin().scenario("cargo-plane")
    except Exception:  # noqa: BLE001
        return [
            "Approve sourcing $40K Tool X-V7 from Lagos to Luanda",
            "Approve sourcing $420K cargo charter from Darwin to Luanda",
            "Approve sourcing $750K MWD tool from Bohai to Houston",
        ]
    rec_cost = int(sc.recommended_cost_usd or 40_000)
    naive_cost = int(sc.naive_cost_usd or 420_000)
    return [
        f"Approve sourcing ${rec_cost // 1000}K "
        f"{sc.asset_focus_label} from "
        f"{sc.recommended_origin_label or '(origin)'} to {sc.location_focus_label}",
        f"Approve sourcing ${naive_cost // 1000}K cargo charter from "
        f"{sc.naive_origin_label or '(naive origin)'} to {sc.location_focus_label}",
        "Approve sourcing $750K MWD tool from Bohai to Houston",
    ]


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
        examples=_build_examples(),
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
