# TASK-07: Memory Bank profiles and persona context

**Prerequisites:** TASK-06 complete. Cargo-plane scenario runs end-to-end on Knowledge Catalog + custom MCP servers + ADK 2.0 Workflow.

**Estimated effort:** 2-3 days for one engineer.

**Stream:** Backend

---

## Context

Memory Bank is Gemini Enterprise Agent Platform's managed memory infrastructure. Two primitives matter for this build:

- **Memory Profiles** — per-user persistent state that survives across sessions. Stores who the user is, their preferences, their stable context (region of responsibility, customer portfolio, KPIs they track), and durable preferences (units, language, default views).
- **Sessions** — per-conversation state with first-class custom session ID support. Lets us pre-warm a deterministic conversation state for demo reproducibility.

For the demo we define **six Memory Profiles** (one per persona) and **deterministic session IDs** so that "demo run #4 of the cargo-plane scenario" reproduces exactly. The platform narration win: when Maria opens her view, the Orchestrator already knows she's the OCC planner for West Africa, knows she handles the Chevron-Lagos contract, and pre-loads the right dashboard. That happens because Memory Bank surfaced her profile to the agent before her first message. No prompting, no manual context loading.

This task does not change any agent logic. It adds the memory layer underneath, configures pre-warmed states, and verifies the trace shows Memory Bank calls happening at session start.

---

## Inputs

- TASK-06 complete (Knowledge Catalog populated, MCP servers governed by Agent Gateway, Workflow Orchestrator working)
- Memory Bank docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank`
- Sessions docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions`
- The six persona descriptions in `agentic_sop_oilfield_services_brief.md`

---

## Deliverables

When this task is complete:

1. Six Memory Profiles defined and populated in Memory Bank:
   - `david-basin-leader-west-africa`
   - `tomas-fleet-scheduler-permian`
   - `maria-occ-planner-west-africa`
   - `priya-operations-vp-global`
   - `rafael-citizen-dev-permian`
   - `ayesha-audit-director-global`
2. Each profile contains: identity fields, role, region of responsibility, customer portfolio, default units/language, recent interaction history (seeded for the demo)
3. The Orchestrator and other agents are wired with `auto_save_memories` callback so Memory Bank stays current with new interactions
4. Pre-warmed sessions exist for each demo scenario with deterministic IDs:
   - `demo-maria-cargo-plane-v1`
   - `demo-tomas-buffer-planning-v1`
   - `demo-david-forecast-review-v1`
   - (plus three more for the remaining personas)
5. Idempotent setup script (`memory_bank/setup.py`) creates and updates Profiles + Sessions
6. The integration test verifies a Memory Bank lookup happens at session start; Cloud Trace shows the call
7. Demo narration in the brief calls out Memory Bank specifically at the moment context appears "magically" pre-loaded

---

## Step-by-step instructions

### Step 1 — Understand the Memory Bank model

Before writing code, internalize the conceptual model:

- **Memory Profile** is a key-value document keyed by a stable user ID. Stores durable user context.
- **Session** is a transient context object scoped to one conversation. Has a session ID, a memory profile reference, and per-turn state.
- **Auto-save callback** is a hook ADK invokes after each agent turn; it writes salient information from the turn back to the Memory Profile.

For the demo, we want all six personas pre-populated, all six demo scenarios pre-seeded with deterministic session IDs. This way, when the demoer hits "run scenario," the agent immediately has the right context — no warm-up turns visible to the audience.

### Step 2 — Define the profile schema

`src/orchestrator_agent/memory/profile_schema.py`:

```python
"""Memory Profile schema for oilfield services personas.

Each persona maps to a Memory Profile in Memory Bank. Schema is shared
across personas; field values vary by role.
"""

from typing import Literal
from pydantic import BaseModel, Field


class CustomerCommit(BaseModel):
    """A specific customer contract obligation tracked by the persona."""
    customer_id: str
    customer_name: str
    contract_name: str
    region: str
    next_milestone: str
    next_milestone_date: str  # ISO date


class RegionContext(BaseModel):
    """Geographic region of responsibility."""
    primary_basin: str
    secondary_basins: list[str] = Field(default_factory=list)
    hub_locations: list[str] = Field(default_factory=list)


class PersonaPreferences(BaseModel):
    """UI and reasoning preferences."""
    units: Literal["imperial", "metric"] = "imperial"
    language: str = "en-US"
    default_view: str = "global_asset"
    risk_tolerance: Literal["conservative", "balanced", "aggressive"] = "balanced"
    notification_channels: list[str] = Field(default_factory=lambda: ["agent_inbox"])


class RecentInteraction(BaseModel):
    """A recent decision or query, surfaced as context for follow-ups."""
    timestamp: str
    interaction_type: Literal[
        "forecast_review",
        "capacity_plan_approved",
        "capacity_plan_rejected",
        "sourcing_plan_approved",
        "investigation",
    ]
    summary: str
    artifact_ref: str | None = None  # link to the plan / report / etc.


class PersonaMemoryProfile(BaseModel):
    """The Memory Profile for one persona."""
    user_id: str
    display_name: str
    role: str
    region_context: RegionContext
    customer_portfolio: list[CustomerCommit]
    preferences: PersonaPreferences
    recent_interactions: list[RecentInteraction] = Field(default_factory=list)
    kpis_tracked: list[str] = Field(default_factory=list)
```

### Step 3 — Build the Memory Profile setup script

`memory_bank/setup.py`:

```python
"""Populate Memory Bank with the six demo persona profiles.

Idempotent: re-running updates existing profiles rather than duplicating.
"""

import os
from datetime import datetime, timedelta

from google.cloud import aiplatform   # verify exact import path for Memory Bank SDK

from src.orchestrator_agent.memory.profile_schema import (
    PersonaMemoryProfile,
    RegionContext,
    CustomerCommit,
    PersonaPreferences,
    RecentInteraction,
)

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


def maria_occ_planner_profile() -> PersonaMemoryProfile:
    """Maria — OCC Planner, West Africa. Centerpiece persona for the cargo-plane scenario."""
    return PersonaMemoryProfile(
        user_id="maria-occ-planner-west-africa",
        display_name="Maria Adeyemi",
        role="Operations Control Center Planner",
        region_context=RegionContext(
            primary_basin="West_Africa",
            secondary_basins=["North_Africa"],
            hub_locations=["Lagos, Nigeria", "Luanda, Angola", "Port Harcourt, Nigeria"],
        ),
        customer_portfolio=[
            CustomerCommit(
                customer_id="chevron-001",
                customer_name="Chevron",
                contract_name="Chevron-Lagos Deepwater",
                region="West_Africa",
                next_milestone="Tool X delivery for completion phase",
                next_milestone_date="2026-05-22",
            ),
            CustomerCommit(
                customer_id="shell-002",
                customer_name="Shell",
                contract_name="Shell-Angola Block 17",
                region="West_Africa",
                next_milestone="Workforce rotation",
                next_milestone_date="2026-06-01",
            ),
        ],
        preferences=PersonaPreferences(
            units="imperial",
            language="en-US",
            default_view="global_asset",
            risk_tolerance="balanced",
            notification_channels=["agent_inbox", "email"],
        ),
        recent_interactions=[
            RecentInteraction(
                timestamp=(datetime.now() - timedelta(days=3)).isoformat(),
                interaction_type="sourcing_plan_approved",
                summary="Approved sourcing plan for Tool X-V7 ex-Lagos to Luanda (Chevron-Lagos #18)",
                artifact_ref="plan-2026-05-15-a",
            ),
            RecentInteraction(
                timestamp=(datetime.now() - timedelta(days=7)).isoformat(),
                interaction_type="investigation",
                summary="Investigated repeated late starts on Block 17 — root caused to workforce visa delays",
                artifact_ref=None,
            ),
        ],
        kpis_tracked=[
            "on_time_start_rate",
            "avoided_logistics_cost",
            "fleet_utilization",
            "customer_satisfaction_quarterly",
        ],
    )


def tomas_fleet_scheduler_profile() -> PersonaMemoryProfile:
    """Tomas — Fleet Scheduler, Permian. Persona 2."""
    return PersonaMemoryProfile(
        user_id="tomas-fleet-scheduler-permian",
        display_name="Tomas Reyes",
        role="Fleet Scheduler",
        region_context=RegionContext(
            primary_basin="Permian",
            secondary_basins=["Eagle_Ford"],
            hub_locations=["Midland, TX", "Odessa, TX"],
        ),
        customer_portfolio=[
            CustomerCommit(
                customer_id="exxon-003",
                customer_name="ExxonMobil",
                contract_name="ExxonMobil-Permian Frac Pump Fleet",
                region="Permian",
                next_milestone="Q3 buffer planning review",
                next_milestone_date="2026-06-15",
            ),
        ],
        preferences=PersonaPreferences(
            units="imperial",
            language="en-US",
            default_view="fleet_utilization",
            risk_tolerance="conservative",  # Tomas tends conservative on buffers
            notification_channels=["agent_inbox"],
        ),
        recent_interactions=[
            RecentInteraction(
                timestamp=(datetime.now() - timedelta(days=2)).isoformat(),
                interaction_type="capacity_plan_approved",
                summary="Approved 12% buffer for Q3 frac pump fleet — Permian",
                artifact_ref="capacity-plan-2026-q3-a",
            ),
        ],
        kpis_tracked=["fleet_utilization", "idle_time_pct", "buffer_cost_vs_late_cost"],
    )


def david_basin_leader_profile() -> PersonaMemoryProfile:
    """David — Basin Leader, West Africa. Persona 1."""
    return PersonaMemoryProfile(
        user_id="david-basin-leader-west-africa",
        display_name="David Okeke",
        role="Basin Leader",
        region_context=RegionContext(
            primary_basin="West_Africa",
            secondary_basins=[],
            hub_locations=["Lagos, Nigeria", "Port Harcourt, Nigeria"],
        ),
        customer_portfolio=[],  # basin leaders don't own individual contracts
        preferences=PersonaPreferences(
            default_view="forecast_review",
            risk_tolerance="balanced",
        ),
        recent_interactions=[
            RecentInteraction(
                timestamp=(datetime.now() - timedelta(days=14)).isoformat(),
                interaction_type="forecast_review",
                summary="Overrode ML forecast for Q3 Chevron-Lagos based on geological survey delay signal",
                artifact_ref="forecast-2026-q3-rev-2",
            ),
        ],
        kpis_tracked=["forecast_accuracy", "basin_revenue_attainment"],
    )


# Add similar definitions for Priya, Rafael, Ayesha


def upsert_memory_profile(profile: PersonaMemoryProfile) -> None:
    """Create or update a Memory Profile in Memory Bank.

    The exact API surface should be verified against:
    https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank
    """
    # DEMO NARRATION: "We're populating Memory Bank — the managed memory
    # infrastructure that ships with the platform. Each persona gets a Memory
    # Profile with their role, region, customer portfolio, and recent decisions.
    # When the agent sees this user in its next session, it already knows
    # everything in this profile. No warm-up turns, no manual context."
    print(f"Upserting Memory Profile for {profile.display_name} ({profile.user_id})")
    # client.create_memory_profile(parent=..., profile_id=profile.user_id,
    #                              memory_profile={...})


def main():
    profiles = [
        david_basin_leader_profile(),
        tomas_fleet_scheduler_profile(),
        maria_occ_planner_profile(),
        # priya_operations_vp_profile(),
        # rafael_citizen_dev_profile(),
        # ayesha_audit_director_profile(),
    ]
    for profile in profiles:
        upsert_memory_profile(profile)
    print(f"Memory Bank setup complete. {len(profiles)} profiles upserted.")


if __name__ == "__main__":
    main()
```

### Step 4 — Wire the Orchestrator to load Memory Profiles at session start

ADK has a callback pattern for memory loading. Add the appropriate callback to the Orchestrator's Workflow.

In `src/orchestrator_agent/core/agent.py` (the Workflow from TASK-04):

```python
from google.adk.callbacks import auto_load_memory_profile, auto_save_memories

# Define callbacks at the Workflow level
root_agent = Workflow(
    name="capacity_orchestrator",
    description=(...),
    edges=[...],
    callbacks={
        "before_session": auto_load_memory_profile,  # loads profile by user_id
        "after_turn": auto_save_memories,            # writes salient context back
    },
)
```

When a session starts with `user_id="maria-occ-planner-west-africa"`, the workflow's `before_session` callback fetches Maria's Memory Profile and injects it into the Workflow's context. Every node downstream — function nodes, LLM nodes, A2A calls — can access it.

Verify the exact callback names against `https://adk.dev/callbacks/memory/` since 2.0 may have renamed these.

### Step 5 — Use Memory Profile context in the parse_request node

The first function node should use the loaded profile to fill in defaults:

```python
# src/orchestrator_agent/core/nodes/parse_request.py
def parse_capacity_gap_request(node_input: dict, context: dict) -> Event:
    """Parse the request, using Memory Profile to fill defaults."""
    profile = context.get("memory_profile", {})

    # DEMO NARRATION: "Notice the agent didn't ask Maria what region she
    # cares about or what units to use. The Memory Profile told it. She's
    # the OCC planner for West Africa, she prefers imperial units, her
    # default view is global_asset. All loaded before her first message."
    target_region = (
        node_input.get("target_region")
        or profile.get("region_context", {}).get("primary_basin")
    )
    units = profile.get("preferences", {}).get("units", "imperial")

    # ... rest of parse logic
```

### Step 6 — Configure deterministic demo sessions

For demo reproducibility, every scenario should run with a fixed session ID. This way: same input + same session ID + same Memory Profile = same agent behavior.

`memory_bank/seed_demo_sessions.py`:

```python
"""Seed deterministic Sessions for the six demo scenarios.

Each Session has a known ID and pre-warmed state. The demoer triggers
a scenario by sending the trigger prompt to the known session ID;
the agent picks up exactly where the session was seeded.
"""

import os

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

DEMO_SESSIONS = [
    {
        "session_id": "demo-maria-cargo-plane-v1",
        "user_id": "maria-occ-planner-west-africa",
        "scenario": "Cargo plane Australia → Luanda being chartered for $420K. Tool X-V7 available in Lagos at 50km. Need pivot recommendation.",
        "initial_turns": [
            # Optional pre-warm turns to set context before the demo trigger
        ],
    },
    {
        "session_id": "demo-tomas-buffer-planning-v1",
        "user_id": "tomas-fleet-scheduler-permian",
        "scenario": "Q3 frac pump fleet buffer planning for ExxonMobil-Permian. Probabilistic forecast available; need risk-tolerance-aware buffer recommendation.",
        "initial_turns": [],
    },
    {
        "session_id": "demo-david-forecast-review-v1",
        "user_id": "david-basin-leader-west-africa",
        "scenario": "Q4 forecast review with two basin-leader overrides requiring rationale extraction and re-ingestion into the model.",
        "initial_turns": [],
    },
    # Three more for Priya, Rafael, Ayesha
]


def seed_session(session_config: dict) -> None:
    """Create a Session with deterministic ID and pre-warmed state."""
    print(f"Seeding session {session_config['session_id']}")
    # client.create_session(parent=..., session_id=session_config['session_id'],
    #                      session={
    #                          'user_id': session_config['user_id'],
    #                          'metadata': {'scenario': session_config['scenario']},
    #                      })


def main():
    for cfg in DEMO_SESSIONS:
        seed_session(cfg)


if __name__ == "__main__":
    main()
```

### Step 7 — Integration test

`tests/integration/test_memory_bank.py`:

```python
async def test_cargo_plane_session_loads_maria_profile():
    """When the cargo-plane session starts, Maria's profile should be loaded."""
    response = await root_agent.run_async(
        user_input="I need a Tool X variant in Luanda by Friday",
        session_id="demo-maria-cargo-plane-v1",
        user_id="maria-occ-planner-west-africa",
    )

    # Verify trace shows Memory Bank load
    trace = response.cloud_trace
    memory_spans = [s for s in trace.spans if "memory_bank" in s.name or "load_profile" in s.name]
    assert len(memory_spans) >= 1, "Expected Memory Bank profile load at session start"

    # Verify the loaded profile influenced the agent's reasoning
    # (e.g., didn't ask Maria what region she meant — used West_Africa from profile)
    plan = SourcingPlan.model_validate(response.output)
    assert plan.target_region == "West_Africa"
    assert plan.units_system == "imperial"


async def test_after_turn_saves_to_memory():
    """After approving a plan, the interaction should be saved to Memory Profile."""
    session_id = f"test-memory-save-{uuid.uuid4()}"
    user_id = "maria-occ-planner-west-africa"

    response = await root_agent.run_async(
        user_input="Approve the Lagos sourcing plan",
        session_id=session_id,
        user_id=user_id,
    )

    # Fetch the updated profile
    profile = await fetch_memory_profile(user_id)
    recent = profile["recent_interactions"]
    assert any(r["interaction_type"] == "sourcing_plan_approved" for r in recent[-5:])
```

### Step 8 — Add Makefile targets

```makefile
.PHONY: setup-memory-bank seed-demo-sessions

setup-memory-bank:
	uv run python memory_bank/setup.py

seed-demo-sessions:
	uv run python memory_bank/seed_demo_sessions.py

reset-and-seed: setup-memory-bank seed-demo-sessions
```

### Step 9 — Update demo narration in the brief

Add a note in `agentic_sop_oilfield_services_brief.md` under the Persona 3 section: when the canvas loads Maria's view in Beat 0 (pre-scenario), the narration calls out:

> *"Notice the dashboard didn't ask Maria where she works or what units she uses. Her Memory Profile is already loaded — Memory Bank surfaced her West Africa region context, her Chevron-Lagos commit, her preference for imperial units, all before her first message. That's the managed memory layer."*

This is a small, specific moment that customers will remember.

### Step 10 — Commit

```bash
git add .
git commit -m "feat: Memory Bank profiles and pre-warmed demo sessions (TASK-07)"
git push
```

---

## Acceptance criteria

- [ ] Six Memory Profiles defined in `memory_bank/setup.py` with all required fields
- [ ] `make setup-memory-bank` runs idempotently (re-runs produce same state)
- [ ] Six deterministic demo sessions seeded via `make seed-demo-sessions`
- [ ] Orchestrator Workflow has `before_session` callback that loads the Memory Profile
- [ ] `auto_save_memories` callback wired so new interactions update profiles
- [ ] At least one function node (parse_request) uses Memory Profile context for defaults
- [ ] Integration test passes verifying Memory Bank load happens at session start
- [ ] Cloud Trace shows Memory Bank spans at session start and end-of-turn
- [ ] Brief updated with Persona 3 Memory Bank narration moment
- [ ] Commit pushed

---

## Common pitfalls

**Memory Bank API surface uncertain at writing time.** Memory Bank is a managed platform service; exact SDK method names may have evolved. Verify against the live docs before implementing. The script skeleton shows intent; treat the API calls as illustrative.

**Profile-vs-Session confusion.** Memory Profile = persistent, keyed by user_id. Session = transient, keyed by session_id. Don't store transient state in a Profile (it gets stale) or persistent state in a Session (it gets lost).

**Auto-save scope creep.** The `auto_save_memories` callback decides what's salient from each turn. Default behavior is usually correct, but if your demo has chatty turns that should NOT pollute Memory, configure the callback's salience filter. Otherwise Maria's Memory Profile fills with every joke and "hello" she ever typed.

**Session ID collisions across demo runs.** If two runs use `demo-maria-cargo-plane-v1` but expect different starting states, you'll see state from the previous run leaking. Either reset the session between runs (`make reset-and-seed`) or use UUIDs for non-repeatable runs.

**Privacy on demo profiles.** The demo profiles contain "real-looking" customer names (Chevron, Shell, ExxonMobil). Mark them clearly as synthetic in the profile metadata. If a customer ever sees the demo source, they should understand these are illustrative.

**Forgetting the `user_id` in run calls.** ADK's `run_async` accepts a `user_id` param that points to the right Memory Profile. Without it, the session has no profile and the agent acts like a stranger.

**Region mismatch between Memory Bank and other services.** Memory Bank is regional. If your Memory Profiles are in `us-central1` and the agent runs in `us-east1`, every Profile lookup is cross-region. Keep both in the same region.

**Cold-start memory profile size.** Loading a large Memory Profile at session start can add latency. For our use case profiles are <2KB, no issue. If a customer's profile grows to MBs (large interaction history), consider truncating recent_interactions to the last 10.

---

## References

- Memory Bank overview: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank`
- Sessions: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/sessions`
- ADK callbacks: `https://adk.dev/callbacks/`
- ADK memory integration: `https://adk.dev/callbacks/memory/`

---

*When TASK-07 is complete, the demo has the personalization layer wired. Maria's view "knows her" at session start, Tomas's view defaults to fleet_utilization, and every demo run is deterministically reproducible. Next: build the Operations Canvas frontend that renders the cargo-plane scenario visually.*
