# TASK-07: Memory Bank topics + persona-seeded memories

**Prerequisites:** TASK-06 complete. Cargo-plane scenario runs end-to-end on Knowledge Catalog + custom MCP servers + ADK 2.0 Workflow. Each agent already declares Memory Bank topics at deploy time via `services/memory_manager.py` (built in TASK-02).

**Estimated effort:** 2-3 days for one engineer.

**Stream:** Backend

---

> **Spec-history note (2026-05-20):** This spec originally framed the work as creating six "Memory Profile" documents (one per persona) plus a `Workflow(callbacks={...})` hook and an `auto_load_memory_profile` framework callable. That mental model conflicts with the real API:
>
> - Memory Bank is **topic-based**, not profile-based. You declare *topics* at deploy time (`MemoryBankCustomizationConfig`), then memories are individual structured records keyed by `user_id` and attached to a topic. There is no "Profile" document. Per-persona state is modeled as *seed memories* written into the appropriate topics for that `user_id`.
> - ADK 2.0 `Workflow` has no `callbacks=` parameter; callbacks live on individual `LlmAgent`s (`before_agent_callback`, `after_agent_callback`). There is no `google.adk.callbacks` module with framework-provided memory hooks.
> - `auto_save_memories` is a *project-defined* callback (verbatim pattern from demo-2); the repo's `src/orchestrator_agent/services/memory_manager.py` already implements it correctly.
> - Memory reads at run-time use the built-in `preload_memory` tool or a direct `VertexAiMemoryBankService.search_memories(...)` call from a `before_agent_callback`.
>
> This rewrite reflects the actual surface per `~/.claude/references/vertex-agent-engine-deploys.md` §Memory Bank and `~/.claude/references/google-adk-2.0.md` §Memory Bank.

---

## Context

Memory Bank is Gemini Enterprise Agent Platform's managed cross-session memory infrastructure. Two primitives matter for this build:

- **Memory topics** — semantic categories declared at deploy time on the Agent Engine resource. Each topic has a `label` + a `description` that tells Memory Bank's extractor what to capture from session transcripts. Topics for the Orchestrator already exist in `services/memory_manager.py`: `sourcing_history`, `planner_preferences`, `equivalence_patterns`. Other agents declare their own (forecast_review's `rationale_tags` + `leader_profiles`, capacity_planning's `risk_tolerance` + `buffer_outcomes`, etc.).
- **Memories** — individual structured records keyed by `user_id` and attached to a topic. Written automatically by the `auto_save_memories` after-agent callback (extracted by Memory Bank from the session transcript) OR explicitly via direct API calls.

For the demo we **seed memories per persona** under the appropriate topics so that, on first turn of any scenario, the agent already knows the user's region, customer portfolio, risk tolerance, and recent decisions. We also **pre-create deterministic Sessions** so a scenario run is reproducible across rehearsals.

The platform narration win: when Maria types her first message, the Orchestrator's first LLM node has already pre-loaded her memories via `preload_memory` — the agent's prompt context already says "User has primary basin West Africa, customer portfolio: Chevron-Lagos Deepwater, Shell-Angola Block 17, prefers imperial units, recently approved a Tool X-V7 substitution avoiding $474K of charter cost." No warm-up turns, no manual context.

This task does not change any agent core logic. It populates the memory layer, configures pre-warmed Sessions, and verifies the trace shows the Memory Bank `searchMemories` call at agent start.

---

## Inputs

- TASK-06 complete (Knowledge Catalog populated, MCP servers governed by Agent Gateway, Workflow Orchestrator working)
- Memory Bank reference: `~/.claude/references/vertex-agent-engine-deploys.md` §Memory Bank — `context_spec`
- ADK 2.0 memory tooling reference: `~/.claude/references/google-adk-2.0.md` §Memory Bank, §Built-in tools (`preload_memory`)
- The six persona descriptions in `docs/planning/agentic_sop_oilfield_services_brief.md`
- Existing `services/memory_manager.py` in each agent — already declares topics + has `auto_save_memories` callback. Re-use, don't rebuild.

---

## Deliverables

When this task is complete:

1. **Topics inventory consolidated** — `memory_bank/topics.md` documents the union of topics declared by all four agents (Orchestrator, Procurement, Forecast Review, Capacity Planning) so the demoer / customer can see the full memory model in one place.
2. **Seed memories per persona** — `memory_bank/seed_memories.py` writes individual memories per `user_id` into the appropriate topics, populating the six personas:
   - `david-basin-leader-west-africa`
   - `tomas-fleet-scheduler-permian`
   - `maria-occ-planner-west-africa`
   - `priya-operations-vp-global`
   - `rafael-citizen-dev-permian`
   - `ayesha-audit-director-global`
3. **Deterministic demo Sessions** — `memory_bank/seed_demo_sessions.py` pre-creates Sessions with known IDs per scenario (`demo-maria-cargo-plane-v1`, etc.) bound to the right `user_id` and `app_name`.
4. **`preload_memory` wired into the first LLM nodes** — every agent's first LLM-bearing node has `preload_memory` in its `tools=` list (or a `before_agent_callback` that hits `search_memories` directly). So the agent's prompt context is populated from Memory Bank before the LLM is invoked.
5. **`auto_save_memories` callback verified active** — already implemented in each agent's `services/memory_manager.py`; verify it's wired as `after_agent_callback` on every `LlmAgent` (not just the Orchestrator's plan_evaluator).
6. **Idempotent setup** — both seed scripts are re-runnable; re-running updates rather than duplicating.
7. **Integration test** verifies a Memory Bank `searchMemories` span shows up in Cloud Trace at agent start and `createMemory` spans show up after the response.
8. **Demo narration in the brief** calls out Memory Bank specifically at the moment context appears "pre-loaded."

---

## Step-by-step instructions

### Step 1 — Read the existing memory_manager.py before writing new code

Every agent already has a `services/memory_manager.py` that declares its topics + provides `auto_save_memories`. Inventory them:

```bash
grep -l "MemoryBankCustomizationConfig\|MemoryTopic" src/*/services/memory_manager.py
# src/orchestrator_agent/services/memory_manager.py     — sourcing_history, planner_preferences, equivalence_patterns
# src/procurement_approval_agent/services/memory_manager.py — approval_decisions, blocker_patterns
# src/forecast_review_agent/services/memory_manager.py  — rationale_tags, leader_profiles
# src/capacity_planning_agent/services/memory_manager.py — risk_tolerance, buffer_outcomes
```

If a topic you need to seed against doesn't exist yet, add it to the relevant agent's `memory_manager.py` and re-deploy that agent (`make deploy-<agent>`) — the topic must be declared in `context_spec` at create-time for memories to land in it.

### Step 2 — Document the consolidated topic model

`memory_bank/topics.md`:

```markdown
# Memory Bank topics — Oilfield S&OP

Each topic is declared in one agent's `services/memory_manager.py` and
attached to that agent's Agent Engine resource at deploy time via
`context_spec.memory_bank_config.customization_configs`.

| Agent | Topic label | What it captures |
| --- | --- | --- |
| Orchestrator | `sourcing_history` | Asset + basin + savings + approval outcome per sourcing decision |
| Orchestrator | `planner_preferences` | Per-planner basin, authorization tier, default transit modes |
| Orchestrator | `equivalence_patterns` | Canonical asset → variant substitutions with spec refs |
| Procurement | `approval_decisions` | Tier + amount + outcome per approval |
| Procurement | `blocker_patterns` | Recurring blocker types per customer / basin |
| Forecast Review | `rationale_tags` | Tags extracted from basin-leader overrides |
| Forecast Review | `leader_profiles` | Per-leader override patterns + signal strength |
| Capacity Planning | `risk_tolerance` | Per-planner buffer / late-start cost tradeoff |
| Capacity Planning | `buffer_outcomes` | Realized vs. recommended buffer per scenario |

Memories under any topic are scoped by `user_id`; topics are global within
an agent. Read with `VertexAiMemoryBankService.search_memories(user_id=,
topic=)`; write happens automatically via the
`after_agent_callback=auto_save_memories` pattern (see each agent's
`services/memory_manager.py`).
```

### Step 3 — Build the persona seed-memories script

The script writes 5-10 individual memories per persona into the right topics, using the deployed Agent Engine resources' Memory Bank backends.

`memory_bank/seed_memories.py`:

```python
"""Seed Memory Bank with persona-specific starting memories.

Re-runnable: existing memories are not duplicated because Memory Bank
deduplicates on canonical content. Run after all four agents are deployed
(so AGENT_ENGINE_IDs are known) — each persona's memories land in the
topics declared by the appropriate agent.

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

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


class Memory(TypedDict):
    """A single memory record keyed by user_id under a topic."""
    user_id: str
    topic: str          # one of the labels documented in memory_bank/topics.md
    content: str        # natural-language record Memory Bank's extractor stored


# ----------------------------------------------------------------------------
# Persona seed data — natural-language records that Memory Bank stores
# verbatim. Match the topic's description format so the extractor surfaces
# the record cleanly at read time.
# ----------------------------------------------------------------------------

MARIA_MEMORIES: list[Memory] = [
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "planner_preferences",
        "content": (
            "Preference: planner=maria, type=basin, value=West Africa OCC. "
            "Authorization tier: Tier 2 (up to $500K self-approve). "
            "Default transit modes: sea_freight, regional_air_charter."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "sourcing_history",
        "content": (
            "Sourcing: asset=Tool X-V7, basin=West Africa, savings_usd=474000. "
            "Cargo charter from Australia (Tool X) was the naive plan; pivoted "
            "to Tool X-V7 ex-Lagos via Knowledge Catalog equivalence lookup. "
            "Chevron-Lagos Deepwater contract, approved 2026-05-15."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "equivalence_patterns",
        "content": (
            "Equivalence: Tool X -> Tool X-V7, customer=Chevron Lagos, "
            "spec=InTouch 3.2. Confidence 0.92. Variant approved for completion-"
            "phase use under same operational envelope."
        ),
    },
    {
        "user_id": "maria-occ-planner-west-africa",
        "topic": "planner_preferences",
        "content": (
            "Customer portfolio: Chevron-Lagos Deepwater (next milestone: Tool X "
            "delivery 2026-05-22), Shell-Angola Block 17 (workforce rotation "
            "2026-06-01). Units: imperial. Language: en-US."
        ),
    },
]


TOMAS_MEMORIES: list[Memory] = [
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "planner_preferences",
        "content": (
            "Preference: planner=tomas, type=basin, value=Permian / Eagle Ford. "
            "Risk tolerance: conservative (prefers higher buffer over late-start "
            "exposure). Units: imperial."
        ),
    },
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "risk_tolerance",
        "content": (
            "Buffer tradeoff: planner=tomas, prefers buffer_pct over late_start_cost "
            "at 1.5x ratio. Q2 2026 ExxonMobil Permian frac pump fleet: "
            "approved 12% buffer."
        ),
    },
    {
        "user_id": "tomas-fleet-scheduler-permian",
        "topic": "buffer_outcomes",
        "content": (
            "Outcome: buffer_pct=12, scenario=ExxonMobil-Permian-Q2, "
            "on_time_actual=true, idle_hours=210. Slight over-buffer; planner "
            "noted in retro that 10% would have sufficed."
        ),
    },
]


DAVID_MEMORIES: list[Memory] = [
    {
        "user_id": "david-basin-leader-west-africa",
        "topic": "leader_profiles",
        "content": (
            "Leader: david, basin=West Africa. Override pattern: aggressive "
            "downward revisions when geological survey signals delay (Q3 2026 "
            "Chevron-Lagos -18% vs ML)."
        ),
    },
    {
        "user_id": "david-basin-leader-west-africa",
        "topic": "rationale_tags",
        "content": (
            "Tag: geological_survey_delay. Frequency: high (3 overrides in last "
            "2 quarters). Predictive of: 14-day average shift in actual start "
            "vs ML forecast."
        ),
    },
]


PRIYA_MEMORIES: list[Memory] = [
    {
        "user_id": "priya-operations-vp-global",
        "topic": "planner_preferences",
        "content": (
            "Preference: planner=priya, role=Operations VP, scope=Global. "
            "Views: cross-basin rollups, customer-level revenue attainment, "
            "fleet utilization vs target. Units: metric."
        ),
    },
]


RAFAEL_MEMORIES: list[Memory] = [
    {
        "user_id": "rafael-citizen-dev-permian",
        "topic": "planner_preferences",
        "content": (
            "Preference: planner=rafael, role=Citizen Developer, basin=Permian. "
            "Builds custom Gemini Enterprise extensions; prefers Knowledge "
            "Catalog metadata visibility in agent outputs."
        ),
    },
]


AYESHA_MEMORIES: list[Memory] = [
    {
        "user_id": "ayesha-audit-director-global",
        "topic": "planner_preferences",
        "content": (
            "Preference: planner=ayesha, role=Audit Director, scope=Global. "
            "Auditing focus: procurement-approval decisions over $500K threshold, "
            "Model Armor blocked-attack incidents, Agent Identity SPIFFE chain."
        ),
    },
]


ALL_MEMORIES: list[Memory] = [
    *MARIA_MEMORIES,
    *TOMAS_MEMORIES,
    *DAVID_MEMORIES,
    *PRIYA_MEMORIES,
    *RAFAEL_MEMORIES,
    *AYESHA_MEMORIES,
]


# ----------------------------------------------------------------------------
# Writer — uses the deployed agent's Memory Bank backend per topic
# ----------------------------------------------------------------------------

# Map each topic to the agent that declared it. Topic -> AGENT_ENGINE_ID env var.
TOPIC_TO_AGENT_ENV: dict[str, str] = {
    "sourcing_history": "ORCHESTRATOR_AGENT_ENGINE_ID",
    "planner_preferences": "ORCHESTRATOR_AGENT_ENGINE_ID",
    "equivalence_patterns": "ORCHESTRATOR_AGENT_ENGINE_ID",
    "approval_decisions": "PROCUREMENT_APPROVAL_AGENT_ENGINE_ID",
    "blocker_patterns": "PROCUREMENT_APPROVAL_AGENT_ENGINE_ID",
    "rationale_tags": "FORECAST_REVIEW_AGENT_ENGINE_ID",
    "leader_profiles": "FORECAST_REVIEW_AGENT_ENGINE_ID",
    "risk_tolerance": "CAPACITY_PLANNING_AGENT_ENGINE_ID",
    "buffer_outcomes": "CAPACITY_PLANNING_AGENT_ENGINE_ID",
}


def _agent_engine_id_for(topic: str) -> str | None:
    """Return the AGENT_ENGINE_ID for the agent that declared this topic."""
    env_key = TOPIC_TO_AGENT_ENV.get(topic)
    if env_key is None:
        logger.warning("No agent registered for topic %r — skipping", topic)
        return None
    value = os.environ.get(env_key)
    if not value:
        logger.warning("%s not set in env — skipping topic %r", env_key, topic)
        return None
    # Resource names look like projects/.../reasoningEngines/<id>; strip prefix.
    return value.rsplit("/", 1)[-1]


async def seed_one(memory: Memory) -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")
    agent_engine_id = _agent_engine_id_for(memory["topic"])
    if agent_engine_id is None:
        return

    service = VertexAiMemoryBankService(
        project=project,
        location=location,
        agent_engine_id=agent_engine_id,
    )
    # DEMO NARRATION: "We're populating Memory Bank topic by topic. Each
    # persona gets a handful of seed memories — region, customer portfolio,
    # past decisions — under the topics the agent declared at deploy time.
    # No 'profile document' to manage; just typed memories the agent's
    # preload_memory tool will surface on first turn."
    await service.create_memory(
        user_id=memory["user_id"],
        topic=memory["topic"],
        content=memory["content"],
    )
    logger.info(
        "Seeded memory: user=%s topic=%s",
        memory["user_id"], memory["topic"],
    )


async def main() -> None:
    for mem in ALL_MEMORIES:
        await seed_one(mem)
    logger.info("Memory Bank seeding complete (%d memories).", len(ALL_MEMORIES))


if __name__ == "__main__":
    asyncio.run(main())
```

**Note on the exact `create_memory` signature.** `VertexAiMemoryBankService` in `google-adk>=2.0.0` exposes `add_session_to_memory(session)` for the implicit write path (the `auto_save_memories` callback uses this). Direct seeding may go through `create_memory(user_id=, topic=, content=)` OR through the raw REST `projects/.../reasoningEngines/.../memories` endpoint depending on SDK version. **Verify with `inspect.getsource(VertexAiMemoryBankService)` from `venv-deploy-310/`** before running; if the method name has drifted, switch to the REST call directly per the auth/example in `~/.claude/references/gemini-enterprise-agent-platform.md` §REST API patterns. Do not invent method names — read the source.

### Step 4 — Wire `preload_memory` into the first LLM node of each agent

ADK 2.0 ships a built-in `preload_memory` tool (per `~/.claude/references/google-adk-2.0.md` §Built-in tools). Add it to the `tools=` list of every agent's `LlmAgent` (or in the Orchestrator's case, every LLM node placed in `edges`). The tool calls `VertexAiMemoryBankService.search_memories(user_id=<session.user_id>)` and injects the results into the prompt context BEFORE the LLM is invoked.

For the Orchestrator's `equivalence_lookup` LLM node (`src/orchestrator_agent/core/nodes/equivalence_lookup.py`):

```python
from google.adk import Agent
from google.adk.tools import preload_memory

from ...prompts import EQUIVALENCE_LOOKUP_INSTRUCTION
from ....schemas import EquivalentAssetCandidate
from ....utils.global_gemini import GlobalGemini

equivalence_lookup_agent = Agent(
    name="equivalence_lookup",
    description="Pick the best functional substitute for a canonical asset.",
    model=GlobalGemini(model="gemini-3.1-pro-preview"),
    instruction=EQUIVALENCE_LOOKUP_INSTRUCTION,
    output_schema=EquivalentAssetCandidate,
    tools=[preload_memory, *_existing_skill_tools()],
    after_agent_callback=auto_save_memories,
)
```

Same pattern for `sourcing_logistics`, `revise_plan`, and the plan_evaluator. For the standalone agents (Procurement, Forecast Review, Capacity Planning), add `preload_memory` to their root `LlmAgent`'s `tools=`.

**Memory read happens implicitly when the LLM decides to call `preload_memory`.** If you want it guaranteed-called on every turn, add a `before_agent_callback` that hits `search_memories` directly and writes the results into `ctx.state` for downstream nodes to read:

```python
# src/orchestrator_agent/core/nodes/preload.py
async def load_persona_memories(callback_context: CallbackContext) -> None:
    """Eagerly fetch persona memories at the start of every Orchestrator turn."""
    service = create_memory_service()  # from services/memory_manager.py
    if service is None:
        return
    user_id = callback_context._invocation_context.session.user_id
    memories = await service.search_memories(user_id=user_id)
    callback_context.state["persona_memories"] = [m.content for m in memories]
```

Then the first function node (`parse_request`) can read `ctx.state["persona_memories"]` and fold them into the parsed `CapacityGapRequest` defaults.

### Step 5 — Use loaded memories in `parse_request`

The parse_request node should use loaded memories to fill defaults:

```python
# src/orchestrator_agent/core/nodes/parse_request.py
from google.adk import Context, Event

def parse_capacity_gap_request(node_input: dict, ctx: Context) -> Event:
    """Parse the request, using preloaded persona memories for defaults."""
    memories = ctx.state.get("persona_memories", [])

    # DEMO NARRATION: "Notice the agent didn't ask Maria what region she
    # cares about or what units to use. preload_memory pulled her planner
    # preferences from Memory Bank — basin=West Africa OCC, units=imperial,
    # authorization tier=Tier 2. All loaded before her first message."
    target_region = (
        node_input.get("target_region")
        or _extract_region_from_memories(memories)
    )
    units = _extract_units_from_memories(memories) or "imperial"

    # ... rest of parse logic
```

The `_extract_*_from_memories` helpers are small string parsers that pull labeled fields out of the memory content (e.g., `value=West Africa OCC` → `"West Africa OCC"`). Keep them simple — they're parsing structured strings we authored in Step 3.

### Step 6 — Seed deterministic demo Sessions

For demo reproducibility, every scenario should run with a fixed `session_id`. Same input + same session ID + same memories = same agent behavior. ADK's `VertexAiSessionService` accepts caller-supplied session IDs.

`memory_bank/seed_demo_sessions.py`:

```python
"""Seed deterministic Sessions for the six demo scenarios.

Each Session has a known ID and is bound to the appropriate user_id +
app_name. The Orchestrator's app_name was set explicitly to
'capacity_orchestrator_agent' in TASK-02 deploy.py — match that exactly.
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
    app_name: str       # must match the deployed AdkApp/A2aAgent app_name
    scenario: str


DEMO_SESSIONS: list[DemoSession] = [
    {
        "session_id": "demo-maria-cargo-plane-v1",
        "user_id": "maria-occ-planner-west-africa",
        "app_name": "capacity_orchestrator_agent",
        "scenario": (
            "Cargo plane Australia → Luanda being chartered for $474K. Tool X-V7 "
            "available in Lagos at 50km. Need pivot recommendation."
        ),
    },
    {
        "session_id": "demo-tomas-buffer-planning-v1",
        "user_id": "tomas-fleet-scheduler-permian",
        "app_name": "capacity_planning_agent",
        "scenario": (
            "Q3 frac pump fleet buffer planning for ExxonMobil-Permian. "
            "Probabilistic forecast available; need risk-tolerance-aware buffer "
            "recommendation."
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
        "scenario": "Citizen-developer extension that adds a custom Permian view.",
    },
    {
        "session_id": "demo-ayesha-audit-v1",
        "user_id": "ayesha-audit-director-global",
        "app_name": "procurement_approval_agent",
        "scenario": "Audit of last 30 days of procurement-approval decisions.",
    },
]


async def seed_one(cfg: DemoSession) -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")
    agent_engine_id = os.environ.get(_engine_id_env_for(cfg["app_name"]))
    if not agent_engine_id:
        logger.warning("No agent_engine_id for app %s — skipping", cfg["app_name"])
        return
    agent_engine_id = agent_engine_id.rsplit("/", 1)[-1]

    service = VertexAiSessionService(
        project=project, location=location, agent_engine_id=agent_engine_id,
    )

    # If the session already exists (idempotent re-run), skip the create.
    try:
        existing = await service.get_session(
            app_name=cfg["app_name"],
            user_id=cfg["user_id"],
            session_id=cfg["session_id"],
        )
        if existing:
            logger.info("Session %s exists — skipping", cfg["session_id"])
            return
    except Exception:
        # get_session raises if not found; fall through to create.
        pass

    await service.create_session(
        app_name=cfg["app_name"],
        user_id=cfg["user_id"],
        session_id=cfg["session_id"],
        state={"scenario_description": cfg["scenario"]},
    )
    logger.info("Seeded session %s", cfg["session_id"])


def _engine_id_env_for(app_name: str) -> str:
    return {
        "capacity_orchestrator_agent": "ORCHESTRATOR_AGENT_ENGINE_ID",
        "procurement_approval_agent": "PROCUREMENT_APPROVAL_AGENT_ENGINE_ID",
        "forecast_review_agent": "FORECAST_REVIEW_AGENT_ENGINE_ID",
        "capacity_planning_agent": "CAPACITY_PLANNING_AGENT_ENGINE_ID",
    }[app_name]


async def main() -> None:
    for cfg in DEMO_SESSIONS:
        await seed_one(cfg)


if __name__ == "__main__":
    asyncio.run(main())
```

**Verify `VertexAiSessionService.create_session` accepts a caller-supplied `session_id`** (per `~/.claude/references/vertex-agent-engine-deploys.md` §Sessions, this is documented but worth confirming with `inspect.getsource(VertexAiSessionService.create_session)` in the venv-deploy-310 env before running).

### Step 7 — Integration test

`tests/integration/test_memory_bank.py`:

```python
"""Verify Memory Bank is loaded at agent start and saved at end."""

import asyncio
import os

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason="Set ORCHESTRATOR_AGENT_RESOURCE_NAME to a deployed engine to run.",
)


async def test_cargo_plane_session_loads_maria_memories():
    """When the cargo-plane session starts, Maria's memories should be loaded.

    Verifies Cloud Trace shows a Memory Bank search span at agent start.
    """
    from google.adk.memory import VertexAiMemoryBankService
    from src.orchestrator_agent.core.agent import root_agent

    response = await root_agent.run_async(
        user_input="I need a Tool X variant in Luanda by Friday — what are my options?",
        session_id="demo-maria-cargo-plane-v1",
        user_id="maria-occ-planner-west-africa",
    )

    # Verify trace shows the searchMemories call
    span_names = [s.name for s in response.cloud_trace.spans]
    assert any("searchMemories" in n or "search_memories" in n for n in span_names), (
        f"Expected a Memory Bank search span at session start. Got: {span_names}"
    )


async def test_after_response_creates_new_memory():
    """After the agent completes a turn, Memory Bank should have a new entry."""
    from google.adk.memory import VertexAiMemoryBankService
    import uuid

    user_id = f"test-after-save-{uuid.uuid4()}"
    # Run a turn; the after_agent_callback should write a memory under
    # sourcing_history.
    # ... (omitted for brevity; pattern: count memories before, run, count after)
```

### Step 8 — Add Makefile targets

```makefile
.PHONY: setup-memory-bank seed-demo-sessions reset-and-seed

setup-memory-bank:
	$(DEPLOY_PYTHON) -m memory_bank.seed_memories

seed-demo-sessions:
	$(DEPLOY_PYTHON) -m memory_bank.seed_demo_sessions

reset-and-seed: setup-memory-bank seed-demo-sessions
	@echo "Memory Bank seeded; Sessions pre-warmed. Demo is reproducible."
```

(Use `$(DEPLOY_PYTHON)` so the scripts run from `venv-deploy-310/`. Memory Bank + Sessions SDKs are heavy and the deploy venv already has them.)

### Step 9 — Update demo narration in the brief

Add to `docs/planning/agentic_sop_oilfield_services_brief.md` under the Persona 3 section, right after Maria's first message lands and before the canvas shows the gap:

> *"Notice the dashboard didn't ask Maria where she works or what units she uses. The Capacity Orchestrator's first node called `preload_memory` — and Memory Bank, the platform's managed memory infrastructure, returned her West Africa region context, her Chevron-Lagos commit, her preference for imperial units, all under topics the Orchestrator declared at deploy time. No warm-up turns, no manual context loading. That's the managed memory layer."*

### Step 10 — Commit

```bash
git add memory_bank/ tasks/TASK-07-memory-bank.md docs/planning/agentic_sop_oilfield_services_brief.md \
  src/orchestrator_agent/core/nodes/parse_request.py \
  src/orchestrator_agent/core/nodes/equivalence_lookup.py \
  src/orchestrator_agent/core/nodes/sourcing_logistics.py \
  src/orchestrator_agent/core/nodes/revise_plan.py \
  src/orchestrator_agent/plan_evaluator/agent.py
git commit -m "feat: Memory Bank topics + persona seed memories + deterministic sessions (TASK-07)"
git push
```

---

## Acceptance criteria

- [ ] `memory_bank/topics.md` documents the union of topics across all four agents
- [ ] `memory_bank/seed_memories.py` writes seed memories per persona under the appropriate topics; re-running is idempotent
- [ ] `memory_bank/seed_demo_sessions.py` pre-creates Sessions with deterministic IDs bound to the right `user_id` + `app_name`
- [ ] Every `LlmAgent` in the Orchestrator (and the three sibling agents) has `preload_memory` in `tools=` AND `after_agent_callback=auto_save_memories`
- [ ] At least one function node (e.g., `parse_request`) reads `ctx.state["persona_memories"]` (or equivalent) and uses it to fill defaults
- [ ] `make setup-memory-bank` runs idempotently
- [ ] `make seed-demo-sessions` runs idempotently
- [ ] Integration test verifies a `searchMemories`-style span appears at agent start
- [ ] Brief updated with the Persona 3 Memory Bank narration moment
- [ ] Commit pushed

---

## Common pitfalls

**Topics must exist before memories.** A memory written to a topic that isn't declared in the agent's `MemoryBankCustomizationConfig` at deploy time will land in an "unsorted" bucket (or be rejected) and won't surface via `search_memories(topic=)`. If you add a new topic in `services/memory_manager.py`, you must redeploy the agent before seeding memories that target it.

**Wrong `agent_engine_id` per topic.** Memories are stored per agent (each Reasoning Engine has its own Memory Bank backend). The seed script's `TOPIC_TO_AGENT_ENV` mapping must reflect which agent declared each topic. If you seed `sourcing_history` against the Procurement engine, the Orchestrator won't see it — they have separate Memory Bank stores.

**`user_id` vs persona display name.** Always seed memories with the slugified `user_id` (`maria-occ-planner-west-africa`), never the display name. The Orchestrator passes the slug through; a display-name memory won't match the search.

**SDK method name drift.** `VertexAiMemoryBankService.create_memory(...)` may have a different signature across `google-adk` minor versions. Per CLAUDE.md §Confidence and ambiguity: verify with `inspect.getsource(...)` before running; if it doesn't exist, fall back to the REST API call.

**Region mismatch.** Memory Bank is regional, bound to the Agent Engine resource. Memories created in `us-central1` are invisible from agents running in `us-east1`. Keep everything in `us-central1` for v1.

**Session ID re-use across demo runs.** If two runs use `demo-maria-cargo-plane-v1` but expect different starting states, state from the previous run will leak (Memory Bank accumulates). For repeatable demos: either run `make reset-and-seed` between rehearsals (wipes the session + re-seeds), or use UUIDs for non-repeatable runs.

**Memory Bank quotas.** Per-topic memory counts are not publicly documented. demo-2 ships 4 topics per agent without issue. For this demo (3 topics × 4 agents × ~3 memories per persona = ~70 records) we're well within any reasonable bound, but watch the Cloud Logging quota errors during a sustained demo week.

**Privacy on demo memories.** Memories include "real-looking" customer names (Chevron, Shell, ExxonMobil). Mark them clearly as synthetic in the seed content. The Customer Skin task (TASK-13) parameterizes these — re-seed via `make reset-and-seed` after a skin swap.

**Forgetting `user_id` in agent invocations.** Both the canvas SSE consumer (TASK-10) and any direct `runner.run_async` call must pass `user_id`. Without it, `preload_memory` has nothing to search against; the agent acts like a stranger.

**`auto_save_memories` coverage gaps.** The callback is currently only attached to the Orchestrator's LlmAgents. Verify it's also on Procurement / Forecast / Capacity if you want their interactions to land in their own Memory Bank topics. (Each agent's `services/memory_manager.py` defines its own `auto_save_memories`; just wire it as `after_agent_callback` on each LlmAgent.)

---

## References

- Memory Bank reference: `~/.claude/references/vertex-agent-engine-deploys.md` §Memory Bank — `context_spec`
- ADK 2.0 Memory Bank + `preload_memory` tool: `~/.claude/references/google-adk-2.0.md` §Memory Bank, §Built-in tools
- Existing project implementation: `src/orchestrator_agent/services/memory_manager.py` (topics + `auto_save_memories`)
- Demo-2 reference pattern: `/tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/services/memory_manager.py` (4-topic example, `auto_save_memories` shape)
- Memory Bank official docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank`
- Sessions official docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions`

---

*When TASK-07 is complete, the demo has the personalization layer wired. Maria's first message lands and the Orchestrator already knows her region, her customer portfolio, her preferences — surfaced via `preload_memory` from the topics each agent declared at deploy time. Every scenario is deterministically reproducible across rehearsals via the pre-warmed Sessions. Next: TASK-08 — Operations Canvas frontend renders the cargo-plane scenario in static mode against this newly-personalized agent.*
