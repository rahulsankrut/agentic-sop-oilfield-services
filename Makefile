# Oilfield Services Domain Pack — Makefile
#
# Activate the venv first: `source venv/bin/activate`. All `poetry run …`
# targets assume the venv is active (per CLAUDE.md, we use venv/ + Poetry,
# not uv).

.PHONY: help setup auth test lint
.PHONY: deploy-orchestrator-skeleton
.PHONY: deploy teardown
.PHONY: demo-cargo-plane demo-forecast demo-fleet-buffer demo-health
.PHONY: clean

help:
	@echo "Available targets:"
	@echo "  setup                          Install dependencies (poetry install)"
	@echo "  auth                           Authenticate with GCP (ADC)"
	@echo "  test                           Run unit tests"
	@echo "  lint                           Run ruff check + format check"
	@echo "  deploy-orchestrator-skeleton   Deploy the placeholder Orchestrator to Agent Engine (TASK-01)"
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

deploy-orchestrator-skeleton:
	poetry run adk deploy agent_engine \
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
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache build dist
	find . -type d -name __pycache__ -not -path "./venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./venv/*" -delete 2>/dev/null || true
	@echo "Cleaned local caches (venv/ preserved)"
