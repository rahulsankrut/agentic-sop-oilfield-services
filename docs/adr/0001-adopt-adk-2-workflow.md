# ADR 0001: Adopt ADK 2.0 Workflow for the Capacity Orchestrator

## Status

Accepted (TASK-04, 2026-05-19).

## Context

The Capacity Orchestrator in ADK 1.x was an `LlmAgent` with a 9-step
`static_instruction` (see `core/agent_v1_llmagent.py.bak`). It worked, but it
had three issues:

1. The LLM had latitude to skip or re-order steps despite "MUST execute in
   order" framing. Cloud Trace inspections from TASK-03 showed the model
   occasionally invoking `query_intouch_specs` before
   `resolve_canonical_asset`, breaking the canonical-id-first invariant.
2. Demo narration reduced to "the LLM reasons through these steps," which is
   less compelling for a Next '26 keynote audience than showing an explicit
   graph executing in Cloud Trace.
3. Procurement-audit defensibility is harder to argue for a monolithic
   prompt-based agent. Tier-one oilfield services buyers (SLB, Halliburton,
   Baker Hughes) have audit and regulatory exposure; their procurement orgs
   want to see deterministic flow with AI at decision points, not "an LLM
   reasons through it."

ADK 2.0 Beta introduces `Workflow` agents: explicit graphs of nodes where
each node is either an LLM agent, a deterministic function, a tool call, or
a sub-workflow. This pattern matches how operations workflows are already
modeled in oilfield services (process flow diagrams, decision trees) and
aligns with Google's narrative for Gemini Enterprise Agent Platform at
Next '26: control, predictability, reliability.

## Decision

The Capacity Orchestrator is refactored from `LlmAgent` to `Workflow`. The
new graph (see `src/orchestrator_agent/core/agent.py`):

```
START
  → parse_capacity_gap_request           (function)
  → resolve_canonical_asset_node         (function)
  → parallel_system_queries              (async function — Maximo/SAP/FDP/InTouch)
  → evaluate_direct_availability         (function)
  → route_on_availability                (router)
     ├── DIRECT_AVAILABLE   → build_direct_plan         (function)
     └── NEEDS_EQUIVALENCE → equivalence_lookup_agent   (LLM, output_schema)
                              → build_equivalent_plan   (function)
  → sourcing_logistics_agent             (LLM, output_schema=SourcingPlan)
  → plan_evaluator                       (AgentTool — existing LlmAgent)
  → route_on_evaluation_score            (router)
     ├── ACCEPTED   → route_on_procurement_threshold
     ├── REVISE     → revise_plan_agent (LLM) ↩ plan_evaluator (loop, cap=2)
     └── EXHAUSTED  → route_on_procurement_threshold
  → route_on_procurement_threshold       (router)
     ├── AUTO_APPROVE      → finalize_sourcing_plan
     └── REQUIRES_APPROVAL → procurement_approval (A2A) → finalize_sourcing_plan
  → finalize_sourcing_plan               (function)
  → END
```

LLM nodes are scoped to specific decisions:
- `equivalence_lookup_agent` → pick the best functional substitute
- `sourcing_logistics_agent` → refine the plan with logistics judgment
- `revise_plan_agent` → improve a low-scoring plan based on findings

All routing, parallel dispatch, threshold checks, and structured-data shaping
is deterministic Python in the function nodes / routers. Policy constants
(`SCORE_THRESHOLD=0.85`, `MAX_REVISION_ITERATIONS=2`,
`PROCUREMENT_USD_THRESHOLD=500_000`) live in `nodes/routers.py` next to the
branching code, so audit can review them directly.

Other agents stay as `LlmAgent`s for now:
- **Plan Evaluator** — LLM-as-Judge over 7 weighted criteria; single-decision.
- **Procurement Approval Agent** — single-purpose, called via A2A.
- **Forecast Review Agent** — conversational extraction; LlmAgent is natural.
- **Capacity Planning Agent** — will be refactored to Workflow in a future
  task (multi-week scheduling + deterministic optimization + AI sensitivity
  analysis is a natural fit; out of scope for TASK-04).

## Consequences

### Positive

- **Cloud Trace shows the graph executing.** Each node is a distinct span;
  the four parallel system queries fan out and fan in as parallel spans
  inside the `parallel_system_queries` parent. The trace IS the demo's
  narrative spine — graph in code, graph in trace, graph on the slide deck.
- **LLM calls are isolated to decision points.** Three LLM nodes vs. the
  v1 monolithic prompt; token usage drops and the deterministic steps
  (parsing, joins, routers) become microsecond-fast Python.
- **Procurement audit reviews graph structure independently of prompts.**
  Policy thresholds live in code with the routing they govern, not
  embedded in instructions the LLM might re-interpret.
- **Future iterations add nodes, not prompts.** Adding e.g. a regulatory
  compliance check becomes "insert a node between X and Y" — no risk of
  the LLM dropping a step from a longer prompt.
- **Demo narration is graph-shaped.** Every node has a `# DEMO NARRATION:`
  comment with the demoer's line; the rehearsal script writes itself.

### Negative

- **ADK 2.0 Beta carries breaking-change risk.** We pin to `>=2.0.0b1,<2.1`
  in `pyproject.toml`; tighten to an exact Beta release once a stable
  Beta version is identified.
- **Workflow + Live Streaming are not compatible** per the ADK 2.0 docs.
  We do not use Live Streaming in this build, so this is acceptable.
- **Some third-party integrations may not be compatible.** Our integration
  set (MCP, A2A, Memory Bank, Skills, GlobalGemini) is platform-native;
  TASK-04 step 2 verifies the cargo-plane integration test still passes
  after the upgrade (out of scope for this ADR — covered in the task).
- **The Event API in ADK 2.0 graph workflows uses `Event(output=...)`,
  not `Event(payload=...)`** as the original TASK-04 spec drafted.
  `output` is the standard data-passing parameter; `route` is the
  routing key; `message` is the human-readable summary. The nodes in
  this commit use `output=...`. See `nodes/parse_request.py` for the
  canonical shape.

## Migration notes

- `core/agent_v1_llmagent.py.bak` preserves the LlmAgent shape for diff
  reference. Once the Workflow has shipped through the integration tests
  (TASK-04 step 2 + step 8, run by main thread), this file is removed.
- The v1 `core/prompts.py` 9-step instruction is collapsed into three
  focused per-node instructions in the same file. Each node has ONE
  decision; no monolithic "Orchestrator instruction" anymore.
- `core/tools.py` is preserved verbatim — the Workflow imports
  `create_plan_evaluator_tool` and `create_procurement_approval_tool`
  from it. The `get_tools()` builder (which assembled the full LlmAgent
  tool list) is unused by the Workflow but kept for the .bak file.
- New shared helper `src/utils/skill_imports.py` exposes each skill's
  Python tool functions as direct callables so the deterministic function
  nodes can call them without going through `FunctionTool` /
  `SkillToolset`. The LlmAgent path (Plan Evaluator) still uses the
  existing `src/utils/skill_tools.py` `FunctionTool` wrappers.
- New shared schemas in `src/schemas.py`:
  - `CapacityGapRequest` — structured form of the parsed query
  - `SystemQueryResults` — aggregated MCP query payloads
  - `EquivalentAssetCandidate` — structured output of `equivalence_lookup`

## References

- ADK 2.0 home: https://adk.dev/2.0/
- Graph workflows: https://adk.dev/graphs/
- Graph routes: https://adk.dev/graphs/routes/
- Data handling: https://adk.dev/graphs/data-handling/
- Workflow samples: https://github.com/google/adk-python/tree/v2/contributing/workflow_samples
- TASK-04 spec: `tasks/TASK-04-adk2-workflow-refactor.md`
- SPECS.md §Architectural principle 5 — Workflow agents for deterministic flow
