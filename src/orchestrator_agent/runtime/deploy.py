"""Deploy the Capacity Orchestrator Agent to Vertex AI Agent Engine.

For TASK-02 the Orchestrator is deployed via the ADK CLI path (`adk deploy
agent_engine`) — see Makefile target `deploy-orchestrator`. The CLI deploys
the bare root_agent without an `agent_card` attribute, so the Pydantic-
AgentCard / protobuf bug (handled by src/utils/deploy.py for the other A2A
sub-agents) is not triggered here.

This module exists so the per-agent layout is uniform across agents and to
host a programmatic deploy entrypoint that mirrors the CLI behaviour. The
CLI is the primary path because it auto-resolves dependencies and
generates `agent_engine_app.py`; this script is here for parity.

Usage:
    poetry run python -m src.orchestrator_agent.runtime.deploy
"""

import logging
import os

import vertexai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def _env_vars(agent_engine_id: str, location: str) -> dict[str, str]:
    """Build env_vars baked into the deployed Orchestrator runtime.

    Includes every sibling-agent resource name so tools.py can wire the
    A2A RemoteA2aAgent at startup. Empty/unset names are skipped.
    """
    out: dict[str, str] = {
        "AGENT_ENGINE_ID": agent_engine_id,
        "AGENT_ENGINE_LOCATION": location,
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "ORCHESTRATOR_MODEL": os.environ.get(
            "ORCHESTRATOR_MODEL", "gemini-3.1-pro-preview"
        ),
    }
    for var in (
        "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME",
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME",
        "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
    ):
        value = os.environ.get(var)
        if value:
            out[var] = value
    return out


def deploy_orchestrator() -> str:
    """Deploy the Orchestrator's root_agent to Agent Engine.

    Returns the full reasoning-engine resource name.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")

    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    from ..core.agent import root_agent
    from ..services.memory_manager import create_orchestrator_memory_topics

    print("=" * 60)
    print("Deploying Capacity Orchestrator Agent to Vertex AI Agent Engine")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (Agent Engine; model calls use 'global')")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    client = vertexai.Client(project=project_id, location=location)
    memory_config = create_orchestrator_memory_topics()

    print("Step 1: Creating Agent Engine with Memory Bank...")
    created = client.agent_engines.create(
        config={
            "staging_bucket": staging_bucket,
            "display_name": "Capacity Orchestrator Agent",
            "description": (
                "Lead architect for service capacity gap resolution. Coordinates "
                "Plan Evaluator and Procurement Approval Agent."
            ),
            "context_spec": {"memory_bank_config": {"customization_configs": [memory_config]}},
        }
    )
    resource_name = created.api_resource.name
    agent_engine_id = resource_name.split("/")[-1]
    print(f"Agent Engine created with ID: {agent_engine_id}")

    print("\nStep 2: Uploading agent code + dependencies...")
    client.agent_engines.update(
        name=resource_name,
        agent=root_agent,
        config={
            "staging_bucket": staging_bucket,
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk,evaluation]>=1.121.0",
                "google-adk==1.33.0",
                "a2a-sdk>=0.3.9,<1.0",
                "pydantic>=2.12.0",
                "python-dotenv>=1.0.0",
            ],
            "extra_packages": ["src/orchestrator_agent", "src/utils", "src/schemas.py"],
            "env_vars": _env_vars(agent_engine_id, location),
        },
    )

    print(f"\n{'=' * 60}")
    print("Capacity Orchestrator Agent deployed successfully!")
    print(f"{'=' * 60}")
    print(f"Agent Resource Name: {resource_name}")
    print(f"Agent Engine ID: {agent_engine_id}")
    print()
    print("Add this to your .env file:")
    print(f'ORCHESTRATOR_AGENT_RESOURCE_NAME="{resource_name}"')
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_orchestrator()
