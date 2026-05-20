"""Deploy the Capacity Orchestrator Agent to Vertex AI Agent Engine.

Deployed as ``AdkApp``. The Orchestrator's Workflow nodes emit canvas
events into ``ctx.state["canvas_events"]`` via ``src.orchestrator_agent.
events.emit``; ``AdkApp.async_stream_query`` (the body of the deployed
``streamQuery`` REST endpoint) yields every ADK ``Event`` including the
``actions.state_delta`` payload, so the canvas reads canvas events from
that stream directly. No A2A wrap is needed on the inbound side.

(The Orchestrator is still an A2A *client* of the Procurement Approval
Agent — that lives in ``core/tools.py`` via ``RemoteA2aAgent``. We only
deploy Procurement as ``A2aAgent`` because it's the customer-facing
demonstration of the A2A protocol, not an architectural necessity.)

Usage:
    poetry run python -m agents.orchestrator_agent.deploy
"""

from __future__ import annotations

import logging
import os

import vertexai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def _env_vars(agent_engine_id: str, location: str) -> dict[str, str]:
    """Build the env dict baked into the deployed runtime.

    Threads sibling-agent resource names so ``core/tools.py`` can wire
    the ``RemoteA2aAgent`` calling into Procurement. Per-LLM model env
    vars carry the model selection that ``core/nodes/*.py`` reads at
    import time. Empty / unset values are skipped.
    """
    out: dict[str, str] = {
        "AGENT_ENGINE_ID": agent_engine_id,
        "AGENT_ENGINE_LOCATION": location,
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "ORCHESTRATOR_MODEL": os.environ.get("ORCHESTRATOR_MODEL", "gemini-3.1-pro-preview"),
        "EQUIVALENCE_LOOKUP_MODEL": os.environ.get(
            "EQUIVALENCE_LOOKUP_MODEL", "gemini-3.1-pro-preview"
        ),
        "SOURCING_LOGISTICS_MODEL": os.environ.get(
            "SOURCING_LOGISTICS_MODEL", "gemini-3.1-pro-preview"
        ),
        "REVISE_PLAN_MODEL": os.environ.get("REVISE_PLAN_MODEL", "gemini-3.1-pro-preview"),
        "EVALUATOR_MODEL": os.environ.get("EVALUATOR_MODEL", "gemini-3.1-pro-preview"),
    }
    for var in (
        "PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME",
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME",
        "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
        "AGENT_GATEWAY_ENDPOINT",
    ):
        value = os.environ.get(var)
        if value:
            out[var] = value
    return out


def deploy_orchestrator() -> str:
    """Deploy the Orchestrator's ``root_agent`` to Agent Engine via AdkApp.

    Returns the full reasoning-engine resource name. The streamQuery URL
    that the canvas consumes is::

        https://<location>-aiplatform.googleapis.com/v1beta1/<resource>:streamQuery

    Operator captures that URL into ``canvas/.env.local`` as
    ``NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL`` after deploy.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")

    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    # Lazy import — heavy ADK + Workflow graph; keeps module-load fast.
    from vertexai.preview.reasoning_engines import AdkApp

    from ..agent import root_agent
    from ..services.memory_manager import create_orchestrator_memory_topics

    adk_app = AdkApp(agent=root_agent, enable_tracing=False)
    memory_config = create_orchestrator_memory_topics()

    print("=" * 60)
    print("Deploying Capacity Orchestrator Agent to Vertex AI Agent Engine")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (Agent Engine; model calls use 'global')")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    client = vertexai.Client(project=project_id, location=location)

    print("Step 1: Creating Agent Engine with Memory Bank...")
    created = client.agent_engines.create(
        config={
            "staging_bucket": staging_bucket,
            "display_name": "Capacity Orchestrator Agent",
            "description": (
                "Lead architect for service capacity gap resolution. Coordinates "
                "Plan Evaluator and Procurement Approval Agent. Emits canvas "
                "events via session state_delta on every Workflow step; the "
                "canvas consumes them off the deployed streamQuery endpoint."
            ),
            "context_spec": {
                "memory_bank_config": {"customization_configs": [memory_config]},
            },
        }
    )
    resource_name = created.api_resource.name
    agent_engine_id = resource_name.split("/")[-1]
    print(f"Agent Engine created with ID: {agent_engine_id}")

    print("\nStep 2: Uploading agent code + dependencies...")
    client.agent_engines.update(
        name=resource_name,
        agent=adk_app,
        config={
            "staging_bucket": staging_bucket,
            "requirements": [
                "google-cloud-aiplatform[agent_engines,evaluation]>=1.121.0",
                "google-adk>=2.0.0,<2.1",
                "a2a-sdk[http-server]>=0.3.9,<1.0",
                "pydantic>=2.12.0",
                "python-dotenv>=1.0.0",
            ],
            "extra_packages": [
                "agents/orchestrator_agent",
                "agents/utils",
                "agents/schemas.py",
            ],
            "env_vars": _env_vars(agent_engine_id, location),
        },
    )

    stream_url = f"https://{location}-aiplatform.googleapis.com/v1beta1/{resource_name}:streamQuery"

    print(f"\n{'=' * 60}")
    print("Capacity Orchestrator Agent deployed!")
    print(f"{'=' * 60}")
    print(f"Resource: {resource_name}")
    print()
    print("Add to .env:")
    print(f'ORCHESTRATOR_AGENT_RESOURCE_NAME="{resource_name}"')
    print()
    print("Add to canvas/.env.local for Live mode:")
    print(f'NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL="{stream_url}"')
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_orchestrator()
