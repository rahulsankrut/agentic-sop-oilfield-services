"""Finalize the SourcingPlan: compute avoided cost, attach the naive baseline.

Last node before END. Pure-Python compute over the structured plan that
``sourcing_logistics`` (LLM) produced.
"""

from __future__ import annotations

from google.adk import Event

from src.schemas import (
    AssetIdentifier,
    CapacityGapRequest,
    GeoPoint,
    SourcingOption,
    SourcingPlan,
    SystemQueryResults,
)
from src.utils.skill_imports import estimate_transit

# Long-haul fallback hubs by region — the "what Maria would have done without
# the agent" baselines. Hard-coded for the demo's hero scenario; production
# would derive these from Maximo's farthest-deployable instance.
_FALLBACK_HUBS = {
    "west_africa": GeoPoint(latitude=-12.4634, longitude=130.8456, label="Darwin, Australia"),
    "north_america": GeoPoint(latitude=29.7604, longitude=-95.3698, label="Houston, TX, USA"),
    "europe": GeoPoint(latitude=57.1497, longitude=-2.0943, label="Aberdeen, Scotland"),
    "asia_pacific": GeoPoint(latitude=-12.4634, longitude=130.8456, label="Darwin, Australia"),
}


# DEMO NARRATION: "Final node: compute avoided_cost_usd against the
# naive-baseline option — the cargo charter Maria would have ordered without
# the workflow. This is the number the OCC director sees on the canvas:
# 'saved $380K vs. baseline.' Deterministic, traceable, defensible."
def finalize_sourcing_plan(node_input: dict) -> Event:
    """Compute avoided cost and produce the final SourcingPlan envelope."""
    request = CapacityGapRequest(**node_input["request"])
    results = SystemQueryResults(**node_input.get("results", {}))
    plan_dict = node_input.get("plan")
    if not plan_dict:
        return Event(
            message="finalize_sourcing_plan: no plan to finalize",
            output={"request": request.model_dump(), "plan": None},
        )
    plan = SourcingPlan(**plan_dict)

    # Build the naive baseline: cargo charter from the fallback hub for this
    # region (typically Darwin → Luanda for the cargo-plane scenario).
    fallback_hub = _FALLBACK_HUBS.get(request.target_region or "", None)
    naive_baseline: SourcingOption | None = None
    if fallback_hub is not None:
        transit = estimate_transit(
            from_lat=fallback_hub.latitude,
            from_lon=fallback_hub.longitude,
            to_lat=request.target_location.latitude,
            to_lon=request.target_location.longitude,
            asset_size_class="downhole_tool",
        )
        naive_baseline = SourcingOption(
            asset=AssetIdentifier(
                canonical_id=plan.primary_option.asset.canonical_id,
                canonical_label=plan.primary_option.asset.canonical_label,
            ),
            source_location=fallback_hub,
            destination=request.target_location,
            transit_mode=transit["transit_mode"],
            estimated_cost_usd=int(transit["estimated_cost_usd"]),
            transit_hours=float(transit["transit_hours"]),
            certification_hours=0.0,
            customer_compatibility=plan.primary_option.customer_compatibility,
            workforce_available=False,
            blockers=["Naive baseline — long-haul charter, no source workforce attached"],
        )

    avoided = 0
    if naive_baseline is not None:
        avoided = max(0, naive_baseline.estimated_cost_usd - plan.primary_option.estimated_cost_usd)

    final = plan.model_copy(
        update={
            "naive_baseline": naive_baseline,
            "avoided_cost_usd": avoided,
        }
    )

    return Event(
        message=(
            f"Final SourcingPlan: primary=${final.primary_option.estimated_cost_usd:,} "
            f"avoided=${final.avoided_cost_usd:,}"
        ),
        output={
            "request": request.model_dump(),
            "results": results.model_dump(),
            "plan": final.model_dump(),
        },
    )
