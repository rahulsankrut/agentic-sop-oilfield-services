"""Memory Bank seed verification integration tests (TASK-07 Step 7).

Verifies that the persona seed memories and demo Sessions landed in the
deployed Memory Bank / Session backends for the Capacity Orchestrator
agent. Both tests are gated by ``ORCHESTRATOR_AGENT_RESOURCE_NAME`` so
they skip cleanly on local-only / CI-without-deploy runs.

API surface verified against the deployed SDK (Python 3.10 venv):

* ``VertexAiMemoryBankService.search_memory(*, app_name, user_id, query)``
  returns a ``SearchMemoryResponse`` whose ``.memories`` is a list of
  ``MemoryEntry``; each entry's ``.content`` is a ``google.genai`` Content
  with ``parts[*].text``.
* ``VertexAiSessionService.get_session(*, app_name, user_id, session_id)``
  returns ``Optional[Session]`` — ``None`` on 404, not an exception.

Run (after ``make deploy-orchestrator`` and ``make seed-memory-bank``):

    pytest -xvs agents/tests/integration/test_memory_bank.py
"""

from __future__ import annotations

import os

import pytest
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService

APP_NAME = "capacity_orchestrator_agent"
MARIA_USER_ID = "maria-occ-planner-west-africa"
MARIA_DEMO_SESSION_ID = "demo-maria-cargo-plane-v1"


pytestmark = pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason=(
        "ORCHESTRATOR_AGENT_RESOURCE_NAME not set — skipping live Memory "
        "Bank / Session integration tests"
    ),
)


def _agent_engine_id() -> str:
    """Strip the projects/.../reasoningEngines/ prefix to get the numeric id."""
    resource_name = os.environ["ORCHESTRATOR_AGENT_RESOURCE_NAME"]
    return resource_name.rsplit("/", 1)[-1]


def _project_and_location() -> tuple[str, str]:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")
    return project, location


def _entry_text(entry) -> str:
    """Best-effort flatten of a MemoryEntry's text parts."""
    content = getattr(entry, "content", None)
    if content is None:
        return ""
    parts = getattr(content, "parts", None) or []
    chunks: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


@pytest.mark.asyncio
async def test_seed_memories_are_retrievable_for_maria() -> None:
    """Maria's region seed should surface on a region-shaped query."""
    project, location = _project_and_location()
    service = VertexAiMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=_agent_engine_id(),
    )

    response = await service.search_memory(
        app_name=APP_NAME,
        user_id=MARIA_USER_ID,
        query="What region do I cover?",
    )

    memories = list(getattr(response, "memories", []) or [])
    assert memories, (
        "Expected at least one memory for Maria — did `make seed-memory-bank` run after deploy?"
    )
    joined = "\n".join(_entry_text(m) for m in memories).lower()
    assert "west africa" in joined, (
        f"Expected a returned memory to mention 'West Africa' (case-insensitive); got: {joined!r}"
    )


@pytest.mark.asyncio
async def test_session_seed_exists() -> None:
    """The `demo-maria-cargo-plane-v1` Session should be pre-created."""
    project, location = _project_and_location()
    service = VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=_agent_engine_id(),
    )

    session = await service.get_session(
        app_name=APP_NAME,
        user_id=MARIA_USER_ID,
        session_id=MARIA_DEMO_SESSION_ID,
    )

    assert session is not None, (
        f"Demo session {MARIA_DEMO_SESSION_ID!r} not found for user "
        f"{MARIA_USER_ID!r} on app {APP_NAME!r}. Did "
        "`make seed-demo-sessions` run after deploy?"
    )
