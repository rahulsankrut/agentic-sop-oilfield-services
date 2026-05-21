"""Node implementations for the Capacity Orchestrator Workflow.

Each module here defines either:

- a deterministic function node (parse_request, resolve_asset, routers, etc.)
- an LLM agent node (equivalence_lookup, sourcing_logistics, revise_plan)

These are composed in ``agent.py`` via ADK 2.0 ``Workflow`` edges.
"""
