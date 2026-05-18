# Adapting the Next '26 Multi-Agent Keynote Demo
## For End-to-End Service Capacity Orchestration

*A scaffold-and-adapt plan for the customer demo.*

---

## What the keynote demo actually is

The Next '26 developer keynote shipped a **marathon planning multi-agent system** as its reference application, with the full source code published at `github.com/GoogleCloudPlatform/next-26-keynotes`. There are five demos under `devkey/`:

| Demo | What it shows | Useful for us |
|---|---|---|
| `demo-1` | Single ADK agent with skills + MCP tools (single-agent foundation) | The single-agent baseline. Start here to understand the scaffold. |
| `demo-2` | **Multi-agent system: Planner + Evaluator + Simulator, communicating via A2A** | **This is the one we adapt.** It is the full keynote demo. |
| `enhancing-agents-with-memory` | VertexAI Memory Bank + AlloyDB MCP + Document AI ingestion of unstructured PDFs | The pattern for ingesting InTouch documents into a queryable rules layer. |
| `debugging-agents` | Agent Runtime, Cloud Trace, Gemini Cloud Assist, ADK EventCompaction | Production-grade observability story for the customer pitch. |
| `intent-to-infrastructure` | Natural-language to Terraform infrastructure | Optional — for the "platform" story arc, not for the agent itself. |

The narrative arc across the keynote: build an agent → make it collaborate → give it memory → debug at scale → declare infrastructure → secure it. For our purposes, demo-2 is the spine and the memory demo gives us the InTouch ingestion pattern.

### Demo-2 architecture in one diagram

```
            ┌─────────────────────────┐
            │ Marathon Planner Agent  │  (Lead Architect, Cloud Run)
            │ Gemini 3 Flash + Skills │  Iterates plans until score ≥ 0.85
            └────────┬────────────────┘
                     │
       ┌─────────────┴─────────────┐
       │                           │
       │ AgentTool (in-process)    │ A2A Protocol (over HTTPS)
       │                           │
       ▼                           ▼
┌────────────────┐         ┌──────────────────────┐
│ Evaluator      │         │ Simulation Controller│
│ Agent          │         │ Agent                │
│ LLM-as-Judge   │         │ Approval Gate        │
│ 7 weighted     │         │ Prerequisite check   │
│ criteria       │         │ Returns SimulationApproval
│ (Bundled)      │         │ (Agent Engine)       │
└────────────────┘         └──────────────────────┘
```

Key technical patterns:

- **ADK Skills** as the unit of domain knowledge — each skill is a directory with `SKILL.md` (frontmatter + instructions), `scripts/tools.py` (callable functions), `references/` (markdown reference content). The agent uses `load_skill_from_dir` and `SkillToolset` to expose them lazily — tools only become available *after* the LLM calls `load_skill("skill-name")`.
- **PromptBuilder** for prompt composition — an immutable `OrderedDict`-backed class with `role`, `rules`, `skills`, `tools`, `workflow` sections, joined with double newlines via `build()`.
- **A2A protocol** via `RemoteA2aAgent` for cross-deployment agent calls (Planner → Simulator). The remote agent is wrapped in an `AgentTool` so the planner sees it as just another callable tool.
- **AgentTool** for in-process collaboration (Planner → Evaluator, bundled together) — same interface as A2A, no network hop.
- **Structured outputs** via Pydantic schemas attached to `LlmAgent(output_schema=...)`. The Evaluator returns `EvaluationResult`; the Simulator returns `SimulationApproval`.
- **Iterative refinement** — Planner generates plan → Evaluator scores → if score < 0.85, Planner revises → loop. The threshold is hard-coded in the workflow.
- **`PreloadMemoryTool`** + `auto_save_memories` `after_agent_callback` — cross-session memory via VertexAI Memory Bank.
- **`ThinkingConfig`** with `thinking_budget` — Gemini 3 reasoning depth control per agent.
- **Standardized directory structure per agent**:
  ```
  src/{agent_name}/
    core/        # agent.py, config.py, prompts.py, schemas.py, tools.py, auth.py
    skills/      # SKILL.md + references/ + scripts/  (one dir per skill)
    runtime/     # agent_card.py (A2A discovery), agent_executor.py, deploy.py, local_server.py
    services/    # memory_manager.py, session_manager.py
  ```
- **Deployment topology**: Terraform for infrastructure (buckets, IAM, Artifact Registry, Cloud Run services), Cloud Build for Planner container, Agent Engine for Evaluator and Simulator. A single `Makefile` ties it all together with targets: `setup`, `auth`, `test`, `deploy`, `demo-solo`, `demo-full`, `teardown`.

### What demos `solo` vs `full_team` actually show

The same Planner runs in two modes via different Cloud Run endpoints:

- **`solo`**: Planner + Evaluator. Iterative quality improvement loop. Score ≥ 0.85 to ship.
- **`full_team`**: Planner + Evaluator + Simulation Controller. After evaluation passes, the plan goes to the Simulator for a formal approval gate. This is the production-grade version.

The two-mode pattern is genuinely useful for customer demos — you show the "quality loop" first (clean, fast, impressive), then show the "approval gate" (production-realism, governance, audit trail).

---

## Why this scaffold maps cleanly to our use case

Our use case — end-to-end service capacity orchestration for the customer — has the same shape as marathon planning:

| Marathon planning | Service capacity orchestration |
|---|---|
| User asks for a marathon plan | OCC planner asks for capacity gap resolution |
| Planner Agent designs route, logistics, safety | Orchestrator Agent designs sourcing plan, deployment logistics, compatibility check |
| Calls Evaluator for quality scoring | Calls Plan Evaluator for feasibility/cost/safety scoring |
| Calls Simulator for "ready to run on race day" approval | Calls Procurement Approval Agent for "ready to commit logistics dollars" approval |
| Skills: GIS, race-director, mapping | Skills: asset-equivalence, operations-director, enterprise-systems |
| Maps MCP for real-world geography | Maximo / SAP / FDP MCP for enterprise systems |
| Memory Bank for marathon preferences | Memory Bank per OCC planner profile |
| Score threshold (0.85) for plan acceptance | Score threshold for sourcing plan acceptance |
| Two demo modes (solo, full_team) | Two demo modes (quality loop, approval flow) |

The architecture is essentially identical. What changes is domain content — skills, schemas, scoring criteria, source-system connectors. The runtime, the orchestration pattern, the A2A wiring, the memory integration, the deployment topology, the demo scenarios all carry over verbatim.

This is exactly the right scaffold for the customer demo. We are not building from scratch; we are forking a Google-published reference architecture and re-skinning it with domain content.

---

## What to fork, what to change, what to add

### Recommended fork strategy

Fork the entire `devkey/demo-2` directory as the starting point. Preserve:

- `pyproject.toml`, `Makefile`, `cloudbuild.yaml`, `terraform/`, `demo/test_endpoints.py`
- `src/_agent_template/` — the canonical agent shape
- `src/utils/`, `src/config.py`, `src/schemas.py`
- All `runtime/` modules per agent (agent_card.py, agent_executor.py, deploy.py, local_server.py)
- All `services/` modules per agent (memory_manager.py, session_manager.py)
- The `PromptBuilder` utility class
- The `SkillToolset` integration pattern
- The A2A wiring in `tools.py`

These are the parts that are domain-agnostic. They give us the scaffolding for free.

### What changes (domain content)

| File | Marathon (original) | Service Capacity (ours) |
|---|---|---|
| `src/planner_agent/` | Marathon Planner | **Capacity Orchestrator Agent** |
| `src/planner_agent/core/prompts.py` | Marathon planning instruction | Capacity gap resolution instruction |
| `src/planner_agent/core/schemas.py` | `MarathonPlan` Pydantic model | `SourcingPlan` Pydantic model |
| `src/planner_agent/core/config.py` | Marathon model + name | Orchestrator config |
| `src/planner_agent/skills/` | `route-planning`, `plan-evaluation` | **`asset-equivalence`, `sourcing-logistics`** |
| `src/planner_agent/evaluator/` (bundled) | 7-criterion marathon eval | 7-criterion sourcing eval |
| `src/planner_agent/evaluator/schemas.py` | `EvaluationResult` for marathon | `RiskAssessment` for sourcing |
| `src/simulator_agent/` | Simulation Controller | **Procurement Approval Agent** |
| `src/simulator_agent/skills/review-marathon-plan/` | Marathon prerequisite check | `review-sourcing-plan` (procurement check) |
| `demo/scenarios.py` | Marathon prompts | Capacity gap scenarios |
| `terraform/*.tf` | Cloud Run for Marathon Planner | Cloud Run for Orchestrator |

### What needs to be added (not in the original)

These are the customer-specific pieces:

1. **MCP servers for source systems** — the marathon demo only has Maps MCP. We need MCP servers (or mocked equivalents for the demo) for:
   - **Maximo MCP** — equipment status, location, availability
   - **SAP MCP** — M&S inventory, workforce
   - **FDP MCP** — historical customer configurations
   - **InTouch retrieval** — via Knowledge Catalog + Smart Storage (or for demo speed, an AlloyDB MCP using the memory demo's pattern)

   For the Gate 2 demo, mock these with synthetic data exposed via MCP. The architecture is identical; the data behind is synthetic.

2. **Knowledge Catalog integration** — exposed as MCP for entity grounding. The marathon demo uses an in-memory `network.json` for the road graph. We use Knowledge Catalog as the canonical entity layer. For the Gate 2 demo, this can be a curated set of canonical-entity records in BigQuery exposed via MCP.

3. **A canonical asset taxonomy** — synthetic but realistic: 50-100 canonical tool entries with cross-system aliases (e.g., "Tool-X" in Maximo, "TX-A-Variant" in FDP, "TX_VAR_A" in SAP, all resolving to canonical `canonical_asset_id=TX-001`). Plus 5-10 `functional_equivalence` relationships (e.g., `TX-001` ≈ `TX-007` per spec §3.2).

4. **A2UI rendering** (optional but high-impact) — the keynote also used A2UI (`A01DQ8_xy7Q` showed this) where the agent returns a declarative UI JSON instead of text. For our demo, the agent could return a structured "sourcing recommendation card" with the equivalent asset, location, savings, and reasoning — rendered natively in the frontend. Worth considering for the executive demo moment.

5. **The cargo-plane scenario** — explicit demo scenario added to `demo/scenarios.py`.

---

## The skills to build (concrete SKILL.md outlines)

The skills are where the domain logic lives. Here's what each one should contain. Each gets a directory under `src/{agent}_agent/skills/`.

### `asset-equivalence` (under Orchestrator Agent)

```yaml
---
name: asset-equivalence
description:
  Expert reasoning over canonical asset taxonomy to identify functionally equivalent
  equipment variants. Queries Knowledge Catalog for canonical entities and traverses
  functional_equivalence relationships. Returns ranked candidates with confidence scores.
metadata:
  adk_additional_tools:
    - resolve_canonical_asset
    - find_functional_equivalents
    - score_equivalence_confidence
---
```

Tools:
- `resolve_canonical_asset(local_name, source_system)` — given "Tool X Variant A" from Maximo, return canonical entity ID
- `find_functional_equivalents(canonical_asset_id)` — return list of equivalent sub-variants from Knowledge Catalog
- `score_equivalence_confidence(asset_a, asset_b, customer_config)` — score how confident we are that asset B can substitute for asset A in customer's deployment

References:
- `references/equivalence_rules.md` — engineering rules for when sub-variants are interchangeable
- `references/customer_configurations.md` — common customer-specific compatibility requirements

### `sourcing-logistics` (under Orchestrator Agent)

```yaml
---
name: sourcing-logistics
description:
  Plans the physical logistics of sourcing equipment from inventory to deployment site,
  including transit time estimation, cost calculation, and route optimization.
metadata:
  adk_additional_tools:
    - estimate_transit
    - calculate_sourcing_cost
    - identify_blockers
---
```

Tools:
- `estimate_transit(from_location, to_location, asset_size_class)` — time + cost envelope for moving equipment between locations
- `calculate_sourcing_cost(option)` — full cost calculation including transit, repair, certification, workforce dispatch
- `identify_blockers(sourcing_plan, customer_config)` — surface any blockers (customer cert requirement, regulatory clearance, etc.)

References:
- `references/transit_modes.md` — air/sea/road tradeoffs for equipment categories
- `references/cost_envelopes.md` — typical cost ranges by route and asset class

### `enterprise-systems` (under Orchestrator Agent — the MCP wrapper skill)

```yaml
---
name: enterprise-systems
description:
  Provides standardized queries against the customer's enterprise systems
  (Maximo, SAP, FDP, InTouch) via MCP. All calls return canonical-asset-grounded
  results — the asset taxonomy resolution happens upstream in Knowledge Catalog.
metadata:
  adk_additional_tools:
    - query_maximo_availability
    - query_sap_workforce
    - query_fdp_customer_config
    - query_intouch_specs
---
```

Tools wrap the MCP servers — they're thin Python functions that delegate to MCP and return Pydantic-typed results.

### `plan-evaluation` (under Evaluator Agent)

```yaml
---
name: plan-evaluation
description:
  Evaluates sourcing plans across 7 weighted criteria using LLM-as-Judge plus
  deterministic financial checks. Returns RiskAssessment with score, severity,
  blockers, and revision recommendations.
---
```

The 7 criteria for oilfield services sourcing:

| Criterion | Weight | What it checks |
|---|---|---|
| `safety_compliance` | 0.20 | Equipment certifications, customer site safety requirements |
| `customer_compatibility` | 0.20 | Customer-specific config requirements satisfied |
| `logistics_feasibility` | 0.15 | Transit window achievable, workforce available |
| `cost_optimality` | 0.15 | Sourcing cost reasonable vs alternatives |
| `equivalence_confidence` | 0.10 | Confidence that the functional equivalent is actually equivalent |
| `regulatory_compliance` | 0.10 | Cross-border, export control, environmental clearances |
| `schedule_feasibility` | 0.10 | Realistic vs declared customer start date |

References:
- `references/scoring_rubrics.md` — detailed rubric per criterion
- `references/severity_thresholds.md` — when to mark a plan as high/medium/low severity
- `references/customer_calibration.md` — customer-specific weight overrides (e.g., some customers prioritize cost, others safety)

### `review-sourcing-plan` (under Procurement Approval Agent)

```yaml
---
name: review-sourcing-plan
description:
  Procurement readiness check — fast, deterministic verification that a sourcing
  plan has all required fields, signatures, certifications, and financial
  thresholds to commit logistics dollars. Not a quality check — a prerequisite check.
---
```

The procurement gate is fast and deterministic, like the marathon Simulator. It does not score quality — it verifies that the plan has everything needed for procurement to act on it: budget threshold, customer authorization, certification check, regulatory clearance flag, etc.

---

## The cargo-plane demo scenario

This goes in `demo/scenarios.py` alongside or in place of the marathon scenarios:

```python
_CAPACITY_GAP_PROMPT = (
    "I need a Tool X variant on site in Luanda by Friday. "
    "Current Maximo shows no Tool X available in West Africa. "
    "What are my options?"
)

SCENARIOS = {
    "solo": Scenario(
        name="solo",
        description=(
            "Capacity Orchestrator runs with Plan Evaluator only. "
            "Surfaces sourcing options, scores them, iterates."
        ),
        demo_prompt=_CAPACITY_GAP_PROMPT,
        enabled_agents=["plan_evaluator"],
        expected_behavior=(
            "1. Orchestrator queries Maximo: no Tool X in West Africa.\n"
            "2. Loads asset-equivalence skill, queries Knowledge Catalog.\n"
            "3. Identifies Tool X-V7 as functionally equivalent (per spec §3.2).\n"
            "4. Queries Maximo for Tool X-V7: one in Lagos repair shop, 50 km from site.\n"
            "5. Queries SAP for workforce: clear.\n"
            "6. Queries FDP for customer config: V7 acceptable.\n"
            "7. Sends sourcing plan to Plan Evaluator.\n"
            "8. Plan Evaluator returns score 0.88 with low-severity findings.\n"
            "9. Orchestrator presents recommendation: ~$380K savings vs cargo charter."
        ),
        endpoint_suffix="-solo",
    ),
    "full_team": Scenario(
        name="full_team",
        description=(
            "Full flow: Orchestrator + Plan Evaluator + Procurement Approval Agent. "
            "Sourcing plan must pass both quality and procurement readiness."
        ),
        demo_prompt=_CAPACITY_GAP_PROMPT,
        enabled_agents=["plan_evaluator", "procurement_approval"],
        expected_behavior=(
            "1-8. Same as solo through Plan Evaluator approval.\n"
            "9. Plan sent to Procurement Approval Agent via A2A.\n"
            "10. Gate verifies: budget threshold (under $X), customer authorization,\n"
            "    certification chain, regulatory clearance.\n"
            "11. Returns SourcingApproval with approved=true and audit trail.\n"
            "12. Orchestrator presents final recommendation with full reasoning,\n"
            "    risk scores, and procurement sign-off ready for dispatch."
        ),
        endpoint_suffix="-full",
    ),
}
```

This maps the cargo-plane story directly onto the keynote's demo runner — same Make targets (`make demo-solo`, `make demo-full`), same A2A wiring, same observability traces.

---

## What this delivers for the platform pitch

When the customer sees this demo, they see — in one running system — every component of the Gemini Enterprise Agent Platform working together:

- **ADK** building the agents (`LlmAgent`, `SkillToolset`, structured outputs)
- **Agent Runtime / Agent Engine** hosting them (Cloud Run for Orchestrator, Agent Engine for Procurement Approval Agent)
- **A2A protocol** as the inter-agent comms layer (open standard, not a Google lock-in)
- **Skills** as the unit of domain knowledge (and where the customer extends the system later)
- **Memory Bank** for per-planner context that persists across sessions
- **Knowledge Catalog** grounding every agent in the canonical asset taxonomy (this is what makes "Tool X Variant A" and "TX_VAR_A" resolve correctly)
- **MCP** as the connector pattern to source systems (Maximo, SAP, FDP)
- **Cloud Trace + Agent Observability** providing the audit trail for procurement
- **Terraform + Cloud Build** for the deployment story (the IaC reflex IT will want to see)
- **Gemini 3 Flash / Pro** as the underlying model (with Model Garden alternatives available)

That is the full platform vision running on a single use case — exactly what the engagement strategy in the main brief calls for. The customer is not told "Google has a platform"; they are shown the platform delivering their use case.

---

## Recommended build sequence (3-4 weeks)

This is roughly the Gate 2 timeline from the main engagement brief.

**Week 1 — Fork and re-skin:**
- Fork `next-26-keynotes/devkey/demo-2` into a new repo
- Rename `planner_agent` → `orchestrator_agent`, `simulator_agent` → `procurement_approval_agent`, evaluator references
- Update `pyproject.toml`, agent names, descriptions, agent cards
- Replace marathon prompts with capacity-gap prompts (placeholder content fine)
- Make sure the bare scaffold deploys and the smoke-test passes (`make test`, `make demo-solo` with the placeholder content)

**Week 2 — Build domain skills:**
- Create the four skills: `asset-equivalence`, `sourcing-logistics`, `enterprise-systems`, `plan-evaluation`, `review-sourcing-plan`
- Each gets a `SKILL.md` + `scripts/tools.py` + `references/` markdown content
- Tools start as in-memory implementations against synthetic data (network.json analog = synthetic asset catalog JSON)
- Memory Profiles defined for 2-3 representative OCC planner personas

**Week 3 — MCP and Knowledge Catalog wiring:**
- Stand up mock MCP servers for Maximo / SAP / FDP (Cloud Run services exposing canned responses, behind the same MCP interface)
- Wire Knowledge Catalog as the canonical entity layer (or for speed, a BigQuery table exposed via MCP)
- Ingest synthetic InTouch documents through Smart Storage + Object Context API
- Validate the cargo-plane scenario runs end-to-end with realistic-looking data

**Week 4 — Demo polish and observability:**
- Wire Cloud Trace, Agent Observability — the reasoning trace must be visible in the demo
- Connect to Gemini Enterprise app surface — Agent Inbox view, agent registry view
- Optional: A2UI rendering for the recommendation card
- Build the mockup tiles for the other three breakpoints (forecast review, Capacity Planning Agent, naming reconciliation) — they live as Gemini Enterprise app tiles that show "demo not enabled" but anchor the platform vision
- Dry-run the demo flow end-to-end; tighten the storyboard

---

## What I'd recommend you do this week

1. **Clone the repo** locally and run `make test` + `make demo-solo` on the marathon demo as-is. Spend an afternoon. You'll have a much sharper sense of what the scaffold gives us once you've seen it run.

2. **Pick the synthetic dataset shape** for the cargo-plane scenario. Decide: how many canonical assets in the catalog, how many functional-equivalence relationships, which two locations are in the demo (Luanda + Lagos? Substitute customer-realistic city pair?), what cost envelopes feel real. This decision drives a lot of the demo credibility — too synthetic and it looks like toy data; too elaborate and Week 2 stretches.

3. **Decide on the partner / specialist staffing** for Weeks 2-4. The scaffold lets a Google specialist + a data engineer cover this in 4 weeks. Without that, plan for 6 weeks.

4. **Validate with the customer's technical champion** that the cargo-plane scenario is *their* most vivid pain point. If they have a different "memorable disaster story," lead with that — but the scaffold accommodates it without architectural change.

---

## Open questions worth flagging

- **Model choice**: Demo-2 uses Gemini 3 Flash Preview throughout for speed. For a customer demo, the Orchestrator should probably run Gemini 3.1 Pro for reasoning depth, with Flash on the Procurement Approval Agent. Decide once you've benchmarked locally.
- **MCP servers**: Are we mocking all four source systems for the demo, or building one real connector (against an SAP test environment if the customer has one available)? Mocking is faster; one real connector is more credible.
- **Knowledge Catalog vs. simpler entity layer**: For the demo, a BigQuery table with canonical-entity records + a thin MCP wrapper is faster than full Knowledge Catalog deployment. But Knowledge Catalog is the differentiator we want to showcase. Probably do both — the entity logic in a BigQuery table for speed, with the demo narration saying "in production, this is Knowledge Catalog."
- **A2UI**: high-impact but late-preview. Decide whether to invest in it for this demo or keep the output as structured JSON rendered by a simple Streamlit / Next.js frontend.
- **GitHub vs. customer's own repo**: where does the demo code live? If we want this to become a starting point for the Gate 3 paid POC, it should probably live in a customer-accessible GitHub Enterprise space from Day 1, not in your personal GitHub.

---

## A note on Anthropic / Claude in this scaffold

Worth knowing: the keynote explicitly showcased Claude Opus 4.7 in Model Garden alongside the four Google models (Gemini 3.1 Pro, Gemini 3 Flash Image, Lyria 3 Pro, Veo 3.1 Lite). The ADK is model-agnostic — `LlmAgent(model=...)` takes Gemini, Claude, Llama, or any Model Garden model. If the customer specifically asks about "are we locked into Gemini?", the answer is concretely no, and demo-2's architecture would run on Claude with a one-line change.

Useful in the room. Not the headline.

---

*End of adaptation plan.*
