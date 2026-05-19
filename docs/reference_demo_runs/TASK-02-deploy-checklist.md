# TASK-02 Step 9 — Live deploy checklist (morning run)

**Status when authored**: code complete, deploys blocked on ADC re-auth.

ADC tokens expired mid-run (`Reauthentication is needed. Please run gcloud
auth application-default login to reauthenticate`). That command is
interactive (browser-based) and can't be done in the autonomous overnight
session — left as a morning checklist.

## 1. Re-authenticate ADC

```bash
cd ~/Desktop/agentic-sop-oilfield-services
source venv/bin/activate
gcloud auth application-default login
# Verify
gcloud auth application-default print-access-token | head -c 50
```

## 2. Tear down the TASK-01 placeholder Orchestrator

The skeleton Orchestrator from TASK-01 (`reasoningEngines/6182242171437973504`)
should be retired before redeploying:

```bash
python -c "
import vertexai; from vertexai import agent_engines
vertexai.init(project='vertex-ai-demos-468803', location='us-central1')
for e in agent_engines.list():
    print(f'Deleting {e.resource_name}')
    e.delete(force=True)
"
```

## 3. Deploy in dependency order

The Orchestrator's `tools.py` reads `PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME`
at deploy time, so procurement gate must deploy first. The other two are
independent; the orchestrator is last.

```bash
# Procurement first (exercises the deploy_a2a_agent_engine helper +
# patch_message_to_json_for_pydantic shim).
make deploy-procurement-gate
# → capture the printed PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME=…

# Edit .env (repo root) — paste the procurement resource name
# Edit src/orchestrator_agent/.env — append the same line

make deploy-forecast-review
# → capture FORECAST_REVIEW_AGENT_RESOURCE_NAME for .env

make deploy-capacity-planning
# → capture CAPACITY_PLANNING_AGENT_RESOURCE_NAME for .env

make deploy-orchestrator
# → capture ORCHESTRATOR_AGENT_RESOURCE_NAME for .env
```

## 4. Run the integration smoke test

```bash
# Re-source .env so the env vars from step 3 are in scope
set -a && source .env && set +a

poetry run pytest tests/integration/test_orchestrator_skeleton.py -v -s
```

Expected: 3 passed (smoke tests) + 1 passed (schema round-trip).

If a test fails, capture the output and the failing agent's Cloud Logging:

```bash
gcloud logging read 'resource.type="aiplatform.googleapis.com/ReasoningEngine"' \
  --project=vertex-ai-demos-468803 --limit=20 --format='value(textPayload)'
```

## 5. Update CLAUDE.md if anything surprised you

If the deploys uncovered fresh gotchas (e.g., Memory Bank API drift, the
A2A patch missed an edge case), update the "Known gotchas" section.

## 6. Risks tracked from the autonomous run

1. **`deploy_a2a_agent_engine` patch is unit-tested only.** The procurement
   deploy is its first live exercise. If it fails with a *different*
   protobuf/Pydantic error, the patch's feature-detection needs widening
   (`patch_message_to_json_for_pydantic` in `src/utils/deploy.py`).
2. **Memory Bank `context_spec.memory_bank_config.customization_configs`**
   API surface is `vertexai.preview` — may have drifted.
3. **`gemini-3.1-pro-preview` structured-output adherence** for the
   Orchestrator's `output_schema=SourcingPlan`. Local probe with a
   minimal prompt succeeded; the placeholder full workflow may need
   prompt tuning if the model returns malformed JSON. Fallback: lower
   to `gemini-2.5-pro` via `ORCHESTRATOR_MODEL` env var.

## 7. Optional teardown after smoke test passes

To stop ongoing Agent Engine idle billing:

```bash
python -c "
import vertexai; from vertexai import agent_engines
vertexai.init(project='vertex-ai-demos-468803', location='us-central1')
for e in agent_engines.list():
    e.delete(force=True)
"
```

(Or leave running for TASK-03 development — at ~pennies/hour, the cost
across all 4 instances is a few dollars per day.)
