# Capacity Planning — evals

ADK 2.0 eval set + pytest runner for the Capacity Planning Agent.

## Files

- `capacity_planning_agent.evalset.json` — ADK ``EvalSet`` schema. Three cases.
- `test_capacity_planning_agent_evals.py` — pytest runner with fast + live layers.

## Schema note

The task spec mentions ``OptimalBuffer``; the deployed agent returns
``BufferOptimization`` (the renamed schema). The load-bearing fields the spec
asserts on — ``recommended_buffer_days``, ``projected_on_time_rate`` — live on
``BufferOptimization``.

## What's tested

| Case | Layer | Asserts |
| --- | --- | --- |
| `happy_path_west_africa_risk_05` | fast | expected response satisfies `recommended_buffer_days >= 0`, `projected_on_time_rate ∈ [0,1]` |
| `happy_path_west_africa_risk_05` | live | live response satisfies the same range constraints, basin == west_africa |
| `happy_path_permian_strict_risk` | fast | strict risk (0.85) recommends more buffer than loose risk (0.5) |
| `edge_basin_without_wo_history` | live | unknown basin returns a degraded BufferOptimization (or graceful error), never NaN |
| (schema) | fast | `BufferOptimization` round-trips JSON |

The strict > loose inequality is the load-bearing semantic check for the
agent: higher risk tolerance → demand more on-time rate → recommend more
buffer. Reversing it would be a real regression.

## Run

```bash
poetry run pytest agents/capacity_planning_agent/evals/
poetry run pytest agents/capacity_planning_agent/evals/ --run-live-evals

make evals-capacity
make evals-capacity EVAL_FLAGS=--run-live-evals
```

## Expected runtimes

| Layer | Wall time | Cost |
| --- | --- | --- |
| Fast | < 1s | $0 |
| Live (per case) | ~10-20s | ~$0.02 per run (Gemini 3 Flash) |
| Live (all 2 live tests) | ~40s | ~$0.04 per run |
