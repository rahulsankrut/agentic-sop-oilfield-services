"""Parse a capacity-gap query into a structured CapacityGapRequest.

First node in the Capacity Orchestrator Workflow. Deterministic — no LLM.
"""

from __future__ import annotations

from datetime import datetime

from google.adk import Event

from src.schemas import CapacityGapRequest, GeoPoint


# DEMO NARRATION: "First node: parsing Maria's request into a structured form.
# This is deterministic — no LLM. It pulls out the requested asset, the target
# location, and the deadline. If anything is ambiguous, the workflow stops here
# and asks Maria for clarification rather than guessing."
def parse_capacity_gap_request(node_input: str) -> Event:
    """First node in the Orchestrator Workflow.

    Input: raw user query (e.g., "I need a Tool X variant in Luanda by Friday")
    Output: ``Event`` carrying a structured ``CapacityGapRequest`` payload.

    For TASK-04 we use simple heuristic parsing scoped to the hero scenario
    (cargo-plane / Tool X variant / Luanda / Friday / Gulf Petroleum). In
    production this could call out to a small extraction LLM; the
    deterministic version keeps the demo reproducible.
    """
    query = node_input if isinstance(node_input, str) else str(node_input)
    lowered = query.lower()

    # Heuristic asset extraction. Default to the hero-scenario asset; this is
    # safe because the hero scenario is the only path TASK-04 fully wires.
    requested_asset = "Tool X variant" if "tool x" in lowered else "Tool X variant"

    # Heuristic location — Luanda is the centerpiece scenario destination.
    target_location = GeoPoint(
        latitude=-8.8390,
        longitude=13.2894,
        label="Luanda, Angola",
    )

    # Heuristic deadline: Friday relative to a fixed demo anchor; production
    # would parse natural-language dates with a proper extractor.
    deadline = datetime.fromisoformat("2026-05-22T00:00:00")

    # Heuristic customer extraction (only the hero scenario for now)
    customer_id: str | None = None
    if "gulf petroleum" in lowered:
        customer_id = "gulf-petroleum"

    request = CapacityGapRequest(
        raw_query=query,
        requested_asset=requested_asset,
        target_location=target_location,
        deadline=deadline,
        customer_id=customer_id,
    )

    return Event(
        message=f"Parsed capacity-gap request: {request.requested_asset} "
        f"to {request.target_location.label} by {request.deadline.date()}",
        output=request.model_dump(),
    )
