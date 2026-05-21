# Capacity Orchestrator — evals

ADK 2.0 eval set + pytest runner for the Capacity Orchestrator Workflow.

## Files

- `orchestrator_agent.evalset.json` — ADK ``EvalSet`` schema. Three cases:
  happy-path cargo-plane, unknown-customer edge, basin-without-WO_HISTORY edge.
- `test_orchestrator_agent_evals.py` — pytest runner with two layers (fast + live).

## What's tested

| Case | Layer | Asserts |
| --- | --- | --- |
| `happy_path_cargo_plane` | fast | trajectory matches the canonical Workflow path |
| `happy_path_cargo_plane` | live | TX-007 substitute, Lagos source, positive avoided cost |
| `edge_unknown_customer` | live | workflow degrades gracefully, no infinite loop |
| `edge_basin_without_history` | fast | expected response shape is valid |
| (all) | fast | expected responses are JSON with the load-bearing keys |
| (schema) | fast | `SourcingPlan` round-trips JSON cleanly |

## Trajectory contract

The happy path encodes the Orchestrator's graph as an ordered tool-uses list:

```
parse_capacity_gap_request
  → resolve_canonical_asset_node
  → parallel_system_queries
  → evaluate_direct_availability
  → equivalence_lookup_agent           (LLM node — picks TX-007)
  → build_equivalent_plan
  → sourcing_logistics_agent           (LLM node — logistics refinement)
  → plan_evaluator_tool                (AgentTool node — scores >= 0.85)
  → finalize_sourcing_plan
```

When the Plan Evaluator scores below the threshold the workflow inserts
`revise_plan_agent` and loops back; that's covered by the score-router unit
test in `agents/tests/unit/`, not the live eval (the loop would burn 2× tokens
on every run).

## Run

```bash
# Fast layer only — schema + evalset validity. ~1 second. Safe for CI.
poetry run pytest agents/orchestrator_agent/evals/

# Full layer including live calls — drives the deployed Reasoning Engine.
# ~120s end-to-end per cargo-plane query. Requires ADC + costs Gemini tokens.
poetry run pytest agents/orchestrator_agent/evals/ --run-live-evals

# Or via Makefile
make evals-orchestrator                            # fast
make evals-orchestrator EVAL_FLAGS=--run-live-evals  # live
```

## Expected runtimes

| Layer | Wall time | Cost |
| --- | --- | --- |
| Fast | < 1s | $0 |
| Live (happy path) | ~120s | ~$0.10-$0.30 per run (Gemini 3.1 Pro) |
| Live (all 4 live tests) | ~5-8 min | ~$0.50 per run |
