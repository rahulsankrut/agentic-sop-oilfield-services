# Agent evals

This doc covers the eval suites for the 5 agents in this repo
(4 deployed + 1 bundled Plan Evaluator). It complements
[`docs/testing_guide.md`](testing_guide.md), which covers unit + integration
tests for production code paths.

## TL;DR

```bash
# Fast layer — all agents. Schema + evalset validity. CI-safe.
make evals

# Live layer — drives the deployed Reasoning Engines via :streamQuery.
# Requires ADC (`gcloud auth application-default login`) + spends Gemini tokens.
make evals EVAL_FLAGS=--run-live-evals

# Per-agent
make evals-orchestrator
make evals-procurement
make evals-forecast
make evals-capacity
make evals-plan-evaluator
```

## Layout

```
agents/
├── orchestrator_agent/
│   ├── evals/
│   │   ├── orchestrator_agent.evalset.json
│   │   ├── test_orchestrator_agent_evals.py
│   │   └── README.md
│   └── plan_evaluator/
│       └── evals/
│           ├── plan_evaluator.evalset.json
│           ├── test_plan_evaluator_evals.py
│           └── README.md
├── procurement_approval_agent/evals/
├── forecast_review_agent/evals/
└── capacity_planning_agent/evals/

conftest.py                      # repo-root — registers --run-live-evals + evals_live marker
agents/utils/eval_helpers.py     # shared helpers (evalset loading, :streamQuery driver)
docs/evals.md                    # this file
```

## Framework choice — ADK 2.0 ``.evalset.json``

We use ADK's eval-set format (``.evalset.json``) as the canonical contract
for what each agent should be exercised against and what it should return.
ADK's own ``AgentEvaluator`` would run the agent in-process; we don't use
that runner because our 4 standalone agents are deployed to Vertex AI
Reasoning Engine and the deployed surface is what we care about.

Instead the pytest runner reads the evalset and drives the deployed agent
via ``stream_query`` (same path the canvas's
``/api/orchestrator/stream/route.ts`` SSE proxy uses). This keeps the
evalset format portable — anyone with the ADK Dev UI can import these files
and run the agents in a different environment without rewriting cases.

Per the Anthropic evals guide
(https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents),
each eval has clear pass/fail criteria and we mix programmatic checks (schema
validation, range constraints, threshold comparisons) with semantic checks
on specific output fields. We don't currently wire an LLM-as-judge metric;
the field-level assertions cover the load-bearing behaviors.

## Two layers — fast (CI) vs live (manual / cron)

### Fast layer

Default for ``poetry run pytest agents/<agent>/evals/``. Runs in <1 second per
agent. Asserts:

- The ``.evalset.json`` file parses and has the expected ``eval_id`` keys.
- Every expected response in the evalset validates against the agent's
  Pydantic ``output_schema``.
- The agent's Pydantic schema round-trips JSON cleanly.
- Per-agent invariants that don't need an LLM call (e.g. the Plan Evaluator's
  7-criterion weight scheme sums to 1.0, or strict-risk recommends more
  buffer than loose-risk in the Capacity Planning expected responses).

This layer is safe to run in CI on every PR.

### Live layer

Gated on:

1. ``@pytest.mark.evals_live`` decorator on the test function.
2. ``--run-live-evals`` CLI flag (set up in repo-root ``conftest.py``).
3. The agent's resource-name env var being set (e.g.
   ``ORCHESTRATOR_AGENT_RESOURCE_NAME``). If any of the three is missing the
   test is skipped — not failed — so CI stays green.

Live tests drive the deployed Reasoning Engine via ``stream_query``,
collect the streamed text into a single string, and validate it against the
agent's Pydantic output schema. The streamed text is the same shape the
canvas's SSE proxy consumes — verifying it through the live SDK keeps our
expectations honest about what real customers will see.

**Costs (rough order of magnitude):**

| Agent | Model | Per-eval cost |
| --- | --- | --- |
| Orchestrator | Gemini 3.1 Pro | $0.10–$0.30 |
| Plan Evaluator | (drives Orchestrator) | $0.10–$0.30 |
| Procurement Approval | Gemini 3 Flash | $0.01 |
| Forecast Review | Gemini 3 Flash | $0.02 |
| Capacity Planning | Gemini 3 Flash | $0.02 |

Full live sweep (~12 tests across 5 agents): roughly $0.75–$1.50 per run.

## What's IN each agent's eval suite

Every agent gets three case types in its evalset:

1. **Happy path** — one canonical request that exercises the primary
   workflow. Structured output validated against the Pydantic schema.
2. **Edge case** — one degradation case (unknown customer, missing FDP
   entry, basin without history, malformed plan). Agent should degrade
   gracefully — not crash, not infinite-loop, not silently approve.
3. **Schema conformance** — every expected response in the evalset
   validates against the agent's ``output_schema``.

The Orchestrator additionally has a **tool trajectory** assertion: its
evalset's ``intermediate_data.tool_uses`` for the happy path encodes the
canonical Workflow graph path (parse → resolve → parallel → ...). The
``test_evalset_happy_path_trajectory_is_correct`` test checks this list
matches the ``EXPECTED_HAPPY_PATH_TRAJECTORY`` constant in
``test_orchestrator_agent_evals.py``. If the workflow shape changes,
update both — the asymmetry is intentional (the test guards the evalset).

## Skin-neutrality

Where the evalset cases reference customer accounts / asset names / hero
locations, the prompts are written to work with the strings from the active
skin (``skins/<slug>/customer.yaml``). The default skin's
``scenarios.cargo-plane`` is what the orchestrator's happy path encodes
("Tool X variant in Luanda by Friday", customer "Gulf Petroleum", source
"Lagos"). The Halliburton skin uses the same shape with different specific
strings, but the eval assertions key off canonical IDs (``TX-007``) and
substring matches (``"lagos"``), so both skins should pass.

If you add a third skin that uses materially different scenario fixtures,
plan to either (a) parametrize the eval cases or (b) accept that the live
layer will only pass under the default skin.

## CI integration

Suggested ``cloudbuild.yaml`` step:

```yaml
- name: python:3.10
  id: evals-fast
  entrypoint: bash
  args:
    - -c
    - |
      pip install poetry
      poetry install --no-interaction --no-ansi --only main,dev
      poetry run pytest agents/orchestrator_agent/evals/ \
                        agents/procurement_approval_agent/evals/ \
                        agents/forecast_review_agent/evals/ \
                        agents/capacity_planning_agent/evals/ \
                        agents/orchestrator_agent/plan_evaluator/evals/
```

The live layer should run on a manual trigger or a nightly cron, not on
every PR — it's >$1 per invocation and a flaky live eval would block PRs
unproductively.

## Gotchas / known limitations

- **Schema name drift in the task spec.** The original eval-task spec
  references ``ForecastOverride`` and ``OptimalBuffer``; the deployed
  agents use ``ForecastRationale`` and ``BufferOptimization``. The evals
  follow the actual deployed schemas (see each agent's eval README for the
  details). The load-bearing fields the spec cared about are present in
  both.
- **The Plan Evaluator has no standalone deploy.** Its live eval drives the
  Orchestrator and infers Plan Evaluator behavior from the workflow
  outcome. This works because the Orchestrator's score router gates the
  PROCEED branch on ``overall_score >= 0.85`` — if a SourcingPlan came back,
  the Plan Evaluator scored above threshold.
- **No LLM-as-judge metric is wired.** The task explicitly said to mix
  programmatic + LLM-judged, but we picked field-level programmatic
  assertions for the load-bearing claims (TX-007, Lagos source, $500K
  threshold, range constraints). Adding an LLM-judge metric is straight-
  forward (``google.adk.evaluation.response_evaluator``); we'd recommend it
  for cases where the assertion is "the rationale text is sensible" rather
  than a structured field.
- **The fast layer doesn't validate prompt-input handling.** The evalset's
  ``user_content.parts[0].text`` is what gets sent in the live layer. If a
  case's prompt is invalid (wrong customer name, etc.) the fast layer
  won't catch it — the live layer will.
