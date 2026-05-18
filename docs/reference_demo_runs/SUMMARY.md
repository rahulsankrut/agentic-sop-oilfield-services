# Reference demo run — TASK-01 Step 2

Date: 2026-05-17
Reference repo: `github.com/GoogleCloudPlatform/next-26-keynotes` @ `393a170` (`add mapping skill back`)
Working copy: `/tmp/next-26-keynotes/devkey/demo-2/`
GCP project: `vertex-ai-demos-468803` (project number `552994256750`)

## What ran end-to-end

| Stage | Result |
|---|---|
| Deps install (`uv sync --all-groups --extra dev`) | ✓ clean, with `a2a-sdk<1.0` pin |
| Unit tests (`make test`) | ✓ 179 passed, 2 skipped |
| `terraform apply` (base infra) | ✓ all 11 resources after image bootstrap |
| Image build+push (`gcloud builds submit` with `cloudbuild_bootstrap.yaml`) | ✓ 1m35s |
| Cloud Run planner-agent service | ✓ live, A2A endpoint returns 200, agent card valid |
| Live demo prompt (Las Vegas marathon, A2A JSON-RPC) | ✓ agent built, LLM reasoned, tools/skills loaded, partial completion |

## What didn't complete

- **`make deploy-simulator` failed** with `AttributeError: 'AgentCard' object has no attribute 'DESCRIPTOR'` in `vertexai._genai._agent_engines_utils._generate_class_methods_spec_or_raise`. Caused by `vertexai 1.153.1` calling protobuf `MessageToJson` on a Pydantic `AgentCard` from `a2a-sdk 0.3.26`. Pinning aiplatform to `==1.121.0` (reference's lower bound) breaks resolution against `google-adk>=1.25.0`. No clean version combo found in available time.
- **Full A2A chain to a remote Simulator** therefore not validated live. Pattern was read from the source (`SerializableRemoteA2aAgent` with `_a2a_url_override`, regional URL rewrite for Agent Engine cards) and is unambiguous in code.
- **Score-iteration loop with structured Evaluator output** not validated to a final passing plan: `gemini-2.5-flash` returned empty string for the structured-output evaluator schema; switching to `gemini-2.5-pro` advanced past that point but the planner then tried to call `simulator_agent` (which we'd disabled). Either gemini-3 preview access or a simulator deployment would resolve.

## Patterns confirmed live (from the agent's tool list in production)

```
Available tools: list_skills, load_skill, load_skill_resource, run_skill_script,
                 plan_marathon_route, evaluator_agent
```

- **`SkillToolset` + `load_skill_from_dir`** lazy-loads `route-planning/` and `plan-evaluation/` → `list_skills`/`load_skill`/`load_skill_resource`/`run_skill_script` tools registered.
- **`FunctionTool`** wraps skill-local Python tools → `plan_marathon_route` registered.
- **In-process `AgentTool(agent=evaluator_agent)`** → `evaluator_agent` tool registered.
- **A2A JSON-RPC over Cloud Run** works on `/` (port 8080), agent card on `/.well-known/agent.json`.

## Gotchas captured (logged in CLAUDE.md)

1. `a2a-sdk` v1.0.x breaks `google-adk` — pin `<1.0`.
2. `gemini-3-flash-preview` and `gemini-3.1-pro-preview` are 404 in `vertex-ai-demos-468803` — use `gemini-2.5-flash` / `gemini-2.5-pro`.
3. `terraform/orchestrator_agent.tf` only sets `PLANNER_MODEL` env on Cloud Run — `EVALUATOR_MODEL` and `SIMULATOR_MODEL` defaults are baked into Python and need overrides at the service level. When we adapt this for our agents, plumb all three (and any others) through tf.
4. `google_cloud_run_v2_service` waits for healthy startup → image must exist in Artifact Registry before terraform creates the service. Bootstrap image with `cloudbuild_bootstrap.yaml` first, then `terraform apply`.
5. Reference Makefile's `make infra` lacks `terraform apply -auto-approve`; ran terraform directly.

## Reference scaffold infrastructure stood up (now destroyed)

- GCS bucket `vertex-ai-demos-468803-agent-staging`
- Service account `orchestrator-agent@vertex-ai-demos-468803.iam.gserviceaccount.com`
- Artifact Registry `us-central1-docker.pkg.dev/vertex-ai-demos-468803/orchestrator-agent/`
- Cloud Run service `orchestrator-agent` (URL: `https://orchestrator-agent-5udif2v3cq-uc.a.run.app`)

See `demo_solo_direct.txt` for the raw HTTP/A2A transcript of the live run.
