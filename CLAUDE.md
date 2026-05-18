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

## Boundaries (hard)
- Don't invent platform features, APIs, or library functions. If unsure, check `github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-2` first; then ask.
- Don't deviate from the locked tech stack in SPECS.md.
- Don't build anything on the SPECS.md out-of-scope list.
- Don't delete or recreate pre-existing files without explicit instruction.
- Don't create new top-level docs (README, ARCHITECTURE, etc.) unless the user asks or a TASK spec calls for them.

## Known gotchas (learned the hard way)
- **`a2a-sdk` must be pinned `<1.0`**. v1.0.x was released `2026-05` with breaking API changes (removed `ClientEvent` from `a2a.client`); `google-adk` (current pin `>=1.25,<2`) still expects the 0.x API. Use `a2a-sdk>=0.3.9,<1.0` until ADK ships a 1.x-compatible release.
- **Gemini 3 preview models are not available in `vertex-ai-demos-468803`** (`gemini-3-flash-preview` → 404; `gemini-3.1-pro-preview` likely the same). The SPECS/TASK templates that say `gemini-3-flash-preview` or `gemini-3.1-pro-preview` should be substituted with `gemini-2.5-flash` (and `gemini-2.5-pro` where reasoning depth matters, e.g., the Orchestrator). This affects TASK-01 Step 7's placeholder Orchestrator and the SPECS tech stack note about "Gemini 3.1 Pro for the Orchestrator". If preview access is granted later, swap back.
- **`agent_engines.create` is broken on `google-cloud-aiplatform>=1.150` with `a2a-sdk` 0.x**. `vertexai._genai._agent_engines_utils` calls protobuf `MessageToJson` on the Pydantic `AgentCard`, throwing `AttributeError: 'AgentCard' object has no attribute 'DESCRIPTOR'`. No clean version pin found (older aiplatform conflicts with `google-adk>=1.25`). Workaround for live deploys until upstream fixes: use Cloud Run for the lead agent and either skip Agent Engine for sub-agents or vendor the deploy script with a Pydantic-aware patch. Tracked in `docs/reference_demo_runs/SUMMARY.md`.
- **Plumb ALL model env vars through terraform** when defining agent Cloud Run services, not just `PLANNER_MODEL`. The reference's `orchestrator_agent.tf` only sets `PLANNER_MODEL`, so `EVALUATOR_MODEL` falls back to the Python default (which was a preview model we can't access). For our 5 agents, every `*_MODEL` env var that has a code-level default needs a tf variable + container env block.
- **Image must exist in Artifact Registry before `google_cloud_run_v2_service` apply** — the v2 resource waits for healthy startup, which fails on `image-not-found`. Bootstrap pattern: write a minimal `cloudbuild_bootstrap.yaml` that only does build+push (no `services update`), submit it once, then `terraform apply`. After that, normal `cloudbuild.yaml` flow works for updates.
- **Reference Makefile's `make infra` lacks `-auto-approve`** on terraform apply. Run `terraform apply -auto-approve` directly when scripting, or add the flag to our own Makefile.
- **`adk deploy agent_engine` CLI requires `agent.py` at the package root** (not `core/agent.py`). The CLI generates an `agent_engine_app.py` that does `from .agent import root_agent`. Our standardized per-agent layout (per SPECS) keeps the canonical definition in `core/agent.py`, so every deployable agent package needs a tiny `agent.py` at the package root that re-exports `root_agent` from `core.agent`. Failure mode is silent at deploy time but throws `UserCodeControlPlaneError: No module named '<pkg>.agent'` on Reasoning Engine startup. See `src/orchestrator_agent/agent.py` for the canonical re-export shim. Replicate for all 5 agents in TASK-02.

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
