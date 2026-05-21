# Forecast Review — evals

ADK 2.0 eval set + pytest runner for the Forecast Review Agent.

## Files

- `forecast_review_agent.evalset.json` — ADK ``EvalSet`` schema. Three cases.
- `test_forecast_review_agent_evals.py` — pytest runner with fast + live layers.

## Schema note

The task spec mentions ``ForecastOverride`` but the deployed agent's
``output_schema`` is ``ForecastRationale`` (see ``agents/schemas.py``):
``ForecastOverride`` is the *input* shape (the override record itself).
``ForecastRationale`` holds the agent's extracted tags + confidence — that's
what these evals assert on.

## What's tested

| Case | Layer | Asserts |
| --- | --- | --- |
| `happy_path_q4_west_africa_override` | fast | expected response has non-empty `rationale_tags` |
| `happy_path_q4_west_africa_override` | live | live response is a `ForecastRationale` with non-empty tags |
| `edge_empty_rationale` | fast | expected response has `rationale_tags=[]` — agent must not fabricate |
| `edge_empty_rationale` | live | "gut feeling" override doesn't extract multiple tags |
| `edge_missing_override_id` | live | missing override_id doesn't crash the agent |
| (schema) | fast | `ForecastRationale` round-trips JSON |

The "don't fabricate" assertion is from the agent's own prompt:
> "If rationale_tags is empty after extraction, return the tag list as-is
> (don't fabricate). Surface no tags is itself a signal to the retrain."

## Run

```bash
poetry run pytest agents/forecast_review_agent/evals/
poetry run pytest agents/forecast_review_agent/evals/ --run-live-evals

make evals-forecast
make evals-forecast EVAL_FLAGS=--run-live-evals
```

## Expected runtimes

| Layer | Wall time | Cost |
| --- | --- | --- |
| Fast | < 1s | $0 |
| Live (per case) | ~10-20s | ~$0.02 per run (Gemini 3 Flash, 1024-token thinking) |
| Live (all 3 live tests) | ~45s | ~$0.06 per run |
