"""Capacity Orchestrator Agent — skeleton (TASK-01 placeholder).

Minimal scaffold to verify the Agent Engine deployment pipeline. The real
agent is built in TASK-02 (prompts, skills, tools, A2A wiring, in-process
Plan Evaluator) following the marathon planner pattern from
next-26-keynotes/devkey/demo-2.
"""

import os

import vertexai
from google.adk.agents import LlmAgent

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gemini-2.5-flash")

if PROJECT_ID:
    vertexai.init(project=PROJECT_ID, location=LOCATION)

# DEMO NARRATION: "This is the Capacity Orchestrator Agent — built on ADK,
# deployed on Agent Engine. In production it orchestrates SAP, Maximo, FDP,
# and InTouch queries to resolve oilfield capacity gaps. In this placeholder
# it confirms the deployment pipeline is wired end-to-end before TASK-02
# turns it into the real Persona 3 lead agent."
root_agent = LlmAgent(
    name="orchestrator_agent",
    model=MODEL,
    description="Capacity Orchestrator Agent (skeleton)",
    instruction=(
        "You are a placeholder agent for the Oilfield Services Domain Pack. "
        "When asked anything, respond with: 'Orchestrator skeleton deployed "
        "successfully. TASK-01 complete. Ready for TASK-02 agent build.'"
    ),
    tools=[],
)
