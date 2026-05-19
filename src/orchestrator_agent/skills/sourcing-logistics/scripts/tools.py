"""Tools for the sourcing-logistics skill."""

from __future__ import annotations

import math

from src.utils.synthetic_data import get_customer, load_maximo_inventory

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


def identify_blockers(
    canonical_id_substitute: str,
    customer_id: str,
    source_equipment_instance_id: str | None = None,
) -> list[str]:
    """Surface issues that would block this sourcing option.

    Currently considers:
    - Customer config restriction (substitution disallowed).
    - Workforce / certification at the source (from Maximo inventory record).
    """
    blockers: list[str] = []

    customer = get_customer(customer_id) or {}
    restricted = customer.get("substitution_restrictions", [])
    if canonical_id_substitute in restricted:
        blockers.append(
            f"Customer {customer_id} restricts substitution to {canonical_id_substitute}"
        )

    if source_equipment_instance_id:
        inv = {x["equipment_instance_id"]: x for x in load_maximo_inventory()}
        item = inv.get(source_equipment_instance_id)
        if item is None:
            blockers.append(
                f"Equipment instance {source_equipment_instance_id} not found in Maximo"
            )
        else:
            if item.get("status") not in ("available", "available_after_recert"):
                blockers.append(f"Equipment status is '{item['status']}' — not deployable")
            if not item.get("workforce_attached"):
                blockers.append("No workforce attached to this equipment instance")

    return blockers
