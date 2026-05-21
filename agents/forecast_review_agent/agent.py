"""Forecast Review Agent — captures rationale on basin leader overrides.

Triggered from Gemini Enterprise's Agent Inbox when a basin leader makes a
significant override to the ML forecast. Asks for the qualitative reasoning,
extracts structured rationale tags via Gemini, and writes them back to
BigQuery for inclusion in the next model retrain.

Deployed to Vertex AI Agent Engine via the standard ADK CLI path (no A2A
wrapping — called directly from Gemini Enterprise, not from a sibling agent).
"""

import os

import vertexai
from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import ForecastRationale
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


# DEMO NARRATION: "Forecast Review Agent — runs in Gemini Enterprise app's
# Agent Inbox. When David makes a significant forecast override, this agent
# prompts him for rationale, extracts structured tags via Gemini, and writes
# them back to BigQuery. The next model retrain ingests this — Issue 2 closes."
root_agent = Agent(
    name=AGENT_NAME,
    model=GlobalGemini(model=MODEL_NAME),
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    output_schema=ForecastRationale,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    after_agent_callback=auto_save_memories,
    tools=[*get_tools(), preload_memory],
)
