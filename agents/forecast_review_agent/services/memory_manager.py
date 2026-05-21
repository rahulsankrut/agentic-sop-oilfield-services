"""Memory Manager for the Forecast Review Agent.

Tracks rationale-extraction patterns across sessions: which tags are most
predictive of override magnitude, which leaders provide the highest-signal
freeform text, etc.
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


RATIONALE_PATTERNS = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="rationale_patterns",
        description="""Track which rationale tags accompany large forecast overrides.

        Extract:
        - Override magnitude (override_pct_change)
        - Tags chosen (rig_count_decline, operator_delay, etc.)
        - Basin where override was made
        - Whether actuals later confirmed the rationale

        Format: "Rationale: basin={b}, tags={list}, pct_change={n}"
        Example: "Rationale: basin=Permian, tags=[rig_count_decline], pct_change=-0.22"
        """,
    )
)


LEADER_PROFILES = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="leader_profiles",
        description="""Track per-leader override patterns and signal quality.

        Format: "Leader: name={n}, override_freq={n}, avg_magnitude={n}"
        Example: "Leader: name=david, override_freq=4_per_quarter, avg_magnitude=0.18"
        """,
    )
)


def create_forecast_review_memory_topics() -> MemoryBankCustomizationConfig:
    """Memory Bank customization for the Forecast Review Agent."""
    return MemoryBankCustomizationConfig(memory_topics=[RATIONALE_PATTERNS, LEADER_PROFILES])


def create_memory_service(
    project: str | None = None,
    location: str | None = None,
    agent_engine_id: str | None = None,
) -> VertexAiMemoryBankService | None:
    """Create regional VertexAiMemoryBankService (no-op if AGENT_ENGINE_ID unset)."""
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


_cached_memory_service: VertexAiMemoryBankService | None = None


def _get_memory_service() -> VertexAiMemoryBankService | None:
    """Module-cached Memory Bank client. Code-review MED #12."""
    global _cached_memory_service  # noqa: PLW0603
    if _cached_memory_service is not None:
        return _cached_memory_service
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
    if not agent_engine_id:
        return None
    _cached_memory_service = VertexAiMemoryBankService(
        project=project_id, location=location, agent_engine_id=agent_engine_id
    )
    return _cached_memory_service


async def auto_save_memories(callback_context: "CallbackContext") -> None:
    """Persist session into Memory Bank after each turn (no-op locally)."""
    memory_service = _get_memory_service()
    if memory_service is None:
        return
    try:
        await memory_service.add_session_to_memory(callback_context._invocation_context.session)
    except Exception as e:
        logger.warning("Failed to save memories: %s", e)
