"""Routing functions for the Capacity Orchestrator Workflow.

A router returns ``Event(route="...", output=...)`` — the route key dispatches
to the next node via the workflow's edge dictionary, the payload is forwarded
to that node as its ``node_input``.

Three routers:
- ``route_on_availability``: direct hit vs. equivalence search
- ``route_on_evaluation_score``: accept / revise / exhausted (cap at 2 retries)
- ``route_on_procurement_threshold``: auto-approve under $500K vs. gate above
"""

from __future__ import annotations

from google.adk import Context, Event

from ..events.canvas_events import RouterDecisionEvent
from ..events.emit import emit

# Route keys live in module scope so the agent.py edge dict and the routers
# stay in sync without string-literal drift.
DIRECT_AVAILABLE = "DIRECT_AVAILABLE"
NEEDS_EQUIVALENCE = "NEEDS_EQUIVALENCE"

# PROCEED covers both ACCEPTED (score >= threshold) and EXHAUSTED (out of
# retries) — ADK 2.0 Workflow rejects multiple route keys pointing at the
# same destination node ("duplicate edge"). The semantic distinction is
# preserved via the Event.message + the iteration_count + accepted_reason
# fields in the forwarded payload, so the Cloud Trace still shows whether
# we accepted or exhausted; we just don't fork the graph for it.
PROCEED = "PROCEED"
REVISE = "REVISE"
# Legacy aliases retained for backward-compatibility with any test that
# imports them. New code should use PROCEED.
ACCEPTED = PROCEED
EXHAUSTED = PROCEED

AUTO_APPROVE = "AUTO_APPROVE"
REQUIRES_APPROVAL = "REQUIRES_APPROVAL"

# Threshold constants — encoded here so audit can review them next to the
# branching code (not embedded inside a prompt).
SCORE_THRESHOLD = 0.85
MAX_REVISION_ITERATIONS = 2
PROCUREMENT_USD_THRESHOLD = 500_000


def _router_state(ctx: Context, router_name: str, decision: str, rationale: str) -> dict:
    """Build a state delta emitting one RouterDecisionEvent for the canvas."""
    workflow_id = ""
    session_id = ""
    try:
        workflow_id = ctx.state.get("workflow_id", "") or ""
        session_id = ctx.state.get("session_id", "") or ""
    except Exception:
        pass
    event = RouterDecisionEvent(
        workflow_id=workflow_id,
        session_id=session_id,
        router_name=router_name,
        decision=decision,
        rationale=rationale,
    )
    return emit(ctx, event)


# DEMO NARRATION: "First routing decision. If direct availability exists, we
# take the fast path — build a plan with the existing asset. If not, we go
# into the equivalence pathway, where the agent reasons about functional
# substitutes. This is a deterministic check, not an LLM judgment."
def route_on_availability(node_input: dict, ctx: Context) -> Event:
    """Route based on whether direct asset availability was found."""
    route = DIRECT_AVAILABLE if node_input.get("direct_available") else NEEDS_EQUIVALENCE
    rationale = (
        "Direct availability found in target region"
        if node_input.get("direct_available")
        else "No direct availability — proceeding to equivalence reasoning"
    )
    return Event(
        message=f"Routing on availability: {route}",
        route=route,
        output=node_input,
        state=_router_state(ctx, "route_on_availability", route, rationale),
    )


# DEMO NARRATION: "After the Plan Evaluator scores the plan, we check the
# threshold. Score of 0.85 or higher: we proceed. Below: we send the plan back
# to be revised. Maximum of two revision loops to avoid runaway iteration.
# This is the kind of control structure that's hard to enforce in a pure LLM
# agent — here it's just a Python conditional."
def route_on_evaluation_score(node_input: dict, ctx: Context) -> Event:
    """Route based on the Plan Evaluator's score.

    The plan_evaluator's output IS a ``PlanEvaluation`` dict (no wrapping
    ``{"evaluation": ...}`` key), so ``node_input["overall_score"]`` is
    where the score lives at this point in the workflow.
    ``iteration_count`` lives in ``ctx.state`` because every LLM-output
    boundary clobbers node_input's wrapping keys.
    """
    # Read overall_score from node_input directly (plan_evaluator output),
    # with a fallback to ctx.state["evaluation"] just in case.
    evaluation_dict = node_input if isinstance(node_input, dict) else {}
    if "overall_score" not in evaluation_dict:
        try:
            evaluation_dict = ctx.state.get("evaluation", {}) or {}
        except Exception:
            evaluation_dict = {}
    overall_score = float(evaluation_dict.get("overall_score", 0.0))

    # iteration_count lives in ctx.state across the revise loop.
    try:
        iteration = int(ctx.state.get("iteration_count", 0) or 0)
    except Exception:
        iteration = int(node_input.get("iteration_count", 0) or 0)

    state_delta_extra: dict = {}
    if overall_score >= SCORE_THRESHOLD:
        route = PROCEED
        forward = {**node_input, "accepted_reason": "score_above_threshold"}
        rationale = f"Score {overall_score:.2f} >= threshold {SCORE_THRESHOLD}"
    elif iteration >= MAX_REVISION_ITERATIONS:
        route = PROCEED
        forward = {**node_input, "accepted_reason": "revision_exhausted"}
        rationale = f"Iteration cap ({MAX_REVISION_ITERATIONS}) reached; accepting plan"
    else:
        route = REVISE
        new_iteration = iteration + 1
        # Code-review MED #14: revise_plan's prompt says it receives
        # {plan, evaluation, iteration_count}. node_input is the
        # PlanEvaluation dict (LLM clobbered it). Re-wrap from ctx.state
        # so the LLM sees what its instruction promises.
        try:
            current_plan = ctx.state.get("plan") or {}
        except Exception:  # noqa: BLE001
            current_plan = {}
        forward = {
            "plan": current_plan,
            "evaluation": evaluation_dict,
            "iteration_count": new_iteration,
        }
        # Persist iteration_count into ctx.state via the Event's state
        # delta — the next plan_evaluator invocation reads it from there.
        state_delta_extra["iteration_count"] = new_iteration
        rationale = f"Score {overall_score:.2f} below threshold; requesting revision"

    return Event(
        message=(
            f"Routing on evaluation: score={overall_score:.2f} iteration={iteration} → {route}"
        ),
        route=route,
        output=forward,
        state={
            **_router_state(ctx, "route_on_evaluation_score", route, rationale),
            **state_delta_extra,
        },
    )


# DEMO NARRATION: "Final routing — does this plan need procurement approval?
# Above $500K or any non-trivial blocker, yes. Below that threshold the OCC
# planner can self-approve. This threshold is policy, not LLM judgment — it
# lives right here in the workflow next to the audit log."
def route_on_procurement_threshold(node_input: dict, ctx: Context) -> Event:
    """Route based on whether procurement approval is required.

    By this point in the workflow, ``node_input`` is whatever
    route_on_evaluation_score forwarded — typically the plan_evaluator
    output (PlanEvaluation), which doesn't carry the SourcingPlan. So
    pull ``plan`` from ``ctx.state`` (stashed by sourcing_logistics and
    revise_plan's after_agent_callbacks).
    """
    plan = node_input.get("plan") or {}
    if not plan:
        try:
            plan = ctx.state.get("plan", {}) or {}
        except Exception:
            plan = {}
    primary = (plan.get("primary_option") or {}) if isinstance(plan, dict) else {}
    cost = int(primary.get("estimated_cost_usd", 0) or 0)
    blockers = list(primary.get("blockers", []) or [])

    if cost > PROCUREMENT_USD_THRESHOLD or blockers:
        route = REQUIRES_APPROVAL
        rationale = (
            f"Cost ${cost:,} exceeds ${PROCUREMENT_USD_THRESHOLD:,} threshold "
            f"or {len(blockers)} blocker(s) present — procurement approval required"
        )
    else:
        route = AUTO_APPROVE
        rationale = f"Cost ${cost:,} under threshold and no blockers — OCC planner self-approval"

    return Event(
        message=(f"Routing on procurement: cost=${cost:,} blockers={len(blockers)} → {route}"),
        route=route,
        output=node_input,
        state=_router_state(ctx, "route_on_procurement_threshold", route, rationale),
    )
