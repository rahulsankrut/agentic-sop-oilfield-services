"""Configuration for the Forecast Review Agent."""

import os

AGENT_NAME = "forecast_review_agent"
AGENT_DESCRIPTION = (
    "Forecast Review Agent — captures rationale on basin-leader forecast overrides. "
    "Triggered when a leader makes a significant override; extracts structured "
    "rationale tags via Gemini and writes them back for the next model retrain."
)

# Flash — fast, structured-output extraction work.
MODEL_NAME = os.getenv("FORECAST_REVIEW_MODEL", "gemini-3-flash-preview")
