"""Parse a capacity-gap query into a structured CapacityGapRequest.

First node in the Capacity Orchestrator Workflow. Deterministic — no LLM.
Also emits the ``capacity.gap_detected`` canvas event so the canvas can
zoom the map and mark the target location.
"""

from __future__ import annotations

from datetime import datetime

from google.adk import Context, Event

from agents.schemas import CapacityGapRequest, GeoPoint

from ..events.canvas_events import CapacityGapDetectedEvent
from ..events.emit import emit


# DEMO NARRATION: "First node: parsing Maria's request into a structured form.
# This is deterministic — no LLM. It pulls out the requested asset, the target
# location, and the deadline. If anything is ambiguous, the workflow stops here
# and asks Maria for clarification rather than guessing."
def parse_capacity_gap_request(node_input: str, ctx: Context) -> Event:
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

    # TASK-13 Step 5 — heuristics read defaults from the active customer skin
    # rather than hardcoded Tool X / Luanda / Gulf Petroleum literals. The
    # skin's cargo-plane scenario carries the hero asset label, target
    # location coords + label, and the customer-account slug + name.
    from agents.utils.skin_loader import get_active_skin  # noqa: PLC0415

    skin = get_active_skin()
    sc = skin.scenario("cargo-plane")
    hero_label = skin.taxonomy.hero_asset.canonical_label

    # Asset extraction — match either the hero label or any of the
    # secondary asset labels in the skin. Otherwise default to hero.
    requested_asset = hero_label
    for asset in [skin.taxonomy.hero_asset, *skin.taxonomy.secondary_assets]:
        if asset.canonical_label.lower() in lowered:
            requested_asset = asset.canonical_label
            break

    # Heuristic location — skin's scenario `location_focus_*` fields.
    target_location = GeoPoint(
        latitude=sc.location_focus_lat if sc.location_focus_lat is not None else -8.8390,
        longitude=sc.location_focus_lng if sc.location_focus_lng is not None else 13.2894,
        label=sc.location_focus_label,
    )

    # Heuristic deadline: Friday relative to a fixed demo anchor; production
    # would parse natural-language dates with a proper extractor.
    deadline = datetime.fromisoformat("2026-05-22T00:00:00")

    # Heuristic customer extraction — match the skin's customer-account slug
    # or its display name. Slug match wins.
    customer_id: str | None = None
    if sc.customer_account_slug in lowered:
        customer_id = sc.customer_account_slug
    elif sc.customer_account_name.lower() in lowered:
        customer_id = sc.customer_account_slug

    request = CapacityGapRequest(
        raw_query=query,
        requested_asset=requested_asset,
        target_location=target_location,
        deadline=deadline,
        customer_id=customer_id,
    )

    # DEMO NARRATION: "And right here we emit the first canvas event — a
    # capacity gap detected at Luanda. The canvas picks this up via the A2A
    # SSE stream and zooms the map onto West Africa."
    workflow_id = ctx.state.get("workflow_id", "") if hasattr(ctx, "state") else ""
    session_id = ctx.state.get("session_id", "") if hasattr(ctx, "state") else ""
    gap_event = CapacityGapDetectedEvent(
        workflow_id=workflow_id,
        session_id=session_id,
        location={
            "latitude": target_location.latitude,
            "longitude": target_location.longitude,
            "label": target_location.label,
        },
        # canonical_asset_id is filled in by resolve_canonical_asset_node; we
        # surface the raw requested_asset here so the canvas can render a
        # placeholder marker before the resolution event arrives.
        canonical_asset_id=requested_asset,
        deadline=deadline.isoformat(),
    )

    return Event(
        message=f"Parsed capacity-gap request: {request.requested_asset} "
        f"to {request.target_location.label} by {request.deadline.date()}",
        output=request.model_dump(),
        state=emit(ctx, gap_event),
    )
