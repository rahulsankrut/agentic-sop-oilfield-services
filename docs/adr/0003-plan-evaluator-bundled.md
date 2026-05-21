# ADR 0003: Plan Evaluator bundled in-process via `AgentTool`

## Status

Accepted (TASK-02, 2026-05). Diverges from SPECS acceptance #5 which
called for "all five agents in Agent Registry with cryptographic Agent
Identity." Deviation noted inline in SPECS.md.

## Context

The reference solution describes **five agents**: Capacity Orchestrator,
Plan Evaluator, Procurement Approval, Forecast Review, Capacity
Planning. The earliest spec drafts assumed each is its own standalone
Reasoning Engine deployment, registered in Agent Registry, called
across the network.

Concretely: the Plan Evaluator scores SourcingPlans on 7 weighted
criteria. The Orchestrator invokes it every time a candidate plan
needs review — at minimum once per workflow run, up to 3 times if
revise loops are needed. Each invocation = network roundtrip if
Plan Evaluator is its own Reasoning Engine.

Three factors pushed against the standalone-deploy shape:

1. **Latency.** The Orchestrator workflow is the demo's headline
   visual — Maria types a prompt, the canvas paints arcs as the agent
   reasons. Adding 2-4 seconds of cross-process latency per
   plan_evaluator call drags the user-perceived workflow time from
   ~90s into multi-minute territory.
2. **Reference repo precedent.** The marathon-planner reference
   (`next-26-keynotes/devkey/demo-2`) bundles its evaluator the same
   way — `AgentTool(agent=plan_evaluator_agent)` wired directly into
   the planner's tool list, in-process. SPECS.md §Architectural
   principles names this reference as the source of truth for ADK
   patterns.
3. **No customer-facing surface needs.** Plan Evaluator doesn't
   receive A2A calls from sibling agents or from Gemini Enterprise
   App. Procurement Approval does (it's the customer-facing A2A demo
   of the protocol). Forecast Review and Capacity Planning are
   reached from Gemini Enterprise App. Plan Evaluator's only caller
   is the Orchestrator.

## Decision

Bundle the Plan Evaluator inside the Orchestrator's Reasoning Engine.
The Orchestrator's `core/tools.py` registers it via
`AgentTool(agent=plan_evaluator_agent)`. No standalone deployment, no
Agent Registry entry, no A2A wrap.

The Plan Evaluator agent code lives at
`agents/orchestrator_agent/plan_evaluator/` — a sibling package
inside the orchestrator's tree, not a top-level `agents/<x>` package.
Its skills (`plan-evaluation`) load via the orchestrator's
`SkillToolset` machinery.

Agent count exposed externally: **4** standalone (Orchestrator,
Procurement, Forecast, Capacity), **+1 bundled** (Plan Evaluator).

## Consequences

**Positive**

- Plan Evaluator calls are in-process function invocations, not RPC.
  No network latency, no auth header rebuild, no streaming serialize/
  deserialize cycle. ~100ms vs ~2-3s per call.
- Iteration loop (revise → evaluator → revise → evaluator) stays
  cheap. The current cargo-plane workflow exhausts 3 evaluations
  inside ~140s end-to-end.
- One fewer Reasoning Engine to provision, monitor, and rotate.

**Negative**

- Agent Registry shows 4 agents, not 5. Visible deviation from
  SPECS §Acceptance criteria #5; the workaround is the inline
  deviation note in SPECS.md plus this ADR.
- The "5 agents" demo narrative needs a small caveat slide. The
  Plan Evaluator is real, it just doesn't appear in the registry
  because it's bundled.
- If a future customer build wants to swap the Plan Evaluator's
  model independently of the Orchestrator (different latency or
  cost SLO), the bundled deploy makes that harder. The fix is
  cheap (carve it out into its own deploy then) but explicit.

## Related work

- `agents/orchestrator_agent/plan_evaluator/agent.py` — agent definition.
- `agents/orchestrator_agent/tools.py:create_plan_evaluator_tool` —
  AgentTool wiring.
- SPECS.md §"Acceptance criteria for v1 complete" item 5 — deviation
  note inline.
- Reference: `next-26-keynotes/devkey/demo-2/src/planner_agent/core/
  tools.py` for the same pattern.
