"""Memory Manager for the Capacity Orchestrator Agent.

Wires Memory Bank with oilfield-domain custom topics so the Orchestrator
learns across sessions (sourcing decisions, planner preferences, basin
context). Mirrors the marathon planner's auto_save_memories pattern from
the reference repo, with topics rewritten for the S&OP domain.

Memory Bank is regional (us-central1). The model layer can use a different
region via `src.utils.global_gemini.GlobalGemini` — the dual-location pattern
keeps Memory Bank on us-central1 while model calls go to 'global'. This
module reads AGENT_ENGINE_LOCATION (or GOOGLE_CLOUD_LOCATION as fallback)
to construct the Memory Bank service with the right region.
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


# ============================================================================
# CUSTOM MEMORY TOPICS — Oilfield S&OP domain
# ============================================================================

SOURCING_HISTORY = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="sourcing_history",
        description="""Track sourcing decisions for service capacity gaps across sessions.

        Extract:
        - Requested asset (canonical_id + canonical_label)
        - Target basin / region (Permian, North Sea, Gulf of Guinea, ...)
        - Recommended source location and transit mode
        - Naive-baseline avoided cost (savings)
        - Final approval outcome

        Format: "Sourcing: asset={asset}, basin={basin}, savings_usd={n}"
        Example: "Sourcing: asset=Tool X variant, basin=West Africa, savings_usd=380000"
        """,
    )
)


PLANNER_PREFERENCES = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="planner_preferences",
        description="""Track per-planner defaults and authorization context.

        Extract:
        - Basin the planner operates in
        - Authorization tier (informs $500K threshold logic)
        - Customer compatibility preferences
        - Default transit modes they accept

        Format: "Preference: planner={planner}, type={type}, value={value}"
        Example: "Preference: planner=maria, type=basin, value=West Africa OCC"
        """,
    )
)


EQUIVALENCE_PATTERNS = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="equivalence_patterns",
        description="""Track which canonical-asset equivalences have been applied successfully.

        Extract:
        - Canonical asset + the functionally-equivalent variant chosen
        - Customer + context in which the substitution was accepted
        - Spec reference that grounded the equivalence (InTouch §x.y)

        Format: "Equivalence: asset={a} -> {b}, context={ctx}, spec={ref}"
        Example: "Equivalence: Tool X -> Tool X-V7, customer=Gulf Petroleum, spec=InTouch 3.2"
        """,
    )
)


def create_orchestrator_memory_topics() -> MemoryBankCustomizationConfig:
    """Build the Memory Bank customization config used by the Orchestrator."""
    return MemoryBankCustomizationConfig(
        memory_topics=[
            SOURCING_HISTORY,
            PLANNER_PREFERENCES,
            EQUIVALENCE_PATTERNS,
        ]
    )


# ============================================================================
# MEMORY SERVICE
# ============================================================================


def create_memory_service(
    project: str | None = None,
    location: str | None = None,
    agent_engine_id: str | None = None,
) -> VertexAiMemoryBankService | None:
    """Create a VertexAiMemoryBankService bound to the regional Memory Bank.

    Returns None if AGENT_ENGINE_ID is not set — useful for local dev where
    we don't want Memory Bank calls hitting a remote backend.
    """
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
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )


# ============================================================================
# CALLBACK — wired into LlmAgent(after_agent_callback=auto_save_memories)
# ============================================================================


async def auto_save_memories(callback_context: "CallbackContext") -> None:
    """Persist the session into Memory Bank after the agent finishes responding.

    No-op if AGENT_ENGINE_ID is unset (local dev). Catches exceptions so a
    Memory Bank outage cannot kill an agent turn.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    agent_engine_id = os.environ.get("AGENT_ENGINE_ID")

    if not agent_engine_id:
        return

    try:
        memory_service = VertexAiMemoryBankService(
            project=project_id,
            location=location,
            agent_engine_id=agent_engine_id,
        )
        await memory_service.add_session_to_memory(callback_context._invocation_context.session)
    except Exception as e:
        # DEMO NARRATION: "Memory Bank failures don't block the agent's response —
        # we log and proceed. The full enterprise mode has Cloud Trace + alerting
        # wired up so SRE sees these errors."
        logger.warning("Failed to save memories: %s", e)
