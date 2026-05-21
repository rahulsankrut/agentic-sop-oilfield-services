"""LLM node: revise a low-scoring plan based on Plan Evaluator findings.

The Plan Evaluator returns a structured ``PlanEvaluation`` with criterion
scores and findings. When ``overall_score < 0.85``, the workflow routes here.
This node takes the original plan plus the evaluator's findings and produces
an improved plan; the workflow then re-evaluates. Capped at two iterations.
"""

from __future__ import annotations

import logging
import os

from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import SourcingPlan
from agents.utils.global_gemini import GlobalGemini

from ..prompts import REVISE_PLAN_INSTRUCTION
from ..services.memory_manager import auto_save_memories

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("REVISE_PLAN_MODEL", "gemini-3.1-pro-preview")


async def _stash_plan_and_save_memories(callback_context):
    """Stash revised SourcingPlan into ctx.state so downstream nodes can
    find it after plan_evaluator clobbers node_input. Mirrors the pattern
    in sourcing_logistics._emit_route_events.
    """
    try:
        output = None
        try:
            output = callback_context.output
        except Exception:
            output = None
        plan_dict = None
        if isinstance(output, dict):
            plan_dict = output
        elif hasattr(output, "model_dump"):
            try:
                plan_dict = output.model_dump(mode="json")
            except Exception:
                plan_dict = None
        if plan_dict:
            try:
                callback_context.state["plan"] = plan_dict
            except Exception as exc:
                logger.warning("Failed to stash revised plan in state: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("revise_plan stash failed: %s", exc)
    await auto_save_memories(callback_context)


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
    static_instruction=REVISE_PLAN_INSTRUCTION,
    include_contents="none",
    output_schema=SourcingPlan,
    tools=[preload_memory],
    after_agent_callback=_stash_plan_and_save_memories,
    generate_content_config=GenerateContentConfig(
        temperature=0.0,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
