"""Capacity Orchestrator Agent — ADK 2.0 Workflow.

This is the heart of the cargo-plane demo. The Orchestrator is a graph of
nodes:

- Function nodes (deterministic): parse, resolve, parallel queries, eval-
  availability, routers, plan builders, finalize.
- LLM nodes (Gemini): equivalence_lookup, sourcing_logistics, revise_plan.
- AgentTool node (in-process LlmAgent): plan_evaluator.
- A2A node (Agent Engine via RemoteA2aAgent): procurement_approval.

The graph's purpose is to make the Orchestrator's behavior predictable and
auditable, while preserving Gemini's reasoning at the decision points where
judgment beats rules.

See ``docs/adr/0001-adopt-adk-2-workflow.md`` for the architectural rationale.
"""

from __future__ import annotations

import os

import vertexai
from google.adk import Workflow

from .config import AGENT_DESCRIPTION, AGENT_NAME
from .nodes.build_plans import build_direct_plan, build_equivalent_plan
from .nodes.equivalence_lookup import equivalence_lookup_agent
from .nodes.evaluate_availability import evaluate_direct_availability
from .nodes.finalize import finalize_sourcing_plan
from .nodes.parallel_queries import parallel_system_queries
from .nodes.parse_request import parse_capacity_gap_request
from .nodes.resolve_asset import resolve_canonical_asset_node
from .nodes.revise_plan import revise_plan_agent
from .nodes.routers import (
    AUTO_APPROVE,
    DIRECT_AVAILABLE,
    NEEDS_EQUIVALENCE,
    PROCEED,
    REQUIRES_APPROVAL,
    REVISE,
    route_on_availability,
    route_on_evaluation_score,
    route_on_procurement_threshold,
)
from .nodes.sourcing_logistics import sourcing_logistics_agent
from .tools import (
    create_plan_evaluator_tool,
    create_procurement_approval_tool,
)

# Initialize Vertex AI for Agent Engine / Memory Bank infra (regional —
# us-central1). Model calls route to 'global' via GlobalGemini, so Memory
# Bank stays in us-central1.
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
    "GOOGLE_CLOUD_LOCATION", "us-central1"
)
if project_id:
    vertexai.init(project=project_id, location=location)


# In-process AgentTool wrapper around the Plan Evaluator LlmAgent — same
# pattern as v1, just no longer routed through an Orchestrator prompt. The
# Workflow runner invokes this as a node directly.
plan_evaluator_tool = create_plan_evaluator_tool()

# Procurement Approval is only wired in when the env var is set (matches the
# v1 contract — local dev runs without the A2A hop).
_procurement_tool = None
if os.environ.get("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME"):
    _procurement_tool = create_procurement_approval_tool()


# DEMO NARRATION: "Here's the workflow graph. This is the Capacity Orchestrator
# Agent rebuilt as an explicit graph using ADK 2.0's Workflow primitive. Each
# node is either deterministic code or AI reasoning, and the routing between
# them is policy expressed as graph edges, not LLM judgment encoded in a
# prompt. Watch the Cloud Trace as this executes — you'll see the same shape."
#
# Edge legend (top → bottom in execution order):
#   1. Linear opening: START → parse → resolve → parallel queries → availability eval
#   2. Availability router fans into the direct OR equivalence path
#   3. Equivalence path: LLM picks substitute → function builds plan
#   4. Both paths merge at sourcing_logistics (LLM refinement)
#   5. Plan Evaluator (AgentTool) scores; router accepts / revises / exhausts
#   6. Procurement threshold router: auto-approve or A2A gate
#   7. Finalize → END

_edges: list = [
    # 1. Linear opening
    (
        "START",
        parse_capacity_gap_request,
        resolve_canonical_asset_node,
        parallel_system_queries,
        evaluate_direct_availability,
        route_on_availability,
    ),
    # 2. Availability routing
    (
        route_on_availability,
        {
            DIRECT_AVAILABLE: build_direct_plan,
            NEEDS_EQUIVALENCE: equivalence_lookup_agent,
        },
    ),
    # 3. Equivalence path: LLM → builder
    (equivalence_lookup_agent, build_equivalent_plan),
    # 4. Both paths merge at sourcing_logistics → Plan Evaluator → score router
    (build_direct_plan, sourcing_logistics_agent),
    (build_equivalent_plan, sourcing_logistics_agent),
    (sourcing_logistics_agent, plan_evaluator_tool, route_on_evaluation_score),
    # 5. Evaluation routing: PROCEED (accept-or-exhausted) → procurement check,
    # REVISE → loop back to revise_plan_agent.
    (
        route_on_evaluation_score,
        {
            PROCEED: route_on_procurement_threshold,
            REVISE: revise_plan_agent,
        },
    ),
    # Revision loop — revise_plan flows back into the Plan Evaluator for
    # re-scoring. The iteration_count carried in the payload caps the loop.
    (revise_plan_agent, plan_evaluator_tool),
]

# 6. Procurement-threshold routing
# ADK 2.0 dedups edges by (source, target). When procurement A2A is NOT wired
# (local dev, env var unset), both AUTO_APPROVE and REQUIRES_APPROVAL would
# point at finalize_sourcing_plan — a duplicate edge. So:
# - With procurement wired: route to two distinct nodes (finalize vs procurement_tool)
# - Without procurement: skip the procurement check entirely; route_on_evaluation_score's
#   PROCEED branch goes straight to finalize_sourcing_plan
if _procurement_tool is not None:
    _edges.append(
        (
            route_on_procurement_threshold,
            {
                AUTO_APPROVE: finalize_sourcing_plan,
                REQUIRES_APPROVAL: _procurement_tool,
            },
        )
    )
    _edges.append((_procurement_tool, finalize_sourcing_plan))
else:
    # No procurement gate available — collapse the threshold router to
    # always pass through to finalize.
    _edges.append((route_on_procurement_threshold, finalize_sourcing_plan))

# 7. Terminal — ADK 2.0 Workflow has an implicit terminal: any node with no
# outbound edge ends the workflow. There's no Literal['END'] in the edge schema
# (only Literal['START']). finalize_sourcing_plan is already not the source of
# any other edge, so it's the natural terminator.


root_agent = Workflow(
    name=AGENT_NAME,
    description=AGENT_DESCRIPTION,
    edges=_edges,
)
