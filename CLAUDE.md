# CLAUDE.md

Operating instructions for Claude Code on this repo. Always loaded into context.

## Primary references — read in order
1. `SPECS.md` (repo root) — master spec: tech stack, repo structure, acceptance criteria, out-of-scope list.
2. `tasks/TASK-NN-*.md` — the current task spec. Read fully before starting any step.
3. `docs/planning/agentic_sop_oilfield_services_brief.md` — product brief; the "why" behind decisions.
4. Other artifacts in `docs/planning/` as needed: `customer_engagement_brief.md`, `keynote_adaptation_plan.md`, `persona3_canvas_storyboard.md`.

## Environment
- **Python venv lives at `venv/`** (not `.venv/`), created with vanilla `python -m venv venv`. Always activate it (`source venv/bin/activate`) before any `python` / `pip` / `poetry` / `pytest` / `ruff` / `adk` command. Do **not** create a new venv. If `venv/` is missing or broken, stop and ask.
- **GCP project**: `vertex-ai-demos-468803` (project number `552994256750`).
- **Package manager: Poetry** (installed inside the venv via `pip install poetry`, mirroring the `earnings_analyst` pattern). Use `poetry install`, `poetry add`, `poetry run`. No bare `pip install <pkg>` for project deps (only `pip install poetry` to bootstrap).
  - **Deviation from SPECS.md §Tech stack** — SPECS locks the manager to `uv`, but `uv` does not work on the user's corp laptop where this code will eventually run. Poetry mirrors the existing `earnings_analyst` workflow. When porting `pyproject.toml` templates from the reference repo (which is uv-based), convert to Poetry format (`[tool.poetry]`, `[tool.poetry.dependencies]`, `[tool.poetry.group.dev.dependencies]`, `poetry-core` build backend).
- **Python 3.11+** (ADK requirement).
- **Gitignore must include `venv/`** (SPECS.md's gitignore template uses `.venv/`; add the `venv/` form on top of it).
- **Git remote**: `origin = https://github.com/rahulsankrut/agentic-sop-oilfield-services.git`. The local repo still needs `git init` (the operator kickoff said it was pre-done, but it isn't — verified `2026-05-17`).
- **GCP region**: `us-central1` consistently for v1. Mixing regions causes hard-to-diagnose "resource not found" errors.
- **ADC auth**: `gcloud auth login` is not enough — Agent Engine needs `gcloud auth application-default login` separately.

## Workflow cadence
- Execute one TASK step at a time. After each step: summarize what changed (files created/modified, commands run, notable output) and **wait for explicit confirmation** before the next step.
- If a step fails or produces unexpected results, **stop and report** — don't silently iterate on a fix.
- When a TASK's acceptance criteria are all met, **stop completely**. Do not begin the next TASK until told.
- Don't reorder or skip steps within a TASK.
- For genuine spec ambiguity, **stop and ask** before guessing.

## Confidence and ambiguity (added 2026-05-20)
- **During build**: if you have a question — about an API surface, a config field, a naming convention, a deploy step, anything — **ask** before assuming. A 30-second clarification beats a 20-minute deploy cycle on a wrong hypothesis.
- **During debugging**: if you are not confident about the cause of a failure, **read the documentation or look at sample code first**. Don't guess at fixes. Verified examples to consult, in order: `~/.claude/references/*.md` (cross-project knowledge), `/tmp/next-26-keynotes/devkey/demo-2/` (canonical demo-2 reference), `~/Desktop/agents/*/` (sibling agent projects), then official Google Cloud docs. Use `inspect.getsource(...)` on installed SDK code when docs are silent.
- Symptom of getting this wrong: cycling through redeploys ("maybe it's X… maybe Y… maybe Z") instead of reading the runtime logs + the SDK source first. If you're on the second retry without new information, stop and read.

## Boundaries (hard)
- Don't invent platform features, APIs, or library functions. If unsure, check `github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-2` first; then ask.
- Don't deviate from the locked tech stack in SPECS.md.
- Don't build anything on the SPECS.md out-of-scope list.
- Don't delete or recreate pre-existing files without explicit instruction.
- Don't create new top-level docs (README, ARCHITECTURE, etc.) unless the user asks or a TASK spec calls for them.

## Known gotchas (learned the hard way)
- **`a2a-sdk` must be pinned `<1.0`**. v1.0.x was released `2026-05` with breaking API changes (removed `ClientEvent` from `a2a.client`); `google-adk` (current pin `>=1.25,<2`) still expects the 0.x API. Use `a2a-sdk>=0.3.9,<1.0` until ADK ships a 1.x-compatible release.
- **Gemini 3 preview models live on the `global` endpoint, not `us-central1`.** `gemini-3.1-pro-preview` and `gemini-3-flash-preview` 404 in `us-central1` (and `us-east5`/`us-east4`/`europe-west4`) but work in `location='global'`. Agent Engine itself only exists in regional locations, so a vanilla `vertexai.init(location='us-central1')` blocks model access. The canonical fix (per `github.com/GoogleCloudPlatform/race-condition/agents/utils/global_gemini.py`) is a `GlobalGemini(Gemini)` subclass that overrides `api_client` to use a separate `genai.Client(location='global')` for the model — Agent Engine, Memory Bank, and Sessions keep using `us-central1`, only the model call routes to `global`. Ported to `agents/utils/global_gemini.py`. Use `model=GlobalGemini(model="gemini-3.1-pro-preview")` for reasoning-heavy agents (Orchestrator, Plan Evaluator) and `model=GlobalGemini(model="gemini-3-flash-preview")` for fast/deterministic ones (Procurement Approval, Forecast Review, Capacity Planning). TASK-01's placeholder Orchestrator was deployed on `gemini-2.5-flash` (we hadn't discovered the global pattern yet); it's harmless and will be replaced when TASK-02 rebuilds the Orchestrator.
- **Agent Engine deploy of A2aAgent — Pydantic ↔ protobuf bug (FIXED).** The Vertex AI SDK calls `json_format.MessageToJson(agent.agent_card)` in `_agent_engines_utils.py:636` AND `json_format.MessageToDict(agent.agent_card)` in `_genai/agent_engines.py:2505`. Both blow up when the card is `a2a-sdk` 0.x's Pydantic model. `agents/utils/deploy.py:patch_message_to_json_for_pydantic()` patches **both** call sites. Regression tests in `tests/unit/test_deploy_patch.py` (6 tests) confirm.
- **Use programmatic deploys, NOT `adk deploy agent_engine` CLI.** The CLI stages only the agent's own package directory and the deployed runtime then can't `from agents.schemas import ...` ("No module named 'agents'"). Every agent has a `runtime/deploy.py` that calls `vertexai.Client(...).agent_engines.create/update` with `extra_packages=["src/<agent>", "agents/utils", "agents/schemas.py"]`. The Makefile's `deploy-<agent>` targets call those scripts.
- **The deployed Reasoning Engine runtime is Python 3.10**, not Python 3.14 like our local venv. Avoid 3.11+ syntax in any code path that ships to the runtime:
  - Use `class Foo(str, Enum):` not `class Foo(StrEnum):`
  - Use `from datetime import timezone; timezone.utc` not `datetime.UTC` (in any code that gets uploaded)
  - The `from __future__ import annotations` at the top of every module covers `X | Y` type-hint syntax
- **`google-adk` must be pinned exactly in deploy requirements.** Latest ADK releases (post-1.33.0 as of 2026-05-18) ship a `SkillToolset` with a broken `_registry` attribute path — `process_llm_request` throws `AttributeError`. Every `runtime/deploy.py` pins `google-adk==1.33.0` (matches our local install, 38 skill-tool tests pass). If a newer ADK version becomes the floor for required features, re-test against `_registry` first.
- **UUID fields break ADK output serialization.** The deployed ADK runtime serializes the agent's structured response via stdlib `json.dumps`, which raises `TypeError: Object of type UUID is not JSON serializable` even when the Pydantic model would. `agents/schemas.py` uses `str` for every id field with `default_factory=_new_uuid_str`. Don't introduce `uuid.UUID` in any schema that's an `output_schema=` target.
- **`SkillToolset` does NOT expose each skill's Python functions as direct tools.** It only exposes `load_skill`, `list_skills`, `run_skill_script`, `load_skill_resource`. Without explicit `FunctionTool` wrappers, the LLM reads `SKILL.md`, tries to invoke each tool via `run_skill_script` on a non-existent `scripts/<fn>.py` file (functions live in `scripts/tools.py`, one file per skill), loops on SCRIPT_NOT_FOUND errors, then hallucinates structured output. **Fix:** `agents/utils/skill_tools.py:load_skill_function_tools` parses each `SKILL.md`'s `metadata.adk_additional_tools` frontmatter and registers each named function as a `FunctionTool`. Every agent's `core/tools.py` (and the Plan Evaluator's `agent.py`) splices its output into `tools=`. Pattern preserved verbatim from `next-26-keynotes/devkey/demo-2/src/planner_agent/core/tools.py`.
- **Customer-id inputs MUST be normalized.** The LLM passes display names ("Gulf Petroleum") interchangeably with slugs ("gulf-petroleum"). Any skill tool taking `customer_id` calls `src.utils.synthetic_data.normalize_customer_id(...)` first. `resolve_canonical_asset` also searches by `canonical_label` (case-insensitive substring) so "Tool X" / "Tool X variant" resolve to `TX-001` without the LLM having to know the slug.
- **Deploy from Python 3.12 (or older), NOT 3.13/3.14.** ADK + cloudpickle serializes the agent (and its `FunctionTool`-wrapped functions) at deploy time. The deployed Vertex AI Reasoning Engine container runs Python 3.10. Code objects compiled by Python 3.13+ have 18 args; Python 3.10 expects ≤ 16, so unpickling fails with `TypeError: code expected at most 16 arguments, got 18`. **Local dev venv (`venv/`) uses Python 3.14**; a separate `venv-deploy/` uses Python 3.12 for `runtime/deploy.py` invocations only. All `make deploy-*` targets must source `venv-deploy/` (TODO: bake into the Makefile). Pre-3.13 Python is forward-compatible with 3.10 — same 16-arg layout. Until Vertex AI Reasoning Engine offers Python 3.13+ runtimes, hold the line at 3.12 for deploys.
- **Per-agent package layout for `adk deploy agent_engine`**: the CLI generates `<temp>/agent_engine_app.py` that does `from .agent import root_agent`. Each deployable agent package must therefore have BOTH `<pkg>/__init__.py` re-exporting `root_agent` AND `<pkg>/agent.py` defining or re-exporting `root_agent`. Our SPECS-mandated `core/agent.py` layout means `<pkg>/agent.py` is a one-line shim: `from .core.agent import root_agent`. See `agents/orchestrator_agent/agent.py`. Replicate for all 5 agents in TASK-02. (Failure mode is silent at deploy time — Agent Engine instance is created but won't start, throwing `UserCodeControlPlaneError: No module named '<pkg>.agent'` in startup logs.)
- **Plumb ALL model env vars through terraform** when defining agent Cloud Run services, not just `PLANNER_MODEL`. The reference's `orchestrator_agent.tf` only sets `PLANNER_MODEL`, so `EVALUATOR_MODEL` falls back to the Python default (which was a preview model we can't access). For our 5 agents, every `*_MODEL` env var that has a code-level default needs a tf variable + container env block.
- **Image must exist in Artifact Registry before `google_cloud_run_v2_service` apply** — the v2 resource waits for healthy startup, which fails on `image-not-found`. Bootstrap pattern: write a minimal `cloudbuild_bootstrap.yaml` that only does build+push (no `services update`), submit it once, then `terraform apply`. After that, normal `cloudbuild.yaml` flow works for updates.
- **Reference Makefile's `make infra` lacks `-auto-approve`** on terraform apply. Run `terraform apply -auto-approve` directly when scripting, or add the flag to our own Makefile.
- **ADK 2.0 Workflow nodes pass data via `Event(output=...)`, NOT `Event(payload=...)`.** The TASK-04 spec drafts and some early reference snippets show `payload=`, but the actual ADK 2.0 graph API uses `output` for the data payload, `route` for routing keys, and `message` for the human-readable summary string (see `https://adk.dev/graphs/data-handling/`). Each node receives the previous node's `Event.output` as its single positional arg (named `node_input` by convention). The Capacity Orchestrator Workflow (`agents/orchestrator_agent/nodes/`) uses this verified API. Import is `from google.adk import Agent, Workflow, Event` (the top-level shortcuts — `LlmAgent` still imports from `google.adk.agents` for backwards-compat with v1.x agents like the Plan Evaluator).
- **TASK-11 governance gcloud verbs are Preview and may not exist as drafted.** `gcloud agent-platform gateway-policies …`, `gcloud model-armor templates …`, and `gcloud ai agent-identities …` are all pre-GA verbs (see `~/.claude/references/gemini-enterprise-agent-platform.md` §CLI surface). The verb tree may move (`gcloud agent-platform` → `gcloud agentplatform`, `gcloud ai agent-identities` → `gcloud agent-platform identities`, etc.). `docs/governance.md` is the fallback contract: when a gcloud verb errors with `unknown command`, switch to the verified REST endpoints (`agentplatform.googleapis.com`, `modelarmor.googleapis.com`) or the Console URLs listed in §6 of that runbook.

## Reference implementation
Next '26 dev keynote `demo-2` (marathon planner) is the primary pattern source. When in doubt about an ADK / A2A / Skills choice, look at how `demo-2` solved it and adapt. Clone target: `/tmp/next-26-keynotes/`.

Patterns to preserve verbatim (per SPECS.md §Architectural principles):
- `PromptBuilder` for prompt composition (ordered named sections)
- `SkillToolset` + `load_skill_from_dir` for lazy skill loading
- `RemoteA2aAgent` wrapped in `AgentTool` for A2A collaboration
- Per-agent layout: `core/`, `skills/`, `runtime/`, `services/`
- `auto_save_memories` `after_agent_callback` for Memory Bank
- Iterative refinement with score threshold (Evaluator pattern)
- Pydantic schemas on `LlmAgent(output_schema=...)`

## Code conventions
- **Demo narration cues**: every significant agent action, prompt, or response transformation gets a `# DEMO NARRATION: "..."` comment carrying the line the demoer will say. These become the source for `docs/demo_storyboard.md`.
- **Python**: `ruff` lint + format, type hints everywhere, `logging` (not `print`), `pytest` for tests.
- **TypeScript** (canvas): Prettier + ESLint, strict mode, no `any` without justification.
- **Commits**: conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`). Reference the task spec in the body (e.g., "Implements TASK-01 step 5"). Commit at natural breakpoints; announce the planned commit in the step summary so it's confirmed alongside the step's work.

## Current file layout
- `SPECS.md` — master spec
- `tasks/` — task specs (TASK-01, TASK-02, TASK-03 dropped so far)
- `docs/planning/` — planning artifacts that produced SPECS
- `venv/` — Python virtual environment (gitignored)
- The full target tree (`src/`, `mcp_servers/`, `canvas/`, `terraform/`, etc.) is built out in TASK-01 Step 3 per SPECS.md §Repository structure.

## Roles
- The user is the lead Customer Engineer.
- I (Claude Code) am the engineer building. I execute specs; the user confirms each step before I proceed.
