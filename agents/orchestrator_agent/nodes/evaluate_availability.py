"""Deterministic check: did the parallel queries find a directly-usable asset?

This node enriches the payload with a derived ``direct_available`` boolean
(plus the chosen instance record when one is available). The router that
follows it just reads the flag — no LLM judgment here.
"""

from __future__ import annotations

import logging

from google.adk import Event

from agents.schemas import CapacityGapRequest, SystemQueryResults
from agents.utils.skill_imports import find_functional_equivalents

logger = logging.getLogger(__name__)


def _pick_best_instance(maximo: dict | None) -> dict | None:
    """Pick a deployable Maximo instance from the parallel-query results.

    Preference order: status=='available' over the recert variant; within
    each status, the first row wins (the synthetic loader returns
    deterministic ordering). The BQ synthetic data truncates the recert
    status to ``"available_after_"`` (16-char column), so we match on
    startswith instead of strict equality.
    """
    if not maximo or not maximo.get("instances"):
        return None
    instances = maximo["instances"]
    available = [r for r in instances if (r.get("status") or "") == "available"]
    if available:
        return available[0]
    aftrec = [
        r for r in instances
        if (r.get("status") or "").lower().startswith("available_after_")
    ]
    if aftrec:
        return aftrec[0]
    return None


# DEMO NARRATION: "Third node: deterministic availability check. We look at
# the Maximo instances the parallel query returned, filter to the ones that
# are actually deployable, and stamp a boolean on the payload. The router
# downstream just reads that boolean — no LLM judgment, no surprise routing.
# Predictable enough to put in front of a procurement audit."
def evaluate_direct_availability(node_input: dict) -> Event:
    """Decide whether direct availability exists in the target region."""
    request = CapacityGapRequest(**node_input["request"])
    results = SystemQueryResults(**node_input["results"])

    chosen = _pick_best_instance(results.maximo)
    # Code-review HIGH #9: don't gate direct path on FDP. If FDP returns no
    # row (unknown customer / FDP outage), still route DIRECT when a
    # deployable instance exists — the Plan Evaluator can downgrade
    # customer_compatibility if FDP is missing. Previous behavior
    # silently forced equivalence path for any customer without an FDP
    # entry.
    direct_available = chosen is not None

    # If direct path isn't available, pre-fetch the KC equivalents so the
    # equivalence_lookup LLM has a real list to pick from (otherwise the LLM
    # has no tool to query KC and hallucinates substitute ids).
    equivalents: list[dict] = []
    if not direct_available:
        canonical_id = request.canonical_asset_id or ""
        if canonical_id:
            try:
                equivalents = find_functional_equivalents(canonical_id) or []
            except Exception as exc:  # noqa: BLE001 — degrade to empty
                logger.warning(
                    "find_functional_equivalents(%r) failed: %s",
                    canonical_id, exc,
                )

    logger.info(
        "Direct availability: %s",
        "YES" if direct_available else "NO — equivalence path required",
    )
    return Event(
        output={
            "request": request.model_dump(mode="json"),
            "results": results.model_dump(mode="json"),
            "direct_available": direct_available,
            "chosen_direct_instance": chosen,
            "kc_equivalents": equivalents,
        },
    )
