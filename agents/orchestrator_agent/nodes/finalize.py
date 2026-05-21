"""Finalize the SourcingPlan: compute avoided cost, attach the naive baseline.

Last node before END. Pure-Python compute over the structured plan that
``sourcing_logistics`` (LLM) produced.
"""

from __future__ import annotations

from datetime import datetime

from google.adk import Context, Event

from agents.schemas import (
    AssetIdentifier,
    CapacityGapRequest,
    GeoPoint,
    SourcingOption,
    SourcingPlan,
    SystemQueryResults,
)
from agents.utils.skill_imports import estimate_transit

from ..events.canvas_events import WorkflowCompletedEvent
from ..events.emit import emit

# Long-haul fallback hubs by region — the "what the planner would have done
# without the agent" baselines. Hard-coded for the demo's hero scenario;
# production would derive these from Maximo's farthest-deployable instance.
#
# TASK-13 Step 5: the region matching the active cargo-plane scenario's
# `target_location` reads its naive-baseline label + coords from the skin.
# Other regions retain the in-house demo defaults so the workflow doesn't
# break when run against an off-scenario region.
_FALLBACK_HUBS = {
    "west_africa": GeoPoint(latitude=-12.4634, longitude=130.8456, label="Darwin, Australia"),
    "north_america": GeoPoint(latitude=29.7604, longitude=-95.3698, label="Houston, TX, USA"),
    "europe": GeoPoint(latitude=57.1497, longitude=-2.0943, label="Aberdeen, Scotland"),
    "asia_pacific": GeoPoint(latitude=-12.4634, longitude=130.8456, label="Darwin, Australia"),
}


def _skin_fallback_hub() -> GeoPoint | None:
    """Skin-driven naive-baseline hub for the active cargo-plane scenario.

    Returns the GeoPoint when the skin supplies a complete
    `naive_origin_{label,lat,lng}` triple; otherwise None and callers
    fall back to the `_FALLBACK_HUBS` regional table.
    """
    try:
        from agents.utils.skin_loader import get_active_skin  # noqa: PLC0415

        sc = get_active_skin().scenario("cargo-plane")
    except Exception:  # noqa: BLE001
        return None
    if sc.naive_origin_label is None or sc.naive_origin_lat is None or sc.naive_origin_lng is None:
        return None
    return GeoPoint(
        latitude=sc.naive_origin_lat,
        longitude=sc.naive_origin_lng,
        label=sc.naive_origin_label,
    )


# DEMO NARRATION: "Final node: compute avoided_cost_usd against the
# naive-baseline option — the cargo charter Maria would have ordered without
# the workflow. This is the number the OCC director sees on the canvas:
# 'saved $380K vs. baseline.' Deterministic, traceable, defensible."
def finalize_sourcing_plan(node_input: dict, ctx: Context) -> Event:
    """Compute avoided cost and produce the final SourcingPlan envelope."""
    request = CapacityGapRequest(**node_input["request"])
    results = SystemQueryResults(**node_input.get("results", {}))
    plan_dict = node_input.get("plan")

    # Compute workflow duration from the seed timestamp recorded at start.
    workflow_id = ""
    session_id = ""
    started_iso = ""
    try:
        workflow_id = ctx.state.get("workflow_id", "") or ""
        session_id = ctx.state.get("session_id", "") or ""
        started_iso = ctx.state.get("workflow_started_at", "") or ""
    except Exception:
        pass
    duration_ms = 0
    if started_iso:
        try:
            started_at = datetime.fromisoformat(started_iso)
            duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        except (TypeError, ValueError):
            duration_ms = 0

    if not plan_dict:
        completed = WorkflowCompletedEvent(
            workflow_id=workflow_id,
            session_id=session_id,
            final_output={"request": request.model_dump(mode="json"), "plan": None},
            duration_ms=duration_ms,
        )
        return Event(
            message="finalize_sourcing_plan: no plan to finalize",
            output={"request": request.model_dump(mode="json"), "plan": None},
            state=emit(ctx, completed),
        )
    plan = SourcingPlan(**plan_dict)

    # Build the naive baseline: cargo charter from the fallback hub for this
    # region (typically Darwin → Luanda in the default skin's cargo-plane
    # scenario). Prefer the skin-provided hub if available; fall back to the
    # regional table for off-scenario regions.
    fallback_hub = _skin_fallback_hub() or _FALLBACK_HUBS.get(request.target_region or "", None)
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

    final_output = {
        "request": request.model_dump(mode="json"),
        "results": results.model_dump(mode="json"),
        "plan": final.model_dump(mode="json"),
    }

    completed = WorkflowCompletedEvent(
        workflow_id=workflow_id,
        session_id=session_id,
        final_output=final_output,
        duration_ms=duration_ms,
    )

    state_delta = emit(ctx, completed)

    # TASK-45 Phase 2 — emit the cost-rollup A2UI surface alongside the
    # WorkflowCompleted canvas event. The canvas's A2UIProvider drains
    # `a2ui_envelopes` from the SSE state_delta and renders the surface.
    if naive_baseline is not None:
        try:
            from agents.utils import a2ui  # noqa: PLC0415

            from .emit import emit_a2ui  # noqa: PLC0415

            cost_msgs = a2ui.cost_rollup(
                doomed_usd=int(naive_baseline.estimated_cost_usd),
                recommended_usd=int(final.primary_option.estimated_cost_usd),
                avoided_usd=int(avoided),
            )
            state_delta = {**state_delta, **emit_a2ui(ctx, cost_msgs)}
        except Exception:  # noqa: BLE001
            # A2UI emit is best-effort; canvas falls back to the bespoke
            # cost banner if the surface payload isn't present.
            pass

    return Event(
        message=(
            f"Final SourcingPlan: primary=${final.primary_option.estimated_cost_usd:,} "
            f"avoided=${final.avoided_cost_usd:,}"
        ),
        output=final_output,
        state=state_delta,
    )
