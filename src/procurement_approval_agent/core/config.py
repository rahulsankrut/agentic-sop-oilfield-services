"""Configuration for the Procurement Approval Agent."""

import os

AGENT_NAME = "procurement_approval_agent"
AGENT_DESCRIPTION = (
    "Procurement Approval Agent for oilfield services. Fast deterministic "
    "verification that a sourcing plan has all required fields, certifications, "
    "and is within authorization thresholds to commit logistics dollars."
)

# Gemini 3 Flash for speed — deterministic prerequisite checks, no reasoning depth needed.
MODEL_NAME = os.getenv("PROCUREMENT_APPROVAL_MODEL", "gemini-3-flash-preview")
