"""Configuration for the Capacity Orchestrator Agent."""

import os

AGENT_NAME = "orchestrator_agent"
AGENT_DESCRIPTION = (
    "Capacity Orchestrator Agent — lead architect for service capacity gap "
    "resolution. Decomposes capacity queries across SAP, Maximo, FDP, and InTouch "
    "via MCP. Coordinates with Plan Evaluator (in-process AgentTool) and Procurement "
    "Approval Agent (A2A on Agent Engine). Produces grounded SourcingPlan "
    "recommendations."
)

# Gemini 3.1 Pro for reasoning depth (see CLAUDE.md gotcha re: global endpoint).
# Override via ORCHESTRATOR_MODEL env var if e.g. flash is acceptable for cost.
MODEL_NAME = os.getenv("ORCHESTRATOR_MODEL", "gemini-3.1-pro-preview")
