"""Deploy the Capacity Orchestrator Agent to Vertex AI Agent Engine via A2A.

Switched from ``AdkApp`` to ``A2aAgent`` for TASK-10. The A2A wrapper
exposes ``/a2a/v1/message:stream`` which the canvas consumes as an SSE
stream of canvas events emitted by the underlying Workflow.

Pattern matches ``src/procurement_approval_agent/runtime/deploy.py`` —
same Pydantic-AgentCard / protobuf bug applies, handled by
``src.utils.deploy:deploy_a2a_agent_engine`` (see CLAUDE.md "Agent Engine
deploy of A2aAgent" gotcha).

Usage:
    poetry run python -m src.orchestrator_agent.runtime.deploy
"""

import logging
import os

from a2a.types import TransportProtocol
from dotenv import load_dotenv
from vertexai.preview.reasoning_engines import A2aAgent

from src.utils.deploy import deploy_a2a_agent_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def _env_vars(location: str) -> dict[str, str]:
    """Build env_vars baked into the deployed Orchestrator runtime.

    Includes every sibling-agent resource name so tools.py can wire the
    A2A ``RemoteA2aAgent`` at startup. Empty/unset names are skipped.
    """
    out: dict[str, str] = {
        "AGENT_ENGINE_LOCATION": location,
        "GOOGLE_GENAI_USE_VERTEXAI": "true",
        "ORCHESTRATOR_MODEL": os.environ.get("ORCHESTRATOR_MODEL", "gemini-3.1-pro-preview"),
        # Per-LLM-node model env vars — Cloud Run / Agent Engine doesn't
        # inherit them from the local shell, so we have to plumb them
        # explicitly here (mirrors what terraform does for the other
        # agents). Defaults match the in-code defaults so unset vars
        # still get a sensible model.
        "EQUIVALENCE_LOOKUP_MODEL": os.environ.get(
            "EQUIVALENCE_LOOKUP_MODEL", "gemini-3.1-pro-preview"
        ),
        "SOURCING_LOGISTICS_MODEL": os.environ.get(
            "SOURCING_LOGISTICS_MODEL", "gemini-3.1-pro-preview"
        ),
        "REVISE_PLAN_MODEL": os.environ.get(
            "REVISE_PLAN_MODEL", "gemini-3.1-pro-preview"
        ),
        "EVALUATOR_MODEL": os.environ.get(
            "EVALUATOR_MODEL", "gemini-3.1-pro-preview"
        ),
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
    """Deploy the Orchestrator's root_agent to Agent Engine, A2A-wrapped.

    Returns the full reasoning-engine resource name. The SSE URL is then::

        https://<location>-aiplatform.googleapis.com/v1beta1/<resource>/a2a/v1/message:stream

    The canvas reads this from ``ORCHESTRATOR_STREAM_URL`` in ``.env`` —
    operator pastes the URL after the deploy succeeds.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")

    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    # Imports are lazy so the Pydantic patch in deploy_a2a_agent_engine
    # fires before vertexai's buggy code path is touched, and so the
    # heavy ADK Workflow import doesn't happen at module import time.
    from .agent_card import create_orchestrator_card
    from .agent_executor import CapacityOrchestratorExecutor
    from ..services.memory_manager import create_orchestrator_memory_topics

    agent_card = create_orchestrator_card()
    # A2aAgent only accepts HTTP+JSON transport. SSE is layered on top of
    # the HTTP transport via the ``message:stream`` endpoint — there's no
    # separate transport type for it.
    agent_card.preferred_transport = TransportProtocol.http_json

    a2a_agent = A2aAgent(
        agent_card=agent_card,
        agent_executor_builder=CapacityOrchestratorExecutor,
    )

    memory_config = create_orchestrator_memory_topics()

    print("=" * 60)
    print("Deploying Capacity Orchestrator Agent to Vertex AI Agent Engine (A2A)")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (Agent Engine; model calls use 'global')")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    resource_name = deploy_a2a_agent_engine(
        agent=a2a_agent,
        display_name="Capacity Orchestrator Agent",
        description=(
            "Lead architect for service capacity gap resolution. Coordinates "
            "Plan Evaluator and Procurement Approval Agent. Streams canvas "
            "events via the A2A message:stream SSE endpoint."
        ),
        extra_packages=["src/orchestrator_agent", "src/utils", "src/schemas.py"],
        requirements=[
            "google-cloud-aiplatform[agent_engines,evaluation]>=1.121.0",
            "google-adk>=2.0.0,<2.1",
            "a2a-sdk[http-server]>=0.3.9,<1.0",
            "pydantic>=2.12.0",
            "python-dotenv>=1.0.0",
        ],
        env_vars=_env_vars(location),
        context_spec={"memory_bank_config": {"customization_configs": [memory_config]}},
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    print(f"\n{'=' * 60}")
    print("Capacity Orchestrator Agent deployed successfully!")
    print(f"{'=' * 60}")
    print(f"Resource: {resource_name}")
    print()
    print("Add this to your .env file:")
    print(f'ORCHESTRATOR_AGENT_RESOURCE_NAME="{resource_name}"')
    print(
        f"ORCHESTRATOR_STREAM_URL=\""
        f"https://{location}-aiplatform.googleapis.com/v1beta1/{resource_name}"
        f"/a2a/v1/message:stream\""
    )
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_orchestrator()
