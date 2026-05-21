# Plan Evaluator — evals

ADK 2.0 eval set + pytest runner for the bundled Plan Evaluator sub-agent.

## Deployment shape (important)

The Plan Evaluator is **bundled in-process** with the Capacity Orchestrator
(ADR-0003), invoked via ``AgentTool(agent=plan_evaluator_agent)``. There is
**no** standalone deploy, so there's no ``PLAN_EVALUATOR_AGENT_RESOURCE_NAME``.

The live eval here drives the **Orchestrator** and infers Plan Evaluator
behavior from the workflow outcome: the Orchestrator's evaluation-score
router only forwards to ``finalize_sourcing_plan`` when
``overall_score >= 0.85``. A successful ``SourcingPlan`` return implies the
Plan Evaluator scored it above threshold.

## Files

- `plan_evaluator.evalset.json` — ADK ``EvalSet`` with happy and weak-plan cases.
- `test_plan_evaluator_evals.py` — pytest runner.

## What's tested

| Case | Layer | Asserts |
| --- | --- | --- |
| (weight scheme) | fast | the 7 ``CRITERION_WEIGHTS`` sum to 1.0 |
| `happy_path_good_plan_scores_above_threshold` | fast | expected `overall_score >= 0.85`, 7 criterion scores in [0,1] |
| `edge_weak_plan_triggers_revision` | fast | weak plan has `overall_score < 0.85`, `revision_recommended=true` |
| (all) | fast | every criterion in expected responses ∈ the canonical 7 |
| (schema) | fast | `PlanEvaluation` round-trips JSON |
| `happy_path_good_plan_scores_above_threshold` | live | Orchestrator returns a SourcingPlan ⇒ Plan Evaluator scored >= 0.85 |

The "weighted-1" assertion from the task spec is verified at the weight scheme
level: ``sum(CRITERION_WEIGHTS.values()) == 1.0``. The individual ``criterion_scores``
in any one PlanEvaluation are NOT required to sum to 1 (the spec text is
slightly ambiguous; the load-bearing claim is the weight scheme).

## Run

```bash
poetry run pytest agents/orchestrator_agent/plan_evaluator/evals/
poetry run pytest agents/orchestrator_agent/plan_evaluator/evals/ --run-live-evals

make evals-plan-evaluator
make evals-plan-evaluator EVAL_FLAGS=--run-live-evals
```

## Expected runtimes

| Layer | Wall time | Cost |
| --- | --- | --- |
| Fast | < 1s | $0 |
| Live | ~120s (drives the full Orchestrator workflow) | ~$0.10-$0.30 per run |
