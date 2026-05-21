"""Memory Manager for the Capacity Planning Agent.

Tracks per-planner risk tolerance, basin defaults, and the on-time-vs-buffer
tradeoff curves that have worked across sessions.
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


RISK_TOLERANCE = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="risk_tolerance",
        description="""Track per-planner risk tolerance settings across basins.

        Extract:
        - Planner identifier (e.g. tomas)
        - Basin (West Texas, Permian, North Sea, ...)
        - Risk tolerance value (0.0-1.0)
        - Outcome of past recommendations at this tolerance

        Format: "Risk: planner={p}, basin={b}, tolerance={n}"
        Example: "Risk: planner=tomas, basin=West Texas, tolerance=0.7"
        """,
    )
)


BUFFER_OUTCOMES = MemoryTopic(
    custom_memory_topic=CustomMemoryTopic(
        label="buffer_outcomes",
        description="""Track recommended-vs-actual buffer outcomes.

        Format: "Buffer: basin={b}, recommended={n}_days, actual_on_time_rate={r}"
        Example: "Buffer: basin=Permian, recommended=8_days, actual_on_time_rate=0.68"
        """,
    )
)


def create_capacity_planning_memory_topics() -> MemoryBankCustomizationConfig:
    """Memory Bank customization for the Capacity Planning Agent."""
    return MemoryBankCustomizationConfig(memory_topics=[RISK_TOLERANCE, BUFFER_OUTCOMES])


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
