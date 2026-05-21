"""Plan Evaluator — bundled with the Capacity Orchestrator, called via AgentTool.

Scores SourcingPlans across 7 weighted criteria using LLM-as-Judge. Returns
a structured ``PlanEvaluation``. No separate deployment: this agent ships in
the same Reasoning Engine as the Orchestrator and is invoked in-process via
``AgentTool(agent=plan_evaluator_agent)``.

Skeleton for TASK-02: the prompt instructs the model to return
``overall_score = 0.91`` for any plan. Real domain logic lands in TASK-03.
"""

import logging as _logging
import os
import pathlib

import vertexai
from google.adk.agents import LlmAgent
from google.adk.skills import load_skill_from_dir
from google.adk.tools import google_maps_grounding, preload_memory
from google.adk.tools.skill_toolset import SkillToolset
from google.genai.types import GenerateContentConfig, ThinkingConfig

from agents.schemas import PlanEvaluation, SourcingPlan
from agents.utils.global_gemini import GlobalGemini
from agents.utils.skill_tools import load_skill_function_tools

from ..services.memory_manager import auto_save_memories
from .prompts import INSTRUCTION

_logger = _logging.getLogger(__name__)


async def _stash_evaluation_and_save_memories(callback_context):
    """Stash PlanEvaluation into ctx.state so downstream routers can read it
    (the LLM output replaces node_input, so the wrapping {evaluation, plan,
    iteration_count} keys other nodes expect are not visible past this
    boundary). Then delegate to ``auto_save_memories`` for Memory Bank.
    """
    try:
        output = None
        try:
            output = callback_context.output
        except Exception:
            output = None
        eval_dict = None
        if isinstance(output, dict):
            eval_dict = output
        elif hasattr(output, "model_dump"):
            try:
                eval_dict = output.model_dump(mode="json")
            except Exception:
                eval_dict = None
        if eval_dict:
            try:
                callback_context.state["evaluation"] = eval_dict
            except Exception as exc:
                _logger.warning("Failed to stash evaluation in state: %s", exc)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("plan_evaluator stash failed: %s", exc)
    await auto_save_memories(callback_context)

# Lazy-load the plan-evaluation skill from this package's skills/ dir.
_SKILLS_DIR = pathlib.Path(__file__).parent / "skills"
_skills = (
    [
        load_skill_from_dir(d)
        for d in sorted(_SKILLS_DIR.iterdir())
        if _SKILLS_DIR.exists()
        and d.is_dir()
        and not d.name.startswith("_")
        and (d / "SKILL.md").exists()
    ]
    if _SKILLS_DIR.exists()
    else []
)
_skill_toolset = SkillToolset(skills=_skills) if _skills else None
_skill_function_tools = load_skill_function_tools(_SKILLS_DIR)

# Initialize Vertex AI for Agent Engine / Memory Bank infra (us-central1).
# Model calls route to 'global' via GlobalGemini — Memory Bank stays regional.
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
    "GOOGLE_CLOUD_LOCATION", "us-central1"
)
if project_id:
    vertexai.init(project=project_id, location=location)

MODEL_NAME = os.environ.get("PLAN_EVALUATOR_MODEL", "gemini-3.1-pro-preview")

# 7 weighted criteria for oilfield services sourcing decisions (sum to 1.0)
CRITERION_WEIGHTS = {
    "safety_compliance": 0.20,
    "customer_compatibility": 0.20,
    "logistics_feasibility": 0.15,
    "cost_optimality": 0.15,
    "equivalence_confidence": 0.10,
    "regulatory_compliance": 0.10,
    "schedule_feasibility": 0.10,
}
assert abs(sum(CRITERION_WEIGHTS.values()) - 1.0) < 1e-4, "Weights must sum to 1.0"


# DEMO NARRATION: "The Plan Evaluator is an LLM-as-Judge — same pattern Google
# showed in the Next '26 keynote marathon-planner demo. Seven criteria specific to
# oilfield services: safety, customer compatibility, logistics feasibility,
# cost, equivalence confidence, regulatory, schedule. Each weighted, all
# aggregated into an overall_score the Orchestrator iterates against."
root_agent = LlmAgent(
    name="plan_evaluator_agent",
    model=GlobalGemini(model=MODEL_NAME),
    description=(
        "Plan Evaluator for oilfield services sourcing plans. LLM-as-Judge with "
        "7 weighted criteria. Returns structured PlanEvaluation."
    ),
    static_instruction=INSTRUCTION,
    # input_schema needed because AgentTool wraps this agent — without one,
    # AgentTool._run_async_impl falls through to `args['request']` (default
    # convention) and KeyError's against the SourcingPlan dict we actually
    # pass. With input_schema=SourcingPlan, ADK validates the workflow's
    # node_input as a SourcingPlan and serializes it for the LLM cleanly.
    input_schema=SourcingPlan,
    output_schema=PlanEvaluation,
    generate_content_config=GenerateContentConfig(
        max_output_tokens=4096,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    include_contents="none",
    after_agent_callback=_stash_evaluation_and_save_memories,
    # google_maps_grounding lets the evaluator verify logistics_feasibility +
    # schedule_feasibility claims against real-world Maps data (transit times,
    # cross-border routes, port availability). Model-level GA tool, Gemini 2+.
    tools=(
        [preload_memory, google_maps_grounding]
        + ([_skill_toolset] if _skill_toolset else [])
        + _skill_function_tools
    ),
)
