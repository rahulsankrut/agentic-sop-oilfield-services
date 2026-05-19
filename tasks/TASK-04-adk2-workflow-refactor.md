# TASK-04: ADK 2.0 migration + Capacity Orchestrator Workflow refactor

**Prerequisites:** TASK-01, TASK-02, TASK-03 complete. Cargo-plane integration test passing on ADK 1.x. All five agents deployed and end-to-end smoke test green.

**Estimated effort:** 5-7 days for one engineer.

**Stream:** Backend

---

## Context

ADK 2.0 Beta introduces `Workflow` agents — graphs of nodes where each node is an LLM agent, a deterministic function, a tool call, or a sub-workflow. This pattern fundamentally improves how the Capacity Orchestrator works: instead of one large LLM agent reasoning through a 9-step instruction, the Orchestrator becomes a graph with explicit nodes for parallel system queries, deterministic routing on availability, AI reasoning at equivalence judgment, and deterministic procurement-threshold checks.

This refactor matters for three reasons. First, **demo narration**: showing the Cloud Trace of a Workflow graph executing is materially more compelling than showing an LLM following a prompt. Second, **enterprise credibility**: tier-one oilfield services buyers have procurement audit and regulatory exposure; deterministic flow with AI at decision points is defensible in ways pure LLM agents are not. Third, **alignment with the platform's narrative**: workflow agents, ambient agents, and resume agents are the features Google leads with for Gemini Enterprise Agent Platform at Next '26. Our reference solution should demonstrate them.

This task does two things together: (1) upgrades the dependency from ADK 1.33 to ADK 2.0 Beta and verifies TASK-01–03 still works; (2) refactors the Capacity Orchestrator from `LlmAgent` to `Workflow` with explicit nodes. Other agents (Plan Evaluator, Procurement Approval, Forecast Review) stay as `LlmAgent`s — they are single-purpose reasoning agents where workflow overhead does not add value.

---

## Inputs

- TASK-01–03 deliverables (deployed agents, cargo-plane test passing on ADK 1.33)
- Reference repo at `/tmp/next-26-keynotes/`
- ADK 2.0 docs:
  - `https://adk.dev/2.0/`
  - `https://adk.dev/workflows/`
  - `https://adk.dev/workflows/graph-routes/`
  - `https://adk.dev/workflows/data-handling/`
  - `https://adk.dev/workflows/human-input/`
- Workflow sample repo: `https://github.com/google/adk-python/tree/v2/contributing/workflow_samples`

---

## Deliverables

When this task is complete:

1. `pyproject.toml` updated to `google-adk>=2.0.0b1,<2.1`; `uv sync` runs clean
2. The cargo-plane integration test from TASK-03 still passes after the upgrade (proving backwards compatibility)
3. The Capacity Orchestrator is refactored from `LlmAgent` to `Workflow` with explicit graph nodes
4. Each Workflow node has a `# DEMO NARRATION:` comment explaining what the demoer should say when that node executes
5. The refactored Orchestrator's Cloud Trace shows the workflow graph executing — parallel MCP queries fan out and fan in, deterministic routing branches visible, AI reasoning isolated to specific nodes
6. Plan Evaluator, Procurement Approval, Forecast Review, and Capacity Planning Agent remain `LlmAgent`s for now (Capacity Planning Agent gets its own Workflow refactor in a later task)
7. Updated unit tests validate Workflow node behavior independently
8. The Operations Canvas WebSocket events (which will be wired in TASK-10) are emitted from specific Workflow nodes, not from inside an LLM agent's monolithic execution

---

## Step-by-step instructions

### Step 1 — Upgrade to ADK 2.0 Beta

```bash
source .venv/bin/activate

# Force upgrade — Beta installs require --pre, and --force overrides the existing 1.x install
uv pip install --pre --force "google-adk>=2.0.0b1,<2.1"

# Verify
python -c "import google.adk; print(google.adk.__version__)"
# Expected: 2.0.0b1 or similar Beta string
```

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    "google-adk>=2.0.0b1,<2.1",   # was: google-adk>=1.33,<2.0
    # ... rest unchanged
]
```

Commit the pyproject.toml change immediately with message `chore: upgrade ADK to 2.0 Beta (TASK-04 step 1)`.

### Step 2 — Verify TASK-01–03 still works on 2.0

Before touching any other code, run the existing test suite end-to-end:

```bash
uv run pytest tests/unit/ -v
uv run pytest tests/integration/test_cargo_plane_scenario.py -v
make deploy-all-agents      # redeploy on 2.0
uv run pytest tests/integration/test_orchestrator_skeleton.py -v
```

**Expected outcome:** all tests pass without code changes. ADK 2.0 is designed for backwards compatibility with 1.x agents.

**If tests fail:** capture the exact error. Likely culprits and fixes:
- `LlmAgent` import path changed → use `from google.adk import Agent` (the new top-level shorthand)
- `auto_save_memories` callback signature changed → check the 2.0 callback docs at `https://adk.dev/callbacks/`
- `RemoteA2aAgent` location changed → check `https://adk.dev/a2a/`
- `SkillToolset` API changed → check `https://adk.dev/skills/`

Document any required fixes in a single commit titled `fix: ADK 2.0 compatibility fixes (TASK-04 step 2)`. Do not proceed to Step 3 until tests pass.

### Step 3 — Understand the target Workflow architecture

Before writing code, study the workflow examples:

```bash
git clone --branch v2 https://github.com/google/adk-python.git /tmp/adk-python-v2
ls /tmp/adk-python-v2/contributing/workflow_samples/
```

Read at minimum:
- The samples that demonstrate sequential workflows with mixed agent + function nodes
- The router pattern that uses a dictionary to dispatch on an output value
- The data handling sample that shows how Pydantic schemas flow between nodes

The target architecture for the Capacity Orchestrator looks like this:

```
START
  ↓
[parse_capacity_gap_request]       # function node: extract structured request
  ↓
[resolve_canonical_asset]          # function node: call asset-equivalence skill
  ↓
[parallel_system_queries]          # parallel sub-workflow:
   ├── [query_maximo]              #   function node calling MCP
   ├── [query_sap]                 #   function node calling MCP
   ├── [query_fdp]                 #   function node calling MCP
   └── [query_intouch]             #   function node via Knowledge Catalog MCP
  ↓ (fan-in)
[evaluate_direct_availability]     # function node: deterministic check
  ↓
[router: direct or equivalence?]   # router function
  ├── DIRECT_AVAILABLE → [build_direct_plan]      # function node
  └── NEEDS_EQUIVALENCE → [equivalence_lookup_agent]   # LlmAgent node (Gemini)
                            ↓
                          [build_equivalent_plan]    # function node
  ↓ (merge)
[sourcing_logistics_agent]         # LlmAgent node (Gemini) — refine plan with logistics
  ↓
[plan_evaluator]                   # LlmAgent node (existing Plan Evaluator)
  ↓
[router: score threshold?]
  ├── SCORE >= 0.85 → continue
  └── SCORE < 0.85 → [revise_plan_agent] → loop back to plan_evaluator (max 2 iterations)
  ↓
[router: requires procurement gate?]
  ├── UNDER_THRESHOLD → return SourcingPlan
  └── OVER_THRESHOLD → [procurement_approval_agent]   # A2A call (existing)
  ↓
[finalize_sourcing_plan]           # function node: compute avoided_cost_usd, build final SourcingPlan
  ↓
END
```

Three things to note about this design:
- **LLM nodes are at decision points only**: equivalence judgment, logistics refinement, plan evaluation, plan revision. Everything else is deterministic code.
- **Routers are explicit**: availability check, score threshold, procurement threshold. Each router is a small function that returns a routing key.
- **The graph is the trace**: when the customer sees the Cloud Trace, they see the graph executing — not an LLM monologue.

### Step 4 — Refactor file layout for the Workflow Orchestrator

Move the existing Orchestrator code out of the way and replace with a workflow:

```bash
# Preserve the old LlmAgent version for reference (delete after Step 7 verification)
git mv src/orchestrator_agent/core/agent.py src/orchestrator_agent/core/agent_v1_llmagent.py.bak
```

Then create the new files:

```
src/orchestrator_agent/
├── core/
│   ├── agent.py                   # NEW — Workflow definition
│   ├── nodes/                     # NEW — node implementations
│   │   ├── __init__.py
│   │   ├── parse_request.py
│   │   ├── resolve_asset.py
│   │   ├── parallel_queries.py
│   │   ├── evaluate_availability.py
│   │   ├── routers.py
│   │   ├── build_plans.py
│   │   ├── equivalence_lookup.py  # LlmAgent node
│   │   ├── sourcing_logistics.py  # LlmAgent node
│   │   ├── revise_plan.py         # LlmAgent node
│   │   └── finalize.py
│   ├── config.py                  # unchanged
│   ├── prompts.py                 # now contains prompts for the LLM nodes only
│   └── auth.py                    # unchanged
├── ...
```

### Step 5 — Implement deterministic function nodes

These nodes contain no LLM calls. Each is a Python function that takes structured input and returns structured output.

`src/orchestrator_agent/core/nodes/parse_request.py`:

```python
"""Parse a capacity-gap query into a structured CapacityGapRequest."""

from datetime import datetime
from google.adk import Event

from ....schemas import CapacityGapRequest, GeoPoint


# DEMO NARRATION: "First node: parsing Maria's request into a structured form.
# This is deterministic — no LLM. It pulls out the requested asset, the target
# location, and the deadline. If anything is ambiguous, the workflow stops here
# and asks Maria for clarification rather than guessing."
def parse_capacity_gap_request(node_input: str) -> Event:
    """First node in the Orchestrator workflow.

    Input: raw user query (e.g., "I need a Tool X variant in Luanda by Friday")
    Output: structured CapacityGapRequest

    For TASK-04, use simple string parsing; in production this could call out to
    a small extraction LLM. For demo robustness, we use the deterministic version.
    """
    # Simple parsing for the demo's hero scenario
    # Production: use a structured-extraction agent here
    request = CapacityGapRequest(
        requested_asset="Tool X variant",
        target_location=GeoPoint(latitude=-8.8390, longitude=13.2894, label="Luanda, Angola"),
        deadline=datetime.fromisoformat("2026-05-22T00:00:00"),
        raw_query=node_input,
    )
    return Event(
        message=f"Parsed request: {request.model_dump_json()}",
        payload=request.model_dump(),
    )
```

`src/orchestrator_agent/core/nodes/parallel_queries.py`:

```python
"""Parallel system queries — fan out to Maximo, SAP, FDP, InTouch via MCP."""

import asyncio
from google.adk import Event

from ....schemas import CapacityGapRequest, SystemQueryResults
from ...skills.enterprise_systems.scripts.tools import (
    query_maximo_availability,
    query_sap_workforce,
    query_fdp_customer_config,
    query_intouch_specs,
)


# DEMO NARRATION: "Now the workflow fans out — four parallel queries against
# Maximo, SAP, FDP, and InTouch. All running concurrently, all through MCP.
# No LLM in this step; the agent isn't deciding what to do, the workflow is.
# This is what makes agentic AI defensible to procurement audit — predictable
# steps, parallel execution, full trace."
async def parallel_system_queries(node_input: dict) -> Event:
    """Fan out parallel queries to all four enterprise systems."""
    request = CapacityGapRequest(**node_input["payload"])

    maximo_task = query_maximo_availability(
        canonical_id=request.canonical_asset_id,
        region_filter=request.target_region,
    )
    sap_task = query_sap_workforce(
        basin=request.target_region,
        date_window=(request.deadline.date(), request.deadline.date()),
    )
    fdp_task = query_fdp_customer_config(
        customer_id=request.customer_id,
        asset_canonical_id=request.canonical_asset_id,
    )
    intouch_task = query_intouch_specs(asset_canonical_id=request.canonical_asset_id)

    results = await asyncio.gather(maximo_task, sap_task, fdp_task, intouch_task)

    aggregated = SystemQueryResults(
        maximo=results[0],
        sap=results[1],
        fdp=results[2],
        intouch=results[3],
    )
    return Event(
        message="Parallel system queries complete",
        payload=aggregated.model_dump(),
    )
```

`src/orchestrator_agent/core/nodes/routers.py`:

```python
"""Routing functions for the Orchestrator Workflow."""

from google.adk import Event

from ....schemas import SystemQueryResults, PlanEvaluation, SourcingPlan


# DEMO NARRATION: "First routing decision. If direct availability exists, we take
# the fast path — build a plan with the existing asset. If not, we go into the
# equivalence pathway, where the agent reasons about functional substitutes.
# This is a deterministic check, not an LLM judgment."
def route_on_availability(node_input: dict) -> Event:
    """Route based on whether direct asset availability was found."""
    results = SystemQueryResults(**node_input["payload"])
    if results.maximo.count > 0 and results.fdp.customer_compatibility:
        return Event(route="DIRECT_AVAILABLE", payload=node_input["payload"])
    return Event(route="NEEDS_EQUIVALENCE", payload=node_input["payload"])


# DEMO NARRATION: "After the Plan Evaluator scores the plan, we check the threshold.
# Score of 0.85 or higher: we proceed. Below: we send the plan back to be revised.
# Maximum of two revision loops to avoid runaway iteration. This is the kind of
# control structure that's hard to enforce in a pure LLM agent."
def route_on_evaluation_score(node_input: dict) -> Event:
    """Route based on Plan Evaluator's score."""
    evaluation = PlanEvaluation(**node_input["payload"]["evaluation"])
    iteration = node_input["payload"].get("iteration_count", 0)

    if evaluation.overall_score >= 0.85:
        return Event(route="ACCEPTED", payload=node_input["payload"])
    if iteration >= 2:
        return Event(route="EXHAUSTED", payload=node_input["payload"])
    return Event(
        route="REVISE",
        payload={**node_input["payload"], "iteration_count": iteration + 1},
    )


# DEMO NARRATION: "Final routing — does this plan need procurement approval?
# Above $500K or involving cross-border regulatory clearance, yes. Below that
# threshold, the OCC planner can approve themselves. This threshold is policy,
# not LLM judgment — encoded right here in the workflow."
def route_on_procurement_threshold(node_input: dict) -> Event:
    """Route based on whether procurement approval is required."""
    plan = SourcingPlan(**node_input["payload"]["plan"])
    if plan.primary_option.estimated_cost_usd > 500_000:
        return Event(route="REQUIRES_APPROVAL", payload=node_input["payload"])
    if plan.primary_option.blockers:
        return Event(route="REQUIRES_APPROVAL", payload=node_input["payload"])
    return Event(route="AUTO_APPROVE", payload=node_input["payload"])
```

Add similar implementations for `resolve_asset.py`, `evaluate_availability.py`, `build_plans.py`, `finalize.py`. Each follows the same pattern: takes structured input, returns an `Event` with a structured payload, has a `# DEMO NARRATION:` comment.

### Step 6 — Implement LLM agent nodes

LLM nodes are where Gemini actually reasons. They are `Agent` instances scoped to a single decision.

`src/orchestrator_agent/core/nodes/equivalence_lookup.py`:

```python
"""LLM node: reason about functional equivalence using Knowledge Catalog."""

from google.adk import Agent
from google.genai.types import GenerateContentConfig, ThinkingConfig

from ....schemas import EquivalentAssetCandidate
from ..prompts import EQUIVALENCE_LOOKUP_INSTRUCTION


# DEMO NARRATION: "This is the first AI node in the workflow. Notice it's
# scoped to one decision — find the best functional equivalent for this asset.
# Gemini reasons against Knowledge Catalog's canonical entity model and returns
# a structured candidate with confidence score and rationale source. One job.
# Predictable input, structured output, no instruction sprawl."
equivalence_lookup_agent = Agent(
    name="equivalence_lookup",
    model="gemini-3-1-pro-preview",
    instruction=EQUIVALENCE_LOOKUP_INSTRUCTION,
    output_schema=EquivalentAssetCandidate,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
```

`src/orchestrator_agent/core/nodes/sourcing_logistics.py`:

```python
"""LLM node: refine the sourcing plan with logistics reasoning."""

from google.adk import Agent

from ....schemas import SourcingPlan
from ..prompts import SOURCING_LOGISTICS_INSTRUCTION


# DEMO NARRATION: "Second AI node: refining the plan with logistics judgment.
# Transit mode, cost envelope, blocker identification. Gemini's role here is
# to apply real-world logistics reasoning that's hard to encode in pure rules."
sourcing_logistics_agent = Agent(
    name="sourcing_logistics",
    model="gemini-3-1-pro-preview",
    instruction=SOURCING_LOGISTICS_INSTRUCTION,
    output_schema=SourcingPlan,
)
```

`src/orchestrator_agent/core/nodes/revise_plan.py`:

```python
"""LLM node: revise a low-scoring plan based on Plan Evaluator findings."""

from google.adk import Agent

from ....schemas import SourcingPlan
from ..prompts import REVISE_PLAN_INSTRUCTION


# DEMO NARRATION: "If the Plan Evaluator scores below threshold, we revise.
# This node takes the original plan plus the evaluator's findings and produces
# an improved plan. The workflow then re-evaluates. Up to two iterations.
# This is the kind of self-improvement loop that's structural in our Workflow,
# not behavioral in a prompt."
revise_plan_agent = Agent(
    name="revise_plan",
    model="gemini-3-1-pro-preview",
    instruction=REVISE_PLAN_INSTRUCTION,
    output_schema=SourcingPlan,
)
```

Update `src/orchestrator_agent/core/prompts.py` to contain only the focused instructions for these three LLM nodes (no more giant 9-step orchestration prompt).

### Step 7 — Assemble the Workflow graph

`src/orchestrator_agent/core/agent.py`:

```python
"""Capacity Orchestrator Agent — ADK 2.0 Workflow.

This is the heart of the demo. The Orchestrator is a graph of nodes:
- Function nodes for deterministic operations (parsing, parallel queries, routing, plan building)
- LLM nodes for AI reasoning (equivalence judgment, logistics refinement, plan revision)
- A2A node for Procurement Approval (external A2A call)
- AgentTool for Plan Evaluator (in-process)

The graph's purpose is to make the Orchestrator's behavior predictable and
auditable, while preserving Gemini's reasoning where it adds value.
"""

import os

import vertexai
from google.adk import Workflow

from .nodes.parse_request import parse_capacity_gap_request
from .nodes.resolve_asset import resolve_canonical_asset
from .nodes.parallel_queries import parallel_system_queries
from .nodes.evaluate_availability import evaluate_direct_availability
from .nodes.routers import (
    route_on_availability,
    route_on_evaluation_score,
    route_on_procurement_threshold,
)
from .nodes.build_plans import build_direct_plan, build_equivalent_plan
from .nodes.equivalence_lookup import equivalence_lookup_agent
from .nodes.sourcing_logistics import sourcing_logistics_agent
from .nodes.revise_plan import revise_plan_agent
from .nodes.finalize import finalize_sourcing_plan
from ..plan_evaluator.agent import root_agent as plan_evaluator
from ..core.tools import create_procurement_approval_tool

# Initialize Vertex AI
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if project_id:
    vertexai.init(project=project_id, location=location)


# Build the procurement approval call (A2A, in-process AgentTool wrapper)
procurement_approval = create_procurement_approval_tool()


# DEMO NARRATION: "Here's the workflow graph. This is the Capacity Orchestrator
# Agent rebuilt as an explicit graph using ADK 2.0's Workflow primitive. Each
# node is either deterministic code or AI reasoning, and the routing between
# them is policy expressed as graph edges, not LLM judgment encoded in a
# prompt. Watch the Cloud Trace as this executes — you'll see the same shape."
root_agent = Workflow(
    name="capacity_orchestrator",
    description=(
        "Capacity Orchestrator — lead architect for service capacity gap resolution. "
        "ADK 2.0 Workflow with deterministic flow control and AI reasoning at decision nodes."
    ),
    edges=[
        # Linear opening: parse → resolve → fan out
        ("START", parse_capacity_gap_request, resolve_canonical_asset, parallel_system_queries),

        # Evaluate availability and route on it
        (parallel_system_queries, evaluate_direct_availability, route_on_availability),
        (route_on_availability, {
            "DIRECT_AVAILABLE": build_direct_plan,
            "NEEDS_EQUIVALENCE": equivalence_lookup_agent,
        }),

        # Equivalence path: LLM finds substitute, function builds plan
        (equivalence_lookup_agent, build_equivalent_plan),

        # Merge paths → sourcing logistics refinement → plan evaluation
        (build_direct_plan, sourcing_logistics_agent),
        (build_equivalent_plan, sourcing_logistics_agent),
        (sourcing_logistics_agent, plan_evaluator, route_on_evaluation_score),

        # Evaluation routing: accept, revise, or exhausted
        (route_on_evaluation_score, {
            "ACCEPTED": route_on_procurement_threshold,
            "REVISE": revise_plan_agent,
            "EXHAUSTED": route_on_procurement_threshold,
        }),
        # Revision loop: revise → re-evaluate
        (revise_plan_agent, plan_evaluator),

        # Procurement routing: approve directly or call gate
        (route_on_procurement_threshold, {
            "AUTO_APPROVE": finalize_sourcing_plan,
            "REQUIRES_APPROVAL": procurement_approval,
        }),
        (procurement_approval, finalize_sourcing_plan),

        # Terminal node
        (finalize_sourcing_plan, "END"),
    ],
)
```

### Step 8 — Update the cargo-plane integration test

The test from TASK-03 should still work, but the trace it generates now shows the Workflow graph rather than an LLM monologue. Verify:

```bash
make deploy-orchestrator     # redeploy with Workflow
uv run pytest tests/integration/test_cargo_plane_scenario.py -v
```

If the test passes, pull a Cloud Trace from the run and inspect it. You should see:
- Distinct spans for each Workflow node
- Parallel spans for the four system queries
- A clearly labeled span for `equivalence_lookup` (the LLM node)
- A clearly labeled span for `plan_evaluator` (the AgentTool / LlmAgent call)
- A clearly labeled span for `procurement_approval` (the A2A call)

This trace **is** the demo's narrative spine. The graph in code matches the graph in the trace matches the graph in the slide deck. Customer sees one consistent story.

### Step 9 — Document the architecture decision

Create `docs/adr/0001-adopt-adk-2-workflow.md`:

```markdown
# ADR 0001: Adopt ADK 2.0 Workflow for the Capacity Orchestrator

## Status

Accepted

## Context

The Capacity Orchestrator in ADK 1.x was an LlmAgent with a 9-step instruction.
This worked but had three issues: (1) the LLM had latitude to skip or re-order
steps; (2) demo narration was reduced to "the LLM reasons through these steps,"
which is less compelling than showing an explicit graph; (3) procurement-audit
defensibility was harder to argue for a monolithic prompt-based agent.

ADK 2.0 Beta introduces Workflow agents: explicit graphs of nodes where each
node is either an LLM agent, a deterministic function, a tool call, or a
sub-workflow. This pattern matches how operations workflows are already modeled
in oilfield services (process flow diagrams, decision trees) and aligns with
Google's narrative for Gemini Enterprise Agent Platform at Next '26.

## Decision

The Capacity Orchestrator is refactored from LlmAgent to Workflow. LLM nodes
are scoped to specific decisions (equivalence judgment, logistics refinement,
plan revision). All routing, parallel dispatch, threshold checks, and
structured-data shaping is deterministic code.

Other agents stay as LlmAgents: Plan Evaluator (LLM-as-Judge), Procurement
Approval Agent (single-purpose), Forecast Review Agent (conversational
extraction). These are single-purpose reasoning agents where Workflow overhead
does not add value.

Capacity Planning Agent will be refactored to Workflow in a future task; the
multi-week scheduling logic with deterministic optimization plus AI sensitivity
analysis is a natural fit.

## Consequences

Positive:
- Cloud Trace shows the graph executing, which is the demo's strongest moment
- LLM calls are isolated to decision points, reducing token usage and improving
  latency for the deterministic steps
- Procurement audit can review the graph structure independently of prompts
- Future iterations can add nodes (e.g., compliance checks) without modifying
  prompts

Negative:
- ADK 2.0 Beta carries breaking-change risk; we pin to a specific Beta version
- Live Streaming is not compatible with Workflow agents per the 2.0 docs; we
  do not use Live Streaming in this build
- Some third-party integrations may not be compatible per the 2.0 docs; we
  validate our integration set (MCP, A2A, Memory Bank — all platform-native)
```

### Step 10 — Commit

```bash
git add .
git commit -m "feat: refactor Capacity Orchestrator to ADK 2.0 Workflow (TASK-04)"
git push
```

---

## Acceptance criteria

- [ ] `google-adk>=2.0.0b1,<2.1` installed; `python -c "import google.adk; print(google.adk.__version__)"` returns a 2.0.x version
- [ ] All TASK-01–03 unit tests still pass
- [ ] All TASK-01–03 integration tests still pass
- [ ] `src/orchestrator_agent/core/agent.py` is now a `Workflow`, not an `LlmAgent`
- [ ] At least three function nodes implemented: `parse_capacity_gap_request`, `parallel_system_queries`, `route_on_availability`
- [ ] At least three LLM nodes implemented: `equivalence_lookup_agent`, `sourcing_logistics_agent`, `revise_plan_agent`
- [ ] Every node has a `# DEMO NARRATION:` comment with the demoer's exact line
- [ ] Cargo-plane integration test passes against the new Workflow Orchestrator
- [ ] Cloud Trace from a real run shows distinct spans for each node, with parallel spans for the system queries
- [ ] `docs/adr/0001-adopt-adk-2-workflow.md` written and committed
- [ ] Plan Evaluator, Procurement Approval, Forecast Review remain LlmAgents (no refactor)
- [ ] Old `agent_v1_llmagent.py.bak` file removed once Workflow is verified working
- [ ] Commit pushed to GitHub

---

## Common pitfalls

**Beta API churn.** ADK 2.0 is Beta. Breaking changes between Beta versions are possible. Pin to a specific Beta release (e.g., `google-adk==2.0.0b3`) rather than a range, once a stable Beta version is identified.

**Mixing 1.x and 2.0 imports.** Don't import both `from google.adk.agents import LlmAgent` (1.x) and `from google.adk import Workflow` (2.0) in the same file. Pick one canonical path. In 2.0, use `from google.adk import Agent` for LLM agents and `from google.adk import Workflow` for workflows.

**Forgetting `output_schema` on LLM nodes.** In a Workflow, LLM nodes must produce structured output that the next node consumes. Without `output_schema`, the downstream node receives unstructured text and fails.

**Synchronous functions where async is needed.** `parallel_system_queries` must be async because it uses `asyncio.gather`. Other function nodes can be sync. Mixing causes confusing errors in the Workflow runner.

**Event payload shape inconsistency.** Each node returns `Event(payload=...)`. The next node receives that payload as input. If node A returns `Event(payload=request.model_dump())` and node B expects `Event(payload={"request": request.model_dump()})`, the contract breaks. Pick a convention and stick to it: prefer flat payloads with named keys.

**Forgetting the END terminator.** Workflows need an explicit `"END"` edge. Without it, the runner has no signal that the workflow completed.

**Revision loops without iteration counts.** The revision path can loop indefinitely if there's no counter. The `route_on_evaluation_score` function tracks `iteration_count` in the payload; ensure every node along the revision path preserves it.

**Workflow not deploying to Agent Runtime.** ADK 2.0 Workflows deploy the same way as LlmAgents: `adk deploy agent_engine`. If deployment fails, check the agent_card.py — the Agent Card for a Workflow needs to declare its workflow nature.

**Cloud Trace showing flat structure.** If the trace doesn't show nested spans per node, the deployed environment may need OpenTelemetry configuration. See `https://adk.dev/observability/traces/` for the 2.0 trace setup.

---

## References

- ADK 2.0 home: `https://adk.dev/2.0/`
- Workflows overview: `https://adk.dev/workflows/`
- Graph routes: `https://adk.dev/workflows/graph-routes/`
- Data handling: `https://adk.dev/workflows/data-handling/`
- Workflow samples: `https://github.com/google/adk-python/tree/v2/contributing/workflow_samples`
- ADK 2.0 release notes: `https://adk.dev/release-notes/`

---

*When TASK-04 is complete, proceed to `TASK-05-mcp-servers.md`.*
