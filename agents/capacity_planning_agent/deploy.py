"""Deploy the Capacity Planning Agent to Vertex AI Agent Engine.

Same shape as ``src/forecast_review_agent/runtime/deploy.py`` — programmatic
deploy with ``extra_packages`` so the runtime can import ``src.schemas``,
``src.utils.*``. No A2A wrapping (called directly from Gemini Enterprise).

Usage:
    poetry run python -m agents.capacity_planning_agent.deploy
"""

from __future__ import annotations

import logging
import os

import vertexai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def deploy_capacity_planning() -> str:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")
    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    from vertexai.preview.reasoning_engines import AdkApp

    from .agent import root_agent
    from .services.memory_manager import create_capacity_planning_memory_topics

    adk_app = AdkApp(agent=root_agent, enable_tracing=False)

    print("=" * 60)
    print("Deploying Capacity Planning Agent to Vertex AI Agent Engine")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (model calls use 'global' via GlobalGemini)")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    client = vertexai.Client(project=project_id, location=location)
    memory_config = create_capacity_planning_memory_topics()

    print("Step 1: Creating Agent Engine with Memory Bank...")
    created = client.agent_engines.create(
        config={
            "staging_bucket": staging_bucket,
            "display_name": "Capacity Planning Agent",
            "description": (
                "Risk-calibrated buffer recommendations grounded in per-basin "
                "actual-vs-requested start-date variance."
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
                "agents/capacity_planning_agent",
                "agents/utils",
                "agents/schemas.py",
            ],
            "env_vars": {
                k: v
                for k, v in {
                    "AGENT_ENGINE_ID": agent_engine_id,
                    "AGENT_ENGINE_LOCATION": location,
                    "GOOGLE_GENAI_USE_VERTEXAI": "true",
                    "CAPACITY_PLANNING_MODEL": os.environ.get(
                        "CAPACITY_PLANNING_MODEL", "gemini-3-flash-preview"
                    ),
                    # Vertex AI Search (Discovery Engine) — Phase 3 RAG.
                    "DISCOVERY_ENGINE_PROJECT": os.environ.get("DISCOVERY_ENGINE_PROJECT"),
                    "DISCOVERY_ENGINE_LOCATION": os.environ.get("DISCOVERY_ENGINE_LOCATION"),
                    "BSEE_ENGINE_ID": os.environ.get("BSEE_ENGINE_ID"),
                    "MCC_ENGINE_ID": os.environ.get("MCC_ENGINE_ID"),
                    "INTOUCH_ENGINE_ID": os.environ.get("INTOUCH_ENGINE_ID"),
                }.items()
                if v
            },
        },
    )

    print(f"\n{'=' * 60}")
    print("Capacity Planning Agent deployed!")
    print(f"{'=' * 60}")
    print(f"Resource: {resource_name}")
    print(f'\nCAPACITY_PLANNING_AGENT_RESOURCE_NAME="{resource_name}"')
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_capacity_planning()
