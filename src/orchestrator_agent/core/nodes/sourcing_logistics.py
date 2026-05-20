"""LLM node: refine the SourcingPlan with logistics reasoning.

Takes the deterministically-built plan from ``build_*_plan`` and produces an
improved SourcingPlan (same shape, tighter transit / cost / blocker narrative).
Structured output via ``SourcingPlan``.

Also emits canvas events: a ``DoomedRouteProposedEvent`` for the naive
baseline (the "what Maria would have done") and a
``RecommendedRouteFinalizedEvent`` for the primary option. These let the
canvas draw the contrast arc and surface the cost-rollup banner.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from google.adk import Agent
from google.adk.tools import preload_memory
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.schemas import SourcingPlan
from src.utils.global_gemini import GlobalGemini

from ...events.canvas_events import (
    DoomedRouteProposedEvent,
    RecommendedRouteFinalizedEvent,
)
from ...services.memory_manager import auto_save_memories
from ..prompts import SOURCING_LOGISTICS_INSTRUCTION

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("SOURCING_LOGISTICS_MODEL", "gemini-3.1-pro-preview")


async def _emit_route_events(callback_context: "CallbackContext") -> None:
    """Emit doomed + recommended route canvas events after the refinement.

    The refined SourcingPlan carries both the primary_option and the
    naive_baseline. We surface each as a canvas event so the map can draw
    the contrast.
    """
    try:
        ctx = callback_context
        try:
            workflow_id = ctx.state.get("workflow_id", "") or ""
            session_id = ctx.state.get("session_id", "") or ""
        except Exception:
            workflow_id = ""
            session_id = ""

        output: Any = None
        try:
            output = ctx.output
        except Exception:
            output = None

        plan_dict: dict[str, Any] | None = None
        if isinstance(output, dict):
            plan_dict = output
        elif hasattr(output, "model_dump"):
            try:
                plan_dict = output.model_dump()
            except Exception:
                plan_dict = None

        new_events: list[dict[str, Any]] = []
        if plan_dict:
            primary = plan_dict.get("primary_option") or {}
            naive = plan_dict.get("naive_baseline") or {}

            if naive:
                doomed = DoomedRouteProposedEvent(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    from_location=naive.get("source_location") or {},
                    to_location=naive.get("destination") or {},
                    estimated_cost_usd=float(naive.get("estimated_cost_usd") or 0),
                    rationale="Naive baseline — long-haul charter without source workforce",
                )
                new_events.append(doomed.model_dump(mode="json"))

            if primary:
                primary_cost = float(primary.get("estimated_cost_usd") or 0)
                naive_cost = float(naive.get("estimated_cost_usd") or 0) if naive else 0.0
                avoided = max(0.0, naive_cost - primary_cost) if naive_cost else 0.0
                recommended = RecommendedRouteFinalizedEvent(
                    workflow_id=workflow_id,
                    session_id=session_id,
                    from_location=primary.get("source_location") or {},
                    to_location=primary.get("destination") or {},
                    estimated_cost_usd=primary_cost,
                    avoided_cost_usd=avoided,
                )
                new_events.append(recommended.model_dump(mode="json"))

        if new_events:
            try:
                existing = list(ctx.state.get("canvas_events", []) or [])
            except Exception:
                existing = []
            try:
                ctx.state["canvas_events"] = [*existing, *new_events]
            except Exception as exc:
                logger.warning("Failed to write canvas_events to state: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sourcing_logistics canvas-event emit failed: %s", exc)

    await auto_save_memories(callback_context)


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
    tools=[preload_memory],
    after_agent_callback=_emit_route_events,
    generate_content_config=GenerateContentConfig(
        temperature=0.0,
        thinking_config=ThinkingConfig(thinking_budget=1024),
    ),
)
