# Oilfield Services Domain Pack — Makefile
#
# Activate the venv first: `source venv/bin/activate`. All `poetry run …`
# targets assume the venv is active (per CLAUDE.md, we use venv/ + Poetry,
# not uv).

.PHONY: help setup auth test lint coverage verify
.PHONY: deploy-orchestrator-skeleton deploy-orchestrator
.PHONY: deploy-procurement-gate deploy-forecast-review deploy-capacity-planning
.PHONY: deploy-all-agents
.PHONY: deploy teardown
.PHONY: demo-cargo-plane demo-forecast demo-fleet-buffer demo-health demo-preflight
.PHONY: deploy-mcp-sap deploy-mcp-maximo deploy-mcp-fdp deploy-mcp-servers
.PHONY: register-mcp-servers apply-gateway-policies enable-model-armor
.PHONY: setup-memory-bank seed-demo-sessions reset-and-seed
.PHONY: bq-create-tables
.PHONY: use-skin
.PHONY: evals evals-orchestrator evals-procurement evals-forecast
.PHONY: evals-capacity evals-plan-evaluator
.PHONY: clean

help:
	@echo "Available targets:"
	@echo "  setup                          Install dependencies (poetry install)"
	@echo "  auth                           Authenticate with GCP (ADC)"
	@echo "  test                           Run all tests (agents/tests/)"
	@echo "  coverage                       Run unit tests with coverage report (term-missing)"
	@echo "  verify                         Local pre-commit gate: lint + unit tests + coverage (no infra)"
	@echo "  lint                           Run ruff check + format check"
	@echo "  deploy-orchestrator-skeleton   Deploy the placeholder Orchestrator (TASK-01, alias of deploy-orchestrator)"
	@echo "  deploy-procurement-gate        Deploy Procurement Approval Agent (A2A, via deploy_a2a_agent_engine) (TASK-02)"
	@echo "  deploy-forecast-review         Deploy Forecast Review Agent (ADK CLI) (TASK-02)"
	@echo "  deploy-capacity-planning       Deploy Capacity Planning Agent (ADK CLI) (TASK-02)"
	@echo "  deploy-orchestrator            Deploy Capacity Orchestrator (ADK CLI) (TASK-02)"
	@echo "  deploy-all-agents              Deploy in dependency order: procurement → forecast/capacity → orchestrator"
	@echo "  setup-memory-bank              Seed Memory Bank with persona starting memories (TASK-07)"
	@echo "  seed-demo-sessions             Pre-create deterministic demo Sessions (TASK-07)"
	@echo "  reset-and-seed                 Run setup-memory-bank + seed-demo-sessions in order"
	@echo "  deploy                         Full deployment (TASK-13)"
	@echo "  teardown                       Destroy all resources (TASK-13)"
	@echo "  demo-cargo-plane               Run Persona 3 scenario (TASK-11)"
	@echo "  demo-forecast                  Run Persona 1 scenario (TASK-11)"
	@echo "  demo-fleet-buffer              Run Persona 2 scenario (TASK-11)"
	@echo "  demo-health                    Check endpoints (TASK-13)"
	@echo "  demo-preflight                 Run pre-demo verification suite (TASK-12)"
	@echo "  use-skin SKIN=<slug>           Compile a customer skin into the canvas (TASK-13)"
	@echo "  evals                          Run all agent eval suites (fast layer; add EVAL_FLAGS=--run-live-evals for live)"
	@echo "  evals-orchestrator             Run Orchestrator eval suite"
	@echo "  evals-procurement              Run Procurement Approval eval suite"
	@echo "  evals-forecast                 Run Forecast Review eval suite"
	@echo "  evals-capacity                 Run Capacity Planning eval suite"
	@echo "  evals-plan-evaluator           Run Plan Evaluator eval suite"
	@echo "  clean                          Remove local build artifacts (keeps venv/)"

setup:
	poetry install

auth:
	gcloud auth application-default login

test:
	$(DEPLOY_PYTHON) -m pytest agents/tests/

# Unit-only coverage. Integration tests are skipped here — they hit live
# Agent Engine / Memory Bank when their resource-name env vars are set, and
# we don't want their I/O reflected in unit coverage numbers.
#
# Uses $(DEPLOY_PYTHON) (venv-deploy-310) rather than `poetry run` because
# pyproject.toml pins python = "^3.11" while the deploy venv is 3.10 to
# match the Reasoning Engine runtime. Poetry would refuse to run from 3.10.
coverage:
	$(DEPLOY_PYTHON) -m pytest --cov=agents --cov-report=term-missing agents/tests/unit/

# Local pre-commit gate. Runs everything that does NOT require GCP creds or
# infra: ruff lint + format check, then unit tests with coverage in one pass.
# Use before pushing.
verify: lint coverage verify-no-json-reads

# TASK-16 Step 13 — static check that no agent production module reads
# data/*.json directly (every path now goes through MCP / BQ).
verify-no-json-reads:
	$(DEPLOY_PYTHON) scripts/verify_no_json_reads.py

# TASK-16 Step 13 — programmatic cargo-plane smoke (no LLM in path).
# Exercises every migrated skill tool with the Maria scenario inputs and
# asserts real data flows from BQ through the MCP backends. Requires the
# BQ datasets to be populated (Steps 1-4d).
.PHONY: smoke-cargo-plane verify-no-json-reads
smoke-cargo-plane:
	$(DEPLOY_PYTHON) scripts/smoke_cargo_plane.py

lint:
	$(DEPLOY_PYTHON) -m ruff check agents/
	$(DEPLOY_PYTHON) -m ruff format --check agents/

# Per-agent deploy targets (TASK-02)
# Order is enforced by deploy-all-agents: Procurement Gate first (so the
# Orchestrator can wire PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME), then the
# Gemini-Enterprise-facing agents, then the Orchestrator last.
#
# Deploys run from venv-deploy-310/ (Python 3.10), NOT venv/ (3.14). The
# deployed Reasoning Engine container is Python 3.10 and matching the local
# Python eliminates the pickle-arg-count mismatch (CLAUDE.md gotcha). The
# `python_version` AgentEngineConfig field is silently ignored by the API
# as of 2026-05-20, so the local Python must match the runtime. Bootstrap:
#   brew install python@3.10
#   /opt/homebrew/bin/python3.10 -m venv venv-deploy-310
#   source venv-deploy-310/bin/activate && pip install poetry && poetry install
#
# Programmatic deploys (NOT adk CLI) so we can pass extra_packages — the
# agent code imports agents.schemas / agents.utils which adk CLI doesn't stage.

DEPLOY_PYTHON := venv-deploy-310/bin/python

deploy-procurement-gate:
	$(DEPLOY_PYTHON) -m agents.procurement_approval_agent.deploy

deploy-forecast-review:
	$(DEPLOY_PYTHON) -m agents.forecast_review_agent.deploy

deploy-capacity-planning:
	$(DEPLOY_PYTHON) -m agents.capacity_planning_agent.deploy

deploy-orchestrator:
	$(DEPLOY_PYTHON) -m agents.orchestrator_agent.deploy

# Alias kept for TASK-01 backward compatibility
deploy-orchestrator-skeleton: deploy-orchestrator

deploy-all-agents: deploy-procurement-gate deploy-forecast-review deploy-capacity-planning deploy-orchestrator
	@echo ""
	@echo "========================================="
	@echo " All agents deployed."
	@echo " Capture resource names in your .env file (procurement first — the"
	@echo " Orchestrator's tools wire RemoteA2aAgent against"
	@echo " PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME)."
	@echo "========================================="

# ---------------------------------------------------------------------------
# TASK-07 — Memory Bank seeding + deterministic demo Sessions
# ---------------------------------------------------------------------------
#
# Run after `make deploy-all-agents` so the *_AGENT_RESOURCE_NAME env vars
# are populated. Both scripts run from venv-deploy-310/ — they need
# google-adk + Memory Bank/Sessions SDKs.

setup-memory-bank:
	$(DEPLOY_PYTHON) -m memory_bank.seed_memories

seed-demo-sessions:
	$(DEPLOY_PYTHON) -m memory_bank.seed_demo_sessions

reset-and-seed: setup-memory-bank seed-demo-sessions
	@echo "Memory Bank seeded + Sessions pre-warmed. Demo is reproducible."

deploy:
	@echo "Full deploy not yet implemented (TASK-13)"
	@exit 1

teardown:
	@echo "Teardown not yet implemented (TASK-13)"
	@exit 1

# ---------------------------------------------------------------------------
# Demo runner targets (TASK-12). Each invokes scripts/demo_runner.sh which:
#   1. Sets the active customer skin (default vs halliburton)
#   2. Verifies the deployed agent's resource name is in .env
#   3. Echoes the seed Memory Bank session id for the persona
#   4. Prints presenter URLs (canvas A2UI + GE App live-agent surface)
#   5. Starts the canvas dev server (or skips if port already in use)
#
# Optional env: SKIN=halliburton (default: default), CANVAS_PORT=3001,
# SKIP_CANVAS=1 to skip step 5 and just run the preflight.

DEMO_SKIN ?= default

demo-cargo-plane:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh maria cargo-plane $(DEMO_SKIN)

demo-forecast:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh david forecast-review $(DEMO_SKIN)

demo-fleet-buffer:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh tomas buffer-planning $(DEMO_SKIN)

demo-deep-research:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh priya deep-research $(DEMO_SKIN)

demo-agent-studio:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh rafael agent-studio $(DEMO_SKIN)

demo-audit:
	@SKIN=$(DEMO_SKIN) scripts/demo_runner.sh ayesha audit-registry $(DEMO_SKIN)

demo-health:
	@echo "Health check not yet implemented (TASK-13)"
	@exit 1

# TASK-12 Step 7 — pre-demo verification suite. Run 30-60 min before any
# customer demo. Checks BQ row counts, GCS corpus blobs, cargo-plane smoke,
# no-json-reads static check, and (if present) the canvas build. Two checks
# (Memory Profiles + recent Model Armor block) are advisory STUBs until
# v1.1. Exits 1 only on real FAILs.
demo-preflight:
	$(DEPLOY_PYTHON) scripts/demo_preflight.py

# ---------------------------------------------------------------------------
# Agent evals (TASK-EVALS)
# ---------------------------------------------------------------------------
#
# Per-agent eval suites live under agents/<agent>/evals/. Two layers:
#   - Fast (default): schema + evalset validity. <1s, $0, safe for CI.
#   - Live (EVAL_FLAGS=--run-live-evals): drives the deployed Reasoning Engine
#     via :streamQuery. Requires ADC + spends Gemini tokens.
#
# Run with the deploy venv (Python 3.10) — agents/utils/eval_helpers.py
# imports vertexai for the live layer. See docs/evals.md for full details.
#
# Examples:
#   make evals                                    # fast layer, all agents
#   make evals EVAL_FLAGS=--run-live-evals        # live layer, all agents
#   make evals-orchestrator                       # fast, Orchestrator only
#   make evals-orchestrator EVAL_FLAGS=--run-live-evals

EVAL_FLAGS ?=

evals: evals-orchestrator evals-procurement evals-forecast evals-capacity evals-plan-evaluator

evals-orchestrator:
	$(DEPLOY_PYTHON) -m pytest agents/orchestrator_agent/evals/ $(EVAL_FLAGS)

evals-procurement:
	$(DEPLOY_PYTHON) -m pytest agents/procurement_approval_agent/evals/ $(EVAL_FLAGS)

evals-forecast:
	$(DEPLOY_PYTHON) -m pytest agents/forecast_review_agent/evals/ $(EVAL_FLAGS)

evals-capacity:
	$(DEPLOY_PYTHON) -m pytest agents/capacity_planning_agent/evals/ $(EVAL_FLAGS)

evals-plan-evaluator:
	$(DEPLOY_PYTHON) -m pytest agents/orchestrator_agent/plan_evaluator/evals/ $(EVAL_FLAGS)

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache build dist
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./venv/*" -delete 2>/dev/null || true
	@echo "Cleaned local caches (venv/ preserved)"

# ---------------------------------------------------------------------------
# TASK-16 — BigQuery table creation
# ---------------------------------------------------------------------------
#
# Datasets are created out-of-band (Step 1, idempotent `bq mk --dataset`).
# This target creates the tables + WO_HISTORY view per scripts/bq/ddl/*.sql.
# Idempotent — every CREATE uses IF NOT EXISTS, the view uses CREATE OR REPLACE.

BQ_PROJECT ?= vertex-ai-demos-468803

bq-create-tables:
	@echo "Creating tables in $(BQ_PROJECT)..."
	bq --project_id=$(BQ_PROJECT) query --nouse_legacy_sql < scripts/bq/ddl/sap_extract.sql
	bq --project_id=$(BQ_PROJECT) query --nouse_legacy_sql < scripts/bq/ddl/maximo_extract.sql
	bq --project_id=$(BQ_PROJECT) query --nouse_legacy_sql < scripts/bq/ddl/fdp_extract.sql
	bq --project_id=$(BQ_PROJECT) query --nouse_legacy_sql < scripts/bq/ddl/oilfield_kc.sql
	bq --project_id=$(BQ_PROJECT) query --nouse_legacy_sql < scripts/bq/ddl/public_datasets.sql
	@echo "All tables created. Verify with: bq ls $(BQ_PROJECT):sap_extract"

# ---------------------------------------------------------------------------
# TASK-05 — MCP servers via Agent Registry + Agent Gateway
# ---------------------------------------------------------------------------
#
# Production rollout sequence (run these from the repo root, with the venv
# active and gcloud authenticated to the target project):
#
#   1. make deploy-mcp-servers      — build + deploy SAP, Maximo, FDP to Cloud Run
#   2. make register-mcp-servers    — register all four MCP servers (incl. KC) with Agent Registry
#   3. make apply-gateway-policies  — push Agent Gateway authorization policies
#   4. make enable-model-armor      — create + attach the Model Armor template
#
# Each target is idempotent — re-running is safe.
#
# Required env vars (the .env file produced by terraform / earlier tasks):
#   GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION,
#   SAP_MCP_URL, MAXIMO_MCP_URL, FDP_MCP_URL  (set after deploy-mcp-servers)

GCLOUD_REGION ?= us-central1

deploy-mcp-sap:
	gcloud builds submit --config mcp_servers/sap/cloudbuild.yaml --substitutions=_REGION=$(GCLOUD_REGION) .

deploy-mcp-maximo:
	gcloud builds submit --config mcp_servers/maximo/cloudbuild.yaml --substitutions=_REGION=$(GCLOUD_REGION) .

deploy-mcp-fdp:
	gcloud builds submit --config mcp_servers/fdp/cloudbuild.yaml --substitutions=_REGION=$(GCLOUD_REGION) .

deploy-mcp-servers: deploy-mcp-sap deploy-mcp-maximo deploy-mcp-fdp
	@echo ""
	@echo "========================================="
	@echo " All three MCP servers built + deployed."
	@echo " Next: capture URLs into .env, then run:"
	@echo "   make register-mcp-servers"
	@echo "========================================="

register-mcp-servers:
	poetry run python scripts/register_mcp_servers.py

# Agent Gateway policies are applied via the `gcloud agent-platform` CLI
# (in Preview as of 2026-05). If the CLI surface lands under a different
# verb name, update here. For now we shell out with envsubst to resolve
# ${PROJECT} / ${LOCATION} placeholders in the YAML.
apply-gateway-policies:
	@if [ -z "$$GOOGLE_CLOUD_PROJECT" ]; then echo "GOOGLE_CLOUD_PROJECT is required"; exit 1; fi
	@PROJECT=$$GOOGLE_CLOUD_PROJECT LOCATION=$${GOOGLE_CLOUD_LOCATION:-$(GCLOUD_REGION)} \
		envsubst < infra/gateway_policies.yaml > /tmp/gateway_policies.resolved.yaml
	gcloud agent-platform gateway-policies apply \
		--policy-file=/tmp/gateway_policies.resolved.yaml \
		--project=$$GOOGLE_CLOUD_PROJECT \
		--location=$${GOOGLE_CLOUD_LOCATION:-$(GCLOUD_REGION)}

# Model Armor template import + attach.
enable-model-armor:
	@if [ -z "$$GOOGLE_CLOUD_PROJECT" ]; then echo "GOOGLE_CLOUD_PROJECT is required"; exit 1; fi
	@PROJECT=$$GOOGLE_CLOUD_PROJECT LOCATION=$${GOOGLE_CLOUD_LOCATION:-$(GCLOUD_REGION)} \
		envsubst < infra/model_armor.yaml > /tmp/model_armor.resolved.yaml
	gcloud model-armor templates import oilfield-services-mcp-template \
		--source=/tmp/model_armor.resolved.yaml \
		--project=$$GOOGLE_CLOUD_PROJECT \
		--location=$${GOOGLE_CLOUD_LOCATION:-$(GCLOUD_REGION)}

# ---------------------------------------------------------------------------
# TASK-13 — Customer skin compile + swap
# ---------------------------------------------------------------------------
#
# Compiles skins/<slug>/customer.yaml into canvas/src/data/skin.generated.ts
# and refreshes canvas/public/skin.json. Sets NEXT_PUBLIC_CUSTOMER_SKIN in
# .env.skin so a subsequent `cd canvas && npm run dev` picks up the new skin.
#
# Usage:
#   make use-skin SKIN=default
#   make use-skin SKIN=halliburton
#
# Run from the repo root. After this target completes, re-run the canvas
# build/dev server. If a dev server is already running, hot-reload picks up
# the regenerated TS file automatically.
use-skin:
	@if [ -z "$(SKIN)" ]; then echo "Usage: make use-skin SKIN=<slug>"; exit 1; fi
	@if [ ! -d "skins/$(SKIN)" ]; then echo "Skin not found: skins/$(SKIN)"; exit 1; fi
	@echo "Compiling skin: $(SKIN)"
	$(DEPLOY_PYTHON) scripts/compile_skin.py --skin $(SKIN)
	@echo "NEXT_PUBLIC_CUSTOMER_SKIN=$(SKIN)" > .env.skin
	@echo ""
	@echo "Skin compiled. To rebuild the canvas with this skin:"
	@echo "  cd canvas && NEXT_PUBLIC_CUSTOMER_SKIN=$(SKIN) npm run build"
	@echo "Or just restart the dev server — hot-reload picks up skin.generated.ts."
