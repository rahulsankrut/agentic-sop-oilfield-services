"""Memory Manager for the Procurement Approval Agent.

Tracks approval decisions and common blocker patterns across sessions so the
agent learns which prerequisite failures are recurring. Mirrors the marathon
simulator's auto_save_memories pattern, with topics rewritten for procurement.
"""

import logging
import os
from typing import TYPE_CHECKING

from google.adk.memory import VertexAiMemoryBankService
from vertexai._genai.types import (
    MemoryBankCustomizationConfig,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopic as MemoryTopic,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic as CustomMemoryTopic,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext


APPROVAL_HISTORY = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="approval_history",
        description="""Track procurement-approval verdicts for sourcing plans.

        Extract:
        - Approval verdict (approved/blocked) with the dollar amount
        - Blockers encountered (which prerequisite failed)
        - Number of revision iterations before approval

        Format: "Approval: approved={bool}, cost_usd={n}, blockers={list}"
        Example: "Approval: approved=true, cost_usd=40000, blockers=[]"
        """,
    )
)


def _skin_customer_label() -> str:
    """Customer name for memory topic example fragments. Falls back to the
    in-house default if the skin loader can't be reached."""
    try:
        from agents.utils.skin_loader import get_active_skin  # noqa: PLC0415

        sc = get_active_skin().scenario("cargo-plane")
        if sc.customer_account_name:
            return sc.customer_account_name
    except Exception:  # noqa: BLE001
        pass
    return "Gulf Petroleum"


def _build_blocker_patterns(customer_label: str) -> MemoryTopic:
    example = (
        f"\"Blocker: category=budget, customer={customer_label}, "
        f"resolution=tier-2 approval\""
    )
    return MemoryTopic(
        custom_memory_topic=CustomMemoryTopic(
            label="blocker_patterns",
            description=f"""Track recurring procurement blockers so the agent can flag them earlier.

            Extract:
            - Blocker category (budget, customer auth, certification, regulatory)
            - Frequency in the current basin / customer combination
            - Resolution path that worked

            Format: "Blocker: category={{cat}}, customer={{c}}, resolution={{r}}"
            Example: {example}
            """,
        )
    )


def create_procurement_approval_memory_topics() -> MemoryBankCustomizationConfig:
    """Build the Memory Bank customization config used by the Procurement Gate.

    Reads the active customer skin at call time so the topic descriptions'
    example fragments match the skinned customer.
    """
    return MemoryBankCustomizationConfig(
        memory_topics=[APPROVAL_HISTORY, _build_blocker_patterns(_skin_customer_label())]
    )


def create_memory_service(
    project: str | None = None,
    location: str | None = None,
    agent_engine_id: str | None = None,
) -> VertexAiMemoryBankService | None:
    """Create a regional VertexAiMemoryBankService (no-op if AGENT_ENGINE_ID unset)."""
    project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = location or (
        os.environ.get("AGENT_ENGINE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    agent_engine_id = agent_engine_id or os.environ.get("AGENT_ENGINE_ID")
    if not project:
        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable required")
    if not agent_engine_id:
        return None
    return VertexAiMemoryBankService(
        project=project, location=location, agent_engine_id=agent_engine_id
    )


async def auto_save_memories(callback_context: "CallbackContext") -> None:
    """Persist the session into Memory Bank after each turn (no-op locally)."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
    if not agent_engine_id:
        return
    try:
        memory_service = VertexAiMemoryBankService(
            project=project_id, location=location, agent_engine_id=agent_engine_id
        )
        await memory_service.add_session_to_memory(callback_context._invocation_context.session)
    except Exception as e:
        logger.warning("Failed to save memories: %s", e)
