"""Build candidate SourcingPlans — both the direct and the equivalence branches.

Both builder nodes assemble a ``SourcingPlan`` from tool-returned data
(Maximo / SAP / FDP / InTouch + transit estimates). No LLM here; the LLM nodes
that follow (``sourcing_logistics``, ``revise_plan``) refine these plans, but
the initial shape comes from deterministic data joins.
"""

from __future__ import annotations

from google.adk import Context, Event

from agents.schemas import (
    AssetIdentifier,
    CapacityGapRequest,
    GeoPoint,
    SourcingOption,
    SourcingPlan,
    SystemQueryResults,
)
from agents.utils.skill_imports import (
    estimate_transit,
    identify_blockers,
    resolve_canonical_asset,
)


def _instance_to_geopoint(instance: dict) -> GeoPoint:
    """Pull a GeoPoint out of a Maximo instance row's ``location`` field.

    Q8 resolution (TASK-16 Step 9): the Maximo MCP-backed
    ``query_maximo_availability`` now returns ``location.description``
    (real Maximo LOCATIONS column) instead of the legacy
    ``location.label``. Accept either key so this stays robust during
    the migration window.
    """
    loc = instance.get("location") or {}
    return GeoPoint(
        latitude=float(loc.get("latitude", 0.0)),
        longitude=float(loc.get("longitude", 0.0)),
        label=loc.get("description") or loc.get("label") or loc.get("region"),
    )


def _build_option_for_instance(
    request: CapacityGapRequest,
    canonical_id: str,
    instance: dict,
    fdp_approved: bool,
    intouch_specs: list,
) -> SourcingOption:
    """Common SourcingOption assembly for both direct + equivalence paths."""
    asset_payload = resolve_canonical_asset(local_identifier=canonical_id)
    # TASK-16 Step 9: query_intouch_specs now returns list[str] (the
    # ARRAY<STRING> column). For backwards-compat during the migration
    # window, accept either list[str] or the legacy list[{spec_id,...}].
    spec_ids: list[str] = []
    for s in intouch_specs or []:
        if isinstance(s, str):
            spec_ids.append(s)
        elif isinstance(s, dict) and s.get("spec_id"):
            spec_ids.append(str(s["spec_id"]))
    asset = AssetIdentifier(
        **{
            **asset_payload,
            # Splice in the InTouch spec ids we just fetched (they overrule
            # whatever resolve_canonical_asset returned if the catalog has a
            # more current list).
            "intouch_spec_refs": spec_ids or asset_payload.get("intouch_spec_refs", []),
        }
    )
    source = _instance_to_geopoint(instance)
    transit = estimate_transit(
        from_lat=source.latitude,
        from_lon=source.longitude,
        to_lat=request.target_location.latitude,
        to_lon=request.target_location.longitude,
        asset_size_class="downhole_tool",
    )
    blockers = identify_blockers(
        canonical_id_substitute=canonical_id,
        customer_id=request.customer_id or "",
        source_equipment_instance_id=instance.get("equipment_instance_id"),
    )
    return SourcingOption(
        asset=asset,
        source_location=source,
        destination=request.target_location,
        transit_mode=transit["transit_mode"],
        estimated_cost_usd=int(transit["estimated_cost_usd"]),
        transit_hours=float(transit["transit_hours"]),
        certification_hours=float(instance.get("certification_hours_remaining", 0) or 0),
        customer_compatibility=fdp_approved,
        workforce_available=bool(instance.get("workforce_attached")),
        blockers=blockers,
    )


# DEMO NARRATION: "Direct-path plan builder. We found a deployable instance
# in the target region — assemble the SourcingPlan from Maximo location data,
# transit estimates, and the customer's FDP config. Pure data join. The LLM
# in the next node will refine the logistics narrative on top of this shape."
def build_direct_plan(node_input: dict) -> Event:
    """Build the direct-availability SourcingPlan."""
    request = CapacityGapRequest(**node_input["request"])
    results = SystemQueryResults(**node_input["results"])
    instance = node_input["chosen_direct_instance"]

    fdp_approved = bool((results.fdp or {}).get("approved"))
    intouch_specs = list((results.intouch or {}).get("specs", []) or [])
    canonical_id = request.canonical_asset_id or ""

    option = _build_option_for_instance(
        request=request,
        canonical_id=canonical_id,
        instance=instance,
        fdp_approved=fdp_approved,
        intouch_specs=intouch_specs,
    )
    plan = SourcingPlan(
        requested_asset=request.requested_asset,
        target_location=request.target_location,
        deadline=request.deadline,
        primary_option=option,
    )

    return Event(
        message=f"Direct plan built — primary cost ${option.estimated_cost_usd:,}",
        output={
            "request": request.model_dump(mode="json"),
            "results": results.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "path": "direct",
        },
    )


# DEMO NARRATION: "Equivalence-path plan builder. The equivalence LLM node
# already returned a candidate substitute canonical id; we pick a Maximo
# instance of that substitute, assemble a SourcingPlan, and forward. Again,
# no LLM here — the AI's job was to identify the substitute; the workflow's
# job is to ground the plan in concrete tool-returned data."
def build_equivalent_plan(node_input: dict, ctx: Context) -> Event:
    """Build a SourcingPlan around the LLM-chosen equivalent asset.

    ``node_input`` is the equivalence LLM's structured output (the
    candidate substitute). Because the LLM doesn't echo the original
    ``request`` / ``results`` keys, we read those from ``ctx.state``
    (persisted there by parse_capacity_gap_request +
    parallel_system_queries). Treats ``node_input`` itself as the
    ``equivalent_candidate``.
    """
    # The LLM's structured output IS the candidate; fall back to a
    # node_input["equivalent_candidate"] nested form if a future schema
    # change re-wraps it.
    candidate = node_input.get("equivalent_candidate") or node_input or {}

    # request + results live in ctx.state (set by upstream function nodes).
    state_request = {}
    state_results = {}
    try:
        state_request = ctx.state.get("request", {}) or {}
        state_results = ctx.state.get("results", {}) or {}
    except Exception:  # noqa: BLE001 — defensive; ctx.state is usually present
        pass
    # Final fallback: legacy node_input["request"] (pre-refactor shape).
    request_dict = state_request or node_input.get("request") or {}
    results_dict = state_results or node_input.get("results") or {}
    if not request_dict:
        raise ValueError(
            "build_equivalent_plan: no `request` in ctx.state or node_input — "
            "parse_capacity_gap_request must run first and persist the request"
        )
    request = CapacityGapRequest(**request_dict)
    results = SystemQueryResults(**results_dict)

    substitute_canonical_id = candidate.get("canonical_id") or request.canonical_asset_id or ""
    # The equivalence LLM may have already picked a specific instance; fall
    # back to "first deployable instance of the substitute" otherwise.
    instance = candidate.get("equipment_instance") or _first_deployable_of(
        results, substitute_canonical_id
    )
    if instance is None:
        # No deployable instance — emit a degraded plan that the Plan Evaluator
        # will catch (rather than hard-crashing the workflow).
        return Event(
            message=(
                "No deployable instance found for equivalence candidate "
                f"{substitute_canonical_id!r}"
            ),
            output={
                "request": request.model_dump(mode="json"),
                "results": results.model_dump(mode="json"),
                "plan": None,
                "path": "equivalence",
                "equivalent_candidate": candidate,
            },
        )

    fdp_approved = bool((results.fdp or {}).get("approved"))
    intouch_specs = list((results.intouch or {}).get("specs", []) or [])

    option = _build_option_for_instance(
        request=request,
        canonical_id=substitute_canonical_id,
        instance=instance,
        fdp_approved=fdp_approved,
        intouch_specs=intouch_specs,
    )
    plan = SourcingPlan(
        requested_asset=request.requested_asset,
        target_location=request.target_location,
        deadline=request.deadline,
        primary_option=option,
    )

    return Event(
        message=(
            f"Equivalence plan built — substitute {substitute_canonical_id} "
            f"primary cost ${option.estimated_cost_usd:,}"
        ),
        output={
            "request": request.model_dump(mode="json"),
            "results": results.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "path": "equivalence",
            "equivalent_candidate": candidate,
        },
    )


def _first_deployable_of(results: SystemQueryResults, canonical_id: str) -> dict | None:
    """Find the first deployable Maximo instance of a substitute canonical id.

    The parallel-queries node only ran Maximo against the ORIGINAL canonical
    id, so most of the time the substitute won't be in ``results.maximo``.
    The equivalence LLM is expected to surface a candidate instance; this
    helper is the safety net when it forgets.
    """
    if not results.maximo or not results.maximo.get("instances"):
        return None
    for row in results.maximo["instances"]:
        if row.get("canonical_id") == canonical_id and row.get("status") in (
            "available",
            "available_after_recert",
        ):
            return row
    return None
