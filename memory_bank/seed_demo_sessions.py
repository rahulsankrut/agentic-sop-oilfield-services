"""Seed deterministic Sessions for the six demo scenarios.

Each Session has a known ID and is bound to the appropriate user_id +
app_name. The Orchestrator's app_name was set explicitly to
'capacity_orchestrator_agent' in TASK-02 deploy.py; the three standalone
agents declare their own app_names in their respective ``runtime/deploy.py``
files. Match those exactly or the session will be unreachable from the
deployed AdkApp at runtime.

API verification (run before implementation, see
``google/adk/sessions/vertex_ai_session_service.py``):

* ``create_session(*, app_name, user_id, state=None, session_id=None,
  **kwargs)`` — caller-supplied ``session_id`` is supported (matches spec).
* ``get_session(*, app_name, user_id, session_id, config=None)`` — returns
  ``None`` on 404 rather than raising. The spec's bare-``except`` fallback
  was therefore replaced with an explicit ``is None`` check; ``ClientError``
  (non-404) and ``ValueError`` (user_id mismatch) still propagate so
  genuine failures surface loudly.

Env-var naming adaptation: this module reads the four
``*_AGENT_RESOURCE_NAME`` env vars already populated in the project's
``.env`` (full resource names like
``projects/.../reasoningEngines/<id>``) and extracts the trailing engine ID
via ``rsplit("/", 1)[-1]``. The spec's draft proposed
``*_AGENT_ENGINE_ID`` env vars; those don't exist in this repo's ``.env``,
so the resource-name form is canonical here.

Idempotent: re-running skips any session that already exists.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TypedDict

from dotenv import load_dotenv
from google.adk.sessions import VertexAiSessionService

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


class DemoSession(TypedDict):
    session_id: str
    user_id: str
    app_name: str  # must match the deployed AdkApp/A2aAgent app_name
    scenario: str


DEMO_SESSIONS: list[DemoSession] = [
    {
        "session_id": "demo-maria-cargo-plane-v1",
        "user_id": "maria-occ-planner-west-africa",
        "app_name": "capacity_orchestrator_agent",
        "scenario": (
            "Cargo plane Australia -> Luanda being chartered for $474K. Tool "
            "X-V7 available in Lagos at 50km. Need pivot recommendation."
        ),
    },
    {
        "session_id": "demo-tomas-buffer-planning-v1",
        "user_id": "tomas-fleet-scheduler-permian",
        "app_name": "capacity_planning_agent",
        "scenario": (
            "Q3 frac pump fleet buffer planning for ExxonMobil-Permian. "
            "Probabilistic forecast available; need risk-tolerance-aware "
            "buffer recommendation."
        ),
    },
    {
        "session_id": "demo-david-forecast-review-v1",
        "user_id": "david-basin-leader-west-africa",
        "app_name": "forecast_review_agent",
        "scenario": (
            "Q4 forecast review with two basin-leader overrides requiring "
            "rationale extraction and re-ingestion into the model."
        ),
    },
    {
        "session_id": "demo-priya-rollup-v1",
        "user_id": "priya-operations-vp-global",
        "app_name": "capacity_orchestrator_agent",
        "scenario": "Cross-basin Q3 commit-attainment rollup with drill-downs.",
    },
    {
        "session_id": "demo-rafael-extension-v1",
        "user_id": "rafael-citizen-dev-permian",
        "app_name": "capacity_orchestrator_agent",
        "scenario": (
            "Citizen-developer extension that adds a custom Permian view."
        ),
    },
    {
        "session_id": "demo-ayesha-audit-v1",
        "user_id": "ayesha-audit-director-global",
        "app_name": "procurement_approval_agent",
        "scenario": "Audit of last 30 days of procurement-approval decisions.",
    },
]


def _engine_resource_env_for(app_name: str) -> str:
    """Map app_name -> env var name holding the full Agent Engine resource."""
    return {
        "capacity_orchestrator_agent": "ORCHESTRATOR_AGENT_RESOURCE_NAME",
        "procurement_approval_agent": "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME",
        "forecast_review_agent": "FORECAST_REVIEW_AGENT_RESOURCE_NAME",
        "capacity_planning_agent": "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
    }[app_name]


async def seed_one(cfg: DemoSession) -> None:
    """Idempotently seed one demo Session.

    DEMO NARRATION: "Every persona scenario opens with a fixed session ID.
    Same input + same session + same Memory Bank topics = the same agent
    decisions every time we show this. Reproducibility is the point."
    """
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")

    resource_env_name = _engine_resource_env_for(cfg["app_name"])
    resource_name = os.environ.get(resource_env_name)
    if not resource_name:
        logger.warning(
            "No %s set for app %s — skipping session %s",
            resource_env_name,
            cfg["app_name"],
            cfg["session_id"],
        )
        return
    # Resource is "projects/.../reasoningEngines/<id>"; the SDK only needs the id.
    agent_engine_id = resource_name.rsplit("/", 1)[-1]

    service = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )

    # Idempotent check — get_session returns None on 404 (verified in SDK source
    # at google/adk/sessions/vertex_ai_session_service.py:198-204). It can still
    # raise ClientError on other HTTP errors and ValueError on user_id mismatch;
    # both should surface so we deliberately don't swallow them.
    existing = await service.get_session(
        app_name=cfg["app_name"],
        user_id=cfg["user_id"],
        session_id=cfg["session_id"],
    )
    if existing is not None:
        logger.info("Session %s exists — skipping", cfg["session_id"])
        return

    await service.create_session(
        app_name=cfg["app_name"],
        user_id=cfg["user_id"],
        session_id=cfg["session_id"],
        state={"scenario_description": cfg["scenario"]},
    )
    logger.info("Seeded session %s", cfg["session_id"])


async def main() -> None:
    for cfg in DEMO_SESSIONS:
        await seed_one(cfg)


if __name__ == "__main__":
    asyncio.run(main())
