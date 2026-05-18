# TASK-03: Build the six ADK Skills

**Prerequisites:** TASK-02 complete. All five agent skeletons deployed and end-to-end smoke test passing.

**Estimated effort:** 5-7 days for one engineer.

**Stream:** Backend

---

## Context

ADK Skills are the unit of domain knowledge in this architecture. Each skill is a directory containing:

- `SKILL.md` — frontmatter (name, description, optional `metadata.adk_additional_tools`) plus markdown instructions for the LLM
- `scripts/tools.py` (and optionally other Python files) — callable functions exposed as ADK tools when the skill is loaded
- `references/` — markdown reference content the LLM can consult

Skills are loaded **lazily** via `SkillToolset` and `load_skill_from_dir`. When an agent's prompt mentions a skill name, the LLM calls `load_skill("skill-name")` and the skill's tools become available. This is the same pattern Anthropic uses for Claude skills — Google's ADK has adopted it. Look at how the reference demo uses skills before building.

This task builds the six skills that give our agents their actual domain intelligence. After this task, the agents move from "skeleton placeholder responses" to "real reasoning with real domain logic." The data they reason against is still synthetic (real data integration comes in TASK-05 Knowledge Catalog setup and TASK-04 MCP servers), but the reasoning logic is real.

---

## Inputs

- TASK-02 complete, all agents deployed with skeletons
- Reference repo skill examples at `/tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/skills/` and `/tmp/next-26-keynotes/devkey/demo-1/planner_agent/skills/`
- The shared Pydantic schemas in `src/schemas.py`

---

## Deliverables

When this task is complete:

1. Six fully-built ADK Skills exist:
   - **Capacity Orchestrator** (4 skills): `asset-equivalence`, `sourcing-logistics`, `enterprise-systems`, *(skill toolset wired in `tools.py`)*
   - **Plan Evaluator** (1 skill): `plan-evaluation`
   - **Procurement Approval Agent** (1 skill): `procurement-prerequisites`
   - **Forecast Review Agent** (1 skill): `forecast-rationale`
   - **Capacity Planning Agent** (1 skill): `scheduling-probability`
2. Each skill has `SKILL.md`, `scripts/tools.py`, and `references/*.md`
3. Each agent's `core/tools.py` is updated to wire the skill toolset
4. Each agent's `core/prompts.py` is expanded with the full workflow that references the skills
5. The Orchestrator's `output_schema` produces realistic `SourcingPlan` content with non-placeholder values (using in-memory synthetic data for now; MCP servers come in TASK-04)
6. The Plan Evaluator's 7-criterion scoring is real (not always 0.91)
7. Unit tests for each skill's tools (the deterministic logic, separate from LLM behavior)
8. End-to-end test: the cargo-plane scenario produces a plan recommending Lagos sub-variant with realistic cost/savings numbers

Wait — I count seven skills above, not six. Recount: the Orchestrator has `asset-equivalence`, `sourcing-logistics`, `enterprise-systems` (3); the other agents each have one (4 more). That's 7. Update the count: **seven skills**. Adjust `SPECS.md` and `oilfield_domain_pack_brief.md` if they still say six.

---

## Skill structure (template)

Every skill follows this pattern. See `next-26-keynotes/devkey/demo-1/planner_agent/skills/gis-spatial-engineering/` for a complete reference.

```
skill_name/
├── SKILL.md            # Frontmatter + LLM-facing instructions
├── __init__.py         # Empty
├── scripts/
│   ├── __init__.py
│   └── tools.py        # The callable functions exposed as ADK tools
└── references/         # Optional markdown reference content
    ├── thing_a.md
    └── thing_b.md
```

### `SKILL.md` frontmatter

```yaml
---
name: skill-name
description:
  One-sentence description of what this skill does. Read by the agent's
  routing logic to decide whether to load.
metadata:
  adk_additional_tools:
    - tool_function_name_1
    - tool_function_name_2
---

# Skill Name

Detailed LLM-facing instructions follow as markdown.

## Capabilities

- Bullet points describing what the skill does

## Tools

- `tool_function_name_1(arg: type) -> ReturnType`: description
- `tool_function_name_2(...)`: description

## Instructions

Detailed step-by-step instructions for how the LLM should use this skill.

## References

If the skill has reference content in `references/`, the LLM is told where to find it.
```

### `scripts/tools.py` structure

```python
"""Tools for the {skill_name} skill."""

from ...schemas import SomeSchema   # Pydantic types from src/schemas.py

def my_tool(arg: str) -> SomeSchema:
    """One-line description.

    Args:
        arg: description.

    Returns:
        description.
    """
    # implementation
    ...
```

ADK introspects function signatures and docstrings to expose them as tools.

---

## Step-by-step instructions

### Step 1 — Generate synthetic data for skill testing

Before building skills, you need synthetic data that the skill tools query against. This is preview data only — TASK-05 will move this into Knowledge Catalog and Smart Storage proper.

Create `src/utils/synthetic_data.py` that loads JSON files from `data/`:

```python
"""Synthetic data loader for skill development.

This module loads in-memory representations of the synthetic data files
in /data/. In production this data lives in Knowledge Catalog / BigQuery / GCS.
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@lru_cache(maxsize=1)
def load_canonical_assets() -> list[dict]:
    """Load the canonical asset taxonomy."""
    with open(DATA_DIR / "canonical_assets.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_cross_system_aliases() -> dict[str, dict]:
    """Load cross-system aliases keyed by canonical_id."""
    with open(DATA_DIR / "cross_system_aliases.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_functional_equivalences() -> list[dict]:
    """Load functional equivalence relationships."""
    with open(DATA_DIR / "functional_equivalences.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_customers() -> list[dict]:
    """Load synthetic customer records."""
    with open(DATA_DIR / "customers.json") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_start_date_variance(basin: str) -> list[dict]:
    """Load historical start-date variance for a basin."""
    with open(DATA_DIR / "start_date_variance" / f"{basin}.json") as f:
        return json.load(f)
```

Create initial seed data in `data/`:

**`data/canonical_assets.json`** — 30-50 canonical entries. Build a generator script if needed. Each entry has structure:

```json
{
  "canonical_id": "TX-001",
  "canonical_label": "Tool X",
  "category": "downhole_tool",
  "subcategory": "drilling_motor",
  "specifications": {
    "operating_temp_max_c": 175,
    "operating_pressure_max_psi": 20000,
    "outer_diameter_in": 6.75
  },
  "manufacturer": "OEM-A",
  "introduced_year": 2018
}
```

**`data/cross_system_aliases.json`** — keyed by canonical_id:

```json
{
  "TX-001": {
    "sap_material_number": "MAT-67890",
    "maximo_equipment_id": "EQ-12345",
    "fdp_config_id": "TX-CONFIG-A",
    "intouch_spec_refs": ["spec-3.2-2024", "compatibility-cc-204"]
  }
}
```

**`data/functional_equivalences.json`**:

```json
[
  {
    "canonical_id_a": "TX-001",
    "canonical_id_b": "TX-007",
    "confidence": 0.92,
    "rationale_source": "InTouch Spec §3.2",
    "customer_compatibility_overrides": []
  }
]
```

Generate enough data to make the cargo-plane scenario realistic. Aim for 30-50 canonical assets, 5-10 customers, 10-15 equivalence relationships.

### Step 2 — Build `asset-equivalence` skill (Orchestrator)

Create `src/orchestrator_agent/skills/asset-equivalence/`.

**`SKILL.md`**:

```yaml
---
name: asset-equivalence
description:
  Expert reasoning over the canonical asset taxonomy to identify functionally
  equivalent equipment variants. Queries the canonical entity model and
  traverses functional_equivalence relationships, returning ranked candidates
  with confidence scores and rationale citations.
metadata:
  adk_additional_tools:
    - resolve_canonical_asset
    - find_functional_equivalents
    - score_equivalence_confidence
---

# Asset Equivalence

When a planner needs an asset that isn't directly available, this skill helps
you find functionally equivalent alternatives that may be located closer or
more readily deployable.

## Workflow

1. **Resolve the requested asset** to its canonical entity using
   `resolve_canonical_asset`. The planner may give you a local name from any
   source system (SAP material number, Maximo equipment ID, customer-specific
   label). This tool returns the canonical entity with all aliases.

2. **Find functional equivalents** with `find_functional_equivalents`. This
   returns a list of canonical entities that are functionally interchangeable
   with the input, each with a confidence score and the rationale source
   (typically an InTouch spec reference).

3. **Score for the specific customer config** with `score_equivalence_confidence`.
   Functional equivalence in general doesn't guarantee customer-specific
   compatibility — some customers have configuration overrides that restrict
   substitutions. This tool returns a customer-conditioned confidence score.

## Decision-Making Guidance

- Always start with `resolve_canonical_asset` — never reason about local
  identifiers directly. The agent must reason against canonical entities.
- If `find_functional_equivalents` returns no results, the asset has no known
  substitutes and the planner must use the original.
- Confidence below 0.7 should surface a "high uncertainty" finding to the planner.

## References

- `references/equivalence_rules.md`: engineering rules for substitution
- `references/customer_overrides.md`: known customer-specific compatibility
  constraints
```

**`scripts/tools.py`**:

```python
"""Tools for the asset-equivalence skill."""

from typing import Optional

from ....schemas import AssetIdentifier
from ...utils.synthetic_data import (
    load_canonical_assets,
    load_cross_system_aliases,
    load_functional_equivalences,
    load_customers,
)


def resolve_canonical_asset(
    local_identifier: str,
    source_system: Optional[str] = None,
) -> AssetIdentifier:
    """Resolve a system-local identifier to its canonical asset.

    Args:
        local_identifier: The identifier as it appears in a source system
            (e.g. 'MAT-67890' from SAP, 'EQ-12345' from Maximo, or 'TX-001' canonical).
        source_system: Optional hint ('sap', 'maximo', 'fdp', 'canonical').

    Returns:
        AssetIdentifier with canonical_id, canonical_label, and all cross-system aliases.

    Raises:
        ValueError: if no canonical match is found.
    """
    # DEMO NARRATION: "This is the resolution moment — the agent doesn't reason
    # about MAT-67890 or EQ-12345; it reasons about TX-001 the canonical entity.
    # Issue 4 — taxonomic chaos — is resolved here."
    aliases = load_cross_system_aliases()
    assets = {a["canonical_id"]: a for a in load_canonical_assets()}

    # Direct canonical match
    if local_identifier in assets:
        a = assets[local_identifier]
        alias = aliases.get(local_identifier, {})
        return AssetIdentifier(
            canonical_id=a["canonical_id"],
            canonical_label=a["canonical_label"],
            sap_material_number=alias.get("sap_material_number"),
            maximo_equipment_id=alias.get("maximo_equipment_id"),
            fdp_config_id=alias.get("fdp_config_id"),
            intouch_spec_refs=alias.get("intouch_spec_refs", []),
        )

    # Search aliases
    for canonical_id, alias in aliases.items():
        if local_identifier in (
            alias.get("sap_material_number"),
            alias.get("maximo_equipment_id"),
            alias.get("fdp_config_id"),
        ):
            a = assets[canonical_id]
            return AssetIdentifier(
                canonical_id=a["canonical_id"],
                canonical_label=a["canonical_label"],
                sap_material_number=alias.get("sap_material_number"),
                maximo_equipment_id=alias.get("maximo_equipment_id"),
                fdp_config_id=alias.get("fdp_config_id"),
                intouch_spec_refs=alias.get("intouch_spec_refs", []),
            )

    raise ValueError(f"No canonical asset found for identifier: {local_identifier}")


def find_functional_equivalents(canonical_id: str) -> list[dict]:
    """Find functionally equivalent variants of a canonical asset.

    Args:
        canonical_id: The canonical_id of the source asset.

    Returns:
        List of {canonical_id, confidence, rationale_source} dicts for each
        equivalent asset.
    """
    # DEMO NARRATION: "This is where the cargo-plane scenario pivots. The agent
    # reaches into Knowledge Catalog's functional_equivalence relationships and
    # finds Tool X-V7 is interchangeable with Tool X per InTouch spec §3.2."
    equivalences = load_functional_equivalences()
    results = []
    for eq in equivalences:
        if eq["canonical_id_a"] == canonical_id:
            results.append({
                "canonical_id": eq["canonical_id_b"],
                "confidence": eq["confidence"],
                "rationale_source": eq["rationale_source"],
            })
        elif eq["canonical_id_b"] == canonical_id:
            results.append({
                "canonical_id": eq["canonical_id_a"],
                "confidence": eq["confidence"],
                "rationale_source": eq["rationale_source"],
            })
    return sorted(results, key=lambda r: r["confidence"], reverse=True)


def score_equivalence_confidence(
    canonical_id_source: str,
    canonical_id_substitute: str,
    customer_id: str,
) -> float:
    """Score equivalence confidence conditioned on a specific customer's config.

    Args:
        canonical_id_source: The originally requested asset.
        canonical_id_substitute: The candidate substitute.
        customer_id: The customer for whom this substitution would be deployed.

    Returns:
        Confidence score from 0.0 to 1.0. Below 0.5 indicates the customer's
        configuration restricts this substitution.
    """
    equivalences = load_functional_equivalences()
    customers = {c["customer_id"]: c for c in load_customers()}

    # Find the base equivalence
    base_confidence = 0.0
    for eq in equivalences:
        pair = {eq["canonical_id_a"], eq["canonical_id_b"]}
        if {canonical_id_source, canonical_id_substitute} == pair:
            base_confidence = eq["confidence"]
            overrides = eq.get("customer_compatibility_overrides", [])
            for o in overrides:
                if o.get("customer_id") == customer_id:
                    return o.get("override_confidence", 0.0)
            break

    if base_confidence == 0.0:
        return 0.0  # no known equivalence

    # Apply customer-specific config penalty if any
    customer = customers.get(customer_id, {})
    restricted = customer.get("substitution_restrictions", [])
    if canonical_id_substitute in restricted:
        return base_confidence * 0.3  # heavily penalize

    return base_confidence
```

**`references/equivalence_rules.md`** — Domain reference content for the LLM (1-2 pages of substitution rules in plain markdown).

**`references/customer_overrides.md`** — Customer-specific compatibility overrides (1 page).

Write unit tests in `tests/unit/test_skill_asset_equivalence.py` covering:
- Resolution from each source system
- Resolution from canonical
- Resolution failure for unknown identifier
- Equivalence lookup symmetric (A→B finds same as B→A)
- Customer config penalty applied correctly

### Step 3 — Build `sourcing-logistics` skill (Orchestrator)

Following the same template, create `src/orchestrator_agent/skills/sourcing-logistics/`.

**`SKILL.md`** describes:
- Three tools: `estimate_transit`, `calculate_sourcing_cost`, `identify_blockers`
- Workflow: take a candidate source location and destination, compute transit mode (ground/sea/air), cost, hours, blockers

**`scripts/tools.py`** implements:

```python
def estimate_transit(from_location: GeoPoint, to_location: GeoPoint, asset_size_class: str) -> dict:
    """Estimate transit mode, time, and cost between two locations.

    Returns dict with: transit_mode, transit_hours, estimated_cost_usd.
    """
    # Simple haversine distance + transit mode logic
    # < 200km: ground_transit, $200/km
    # 200-2000km: ground or short-haul air depending on asset size
    # > 2000km: cargo_charter, expensive

def calculate_sourcing_cost(option: SourcingOption) -> int:
    """Full cost including transit, certification, customs (if cross-border)."""

def identify_blockers(option: SourcingOption, customer_id: str) -> list[str]:
    """Surface any blockers (regulatory, customer config, certification)."""
```

**`references/transit_modes.md`** and **`references/cost_envelopes.md`** as markdown references.

Unit tests covering distance calculation, mode selection thresholds, cost computation, blocker identification.

### Step 4 — Build `enterprise-systems` skill (Orchestrator)

This is the abstraction layer over Maximo, SAP, FDP. In TASK-04 the real MCP servers replace the synthetic-data backing; for now, the skill's tools query the in-memory synthetic data.

Create `src/orchestrator_agent/skills/enterprise-systems/`.

**Tools:**
- `query_maximo_availability(canonical_id: str, region_filter: Optional[str] = None) -> list[dict]` — returns equipment locations
- `query_sap_workforce(basin: str, date_window: tuple[date, date]) -> dict` — workforce availability
- `query_fdp_customer_config(customer_id: str, asset_canonical_id: str) -> dict` — customer-specific compatibility
- `query_intouch_specs(asset_canonical_id: str) -> list[str]` — relevant technical document IDs

Backing synthetic data files needed:
- `data/maximo_inventory.json` — equipment instances by location
- `data/sap_workforce.json` — workforce by basin
- `data/fdp_configurations.json` — customer configs
- `data/intouch_index.json` — document index

Generate this data so the cargo-plane scenario works: at least one Tool X-V7 in Lagos repair shop, Tool X-V variants in Australia (Darwin), customer Gulf Petroleum accepts V7 substitution.

### Step 5 — Build `plan-evaluation` skill (Plan Evaluator)

Create `src/orchestrator_agent/plan_evaluator/skills/plan-evaluation/`.

The Plan Evaluator uses skills less than the Orchestrator (it's a focused LLM-as-Judge), but the scoring rubrics live in `references/`:

**`SKILL.md`** describes:
- Tool: `evaluate_plan` — takes a `SourcingPlan`, returns scores per criterion
- The 7 criteria with their weights
- Severity thresholds

**`scripts/tools.py`**:

```python
def evaluate_plan(plan: SourcingPlan) -> dict:
    """Deterministic pre-scoring for a SourcingPlan.

    Returns dict of partial scores. The LLM then combines these with its
    qualitative judgment and produces the final PlanEvaluation.
    """
    # Compute deterministic components:
    # - cost_optimality: if avoided_cost_usd > 0, score higher
    # - schedule_feasibility: actual transit time vs deadline window
    # - logistics_feasibility: no blockers in primary_option
    # ...
```

**`references/scoring_rubrics.md`** — Detailed rubric per criterion (the LLM reads this).

**`references/severity_thresholds.md`** — When to mark findings high/medium/low severity.

### Step 6 — Build `procurement-prerequisites` skill (Procurement Gate)

Create `src/procurement_approval_agent/skills/procurement-prerequisites/`.

**Tools:**
- `check_budget_threshold(plan: SourcingPlan, planner_authorization_tier: str) -> dict`
- `check_certification_chain(plan: SourcingPlan) -> dict`
- `check_regulatory_clearance(plan: SourcingPlan) -> dict`

These are deterministic checks. The agent's job is to call them, aggregate findings, and decide approve/reject.

**`references/authorization_tiers.md`** describes the authorization tiers (e.g. "OCC planners can approve up to $200K; senior planners up to $500K; anything above requires director").

**`references/regulatory_matrix.md`** describes cross-border, export control, and environmental clearance requirements for common routes.

### Step 7 — Build `forecast-rationale` skill (Forecast Review Agent)

Create `src/forecast_review_agent/skills/forecast-rationale/`.

**Tools:**
- `extract_rationale_tags(freeform_text: str) -> list[str]` — Gemini extracts from a list of structured tag candidates (the candidates live in references/)
- `compute_override_significance(override: ForecastOverride) -> float` — how significant is this override (0.0 to 1.0)
- `write_rationale_to_bigquery(rationale: ForecastRationale)` — stub for now; real implementation when BigQuery is wired

**`references/rationale_tags.md`** — The taxonomy of structured rationale tags (rig_count_decline, operator_delay, geopolitical, pricing_shift, customer_specific, etc.).

### Step 8 — Build `scheduling-probability` skill (Capacity Planning Agent)

Create `src/capacity_planning_agent/skills/scheduling-probability/`.

**Tools:**
- `get_start_date_distribution(basin: str, customer_id: str, asset_class: str) -> StartDateDistribution`
- `compute_optimal_buffer(distribution: StartDateDistribution, risk_tolerance: float) -> dict` — returns recommended buffer days, projected on-time rate
- `compute_fleet_utilization_impact(basin: str, buffer_days_delta: float) -> dict` — returns utilization uplift % and deferred CapEx

The synthetic substrate is `data/start_date_variance/{basin}.json` files from Step 1.

**`references/risk_tolerance_calibration.md`** — How risk tolerance maps to buffer percentiles.

### Step 9 — Wire skills into agent tool lists

For each agent, update `core/tools.py` to load and expose its skills via `SkillToolset`. Pattern (from the reference demo):

```python
import pathlib
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

def _load_skills(agent_dir: pathlib.Path) -> list:
    skills_dir = agent_dir / "skills"
    return [
        load_skill_from_dir(d)
        for d in sorted(skills_dir.iterdir())
        if d.is_dir() and not d.name.startswith("_") and (d / "SKILL.md").exists()
    ]

def get_tools() -> list:
    skills_dir = pathlib.Path(__file__).parent.parent / "skills"
    skills = _load_skills(skills_dir.parent)
    skill_toolset = SkillToolset(skills=skills)

    tools = [
        skill_toolset,
        PreloadMemoryTool(),
        # ... + Plan Evaluator AgentTool and Procurement Gate A2A as before
    ]
    return tools
```

### Step 10 — Expand each agent's `prompts.py`

Now that skills exist, replace the skeleton `WORKFLOW_PLACEHOLDER` in each agent with the real workflow that references skills by name. Pattern from reference:

```python
SKILLS = """\
# ADK Skills

Load skills ON DEMAND using `load_skill` before calling their tools.
Do NOT load all skills at once — only load when needed.

1. `asset-equivalence`: canonical resolution + functional equivalence reasoning.
2. `sourcing-logistics`: transit estimation, cost calc, blocker identification.
3. `enterprise-systems`: SAP, Maximo, FDP, InTouch queries.
"""

WORKFLOW = """\
# Workflow (STRICT — each step runs EXACTLY ONCE unless noted)

1. Parse the capacity gap query: requested asset, target location, deadline.
2. Load `asset-equivalence` skill. Call `resolve_canonical_asset` for the requested asset.
3. Load `enterprise-systems` skill. In parallel:
   - `query_maximo_availability(canonical_id, region_filter=<target_region>)`
   - `query_sap_workforce(...)`
   - `query_fdp_customer_config(...)`
4. If no direct asset is available in target region, call
   `find_functional_equivalents` and `score_equivalence_confidence` for each.
5. For each viable candidate, load `sourcing-logistics` skill and call
   `estimate_transit`, `calculate_sourcing_cost`, `identify_blockers`.
6. Construct candidate `SourcingPlan` objects. Use the cheapest viable option
   as `primary_option`; the unfiltered worst case (e.g. cargo charter from
   far source) as `naive_baseline`.
7. Pass the SourcingPlan to the Plan Evaluator (via AgentTool — automatic).
   If overall_score < 0.85, revise and re-score (max 2 retries).
8. Pass the approved SourcingPlan to the Procurement Gate (via A2A).
   If not approved, surface blockers and stop.
9. Return the final SourcingPlan with avoided_cost_usd populated.
"""
```

Update the `INSTRUCTION` builder to include the new sections.

### Step 11 — Realistic Plan Evaluator prompt

Replace the Plan Evaluator's `prompts.py` skeleton with a real prompt that produces graded scores. Use the reference Evaluator's prompt as a template (see `/tmp/next-26-keynotes/devkey/demo-2/src/planner_agent/evaluator/prompts.py` and `instruction.md`).

The prompt should:
1. Reference the `plan-evaluation` skill
2. Define the 7 criteria with weights
3. Specify the scoring rubric (0.0 to 1.0 scale, severity thresholds)
4. Require structured `PlanEvaluation` output

### Step 12 — Realistic Procurement Gate prompt

Same pattern. Reference the `procurement-prerequisites` skill, define prerequisite checks, require structured `ProcurementApproval`.

### Step 13 — Integration test: cargo-plane scenario

Write `tests/integration/test_cargo_plane_scenario.py`:

```python
async def test_cargo_plane_recommendation():
    """The hero scenario: Maria asks for Tool X in Luanda, gets Lagos sub-variant."""
    from src.orchestrator_agent import root_agent

    # Maria's prompt
    response = await root_agent.run_async(
        user_input=(
            "I need a Tool X variant on site in Luanda, Angola by Friday. "
            "Customer: Gulf Petroleum. What are my options?"
        ),
        session_id="test-cargo-plane",
        user_id="maria_chen",
    )

    plan = SourcingPlan.model_validate(response.output)

    # Assertions
    assert plan.primary_option.source_location.label == "Lagos, Nigeria"
    assert plan.primary_option.asset.canonical_id == "TX-007"  # the equivalent variant
    assert plan.primary_option.estimated_cost_usd < 60000      # ground transit, not air
    assert plan.naive_baseline is not None
    assert plan.naive_baseline.transit_mode == "cargo_charter"
    assert plan.naive_baseline.estimated_cost_usd > 350000
    assert plan.avoided_cost_usd > 300000
    assert plan.primary_option.customer_compatibility is True
    assert len(plan.primary_option.blockers) == 0
```

Run:
```bash
make deploy-all-agents
uv run pytest tests/integration/test_cargo_plane_scenario.py -v
```

The test should pass. If the agent isn't producing the expected output:
- Check the synthetic data — is Tool X-V7 in Lagos? Does Gulf Petroleum accept V7?
- Check the workflow prompt — is the agent loading skills in order?
- Look at Cloud Trace — what's the agent actually doing?

Iterate on prompts and synthetic data until the scenario works reliably.

### Step 14 — Commit

```bash
git add .
git commit -m "feat: build all 7 ADK skills with synthetic data backing (TASK-03)"
git push
```

---

## Acceptance criteria

- [ ] All seven skills exist with proper structure (`SKILL.md`, `scripts/tools.py`, `references/`)
- [ ] Each skill's `SKILL.md` has correct frontmatter and complete instructions
- [ ] Synthetic data files exist in `data/` and load via `synthetic_data.py`
- [ ] Unit tests for each skill's tools pass (test the deterministic logic, not LLM behavior)
- [ ] Each agent's `core/tools.py` wires its skills via `SkillToolset`
- [ ] Each agent's `core/prompts.py` has the real workflow referencing the skills
- [ ] `make deploy-all-agents` redeploys all agents with the new skills loaded
- [ ] `test_cargo_plane_scenario` integration test passes
- [ ] Plan Evaluator produces realistic graded scores (not always 0.91)
- [ ] Procurement Gate produces realistic approvals with cited blockers when applicable
- [ ] All code has `# DEMO NARRATION:` comments at key moments
- [ ] `ruff check` runs clean
- [ ] Commit pushed

---

## Common pitfalls

**Forgetting `metadata.adk_additional_tools` in SKILL.md.** Without this, the skill's tools won't be exposed when the skill is loaded. The reference demo's `gis-spatial-engineering/SKILL.md` shows the correct frontmatter pattern.

**Tool functions in scripts but not imported.** ADK's `SkillToolset` uses `additional_tools` to expose callables. If your tool isn't picked up, check that `scripts/tools.py` exports it and (in `tools.py` of the parent agent) it's loaded via `importlib.util` the way the reference demo does. See `next-26-keynotes/devkey/demo-1/planner_agent/tools.py::_load_additional_tools` for the pattern.

**Skill name with underscores instead of hyphens.** Convention from reference: skill directories use hyphens (`asset-equivalence`, not `asset_equivalence`). The `name` in frontmatter matches the directory name exactly.

**Synthetic data inconsistencies.** If your Tool X canonical record says it has SAP material number `MAT-67890` but `cross_system_aliases.json` has `MAT-12345` for the same canonical_id, queries will fail in subtle ways. Validate consistency across the data files with a quick script.

**LLM producing structured output that doesn't match the schema.** This is the #1 source of integration test failures. Inspect agent output, compare to the Pydantic schema, look for type mismatches (date strings vs datetime objects, optional fields with wrong defaults). The schemas in `src/schemas.py` are the contract; agents must produce conforming output.

**Skipping the iterative refinement loop.** The Orchestrator's prompt must include "if overall_score < 0.85, revise and re-score." Without this, the demo's "agent improves its plan" moment doesn't happen. Match the marathon demo's iteration pattern.

**Skill content too long.** SKILL.md files should be focused — every word the LLM reads costs tokens. The reference demos average 50-150 lines per SKILL.md. If yours is 500 lines, split or trim.

---

## References

- `next-26-keynotes/devkey/demo-1/planner_agent/skills/gis-spatial-engineering/` — Best skill structure reference
- `next-26-keynotes/devkey/demo-2/src/planner_agent/skills/route-planning/` — Skill in the multi-agent context
- `next-26-keynotes/devkey/demo-2/src/planner_agent/skills/plan-evaluation/` — Closest to our `plan-evaluation` skill
- `next-26-keynotes/devkey/demo-2/src/simulator_agent/skills/review-marathon-plan/` — Closest to our `procurement-prerequisites` skill
- ADK Skills documentation: `cloud.google.com/agent-builder/docs/adk/skills`

---

*When TASK-03 is complete, the demo runs end-to-end with real reasoning on synthetic data. Subsequent tasks will replace the synthetic backing with real MCP servers, Knowledge Catalog, and the Operations Canvas. Proceed to `TASK-04-mcp-servers.md` (to be issued when ready).*
