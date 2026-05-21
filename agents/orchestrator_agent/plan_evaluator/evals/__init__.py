"""Plan Evaluator evals (TASK-EVALS).

The Plan Evaluator is bundled in-process with the Capacity Orchestrator
(no standalone Agent Engine deploy — see ADR-0003), so its live evals
exercise it via the Orchestrator's :streamQuery surface and assert on the
PlanEvaluation contract.

See agents/orchestrator_agent/plan_evaluator/evals/README.md for details.
"""
