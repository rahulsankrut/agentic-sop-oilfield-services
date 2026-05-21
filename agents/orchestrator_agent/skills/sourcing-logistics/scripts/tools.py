"""Tools for the sourcing-logistics skill.

TASK-16 Step 10: ``identify_blockers`` migrated to use MCP backends +
``oilfield_kc.cross_system_aliases`` via the BQ query helper instead of
the legacy ``customers.json`` / ``maximo_inventory.json`` JSON reads.

``estimate_transit`` and ``calculate_sourcing_cost`` stay pure-Python
(haversine + thresholds) — no data lookups, nothing to migrate.
"""

from __future__ import annotations

import math

from agents.utils import enterprise_data as ed
from agents.utils.bq_query import BQ_PROJECT, bq_query

# Distance thresholds in km
GROUND_TRANSIT_MAX_KM = 250
SEA_FREIGHT_MAX_KM = 8000


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_transit(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    asset_size_class: str = "downhole_tool",
) -> dict:
    """Estimate transit mode, time, and cost between two locations.

    Args:
        from_lat / from_lon: source coordinates.
        to_lat / to_lon: destination coordinates.
        asset_size_class: hint that affects cargo charter cost — one of
            ``downhole_tool``, ``surface_equipment``, ``frac_spread``.

    Returns:
        ``{transit_mode, transit_hours, estimated_cost_usd, distance_km}``.
    """
    distance_km = _haversine_km(from_lat, from_lon, to_lat, to_lon)

    if distance_km <= GROUND_TRANSIT_MAX_KM:
        mode = "ground_transit"
        # ~60 km/h effective + a 4h prep block; $200 per km
        hours = (distance_km / 60.0) + 4.0
        base_cost = int(distance_km * 200)
    elif distance_km <= SEA_FREIGHT_MAX_KM:
        mode = "sea_freight"
        # ~40 km/h effective + 24h prep + 24h customs/handling
        hours = (distance_km / 40.0) + 48.0
        base_cost = int(distance_km * 80)
    else:
        mode = "cargo_charter"
        # ~750 km/h ground speed equivalent + 8h ground handling
        hours = (distance_km / 750.0) + 8.0
        # Charter rate ~$50/km baseline plus asset-class multiplier
        multiplier = {"downhole_tool": 1.0, "surface_equipment": 1.4, "frac_spread": 1.8}.get(
            asset_size_class, 1.0
        )
        base_cost = int(distance_km * 50 * multiplier)

    return {
        "transit_mode": mode,
        "transit_hours": round(hours, 1),
        "estimated_cost_usd": base_cost,
        "distance_km": round(distance_km, 1),
    }


def calculate_sourcing_cost(  # noqa: PLR0913 — config-heavy cost calc is naturally wide
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    asset_size_class: str = "downhole_tool",
    certification_hours: float = 0,
    cross_border: bool = False,
) -> int:
    """Fully-loaded sourcing cost in USD.

    Adds certification labor (at $150/hr) and a flat $5K customs/clearance
    surcharge for cross-border movements.
    """
    transit = estimate_transit(from_lat, from_lon, to_lat, to_lon, asset_size_class)
    cost = transit["estimated_cost_usd"]
    cost += int(certification_hours * 150)
    if cross_border:
        cost += 5000
    return cost


# ---------------------------------------------------------------------------
# identify_blockers — migrated to MCP + BQ backends (TASK-16 Step 10)
# ---------------------------------------------------------------------------


def _normalize_customer_id(raw: str) -> str:
    """Slug-or-display-name → canonical slug.

    Tries SAP MCP's ``sap_resolve_customer_by_name`` first; if the
    input matches a KNA1 NAME1, derive a slug from NAME1 (lowercased,
    spaces → hyphens, "Services"/"Corp"-style suffixes stripped).
    Falls back to the obvious local heuristic (lowercase + replace
    spaces with hyphens) when the SAP lookup returns nothing — which
    is also the path the existing tests use (they pass ``gulf-petroleum``
    as a literal slug; the helper short-circuits when input already
    looks like one).
    """
    if not raw:
        return ""
    needle = raw.strip()

    # Slug shape (lowercase + hyphens, no spaces) — assume already canonical.
    if needle and needle == needle.lower() and " " not in needle:
        return needle

    # Display name: ask SAP MCP. The KNA1 NAME1 → slug bridge isn't stored
    # anywhere directly, so we derive it the same way the original
    # `customers.json` slugs were minted: lowercase the first 1-2 NAME1
    # tokens and join with hyphens.
    matches = ed.sap_resolve_customer_by_name(needle) or []
    if matches:
        name1 = matches[0].get("name1", "")
        return _slug_from_name1(name1) or needle.lower().replace(" ", "-")

    return needle.lower().replace(" ", "-")


def _slug_from_name1(name1: str) -> str:
    """Derive the legacy customer-id slug from a SAP NAME1.

    Matches the convention in ``data/customers.json``: take the first two
    tokens (excluding generic corporate suffixes), lowercase, join with
    hyphens. ``"Gulf Petroleum Services"`` → ``"gulf-petroleum"``.
    """
    if not name1:
        return ""
    suffixes = {"services", "co", "co.", "ltd", "ltd.", "inc", "inc.", "corp", "corp.", "company"}
    tokens = [t for t in name1.lower().split() if t not in suffixes]
    return "-".join(tokens[:2])


def _resolve_canonical_to_matnr(canonical_id: str) -> str | None:
    """Look up the SAP MATNR for a canonical asset id via cross_system_aliases."""
    rows = bq_query(
        f"SELECT SAP_MATNR FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases` "
        "WHERE CANONICAL_ID = @cid LIMIT 1",
        {"cid": canonical_id},
    )
    return rows[0]["SAP_MATNR"] if rows else None


def _resolve_canonical_to_itemnum(canonical_id: str) -> str | None:
    """Look up the Maximo ITEMNUM for a canonical asset id."""
    rows = bq_query(
        f"SELECT MAXIMO_ITEMNUM FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases` "
        "WHERE CANONICAL_ID = @cid LIMIT 1",
        {"cid": canonical_id},
    )
    return rows[0]["MAXIMO_ITEMNUM"] if rows else None


def _customer_restriction_blocker(canonical_id_substitute: str, customer_id: str) -> str | None:
    """Return a 'restricts substitution' blocker string, or None."""
    matnr_sub = _resolve_canonical_to_matnr(canonical_id_substitute)
    if not matnr_sub:
        return None
    normalized = _normalize_customer_id(customer_id)
    restrictions = ed.fdp_list_customer_restrictions(normalized) or []
    for r in restrictions:
        if r.get("matnr_substitute_rejected") == matnr_sub:
            return f"Customer {customer_id} restricts substitution to {canonical_id_substitute}"
    return None


def _open_recert_hours_remaining(assetnum: str, siteid: str) -> float:
    """Sum (est_lab_hrs - act_lab_hrs) across open RECERT work orders."""
    total = 0.0
    wos = ed.maximo_get_open_workorders(assetnum, siteid) or []
    for wo in wos:
        if (wo.get("worktype") or "").upper() != "RECERT":
            continue
        est = float(wo.get("est_lab_hrs") or 0)
        act = float(wo.get("act_lab_hrs") or 0)
        if est - act > 0:
            total += est - act
    return total


def _equipment_blockers(
    canonical_id_substitute: str, source_equipment_instance_id: str
) -> list[str]:
    """Return blockers for the equipment-instance leg of identify_blockers."""
    itemnum = _resolve_canonical_to_itemnum(canonical_id_substitute)
    matched: dict | None = None
    if itemnum:
        for a in ed.maximo_query_assets_by_item(itemnum) or []:
            if a.get("assetnum") == source_equipment_instance_id:
                matched = a
                break
    if matched is None:
        return [f"Equipment instance {source_equipment_instance_id} not found"]

    cert_hours = _open_recert_hours_remaining(
        source_equipment_instance_id, matched.get("siteid", "")
    )
    if cert_hours > 0:
        return [
            f"Equipment {source_equipment_instance_id} has "
            f"{cert_hours:g} certification hours remaining"
        ]
    return []


def identify_blockers(
    canonical_id_substitute: str,
    customer_id: str,
    source_equipment_instance_id: str | None = None,
) -> list[str]:
    """Surface issues that would block this sourcing option.

    Migrated to MCP + BQ backends (TASK-16 Step 10):

    1. **Customer-restriction check** — call FDP MCP's
       ``list_customer_restrictions(customer_id)``. If the substitute's
       resolved SAP MATNR appears as ``matnr_substitute_rejected`` in any
       restriction row, append a ``"Customer X restricts substitution
       to Y"`` blocker.
    2. **Equipment-instance check** (when ``source_equipment_instance_id``
       is given) — resolve the canonical_id to a Maximo ITEMNUM, query
       Maximo MCP for assets matching that ITEMNUM, and filter by
       ``assetnum == source_equipment_instance_id``. If no match,
       append ``"Equipment instance ... not found"``. If the matched
       asset has open RECERT WOs with remaining cert hours
       (``est_lab_hrs - act_lab_hrs > 0``), append a
       ``"has N certification hours remaining"`` blocker.

    The ``workforce_attached`` check from the JSON era is **deliberately
    skipped** — the seeder synthesized it from no real signal and the
    customer's production derivation (LABTRANS join) returns different
    numbers, so a placeholder here would be misleading. The spec §5
    note explicitly flags it as synthesized-signature; we drop rather
    than fake it.
    """
    blockers: list[str] = []

    restriction = _customer_restriction_blocker(canonical_id_substitute, customer_id)
    if restriction:
        blockers.append(restriction)

    if source_equipment_instance_id:
        blockers.extend(_equipment_blockers(canonical_id_substitute, source_equipment_instance_id))

    return blockers
