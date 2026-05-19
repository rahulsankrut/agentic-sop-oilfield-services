"""Deploy the Forecast Review Agent to Vertex AI Agent Engine.

Programmatic deploy (not the ``adk deploy agent_engine`` CLI) so we can
declare ``extra_packages=[src/forecast_review_agent, src/utils, src/schemas.py]``
— the CLI only stages the agent's own directory and the runtime then can't
``from src.schemas import ForecastRationale``.

No A2A wrapping (this agent is called directly from Gemini Enterprise via
the standard ADK query API), so we don't need ``src.utils.deploy``'s patch.

Usage:
    poetry run python -m src.forecast_review_agent.runtime.deploy
"""

from __future__ import annotations

import logging
import os

import vertexai
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def deploy_forecast_review() -> str:
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")
    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    from ..core.agent import root_agent
    from ..services.memory_manager import create_forecast_review_memory_topics

    print("=" * 60)
    print("Deploying Forecast Review Agent to Vertex AI Agent Engine")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (model calls use 'global' via GlobalGemini)")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    client = vertexai.Client(project=project_id, location=location)
    memory_config = create_forecast_review_memory_topics()

    print("Step 1: Creating Agent Engine with Memory Bank...")
    created = client.agent_engines.create(
        config={
            "staging_bucket": staging_bucket,
            "display_name": "Forecast Review Agent",
            "description": (
                "Captures rationale tags from basin-leader forecast overrides; "
                "writes back to BigQuery for the next model retrain."
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
            "extra_packages": ["src/forecast_review_agent", "src/utils", "src/schemas.py"],
            "env_vars": {
                "AGENT_ENGINE_ID": agent_engine_id,
                "AGENT_ENGINE_LOCATION": location,
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "FORECAST_REVIEW_MODEL": os.environ.get(
                    "FORECAST_REVIEW_MODEL", "gemini-3-flash-preview"
                ),
            },
        },
    )

    print(f"\n{'=' * 60}")
    print("Forecast Review Agent deployed!")
    print(f"{'=' * 60}")
    print(f"Resource: {resource_name}")
    print(f'\nFORECAST_REVIEW_AGENT_RESOURCE_NAME="{resource_name}"')
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_forecast_review()
