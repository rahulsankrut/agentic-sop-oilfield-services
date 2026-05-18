# TASK-02: Agent skeletons

**Prerequisites:** TASK-01 complete. Placeholder Orchestrator deployed successfully. Reference repo cloned at `/tmp/next-26-keynotes/`.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Backend

---

## Context

Build the proper skeletal structure for all five ADK agents: Capacity Orchestrator, Plan Evaluator (bundled with Orchestrator as an in-process `AgentTool`), Procurement Approval Agent, Forecast Review Agent, and Capacity Planning Agent. Each agent should have its full directory structure (`core/`, `runtime/`, `services/`) and deploy cleanly, but the actual domain logic (skills, sophisticated prompts) is left for TASK-03+.

Think of this as the "fork and rename" task. We are taking the marathon demo's `planner_agent` + `evaluator` + `simulator_agent` and reshaping them into our domain. We also add two new agents (Forecast Review, Capacity Planning Agent) that don't exist in the marathon demo. By the end of this task, the demo runs end-to-end with placeholder content — agents call each other, structured outputs flow through the pipeline, A2A handoffs work — but the responses are simple acknowledgments, not real domain reasoning.

This task is foundational. Get the structure right; everything else gets built into it.

---

## Inputs

- Reference repo at `/tmp/next-26-keynotes/devkey/demo-2/`
- The repository created in TASK-01
- `SPECS.md` for architectural patterns

---

## Deliverables

When this task is complete:

1. All five agents exist with proper directory structure
2. Each agent has working `core/`, `runtime/`, `services/` modules
3. Each agent deploys via its `make deploy-<agent>-skeleton` target
4. The Orchestrator can call the Plan Evaluator in-process (`AgentTool`) and receive a structured `PlanEvaluation` response
5. The Orchestrator can call the Procurement Gate via A2A (`RemoteA2aAgent`) and receive a structured `ProcurementApproval` response
6. End-to-end test: a prompt to the Orchestrator returns a placeholder sourcing plan that has been scored and approved
7. Shared Pydantic schemas exist in `src/schemas.py` and are imported consistently
8. `PromptBuilder` utility ported from reference repo to `src/utils/prompt_builder.py`
9. Memory Bank integration via `auto_save_memories` callback wired in all agents
10. Agent Cards published for all agents (A2A discovery works)

---

## The five agents at a glance

| Agent | Deployment | Communication | Role |
|---|---|---|---|
| Capacity Orchestrator | Cloud Run (via Agent Engine for v1; can split later) | Receives user prompts | Lead architect; designs sourcing plans |
| Plan Evaluator | Bundled in Orchestrator | `AgentTool` (in-process) | 7-criterion LLM-as-Judge |
| Procurement Approval Agent | Agent Engine | A2A `RemoteA2aAgent` from Orchestrator | Fast deterministic approval gate |
| Forecast Review Agent | Agent Engine | Direct invocation from Gemini Enterprise app | Captures rationale on basin leader overrides |
| Capacity Planning Agent | Agent Engine, long-running | Direct invocation from Gemini Enterprise app | Multi-week buffer optimization |

---

## Step-by-step instructions

### Step 1 — Port `PromptBuilder` utility

The marathon demo uses an immutable, section-based `PromptBuilder` class in `src/planner_agent/utils.py`. Copy this to your `src/utils/prompt_builder.py` and verify it works:

```bash
cp /tmp/next-26-keynotes/devkey/demo-1/planner_agent/utils.py \
   src/utils/prompt_builder.py
```

Update imports if needed. Add a unit test in `tests/unit/test_prompt_builder.py` verifying:
- `build()` joins sections correctly
- `override()` returns a new instance (immutability)
- `dynamic()` produces a valid async provider

### Step 2 — Define shared Pydantic schemas

Create `src/schemas.py` with the shared types every agent will use. These define the structured outputs and A2A message payloads:

```python
"""Shared Pydantic schemas for the Oilfield Services Domain Pack.

These define the structured outputs and inter-agent message payloads.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ============================================================================
# Geographic and identity primitives
# ============================================================================

class GeoPoint(BaseModel):
    """Latitude/longitude point."""
    latitude: float
    longitude: float
    label: Optional[str] = None


class AssetIdentifier(BaseModel):
    """A canonical asset with its cross-system aliases."""
    canonical_id: str                              # e.g. "TX-001"
    canonical_label: str                            # e.g. "Tool X"
    sap_material_number: Optional[str] = None      # e.g. "MAT-67890"
    maximo_equipment_id: Optional[str] = None      # e.g. "EQ-12345"
    fdp_config_id: Optional[str] = None             # e.g. "TX-CONFIG-A"
    intouch_spec_refs: list[str] = Field(default_factory=list)


# ============================================================================
# Sourcing plan (Persona 3 — Maria)
# ============================================================================

class SourcingOption(BaseModel):
    """A single sourcing option (where to get an asset from)."""
    asset: AssetIdentifier
    source_location: GeoPoint
    destination: GeoPoint
    transit_mode: str                              # "ground_transit" | "cargo_charter" | "sea_freight"
    estimated_cost_usd: int
    transit_hours: float
    certification_hours: float = 0
    customer_compatibility: bool
    workforce_available: bool
    blockers: list[str] = Field(default_factory=list)


class SourcingPlan(BaseModel):
    """The Capacity Orchestrator's sourcing recommendation."""
    request_id: UUID = Field(default_factory=uuid4)
    requested_asset: str                            # what the planner asked for
    target_location: GeoPoint                       # where they need it
    deadline: datetime
    primary_option: SourcingOption                  # the recommended source
    naive_baseline: Optional[SourcingOption] = None # what they'd have done without the agent
    avoided_cost_usd: int = 0
    reasoning_trace_url: Optional[str] = None


# ============================================================================
# Plan Evaluator output (Persona 3 — Plan Evaluator sub-agent)
# ============================================================================

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CriterionScore(BaseModel):
    criterion: str
    score: float                                    # 0.0 to 1.0
    severity: Severity
    rationale: str


class PlanEvaluation(BaseModel):
    """Plan Evaluator's evaluation of a SourcingPlan."""
    request_id: UUID
    overall_score: float                            # weighted, 0.0 to 1.0
    criterion_scores: list[CriterionScore]
    findings: list[str] = Field(default_factory=list)
    revision_recommended: bool = False


# ============================================================================
# Procurement Gate output
# ============================================================================

class ProcurementApproval(BaseModel):
    """Procurement Approval Agent's decision on a SourcingPlan."""
    request_id: UUID
    approved: bool
    blockers: list[str] = Field(default_factory=list)
    audit_trail_url: Optional[str] = None


# ============================================================================
# Forecast review (Persona 1 — David)
# ============================================================================

class ForecastOverride(BaseModel):
    basin: str
    period: str                                     # e.g. "2026-Q4"
    metric: str                                     # e.g. "completions_revenue"
    original_value: float
    override_value: float
    override_pct_change: float
    submitted_by: str
    submitted_at: datetime


class ForecastRationale(BaseModel):
    override_id: UUID
    rationale_tags: list[str]                       # e.g. ["rig_count_decline", "operator_delay"]
    freeform_text: str
    confidence: float


# ============================================================================
# Buffer optimization (Persona 2 — Tomas)
# ============================================================================

class StartDateDistribution(BaseModel):
    """Probabilistic distribution of an actual start date vs. requested."""
    requested_date: datetime
    p10_actual_date: datetime
    p50_actual_date: datetime
    p90_actual_date: datetime
    confidence: float


class BufferOptimization(BaseModel):
    """Capacity Planning Agent's buffer recommendation for a fleet."""
    request_id: UUID
    basin: str
    risk_tolerance: float                           # 0.0 to 1.0
    current_buffer_days: float
    recommended_buffer_days: float
    projected_on_time_rate: float                   # 0.0 to 1.0
    fleet_utilization_uplift_pct: float
    deferred_capex_usd: int


# ============================================================================
# WebSocket event envelope (for Operations Canvas)
# ============================================================================

class CanvasEventEnvelope(BaseModel):
    """Wraps any agent event for transmission to the Operations Canvas."""
    event_type: str
    request_id: UUID
    timestamp: datetime
    payload: dict
```

Test with a unit test verifying each schema can serialize to JSON cleanly.

### Step 3 — Fork the Capacity Orchestrator

The Orchestrator is the most complex agent. Mirror the `planner_agent` structure from the reference demo.

Create the following files in `src/orchestrator_agent/`:

**`core/agent.py`** — Replace the placeholder from TASK-01 with the real skeleton:

```python
"""Capacity Orchestrator Agent — the lead architect for capacity gap resolution."""

import os

import vertexai
from google.adk.agents import LlmAgent
from google.genai.types import GenerateContentConfig, ThinkingConfig

from .config import AGENT_NAME, AGENT_DESCRIPTION, MODEL
from .prompts import INSTRUCTION
from .tools import get_tools
from ..services.memory_manager import auto_save_memories
from ...schemas import SourcingPlan

# Initialize Vertex AI
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if project_id:
    vertexai.init(project=project_id, location=location)


# DEMO NARRATION: "This is the Capacity Orchestrator — built on ADK, hosted on
# Agent Runtime. It's the lead agent that decomposes capacity-gap queries,
# coordinates with the Plan Evaluator (in-process) and Procurement Gate (via A2A),
# and produces a SourcingPlan grounded in Knowledge Catalog."
root_agent = LlmAgent(
    name=AGENT_NAME,
    model=MODEL,
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    tools=get_tools(),
    output_schema=SourcingPlan,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=2048),
    ),
    after_agent_callback=auto_save_memories,
)
```

**`core/config.py`**:

```python
"""Configuration for the Capacity Orchestrator Agent."""

import os

AGENT_NAME = "orchestrator_agent"
AGENT_DESCRIPTION = (
    "Capacity Orchestrator Agent — lead architect for service capacity gap resolution. "
    "Decomposes capacity queries across SAP, Maximo, FDP, and InTouch via MCP. "
    "Coordinates with Plan Evaluator (in-process AgentTool) and Procurement Approval Agent "
    "(A2A on Agent Engine). Produces grounded SourcingPlan recommendations."
)

# Gemini 3.1 Pro for reasoning depth; switch to Flash if latency budget tightens
MODEL = os.getenv("ORCHESTRATOR_MODEL", "gemini-3-1-pro-preview")
```

**`core/prompts.py`** — Skeleton instruction. Full prompt comes in TASK-03 when skills are wired:

```python
"""System instruction for the Capacity Orchestrator Agent.

Skeleton version for TASK-02. The full instruction (with skills, workflow,
and detailed rules) is composed in TASK-03 once the skills exist.
"""

from collections import OrderedDict

from ...utils.prompt_builder import PromptBuilder


ROLE = """\
# Role
Capacity Orchestrator Agent — lead architect for service capacity gap resolution.

# Mission
When a planner reports a capacity gap (an asset needed at a location by a deadline),
you decompose the request, query enterprise systems, identify the best sourcing option,
score it for risk, and obtain procurement approval.
"""

RULES = """\
# Rules
- Always return a structured SourcingPlan as your final output.
- Always score plans via the Plan Evaluator before finalizing.
- Plans involving cost > $500K or transit > 8000km must go through the Procurement Approval Agent.
- Cite the Knowledge Catalog canonical entity for every asset you reference.
"""

WORKFLOW_PLACEHOLDER = """\
# Workflow (skeleton — will be expanded in TASK-03)
1. Acknowledge the capacity gap.
2. Produce a placeholder SourcingPlan with example data.
3. Call the Plan Evaluator to score it.
4. If overall_score < 0.85, revise and re-score.
5. Call the Procurement Gate to approve.
6. Return the final SourcingPlan with the avoided_cost_usd field populated.
"""

INSTRUCTION = PromptBuilder(
    OrderedDict(
        role=ROLE,
        rules=RULES,
        workflow=WORKFLOW_PLACEHOLDER,
    )
).build()
```

**`core/tools.py`** — Wires the Plan Evaluator (AgentTool) and Procurement Gate (A2A):

```python
"""Tools for the Capacity Orchestrator Agent.

Includes:
- Plan Evaluator as an in-process AgentTool
- Procurement Approval Agent as a RemoteA2aAgent
- (Skill toolset and MCP servers will be added in TASK-03/TASK-04)
"""

import logging
import os

import httpx
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

from .auth import GoogleAuthRefresh
from ..plan_evaluator.agent import root_agent as plan_evaluator_agent

logger = logging.getLogger(__name__)


# Mirror the reference demo's SerializableRemoteA2aAgent for proper auth
class SerializableRemoteA2aAgent(RemoteA2aAgent):
    """RemoteA2aAgent with Google Cloud authentication and Agent Engine URL fix."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auth_refresh = GoogleAuthRefresh()


def _get_agent_a2a_endpoint(resource_name: str, default_port: int = 8080) -> str:
    """Construct A2A card endpoint from Agent Engine resource name or local address."""
    if resource_name.startswith("local"):
        port = resource_name.split(":")[1] if ":" in resource_name else default_port
        return f"http://127.0.0.1:{port}/.well-known/agent-card.json"

    parts = resource_name.split("/")
    try:
        location_idx = parts.index("locations") + 1
        location = parts[location_idx]
        api_endpoint = f"https://{location}-aiplatform.googleapis.com"
        return f"{api_endpoint}/v1beta1/{resource_name}/a2a/v1/card"
    except (ValueError, IndexError):
        return resource_name


def _get_agent_a2a_url(resource_name: str) -> str | None:
    """Construct the regional A2A message URL from Agent Engine resource name."""
    if resource_name.startswith("local"):
        return None
    parts = resource_name.split("/")
    try:
        location_idx = parts.index("locations") + 1
        location = parts[location_idx]
        api_endpoint = f"https://{location}-aiplatform.googleapis.com"
        return f"{api_endpoint}/v1beta1/{resource_name}/a2a/v1:message"
    except (ValueError, IndexError):
        return None


def create_plan_evaluator_tool() -> AgentTool:
    """Plan Evaluator is bundled in-process — same deployment as Orchestrator."""
    # DEMO NARRATION: "The Plan Evaluator is bundled in-process via AgentTool —
    # no network hop, sub-second response. It's an LLM-as-Judge with 7 weighted
    # criteria specific to oilfield services sourcing decisions."
    return AgentTool(agent=plan_evaluator_agent)


def create_procurement_approval_tool() -> AgentTool:
    """Procurement Gate is remote — Agent Engine, called via A2A."""
    resource_name = os.environ.get("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME")
    if not resource_name:
        raise ValueError("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set")

    endpoint = _get_agent_a2a_endpoint(resource_name, default_port=8089)

    # DEMO NARRATION: "The Procurement Approval Agent runs on Agent Engine,
    # called via A2A protocol. This is the same A2A pattern Google announced
    # for collaboration with SAP Joule agents — open standard, cryptographically
    # signed agent cards."
    remote = SerializableRemoteA2aAgent(
        name="procurement_approval_agent",
        description=(
            "Procurement Approval Agent. Reviews sourcing plans for procurement readiness: "
            "budget threshold, customer authorization, certification check, regulatory clearance."
        ),
        agent_card=endpoint,
        a2a_url=_get_agent_a2a_url(resource_name),
    )
    return AgentTool(agent=remote)


def get_tools() -> list:
    """Build the Orchestrator's tool list."""
    tools = [
        PreloadMemoryTool(),
        create_plan_evaluator_tool(),
    ]
    if os.environ.get("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME"):
        tools.append(create_procurement_approval_tool())
        logger.info("Procurement Gate A2A tool enabled")
    else:
        logger.warning("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set — skipping A2A tool")
    return tools
```

**`core/auth.py`** — Mirror `auth.py` from the reference demo's `planner_agent/core/`:

```bash
cp /tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/core/auth.py \
   src/orchestrator_agent/core/auth.py
```

**`runtime/`** — Port from the reference demo and rename:

```bash
cp /tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/runtime/*.py \
   src/orchestrator_agent/runtime/
```

Update each file to use the Orchestrator's name and description. Critical files:
- `agent_card.py` — describes the agent for A2A discovery
- `agent_executor.py` — ADK runtime hook
- `deploy.py` — deployment script
- `local_server.py` — local dev server for debugging

**`services/memory_manager.py`** — Port from reference:

```bash
cp /tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/services/memory_manager.py \
   src/orchestrator_agent/services/memory_manager.py
```

**`services/session_manager.py`** — Same:

```bash
cp /tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/services/session_manager.py \
   src/orchestrator_agent/services/session_manager.py
```

### Step 4 — Build the Plan Evaluator (bundled in-process)

The Plan Evaluator lives inside the Orchestrator's deployment but is a distinct `LlmAgent`. It is called via `AgentTool`, so the Orchestrator sees it as just another tool.

Create `src/orchestrator_agent/plan_evaluator/`:

**`agent.py`**:

```python
"""Plan Evaluator — bundled with the Orchestrator, called via AgentTool.

Scores SourcingPlans across 7 weighted criteria using LLM-as-Judge.
Returns a structured PlanEvaluation.
"""

import os
import vertexai
from google.adk.agents import LlmAgent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai.types import GenerateContentConfig, ThinkingConfig

from .prompts import INSTRUCTION
from ...schemas import PlanEvaluation

MODEL = os.getenv("RISK_SCORER_MODEL", "gemini-3-1-pro-preview")

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if project_id:
    vertexai.init(project=project_id, location=location)


# 7 weighted criteria for oilfield services sourcing decisions
CRITERION_WEIGHTS = {
    "safety_compliance": 0.20,
    "customer_compatibility": 0.20,
    "logistics_feasibility": 0.15,
    "cost_optimality": 0.15,
    "equivalence_confidence": 0.10,
    "regulatory_compliance": 0.10,
    "schedule_feasibility": 0.10,
}
assert abs(sum(CRITERION_WEIGHTS.values()) - 1.0) < 0.0001, "Weights must sum to 1.0"

SEVERITY_THRESHOLDS = {"high": 40.0, "medium": 60.0, "low": 80.0}


# DEMO NARRATION: "The Plan Evaluator is an LLM-as-Judge — same pattern Google
# showed in the keynote marathon demo. Seven criteria specific to oilfield
# services: safety, customer compatibility, logistics feasibility, cost,
# equivalence confidence, regulatory, schedule. Each weighted, all aggregated."
root_agent = LlmAgent(
    name="plan_evaluator_agent",
    model=MODEL,
    description=(
        "Plan Evaluator for oilfield services sourcing plans. LLM-as-Judge with 7 "
        "weighted criteria. Returns structured PlanEvaluation with overall score, "
        "per-criterion scores, and revision recommendations."
    ),
    static_instruction=INSTRUCTION,
    output_schema=PlanEvaluation,
    generate_content_config=GenerateContentConfig(
        max_output_tokens=4096,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    include_contents="none",
    tools=[PreloadMemoryTool()],
)
```

**`prompts.py`** — Skeleton:

```python
"""Plan Evaluator instruction (TASK-02 skeleton; expanded in TASK-03)."""

INSTRUCTION = """\
You are the Plan Evaluator for oilfield services sourcing plans.

You will be given a SourcingPlan. Score it across 7 criteria:
- safety_compliance (weight 0.20)
- customer_compatibility (weight 0.20)
- logistics_feasibility (weight 0.15)
- cost_optimality (weight 0.15)
- equivalence_confidence (weight 0.10)
- regulatory_compliance (weight 0.10)
- schedule_feasibility (weight 0.10)

For each criterion, return a score from 0.0 to 1.0, severity (low/medium/high),
and a brief rationale. Also produce an overall_score (weighted sum) and any
findings or revision recommendations.

For TASK-02 skeleton purposes, always return overall_score = 0.91 with all
criteria scored 0.90+ and severity "low". The real scoring logic comes in TASK-03.

Always return a structured PlanEvaluation.
"""
```

The Plan Evaluator does NOT have its own `runtime/` directory — it's bundled in-process with the Orchestrator. No separate deployment.

### Step 5 — Build the Procurement Approval Agent (remote, A2A)

Mirror the marathon `simulator_agent` structure. This agent deploys separately to Agent Engine and is called by the Orchestrator via A2A.

Create `src/procurement_approval_agent/` with full directory structure (same as Orchestrator: `core/`, `runtime/`, `services/`, `skills/`).

**`core/agent.py`**:

```python
"""Procurement Approval Agent — fast deterministic approval gate.

Reviews SourcingPlans for procurement readiness: budget threshold, customer
authorization, certification, regulatory clearance. Returns ProcurementApproval.

This is NOT a quality check (that's the Plan Evaluator). This is a prerequisite check.
"""

import os
import vertexai
from google.adk.agents import LlmAgent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai.types import GenerateContentConfig, ThinkingConfig

from .config import AGENT_NAME, AGENT_DESCRIPTION, MODEL
from .prompts import INSTRUCTION
from ..services.memory_manager import auto_save_memories
from ...schemas import ProcurementApproval

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if project_id:
    vertexai.init(project=project_id, location=location)


# DEMO NARRATION: "The Procurement Approval Agent is the final approval. It's
# fast — no LLM reasoning depth needed, just deterministic prerequisite checks.
# Runs on Agent Engine. Called by the Orchestrator via A2A protocol — the same
# protocol that bridges to SAP Joule agents."
root_agent = LlmAgent(
    name=AGENT_NAME,
    model=MODEL,
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    output_schema=ProcurementApproval,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=0),  # no thinking — speed matters
        max_output_tokens=2048,
    ),
    after_agent_callback=auto_save_memories,
    tools=[PreloadMemoryTool()],
)
```

**`core/config.py`**:

```python
import os

AGENT_NAME = "procurement_approval_agent"
AGENT_DESCRIPTION = (
    "Procurement Approval Agent for oilfield services. Fast deterministic "
    "verification that a sourcing plan has all required fields, certifications, "
    "and is within authorization thresholds to commit logistics dollars."
)
MODEL = os.getenv("PROCUREMENT_GATE_MODEL", "gemini-3-flash-preview")
```

**`core/prompts.py`** — Skeleton:

```python
INSTRUCTION = """\
You are the Procurement Approval Agent.

You are given a SourcingPlan. Verify procurement readiness:
1. Cost under $500K (or appropriate threshold for the requester's tier)
2. Customer authorization present
3. Equipment certification chain valid
4. Regulatory clearances (cross-border, environmental) present

Return a ProcurementApproval. For TASK-02 skeleton purposes, always approve
unless cost > $500K (in which case set approved=false with appropriate blocker).
Real logic comes in TASK-03.
"""
```

Port `runtime/`, `services/` from the marathon `simulator_agent`:

```bash
cp /tmp/next-26-keynotes/devkey/demo-2/src/simulator_agent/runtime/*.py \
   src/procurement_approval_agent/runtime/
cp /tmp/next-26-keynotes/devkey/demo-2/src/simulator_agent/services/*.py \
   src/procurement_approval_agent/services/
```

Update `agent_card.py` to describe the Procurement Gate accurately.

### Step 6 — Build the Forecast Review Agent

This agent does not exist in the marathon demo — it's net new for our domain. But it follows the same structure.

Create `src/forecast_review_agent/` with full directory structure.

**`core/agent.py`**:

```python
"""Forecast Review Agent — captures rationale on basin leader overrides.

Triggered when a basin leader makes a significant override to the ML forecast.
Asks for the qualitative reasoning (rig count signals, operator delays, etc.),
extracts structured rationale tags, and writes them back to BigQuery for
inclusion in the next model retrain.
"""

import os
import vertexai
from google.adk.agents import LlmAgent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai.types import GenerateContentConfig, ThinkingConfig

from .config import AGENT_NAME, AGENT_DESCRIPTION, MODEL
from .prompts import INSTRUCTION
from ..services.memory_manager import auto_save_memories
from ...schemas import ForecastRationale

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
if project_id:
    vertexai.init(project=project_id, location=location)


# DEMO NARRATION: "Forecast Review Agent — runs in Gemini Enterprise app's
# Agent Inbox. When David makes a significant forecast override, this agent
# prompts him for rationale, extracts structured tags via Gemini, and writes
# them back to BigQuery. The next model retrain ingests this — Issue 2 closes."
root_agent = LlmAgent(
    name=AGENT_NAME,
    model=MODEL,
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    output_schema=ForecastRationale,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    after_agent_callback=auto_save_memories,
    tools=[PreloadMemoryTool()],
)
```

Port `core/config.py`, `core/prompts.py` skeletons following the same pattern. The skeleton response should always return a placeholder `ForecastRationale` with a few example tags.

Port `runtime/`, `services/` from the marathon `simulator_agent` and rename.

### Step 7 — Build the Capacity Planning Agent

Same structure as the others. This is a long-running agent (multi-week state), so the runtime configuration will need adjustment in a later task. For now, build the skeleton.

Create `src/capacity_planning_agent/` with full directory structure.

**`core/agent.py`** follows the same pattern, with `output_schema=BufferOptimization`.

**`core/prompts.py`** — Skeleton that always returns a placeholder `BufferOptimization` with: current_buffer_days=14, recommended_buffer_days=8, projected_on_time_rate=0.65, fleet_utilization_uplift_pct=12.0, deferred_capex_usd=4500000.

### Step 8 — Update the Makefile with per-agent deploy targets

Add to the existing `Makefile`:

```makefile
.PHONY: deploy-orchestrator deploy-procurement-gate deploy-forecast-review deploy-schedule-copilot
.PHONY: deploy-all-agents

deploy-orchestrator:
	uv run adk deploy agent_engine \
		--env_file src/orchestrator_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/orchestrator_agent

deploy-procurement-gate:
	uv run adk deploy agent_engine \
		--env_file src/procurement_approval_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/procurement_approval_agent

deploy-forecast-review:
	uv run adk deploy agent_engine \
		--env_file src/forecast_review_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/forecast_review_agent

deploy-schedule-copilot:
	uv run adk deploy agent_engine \
		--env_file src/capacity_planning_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/capacity_planning_agent

deploy-all-agents: deploy-procurement-gate deploy-forecast-review deploy-schedule-copilot deploy-orchestrator
	@echo "All agents deployed. Capture resource names in .env files."
```

The Procurement Gate must deploy before the Orchestrator, because the Orchestrator's tools depend on `PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME` being set.

### Step 9 — Deploy and verify end-to-end

Deploy all four remote agents:

```bash
make deploy-procurement-gate
# capture resource name, add to all .env files

make deploy-forecast-review
make deploy-schedule-copilot

# now deploy the orchestrator with procurement gate wired in
make deploy-orchestrator
```

Write a smoke test in `tests/integration/test_orchestrator_skeleton.py` that:
1. Invokes the deployed Orchestrator with a placeholder capacity-gap prompt
2. Verifies a `SourcingPlan` is returned
3. Verifies the `SourcingPlan` was scored (overall_score >= 0.85)
4. Verifies procurement approval was obtained

Run:
```bash
uv run pytest tests/integration/test_orchestrator_skeleton.py -v
```

### Step 10 — Commit

```bash
git add .
git commit -m "feat: agent skeletons for all 5 agents wired end-to-end (TASK-02)"
git push
```

---

## Acceptance criteria

- [ ] `src/utils/prompt_builder.py` ported and tested
- [ ] `src/schemas.py` has all shared Pydantic schemas
- [ ] All five agents have full directory structure (`core/`, `runtime/`, `services/`, `skills/`)
- [ ] Plan Evaluator is bundled in-process with Orchestrator (no separate deployment)
- [ ] All four remote agents deploy successfully to Agent Engine
- [ ] Orchestrator can invoke Plan Evaluator via `AgentTool` and receive a `PlanEvaluation`
- [ ] Orchestrator can invoke Procurement Gate via A2A and receive a `ProcurementApproval`
- [ ] End-to-end smoke test passes: prompt → SourcingPlan → scored → approved
- [ ] All agents have working Agent Cards (visible at `.well-known/agent-card.json` endpoints)
- [ ] Memory Bank `auto_save_memories` callback is wired in all agents
- [ ] `ruff check src/` runs clean
- [ ] All code has `# DEMO NARRATION:` comments at key moments
- [ ] Commit pushed

---

## Common pitfalls

**Forgetting `vertexai.init()`.** Every agent's `agent.py` must initialize Vertex AI before constructing the `LlmAgent`. The reference demo does this in every `core/agent.py`. If you skip it, deployment will fail with cryptic auth errors.

**Wrong A2A endpoint URL format.** Agent Engine A2A endpoints have a specific regional URL pattern (see `_get_agent_a2a_url` in `tools.py`). Don't use the generic `aiplatform.googleapis.com` URL — it returns 404 for `message:send`.

**Deploying the Orchestrator before the Procurement Gate.** The Orchestrator's `tools.py` reads `PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME` at startup. Deploy the Procurement Gate first, capture its resource name, then deploy the Orchestrator.

**Missing `output_schema`.** Every agent in our architecture returns structured data. The Orchestrator returns `SourcingPlan`, the Plan Evaluator returns `PlanEvaluation`, etc. If you forget `output_schema=...` on the `LlmAgent`, you'll get unstructured text back and downstream parsing will fail.

**Forgetting `include_contents="none"` on the Plan Evaluator.** The Plan Evaluator is called with a single sourcing plan to evaluate — it doesn't need conversation history. Setting `include_contents="none"` (as the reference Evaluator does) keeps token usage and latency down.

**Memory Bank callback regional consistency.** `auto_save_memories` writes to Memory Bank in a specific region. Memory Bank, Sessions, and the agent itself all need to be in the same region. Stick with `us-central1` for everything in v1.

---

## References

- `next-26-keynotes/devkey/demo-2/src/planner_agent/core/agent.py` — Orchestrator template
- `next-26-keynotes/devkey/demo-2/src/planner_agent/evaluator/agent.py` — Plan Evaluator template (LLM-as-Judge pattern)
- `next-26-keynotes/devkey/demo-2/src/simulator_agent/core/agent.py` — Procurement Gate template
- `next-26-keynotes/devkey/demo-2/src/planner_agent/core/tools.py` — A2A wiring pattern
- `next-26-keynotes/devkey/demo-2/src/planner_agent/runtime/agent_card.py` — Agent Card pattern

---

*When TASK-02 is complete, proceed to `TASK-03-skills.md`.*
