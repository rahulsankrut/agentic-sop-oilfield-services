# Procurement Approval — evals

ADK 2.0 eval set + pytest runner for the Procurement Approval Agent.

## Files

- `procurement_approval_agent.evalset.json` — ADK ``EvalSet`` schema. Three cases.
- `test_procurement_approval_agent_evals.py` — pytest runner with fast + live layers.

## What's tested

| Case | Layer | Asserts |
| --- | --- | --- |
| `under_threshold_auto_approves` | fast | expected response has `approved=True`, `blockers=[]` |
| `under_threshold_auto_approves` | live | $162K plan returns `approved=True` |
| `over_threshold_rejects` | fast | expected response has `approved=False` and a budget blocker |
| `over_threshold_rejects` | live | $600K plan returns `approved=False` with a non-empty blocker |
| `edge_malformed_plan_degrades_gracefully` | live | malformed input doesn't silently approve |
| (sanity) | fast | the $162K / $600K fixtures are actually under/over $500K |

The $500K threshold is the load-bearing assertion — SPECS.md §Acceptance
criteria #6 ("Agent Gateway policies enforce the $500K human-review threshold").

## Run

```bash
# Fast layer
poetry run pytest agents/procurement_approval_agent/evals/

# Live layer
poetry run pytest agents/procurement_approval_agent/evals/ --run-live-evals

# Via Makefile
make evals-procurement
make evals-procurement EVAL_FLAGS=--run-live-evals
```

## Expected runtimes

| Layer | Wall time | Cost |
| --- | --- | --- |
| Fast | < 1s | $0 |
| Live (per case) | ~5-15s | ~$0.01 per run (Gemini 3 Flash) |
| Live (all 3 live tests) | ~30s | ~$0.05 per run |

Procurement Approval is on the deterministic / fast-LLM path (thinking_budget=0),
so live evals are an order of magnitude cheaper than the Orchestrator's.
