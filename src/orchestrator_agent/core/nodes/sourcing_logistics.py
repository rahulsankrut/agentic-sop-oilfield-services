"""LLM node: refine the SourcingPlan with logistics reasoning.

Takes the deterministically-built plan from ``build_*_plan`` and produces an
improved SourcingPlan (same shape, tighter transit / cost / blocker narrative).
Structured output via ``SourcingPlan``.
"""

from __future__ import annotations

import os

from google.adk import Agent
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.schemas import SourcingPlan
from src.utils.global_gemini import GlobalGemini

from ..prompts import SOURCING_LOGISTICS_INSTRUCTION

_MODEL_NAME = os.getenv("SOURCING_LOGISTICS_MODEL", "gemini-3.1-pro-preview")


# DEMO NARRATION: "Second AI node: refining the plan with logistics judgment.
# Transit mode, cost envelope, blocker identification. Gemini's role here is
# to apply real-world logistics reasoning that's hard to encode in pure rules
# — like 'this customs route adds 12 hours, recommend sea freight instead.'"
sourcing_logistics_agent = Agent(
    name="sourcing_logistics",
    model=GlobalGemini(model=_MODEL_NAME),
    description=(
        "Decision node: refine a deterministically-built SourcingPlan with "
        "logistics reasoning. Returns an updated SourcingPlan."
    ),
    instruction=SOURCING_LOGISTICS_INSTRUCTION,
    output_schema=SourcingPlan,
    generate_content_config=GenerateContentConfig(
        temperature=0.0,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
