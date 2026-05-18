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

deploy-procurement-gate:
	poetry run python -m src.procurement_approval_agent.runtime.deploy

deploy-forecast-review:
	poetry run adk deploy agent_engine \
		--env_file src/forecast_review_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/forecast_review_agent

deploy-capacity-planning:
	poetry run adk deploy agent_engine \
		--env_file src/capacity_planning_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/capacity_planning_agent

deploy-orchestrator:
	poetry run adk deploy agent_engine \
		--env_file src/orchestrator_agent/.env \
		--region=$${GOOGLE_CLOUD_LOCATION:-us-central1} \
		src/orchestrator_agent

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
