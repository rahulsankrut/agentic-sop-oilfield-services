# Oilfield Services Domain Pack — Makefile
#
# Activate the venv first: `source venv/bin/activate`. All `poetry run …`
# targets assume the venv is active (per CLAUDE.md, we use venv/ + Poetry,
# not uv).

.PHONY: help setup auth test lint
.PHONY: deploy-orchestrator-skeleton deploy-orchestrator
.PHONY: deploy-procurement-gate deploy-forecast-review deploy-capacity-planning
.PHONY: deploy-all-agents
.PHONY: deploy teardown
.PHONY: demo-cargo-plane demo-forecast demo-fleet-buffer demo-health
.PHONY: deploy-mcp-sap deploy-mcp-maximo deploy-mcp-fdp deploy-mcp-servers
.PHONY: register-mcp-servers apply-gateway-policies enable-model-armor
.PHONY: clean

help:
	@echo "Available targets:"
	@echo "  setup                          Install dependencies (poetry install)"
	@echo "  auth                           Authenticate with GCP (ADC)"
	@echo "  test                           Run unit tests"
	@echo "  lint                           Run ruff check + format check"
	@echo "  deploy-orchestrator-skeleton   Deploy the placeholder Orchestrator (TASK-01, alias of deploy-orchestrator)"
	@echo "  deploy-procurement-gate        Deploy Procurement Approval Agent (A2A, via deploy_a2a_agent_engine) (TASK-02)"
	@echo "  deploy-forecast-review         Deploy Forecast Review Agent (ADK CLI) (TASK-02)"
	@echo "  deploy-capacity-planning       Deploy Capacity Planning Agent (ADK CLI) (TASK-02)"
	@echo "  deploy-orchestrator            Deploy Capacity Orchestrator (ADK CLI) (TASK-02)"
	@echo "  deploy-all-agents              Deploy in dependency order: procurement → forecast/capacity → orchestrator"
	@echo "  deploy                         Full deployment (TASK-13)"
	@echo "  teardown                       Destroy all resources (TASK-13)"
	@echo "  demo-cargo-plane               Run Persona 3 scenario (TASK-11)"
	@echo "  demo-forecast                  Run Persona 1 scenario (TASK-11)"
	@echo "  demo-fleet-buffer              Run Persona 2 scenario (TASK-11)"
	@echo "  demo-health                    Check endpoints (TASK-13)"
	@echo "  clean                          Remove local build artifacts (keeps venv/)"

setup:
	poetry install

auth:
	gcloud auth application-default login

test:
	poetry run pytest tests/

lint:
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/

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
# agent code imports src.schemas / src.utils which adk CLI doesn't stage.

DEPLOY_PYTHON := venv-deploy-310/bin/python

deploy-procurement-gate:
	$(DEPLOY_PYTHON) -m src.procurement_approval_agent.runtime.deploy

deploy-forecast-review:
	$(DEPLOY_PYTHON) -m src.forecast_review_agent.runtime.deploy

deploy-capacity-planning:
	$(DEPLOY_PYTHON) -m src.capacity_planning_agent.runtime.deploy

deploy-orchestrator:
	$(DEPLOY_PYTHON) -m src.orchestrator_agent.runtime.deploy

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
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache build dist
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./venv/*" -delete 2>/dev/null || true
	@echo "Cleaned local caches (venv/ preserved)"

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
