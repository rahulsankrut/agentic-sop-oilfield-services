"""Plan Evaluator — bundled with the Capacity Orchestrator, called via AgentTool.

Scores SourcingPlans across 7 weighted criteria using LLM-as-Judge. Returns
a structured ``PlanEvaluation``. No separate deployment: this agent ships in
the same Reasoning Engine as the Orchestrator and is invoked in-process via
``AgentTool(agent=plan_evaluator_agent)``.

Skeleton for TASK-02: the prompt instructs the model to return
``overall_score = 0.91`` for any plan. Real domain logic lands in TASK-03.
"""

import os

import vertexai
from google.adk.agents import LlmAgent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.schemas import PlanEvaluation
from src.utils.global_gemini import GlobalGemini

from .prompts import INSTRUCTION

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
# showed in the Next '26 keynote marathon demo. Seven criteria specific to
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
    output_schema=PlanEvaluation,
    generate_content_config=GenerateContentConfig(
        max_output_tokens=4096,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
    include_contents="none",
    tools=[PreloadMemoryTool()],
)
