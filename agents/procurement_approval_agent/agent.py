"""Procurement Approval Agent — fast deterministic approval gate.

Reviews SourcingPlans for procurement readiness: budget threshold, customer
authorization, certification, regulatory clearance. Returns
``ProcurementApproval``.

This is NOT a quality check (that's the Plan Evaluator). This is a
prerequisite check — does the plan have everything needed to commit dollars?

Deployed to Vertex AI Agent Engine, exposed via A2A (wrapped in ``A2aAgent``
by ``runtime/deploy.py``). Called by the Capacity Orchestrator via
``RemoteA2aAgent``.
"""

import os

import vertexai
from google.adk.agents import LlmAgent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import ProcurementApproval
from agents.utils.global_gemini import GlobalGemini

from .config import AGENT_DESCRIPTION, AGENT_NAME, MODEL_NAME
from .prompts import INSTRUCTION
from .services.memory_manager import auto_save_memories
from .tools import get_tools

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
    "GOOGLE_CLOUD_LOCATION", "us-central1"
)
if project_id:
    vertexai.init(project=project_id, location=location)


# DEMO NARRATION: "The Procurement Approval Agent is the final gate before
# logistics dollars commit. Fast — no LLM reasoning depth needed, just
# deterministic prerequisite checks. Runs on Agent Engine. Called by the
# Orchestrator via A2A — the same protocol that bridges to SAP Joule agents."
root_agent = LlmAgent(
    name=AGENT_NAME,
    model=GlobalGemini(model=MODEL_NAME),
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    output_schema=ProcurementApproval,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=0),  # no thinking — speed matters
        max_output_tokens=2048,
    ),
    after_agent_callback=auto_save_memories,
    tools=[*get_tools(), preload_memory],
)
