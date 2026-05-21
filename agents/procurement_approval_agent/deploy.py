"""Deploy the Procurement Approval Agent to Vertex AI Agent Engine via A2A.

This is the agent the Capacity Orchestrator calls via ``RemoteA2aAgent``.
The deployed agent therefore must expose an A2A endpoint — which means
wrapping the root_agent in ``vertexai.preview.reasoning_engines.A2aAgent``.

That wrapping triggers the Pydantic-AgentCard ↔ protobuf bug in
``vertexai._genai._agent_engines_utils``. ``src.utils.deploy:
deploy_a2a_agent_engine`` patches around it. See CLAUDE.md "Agent Engine
deploy of A2aAgent" gotcha.

Usage:
    poetry run python -m agents.procurement_approval_agent.deploy
"""

import logging
import os

from a2a.types import TransportProtocol
from dotenv import load_dotenv
from vertexai.preview.reasoning_engines import A2aAgent

from agents.utils.deploy import deploy_a2a_agent_engine

from .services.memory_manager import create_procurement_approval_memory_topics

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
load_dotenv()
logger = logging.getLogger(__name__)


def deploy_procurement_approval() -> str:
    """Deploy the Procurement Approval Agent to Agent Engine with A2A.

    Returns the full reasoning-engine resource name.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    staging_bucket = os.environ.get("BUCKET_URI")

    if not all([project_id, staging_bucket]):
        raise ValueError("Set GOOGLE_CLOUD_PROJECT and BUCKET_URI in .env file")

    # Imports lazy so the patch in src.utils.deploy fires before vertexai's
    # buggy code path is touched.
    from .agent_card import create_procurement_approval_card
    from .agent_executor import ProcurementApprovalExecutor

    agent_card = create_procurement_approval_card()
    agent_card.preferred_transport = TransportProtocol.http_json

    a2a_agent = A2aAgent(
        agent_card=agent_card,
        agent_executor_builder=ProcurementApprovalExecutor,
    )

    memory_config = create_procurement_approval_memory_topics()

    print("=" * 60)
    print("Deploying Procurement Approval Agent to Vertex AI Agent Engine")
    print("=" * 60)
    print(f"Project: {project_id}")
    print(f"Location: {location}  (Agent Engine; model calls use 'global')")
    print(f"Staging Bucket: {staging_bucket}")
    print()

    resource_name = deploy_a2a_agent_engine(
        agent=a2a_agent,
        display_name="Procurement Approval Agent",
        description=(
            "Reviews oilfield-services SourcingPlans for procurement readiness "
            "(budget, customer authorization, certification, regulatory)."
        ),
        extra_packages=[
            "agents/procurement_approval_agent",
            "agents/utils",
            "agents/schemas.py",
            # TASK-13 Step 5 skin data — see orchestrator_agent/deploy.py.
            "skins/default",
            "skins/halliburton",
        ],
        requirements=[
            "google-cloud-aiplatform[agent_engines,evaluation]>=1.121.0",
            "google-adk>=2.0.0,<2.1",
            "a2a-sdk[http-server]>=0.3.9,<1.0",
                # Required by google.adk.tools.mcp_tool.mcp_toolset
                # (McpToolset → SamplingCapability from `mcp` SDK).
                "mcp>=1.0.0,<2.0",
            "pydantic>=2.12.0",
            "python-dotenv>=1.0.0",
        ],
        env_vars={
            k: v
            for k, v in {
                "AGENT_ENGINE_LOCATION": location,
                "GOOGLE_GENAI_USE_VERTEXAI": "true",
                "PROCUREMENT_APPROVAL_MODEL": os.environ.get(
                    "PROCUREMENT_APPROVAL_MODEL", "gemini-3-flash-preview"
                ),
                # Vertex AI Search (Discovery Engine) — Phase 3 RAG.
                "DISCOVERY_ENGINE_PROJECT": os.environ.get("DISCOVERY_ENGINE_PROJECT"),
                "DISCOVERY_ENGINE_LOCATION": os.environ.get("DISCOVERY_ENGINE_LOCATION"),
                "BSEE_ENGINE_ID": os.environ.get("BSEE_ENGINE_ID"),
                "MCC_ENGINE_ID": os.environ.get("MCC_ENGINE_ID"),
                                "INTOUCH_ENGINE_ID": os.environ.get("INTOUCH_ENGINE_ID"),
                # MCP server URLs — for McpToolset on agents.
                "SAP_MCP_URL": os.environ.get("SAP_MCP_URL"),
                "MAXIMO_MCP_URL": os.environ.get("MAXIMO_MCP_URL"),
                "FDP_MCP_URL": os.environ.get("FDP_MCP_URL"),
            }.items()
            if v
        },
        context_spec={"memory_bank_config": {"customization_configs": [memory_config]}},
        project=project_id,
        location=location,
        staging_bucket=staging_bucket,
    )

    print(f"\n{'=' * 60}")
    print("Procurement Approval Agent deployed!")
    print(f"{'=' * 60}")
    print(f"Resource: {resource_name}")
    print()
    print("Add this to .env so the Orchestrator can wire the A2A tool:")
    print(f'PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME="{resource_name}"')
    print("=" * 60)
    return resource_name


if __name__ == "__main__":
    deploy_procurement_approval()
