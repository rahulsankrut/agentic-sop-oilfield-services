"""Tools for the plan-evaluation skill."""

from __future__ import annotations

import json


def evaluate_plan_deterministic(plan_json: str) -> dict:
    """Compute the deterministic components of a SourcingPlan score.

    Args:
        plan_json: JSON-serialized SourcingPlan (the wire format the
            Orchestrator emits to the Plan Evaluator via AgentTool).

    Returns:
        ``{cost_optimality, schedule_feasibility, logistics_feasibility,
        notes: list[str]}`` — each numeric in [0,1]. The LLM then scores the
        qualitative criteria (safety_compliance, customer_compatibility,
        equivalence_confidence, regulatory_compliance) using the rubrics in
        the references/ directory and combines via the per-criterion weights.
    """
    try:
        plan = json.loads(plan_json) if isinstance(plan_json, str) else plan_json
    except Exception as exc:
        return {"error": f"Could not parse SourcingPlan JSON: {exc}"}

    notes: list[str] = []

    avoided = plan.get("avoided_cost_usd", 0) or 0
    primary_cost = plan.get("primary_option", {}).get("estimated_cost_usd", 0) or 0
    baseline_cost = (plan.get("naive_baseline") or {}).get("estimated_cost_usd", 0) or 0
    if baseline_cost > 0:
        # Savings ratio, capped 0-1 — favouring high savings vs naive baseline.
        savings_ratio = avoided / baseline_cost
        cost_optimality = max(0.0, min(1.0, 0.5 + savings_ratio))
        notes.append(f"avoided ${avoided:,} ({savings_ratio:.0%} of naive baseline)")
    else:
        # No baseline → cost optimality based purely on whether primary_cost is low.
        cost_optimality = 0.75 if primary_cost < 100_000 else 0.5

    transit_hours = plan.get("primary_option", {}).get("transit_hours", 0) or 0
    # Tighter the timeline (shorter transit relative to a 5-day deadline), the better.
    # Crude proxy until we wire a real deadline check.
    if transit_hours <= 24:
        schedule_feasibility = 0.95
    elif transit_hours <= 96:
        schedule_feasibility = 0.85
    elif transit_hours <= 168:
        schedule_feasibility = 0.6
    else:
        schedule_feasibility = 0.35

    blockers = plan.get("primary_option", {}).get("blockers", []) or []
    logistics_feasibility = 1.0 if not blockers else max(0.1, 1.0 - 0.25 * len(blockers))
    if blockers:
        notes.append(f"{len(blockers)} blocker(s) on primary option")

    return {
        "cost_optimality": round(cost_optimality, 2),
        "schedule_feasibility": round(schedule_feasibility, 2),
        "logistics_feasibility": round(logistics_feasibility, 2),
        "notes": notes,
    }
