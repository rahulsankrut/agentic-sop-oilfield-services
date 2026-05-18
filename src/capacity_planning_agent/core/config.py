"""Configuration for the Capacity Planning Agent."""

import os

AGENT_NAME = "capacity_planning_agent"
AGENT_DESCRIPTION = (
    "Capacity Planning Agent — long-running, multi-week scheduling state. "
    "Produces risk-calibrated buffer recommendations grounded in actual "
    "start-date volatility data (per-basin, 6 quarters of history)."
)

# Flash with thinking — buffer-tradeoff math is structured but benefits from
# some chain-of-thought when explaining recommendations. Override to pro if
# more reasoning depth is needed.
MODEL_NAME = os.getenv("CAPACITY_PLANNING_MODEL", "gemini-3-flash-preview")
