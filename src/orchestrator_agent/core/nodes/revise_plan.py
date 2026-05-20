"""LLM node: revise a low-scoring plan based on Plan Evaluator findings.

The Plan Evaluator returns a structured ``PlanEvaluation`` with criterion
scores and findings. When ``overall_score < 0.85``, the workflow routes here.
This node takes the original plan plus the evaluator's findings and produces
an improved plan; the workflow then re-evaluates. Capped at two iterations.
"""

from __future__ import annotations

import os

from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.schemas import SourcingPlan
from src.utils.global_gemini import GlobalGemini

from ...services.memory_manager import auto_save_memories
from ..prompts import REVISE_PLAN_INSTRUCTION

_MODEL_NAME = os.getenv("REVISE_PLAN_MODEL", "gemini-3.1-pro-preview")


# DEMO NARRATION: "If the Plan Evaluator scores below threshold, we revise.
# This node takes the original plan plus the evaluator's findings and produces
# an improved plan. The workflow then re-evaluates. Up to two iterations.
# This is the kind of self-improvement loop that's structural in our Workflow,
# not behavioral in a prompt — the loop limit is a Python integer, not a
# request to the model to please stop after two tries."
revise_plan_agent = Agent(
    name="revise_plan",
    model=GlobalGemini(model=_MODEL_NAME),
    description=(
        "Decision node: revise a sourcing plan based on Plan Evaluator findings. "
        "Returns an updated SourcingPlan."
    ),
    instruction=REVISE_PLAN_INSTRUCTION,
    output_schema=SourcingPlan,
    tools=[preload_memory],
    after_agent_callback=auto_save_memories,
    generate_content_config=GenerateContentConfig(
        temperature=0.0,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
