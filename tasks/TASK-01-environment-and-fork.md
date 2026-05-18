# TASK-01: Environment setup and reference repo fork

**Prerequisites:** None. This is the first task. Read `SPECS.md` before starting.

**Estimated effort:** 1-2 days for one engineer.

**Stream:** Backend

---

> **Note for Claude Code (read this first):** Parts of the local environment may
> already be set up by the operator. Specifically, the working folder may
> already be initialized as a git repository with `origin` pointing at the
> correct GitHub remote, and a Python virtual environment may already exist in
> the working folder. Where this is the case, **do not recreate** these — skip
> Step 3's `git init` / `git remote add` (verify the remote URL instead), and
> skip Step 4's `uv venv` (activate the existing venv and run `uv sync` against
> it). If you encounter unexpected pre-existing files or state, stop and ask
> before deleting or overwriting anything. See the operator's kickoff prompt
> for the specific environment configuration.

---

## Context

Before building anything custom, set up a clean development environment and clone the reference repository (Next '26 keynote demo). The reference repo contains the multi-agent scaffold we're forking and adapting. Running `make demo-solo` and `make demo-full` on the marathon demo end-to-end before any custom work is non-negotiable — the build team must have hands-on familiarity with the scaffold viscerally, not just intellectually.

This task also creates the new `agentic-sop-oilfield-services` repository with the target directory structure from `SPECS.md`, sets up Python tooling, configures GCP authentication, and verifies the development environment by deploying a "hello world" placeholder agent to Agent Engine.

---

## Inputs

- A Google Cloud project with billing enabled and the following APIs enabled:
  - `aiplatform.googleapis.com`
  - `cloudbuild.googleapis.com`
  - `run.googleapis.com`
  - `artifactregistry.googleapis.com`
  - `secretmanager.googleapis.com`
  - `dataplex.googleapis.com` (for Knowledge Catalog later)
- `gcloud` CLI installed and authenticated
- `uv` Python package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `terraform` installed (1.x)
- `node` 20.x and `npm` (for the canvas later)
- A new empty GitHub repository for `agentic-sop-oilfield-services` (create via GitHub UI or `gh repo create`)

---

## Deliverables

When this task is complete, the following will be true:

1. The reference repo is cloned at `/tmp/next-26-keynotes/`
2. `cd /tmp/next-26-keynotes/devkey/demo-2 && make demo-solo` runs successfully end-to-end against a test GCP project, producing a marathon plan and an evaluator score
3. A new repository `agentic-sop-oilfield-services/` is created locally with the target structure from `SPECS.md` (folders only; empty `__init__.py` files where appropriate)
4. `pyproject.toml` is set up with the locked dependencies (see step 5 below)
5. `Makefile` has working stubs for `setup`, `auth`, `test`, `deploy`, `teardown`, `demo-cargo-plane`, `demo-forecast`, `demo-fleet-buffer`
6. A "hello world" placeholder agent (`src/orchestrator_agent/`) deploys to Agent Engine via `make deploy-orchestrator-skeleton` and responds to a trivial test prompt
7. `.gitignore`, `.env.example`, `README.md`, `cloudbuild.yaml` are in place
8. First commit pushed to the new GitHub repo

---

## Step-by-step instructions

### Step 1 — Clone the reference repo and validate locally

```bash
cd /tmp
git clone https://github.com/GoogleCloudPlatform/next-26-keynotes.git
cd next-26-keynotes/devkey/demo-2
cat README.md                    # familiarize with the structure
make help                        # see all available targets
```

Spend at least 30 minutes reading through:
- `devkey/demo-2/README.md`
- `devkey/demo-2/src/planner_agent/core/agent.py` (the LlmAgent wiring)
- `devkey/demo-2/src/planner_agent/core/prompts.py` (the INSTRUCTION builder)
- `devkey/demo-2/src/planner_agent/core/tools.py` (A2A wiring + SkillToolset)
- `devkey/demo-2/src/planner_agent/skills/route-planning/SKILL.md` (skill structure)
- `devkey/demo-2/src/simulator_agent/core/agent.py` (the remote A2A agent pattern)
- `devkey/demo-2/Makefile` (deployment automation)
- `devkey/demo-2/demo/scenarios.py` (demo runner pattern)

### Step 2 — Run the reference demo end-to-end

Set up GCP credentials and run the marathon demo:

```bash
cd /tmp/next-26-keynotes/devkey/demo-2
make setup          # installs dependencies via uv
make auth           # gcloud auth application-default login
cp .env.example .env
# edit .env with GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_MAPS_API_KEY
make test           # run unit tests
make deploy         # deploys infrastructure + agents to Agent Engine + Cloud Run
make demo-health    # verify endpoints
make demo-solo      # run the solo scenario (Planner + Evaluator only)
make demo-full      # run the full team scenario (+ Simulator)
```

**Acceptance check:** the marathon demo successfully generates a plan with an evaluator score and (in `demo-full` mode) a simulation approval. Save the output transcripts in `docs/reference_demo_runs/` for later comparison.

If the demo fails to run for any reason — environment issue, API quota, credentials — resolve before proceeding. The reference must work end-to-end before you fork it.

### Step 3 — Create the new repository

```bash
cd ~
mkdir agentic-sop-oilfield-services
cd agentic-sop-oilfield-services
git init
git remote add origin git@github.com:<your-org>/agentic-sop-oilfield-services.git
```

Create the directory structure exactly matching `SPECS.md`:

```bash
mkdir -p src/{orchestrator_agent,procurement_approval_agent,forecast_review_agent,capacity_planning_agent}/{core,skills,runtime,services}
mkdir -p src/orchestrator_agent/plan_evaluator
mkdir -p src/utils
mkdir -p mcp_servers/{sap,maximo,fdp}
mkdir -p data/{start_date_variance,operational_history,forecast_history,intouch_docs}
mkdir -p knowledge_catalog
mkdir -p canvas/src/{app,components,lib,types}
mkdir -p canvas/public
mkdir -p terraform
mkdir -p demo/deploy
mkdir -p tests/{unit,integration}
mkdir -p docs/adr
mkdir -p tasks
```

Create empty `__init__.py` files for every Python directory:

```bash
find src -type d -exec touch {}/__init__.py \;
find mcp_servers -type d -exec touch {}/__init__.py \;
```

### Step 4 — Set up Python tooling with `uv`

Create `pyproject.toml`:

```toml
[project]
name = "agentic-sop-oilfield-services"
version = "0.1.0"
description = "Agentic S&OP demo for oilfield services on Gemini Enterprise Agent Platform"
requires-python = ">=3.11"
dependencies = [
    "google-cloud-aiplatform>=1.70.0",
    "google-adk>=0.1.0",            # check latest stable in reference demo
    "google-genai>=0.5.0",
    "a2a>=0.1.0",                    # check latest stable in reference demo
    "pydantic>=2.5",
    "fastapi>=0.110.0",
    "uvicorn>=0.27.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.3.0",
    "mypy>=1.8",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "B", "UP", "PL"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Important:** Check the exact versions of `google-adk` and `a2a` used in the reference demo's `pyproject.toml`. Pin to those versions for compatibility. The version numbers above are approximate.

```bash
uv venv
source .venv/bin/activate
uv sync --all-extras
```

### Step 5 — Create supporting config files

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
.env
.env.local
node_modules/
.next/
*.log
.DS_Store
.terraform/
terraform.tfstate*
.uv/
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
.mypy_cache/
```

`.env.example`:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_CLOUD_REGION=us-central1

# Agent Engine resource names (populated after deployment)
ORCHESTRATOR_AGENT_RESOURCE_NAME=
PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME=
FORECAST_REVIEW_AGENT_RESOURCE_NAME=
CAPACITY_PLANNING_AGENT_RESOURCE_NAME=

# Knowledge Catalog
KNOWLEDGE_CATALOG_PROJECT=
KNOWLEDGE_CATALOG_LOCATION=us-central1

# MCP server endpoints (populated after deployment)
SAP_MCP_ENDPOINT=
MAXIMO_MCP_ENDPOINT=
FDP_MCP_ENDPOINT=

# Canvas WebSocket
CANVAS_WS_ENDPOINT=
```

`README.md` — a brief project overview pointing to `SPECS.md`:
```markdown
# Oilfield Services Domain Pack

Agentic S&OP demo for oilfield services on Gemini Enterprise + Gemini Enterprise Agent Platform.

See `SPECS.md` for the master specification. See `tasks/` for build instructions.

## Quick start

\```bash
make setup       # install dependencies
make auth        # GCP auth
make deploy      # deploy everything
make demo-cargo-plane  # run the centerpiece demo
\```
```

Copy `SPECS.md` (the master spec) into the repo root.

### Step 6 — Create the Makefile with stubs

```makefile
.PHONY: help setup auth test deploy teardown
.PHONY: deploy-orchestrator-skeleton
.PHONY: demo-cargo-plane demo-forecast demo-fleet-buffer
.PHONY: demo-health clean lint

help:
	@echo "Available targets:"
	@echo "  setup                          Install dependencies"
	@echo "  auth                           Authenticate with GCP"
	@echo "  test                           Run unit tests"
	@echo "  deploy                         Full deployment (TASK-13)"
	@echo "  deploy-orchestrator-skeleton   Deploy the placeholder orchestrator (TASK-01)"
	@echo "  teardown                       Destroy all resources"
	@echo "  demo-cargo-plane               Run Persona 3 scenario"
	@echo "  demo-forecast                  Run Persona 1 scenario"
	@echo "  demo-fleet-buffer              Run Persona 2 scenario"
	@echo "  demo-health                    Check endpoints"
	@echo "  clean                          Remove local build artifacts"
	@echo "  lint                           Run ruff"

setup:
	uv sync --all-extras

auth:
	gcloud auth application-default login

test:
	uv run pytest tests/

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

deploy-orchestrator-skeleton:
	uv run adk deploy agent_engine \
		--env_file src/orchestrator_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/orchestrator_agent

deploy:
	@echo "Full deploy not yet implemented (TASK-13)"
	@exit 1

teardown:
	@echo "Teardown not yet implemented (TASK-13)"
	@exit 1

demo-cargo-plane:
	@echo "Persona 3 demo not yet implemented (TASK-11)"
	@exit 1

demo-forecast:
	@echo "Persona 1 demo not yet implemented (TASK-11)"
	@exit 1

demo-fleet-buffer:
	@echo "Persona 2 demo not yet implemented (TASK-11)"
	@exit 1

demo-health:
	@echo "Health check not yet implemented (TASK-13)"
	@exit 1

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
```

### Step 7 — Build the placeholder Orchestrator agent

This is a "hello world" agent — just enough to verify the deployment pipeline works. We will flesh out the full Orchestrator in TASK-02.

`src/orchestrator_agent/core/agent.py`:

```python
"""Capacity Orchestrator Agent — skeleton (TASK-01 placeholder).

This is a minimal scaffold to verify the deployment pipeline.
The real agent is built in TASK-02.
"""

import os
import vertexai
from google.adk.agents import LlmAgent

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location=LOCATION)

# DEMO NARRATION: This is the lead agent — built on ADK, deployed on Agent Runtime.
# In production it orchestrates SAP, Maximo, FDP, and InTouch queries to resolve
# capacity gaps. In this placeholder, it just confirms the deployment pipeline works.
root_agent = LlmAgent(
    name="orchestrator_agent",
    model="gemini-3-flash-preview",     # use Flash for the skeleton; switch to 3.1 Pro in TASK-02
    description="Capacity Orchestrator Agent (skeleton)",
    instruction=(
        "You are a placeholder agent for the Oilfield Services Domain Pack. "
        "When asked anything, respond with: 'Orchestrator skeleton deployed successfully. "
        "TASK-01 complete. Ready for TASK-02 agent build.'"
    ),
    tools=[],
)
```

`src/orchestrator_agent/__init__.py`:
```python
from .core.agent import root_agent

__all__ = ["root_agent"]
```

`src/orchestrator_agent/sample.env`:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

### Step 8 — Deploy the placeholder and verify

```bash
cp src/orchestrator_agent/sample.env src/orchestrator_agent/.env
# edit src/orchestrator_agent/.env with your project ID

make deploy-orchestrator-skeleton
```

When deployment succeeds, you'll get an Agent Engine resource name. Capture it in `.env`:

```bash
echo "ORCHESTRATOR_AGENT_RESOURCE_NAME=projects/<NUMBER>/locations/us-central1/reasoningEngines/<ID>" >> .env
```

Test it via the Agent Runtime Playground in the GCP Console, or via a quick CLI test similar to the reference demo's `main.py prompt` pattern.

**Acceptance check:** the placeholder agent deploys successfully and responds to a test prompt with the expected confirmation string.

### Step 9 — First commit and push

```bash
git add .
git commit -m "chore: initial scaffold for oilfield domain pack (TASK-01)"
git push -u origin main
```

---

## Acceptance criteria

Verify each of the following before marking TASK-01 complete:

- [ ] Reference repo cloned and `make demo-solo` ran successfully end-to-end
- [ ] Reference repo `make demo-full` also ran successfully (Planner + Evaluator + Simulator)
- [ ] Reference demo output transcripts saved to `docs/reference_demo_runs/`
- [ ] New `agentic-sop-oilfield-services` repo created with full directory structure from SPECS.md
- [ ] `pyproject.toml` with locked dependencies; `uv sync --all-extras` runs clean
- [ ] `Makefile` with stubs for all major targets
- [ ] `.env.example`, `.gitignore`, `README.md`, `cloudbuild.yaml` in place
- [ ] Placeholder Orchestrator agent deploys via `make deploy-orchestrator-skeleton`
- [ ] Placeholder agent responds to a test prompt with the expected message
- [ ] First commit pushed to GitHub
- [ ] `ruff check` runs clean against the placeholder code

---

## Common pitfalls

**ADK version drift.** The ADK is evolving fast. Pin to whatever version the reference demo uses (check `pyproject.toml` in `next-26-keynotes/devkey/demo-2`). If you use a newer version, APIs may have changed and the patterns we adapt later won't match.

**Wrong Python version.** ADK requires Python 3.11+. If your system Python is older, use `uv python install 3.11` and `uv venv --python 3.11`.

**GCP API quotas.** First time you deploy to Agent Engine, you may hit quota limits on Vertex AI. Request quota increases proactively if you're in a fresh project.

**Confusing region settings.** Agent Engine, Memory Bank, and some services are regional. Use `us-central1` consistently for v1. Mixing regions will cause "resource not found" errors that are hard to diagnose.

**Forgetting to authenticate ADC.** `gcloud auth login` is not enough — Agent Engine deployment uses Application Default Credentials. Run `gcloud auth application-default login` separately.

**Skipping the reference demo run.** Don't. Spending 30 minutes running the marathon demo end-to-end will save days of confusion later. The patterns are not always obvious from the code alone.

---

## References

- `next-26-keynotes/devkey/demo-2/README.md` — the canonical setup pattern
- `next-26-keynotes/devkey/demo-2/Makefile` — Makefile patterns to mirror
- `next-26-keynotes/devkey/demo-2/pyproject.toml` — pinned dependency versions
- `next-26-keynotes/devkey/demo-2/src/planner_agent/core/agent.py` — minimal LlmAgent example

---

*When TASK-01 is complete, proceed to `TASK-02-agent-skeletons.md`.*
