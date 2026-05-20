"""Seed Memory Bank with persona-specific starting memories.

Re-runnable: re-runs append additional memory entries (Memory Bank does
not deduplicate on canonical content). For a clean reset, run
`make reset-memory-bank` (a future Makefile target that calls Memory
Bank's delete endpoints) before re-seeding.

Run after all four agents are deployed (so AGENT_ENGINE_IDs are known).

Usage:
    venv-deploy-310/bin/python -m memory_bank.seed_memories
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TypedDict

from dotenv import load_dotenv
from google.adk.memory import VertexAiMemoryBankService
from google.adk.memory.memory_entry import MemoryEntry
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


class Seed(TypedDict):
    """A single memory record to seed.

    `topic` is metadata used by TOPIC_TO_AGENT_ENV to route to the right
    Memory Bank backend; it is NOT passed to add_memory (topics matter only
    for the extractor on the auto-save path).
    """
    user_id: str
    topic: str
    content: str  # natural-language statement optimized for semantic search


# Map each app_name to the env var holding its Agent Engine resource name.
# app_name must match the explicit AdkApp(app_name=...) set in the deploy
# script for each agent (see src/<agent>/runtime/deploy.py).
APP_NAME_TO_ENV: dict[str, str] = {
    "capacity_orchestrator_agent":  "ORCHESTRATOR_AGENT_RESOURCE_NAME",
    "procurement_approval_agent":   "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME",
    "forecast_review_agent":        "FORECAST_REVIEW_AGENT_RESOURCE_NAME",
    "capacity_planning_agent":      "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
}

# Topic → app_name that owns it (declared in that agent's memory_manager.py).
TOPIC_TO_APP: dict[str, str] = {
    "sourcing_history":     "capacity_orchestrator_agent",
    "planner_preferences":  "capacity_orchestrator_agent",
    "equivalence_patterns": "capacity_orchestrator_agent",
    "approval_history":     "procurement_approval_agent",
    "blocker_patterns":     "procurement_approval_agent",
    "rationale_patterns":   "forecast_review_agent",
    "leader_profiles":      "forecast_review_agent",
    "risk_tolerance":       "capacity_planning_agent",
    "buffer_outcomes":      "capacity_planning_agent",
}


# ----------------------------------------------------------------------------
# Persona seed data — natural-language statements optimized for search.
# Each statement should match how a user might phrase a question:
#   "What's my region?"           -> region statement returned
#   "What customers do I cover?"  -> customer portfolio statement returned
# ----------------------------------------------------------------------------

MARIA_SEEDS: list[Seed] = [
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "planner_preferences",
        "content": (
            "Maria Adeyemi is the Operations Control Center Planner for the "
            "West Africa basin. Primary hubs: Lagos (Nigeria), Luanda (Angola), "
            "Port Harcourt (Nigeria). Authorization tier: Tier 2 with $500K "
            "self-approve threshold. Prefers imperial units, English (en-US)."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "planner_preferences",
        "content": (
            "Maria's customer portfolio: Chevron-Lagos Deepwater (next milestone: "
            "Tool X delivery on 2026-05-22) and Shell-Angola Block 17 (workforce "
            "rotation on 2026-06-01)."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "sourcing_history",
        "content": (
            "Last sourcing decision (approved 2026-05-15, Chevron-Lagos Deepwater): "
            "Tool X-V7 ex-Lagos chosen as functional substitute for Tool X. The "
            "naive plan was an Australia→Luanda cargo charter; equivalence lookup "
            "against InTouch §3.2 surfaced Tool X-V7 available at Lagos at 50km "
            "distance. Avoided $474K of cargo-plane cost."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "equivalence_patterns",
        "content": (
            "For Chevron-Lagos contracts, Tool X-V7 is an accepted functional "
            "substitute for Tool X (Knowledge Catalog confidence 0.92, grounded in "
            "InTouch §3.2). Substitution approved for completion-phase use under "
            "the same operational envelope."
        ),
    },
]


TOMAS_SEEDS: list[Seed] = [
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "planner_preferences",
        "content": (
            "Tomas Reyes is the Fleet Scheduler for the Permian basin (with Eagle "
            "Ford as a secondary). Hubs: Midland and Odessa, Texas. He runs "
            "conservative on buffer tradeoffs — prefers higher buffer over "
            "late-start exposure. Units: imperial."
        ),
    },
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "risk_tolerance",
        "content": (
            "Tomas weights buffer_pct vs late_start_cost at roughly 1.5x — he "
            "accepts ~50% more idle cost to avoid a late start. For Q2 2026 "
            "ExxonMobil Permian frac pump fleet, he approved a 12% buffer."
        ),
    },
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "buffer_outcomes",
        "content": (
            "Q2 2026 ExxonMobil Permian frac pump fleet: 12% buffer delivered "
            "on-time start with 210 idle hours. Slight over-buffer; in retro "
            "Tomas noted 10% would have sufficed."
        ),
    },
]


DAVID_SEEDS: list[Seed] = [
    {
        "user_id": "david-basin-leader-west-africa",
        "topic": "leader_profiles",
        "content": (
            "David Okeke is the Basin Leader for West Africa. Hubs: Lagos and "
            "Port Harcourt. He overrides ML forecasts aggressively when geological "
            "survey signals indicate delay — e.g., Q3 2026 Chevron-Lagos forecast "
            "was revised -18% versus the ML baseline."
        ),
    },
    {
        "user_id": "david-basin-leader-west-africa",
        "topic": "rationale_patterns",
        "content": (
            "David's most common override rationale is the geological_survey_delay "
            "tag (3 overrides in the last 2 quarters). When this tag appears, the "
            "actual start date typically shifts ~14 days later than the ML forecast."
        ),
    },
]


PRIYA_SEEDS: list[Seed] = [
    {
        "user_id": "priya-operations-vp-global",
        "topic": "planner_preferences",
        "content": (
            "Priya is the Operations VP with global scope. She works in "
            "cross-basin rollups: commit attainment by customer, fleet utilization "
            "versus target, basin-level revenue attainment. Units: metric."
        ),
    },
]


RAFAEL_SEEDS: list[Seed] = [
    {
        "user_id": "rafael-citizen-dev-permian",
        "topic": "planner_preferences",
        "content": (
            "Rafael is a citizen developer focused on the Permian basin. He builds "
            "Gemini Enterprise extensions and prefers Knowledge Catalog metadata "
            "to be visible in agent outputs (canonical_id, aspect references, "
            "confidence scores)."
        ),
    },
]


AYESHA_SEEDS: list[Seed] = [
    {
        "user_id": "ayesha-audit-director-global",
        "topic": "planner_preferences",
        "content": (
            "Ayesha is the Audit Director with global scope. Her audit focus: "
            "procurement-approval decisions above the $500K threshold, Model "
            "Armor blocked-attack incidents, and the Agent Identity SPIFFE chain "
            "across A2A calls."
        ),
    },
]


ALL_SEEDS: list[Seed] = [
    *MARIA_SEEDS, *TOMAS_SEEDS, *DAVID_SEEDS,
    *PRIYA_SEEDS, *RAFAEL_SEEDS, *AYESHA_SEEDS,
]


# ----------------------------------------------------------------------------
# Writer — VertexAiMemoryBankService.add_memory(*, app_name, user_id, memories)
# ----------------------------------------------------------------------------


def _agent_engine_id_for(app_name: str) -> str | None:
    """Resolve the deployed Reasoning Engine numeric ID for an app_name."""
    env_key = APP_NAME_TO_ENV.get(app_name)
    if env_key is None:
        logger.warning("Unknown app %r — skipping", app_name)
        return None
    value = os.environ.get(env_key)
    if not value:
        logger.warning("%s not set — skipping seed for app %r", env_key, app_name)
        return None
    return value.rsplit("/", 1)[-1]  # strip projects/.../reasoningEngines/ prefix


async def seed_one(seed: Seed) -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")
    app_name = TOPIC_TO_APP.get(seed["topic"])
    if app_name is None:
        logger.warning("No app owns topic %r — skipping", seed["topic"])
        return
    agent_engine_id = _agent_engine_id_for(app_name)
    if agent_engine_id is None:
        return

    service = VertexAiMemoryBankService(
        project=project, location=location, agent_engine_id=agent_engine_id,
    )

    # DEMO NARRATION: "We're populating Memory Bank with natural-language seed
    # memories per persona. PreloadMemoryTool runs automatically on every LLM
    # turn — it takes the user's prompt as the search query and pulls matching
    # memories into the prompt context. No 'profile document' to manage."
    memory_entry = MemoryEntry(
        content=types.Content(
            role="user",
            parts=[types.Part.from_text(text=seed["content"])],
        ),
    )
    await service.add_memory(
        app_name=app_name,
        user_id=seed["user_id"],
        memories=[memory_entry],
    )
    logger.info(
        "Seeded: app=%s user=%s topic=%s",
        app_name, seed["user_id"], seed["topic"],
    )


async def main() -> None:
    for seed in ALL_SEEDS:
        await seed_one(seed)
    logger.info("Memory Bank seeding complete (%d memories).", len(ALL_SEEDS))


if __name__ == "__main__":
    asyncio.run(main())
