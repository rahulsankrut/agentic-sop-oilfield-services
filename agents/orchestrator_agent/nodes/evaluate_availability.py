"""Deterministic check: did the parallel queries find a directly-usable asset?

This node enriches the payload with a derived ``direct_available`` boolean
(plus the chosen instance record when one is available). The router that
follows it just reads the flag — no LLM judgment here.
"""

from __future__ import annotations

from google.adk import Event

from agents.schemas import CapacityGapRequest, SystemQueryResults


def _pick_best_instance(maximo: dict | None) -> dict | None:
    """Pick a deployable Maximo instance from the parallel-query results.

    Preference order: status=='available' over 'available_after_recert'; within
    each status, the first row wins (the synthetic loader returns deterministic
    ordering). Returns None if no row is deployable.
    """
    if not maximo or not maximo.get("instances"):
        return None
    instances = maximo["instances"]
    available = [r for r in instances if r.get("status") == "available"]
    if available:
        return available[0]
    aftrec = [r for r in instances if r.get("status") == "available_after_recert"]
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
    fdp_approved = bool((results.fdp or {}).get("approved"))
    direct_available = chosen is not None and fdp_approved

    return Event(
        message=(
            "Direct availability: "
            + ("YES" if direct_available else "NO — equivalence path required")
        ),
        output={
            "request": request.model_dump(mode="json"),
            "results": results.model_dump(mode="json"),
            "direct_available": direct_available,
            "chosen_direct_instance": chosen,
        },
    )
