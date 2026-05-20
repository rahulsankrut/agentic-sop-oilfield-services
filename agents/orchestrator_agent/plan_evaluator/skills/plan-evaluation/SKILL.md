---
name: plan-evaluation
description: >
  Deterministic pre-scoring for SourcingPlans across 7 weighted criteria
  (safety, customer compatibility, logistics feasibility, cost, equivalence
  confidence, regulatory, schedule). The LLM consumes these partial scores
  + the rubrics in `references/` to produce the final PlanEvaluation.
metadata:
  adk_additional_tools:
    - evaluate_plan_deterministic
---

# Plan Evaluation

The Plan Evaluator is LLM-as-Judge. The judge reasons with the help of the
rubrics in `references/`, but always grounds its scores in the deterministic
computations exposed here.

## Workflow

1. Call **`evaluate_plan_deterministic(plan_json)`** with the SourcingPlan
   as JSON. It returns a partial scoring dict — values the LLM can be sure
   of (cost optimality, schedule feasibility, blocker count) — leaving the
   qualitative criteria (safety_compliance, customer_compatibility,
   equivalence_confidence) for the LLM.
2. Read `references/scoring_rubrics.md` to score the qualitative criteria
   from 0.0 to 1.0.
3. Read `references/severity_thresholds.md` to map each criterion score
   to a Severity (low/medium/high).
4. Combine via the per-criterion weights into `overall_score`.
5. Recommend revision if `overall_score < 0.85`.
