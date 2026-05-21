"""Memory Manager for the Capacity Orchestrator Agent.

Wires Memory Bank with oilfield-domain custom topics so the Orchestrator
learns across sessions (sourcing decisions, planner preferences, basin
context). Mirrors the marathon-planner reference repo's auto_save_memories pattern from
the reference repo, with topics rewritten for the S&OP domain.

Memory Bank is regional (us-central1). The model layer can use a different
region via `agents.utils.global_gemini.GlobalGemini` — the dual-location pattern
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
#
# Topic descriptions read the active customer skin at runtime so the
# extraction-guidance examples ("Sourcing: asset=Tool X variant ...") map
# to whichever customer this deployment is skinned for. Module-level
# constants would freeze the example values at the wrong moment.


def _skin_examples() -> dict[str, str]:
    """Skin-derived example fragments for the topic descriptions.

    Falls back to in-house defaults if the skin loader can't be reached
    (e.g., during a unit test that monkey-patches the loader away).
    """
    hero_label = "Tool X variant"
    equivalent_label = "Tool X-V7"
    customer_label = "Gulf Petroleum"
    persona_id = "maria"
    basin_label = "West Africa OCC"
    spec_ref = "InTouch 3.2"
    try:
        from agents.utils.skin_loader import get_active_skin  # noqa: PLC0415

        skin = get_active_skin()
        hero_label = skin.taxonomy.hero_asset.canonical_label or hero_label
        # First secondary asset, if any, doubles as the equivalent label.
        for asset in skin.taxonomy.secondary_assets or []:
            if asset.canonical_label:
                equivalent_label = asset.canonical_label
                break
        # Persona 3 = the cargo-plane operator. May be None on minimal skins.
        for p in skin.personas or []:
            if p.scenario_slug == "cargo-plane":
                persona_id = p.id or persona_id
                break
        sc = skin.scenario("cargo-plane")
        if sc.customer_account_name:
            customer_label = sc.customer_account_name
        # Skin doesn't carry a direct "basin" label — fall back to the
        # location-focus label (e.g. "Luanda, Angola" / "Búzios, Brazil"),
        # which is what extraction guidance actually needs as a hint.
        if sc.location_focus_label:
            basin_label = sc.location_focus_label
    except Exception:  # noqa: BLE001 — defensive; defaults still steer extraction
        pass
    return {
        "hero_label": hero_label,
        "equivalent_label": equivalent_label,
        "customer_label": customer_label,
        "persona_id": persona_id,
        "basin_label": basin_label,
        "spec_ref": spec_ref,
    }


def _build_sourcing_history(ex: dict[str, str]) -> MemoryTopic:
    example = (
        f"\"Sourcing: asset={ex['hero_label']}, "
        f"basin={ex['basin_label']}, savings_usd=380000\""
    )
    return MemoryTopic(
        custom_memory_topic=CustomMemoryTopic(
            label="sourcing_history",
            description=f"""Track sourcing decisions for service capacity gaps across sessions.

            Extract:
            - Requested asset (canonical_id + canonical_label)
            - Target basin / region
            - Recommended source location and transit mode
            - Naive-baseline avoided cost (savings)
            - Final approval outcome

            Format: "Sourcing: asset={{asset}}, basin={{basin}}, savings_usd={{n}}"
            Example: {example}
            """,
        )
    )


def _build_planner_preferences(ex: dict[str, str]) -> MemoryTopic:
    return MemoryTopic(
        custom_memory_topic=CustomMemoryTopic(
            label="planner_preferences",
            description=f"""Track per-planner defaults and authorization context.

            Extract:
            - Basin the planner operates in
            - Authorization tier (informs $500K threshold logic)
            - Customer compatibility preferences
            - Default transit modes they accept

            Format: "Preference: planner={{planner}}, type={{type}}, value={{value}}"
            Example: "Preference: planner={ex['persona_id']}, type=basin, value={ex['basin_label']}"
            """,
        )
    )


def _build_equivalence_patterns(ex: dict[str, str]) -> MemoryTopic:
    return MemoryTopic(
        custom_memory_topic=CustomMemoryTopic(
            label="equivalence_patterns",
            description=f"""Track which canonical-asset equivalences have been applied successfully.

            Extract:
            - Canonical asset + the functionally-equivalent variant chosen
            - Customer + context in which the substitution was accepted
            - Spec reference that grounded the equivalence

            Format: "Equivalence: asset={{a}} -> {{b}}, context={{ctx}}, spec={{ref}}"
            Example: "Equivalence: {ex['hero_label']} -> {ex['equivalent_label']}, "
                     "customer={ex['customer_label']}, spec={ex['spec_ref']}"
            """,
        )
    )


def create_orchestrator_memory_topics() -> MemoryBankCustomizationConfig:
    """Build the Memory Bank customization config used by the Orchestrator.

    Reads the active customer skin at call time so the topic
    descriptions' example fragments match the skinned customer.
    """
    ex = _skin_examples()
    return MemoryBankCustomizationConfig(
        memory_topics=[
            _build_sourcing_history(ex),
            _build_planner_preferences(ex),
            _build_equivalence_patterns(ex),
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
#
# `_cached_memory_service` is module-scoped so we don't pay the channel-setup
# + ADC-refresh cost on every agent turn (code-review MED #12). Memory Bank's
# `add_session_to_memory` underneath the cached service is still per-call; we
# just stop reconstructing the client.


_cached_memory_service: VertexAiMemoryBankService | None = None


def _get_memory_service() -> VertexAiMemoryBankService | None:
    global _cached_memory_service  # noqa: PLW0603 — small intentional cache
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
        project=project_id,
        location=location,
        agent_engine_id=agent_engine_id,
    )
    return _cached_memory_service


async def auto_save_memories(callback_context: "CallbackContext") -> None:
    """Persist the session into Memory Bank after the agent finishes responding.

    No-op if AGENT_ENGINE_ID is unset (local dev). Catches exceptions so a
    Memory Bank outage cannot kill an agent turn.
    """
    memory_service = _get_memory_service()
    if memory_service is None:
        return
    try:
        await memory_service.add_session_to_memory(callback_context._invocation_context.session)
    except Exception as e:
        # DEMO NARRATION: "Memory Bank failures don't block the agent's response —
        # we log and proceed. The full enterprise mode has Cloud Trace + alerting
        # wired up so SRE sees these errors."
        logger.warning("Failed to save memories: %s", e)
