"""Capacity Planning Agent — long-running, multi-week buffer optimizer.

Triggered from Gemini Enterprise chat. Pulls probabilistic start-date
distributions from BigQuery ML, surfaces actual-vs-requested variance,
and produces risk-calibrated buffer recommendations. Deployed to Vertex
AI Agent Engine via the standard ADK CLI path (no A2A wrapping needed —
called directly from Gemini Enterprise, not from a sibling agent).
"""

import os

import vertexai
from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import BufferOptimization
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


# DEMO NARRATION: "The Capacity Planning Agent runs long — multi-week scheduling
# state. Pulls probabilistic distributions from BigQuery ML, applies the planner's
# risk tolerance, and recommends buffers. This is how Issue 1 resolves: static
# worst-case buffers replaced with risk-calibrated recommendations grounded in
# real start-date volatility data."
root_agent = Agent(
    name=AGENT_NAME,
    model=GlobalGemini(model=MODEL_NAME),
    description=AGENT_DESCRIPTION,
    static_instruction=INSTRUCTION,
    output_schema=BufferOptimization,
    generate_content_config=GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    after_agent_callback=auto_save_memories,
    tools=[*get_tools(), preload_memory],
)
