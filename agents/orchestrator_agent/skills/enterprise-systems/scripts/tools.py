"""Tools for the enterprise-systems skill (Maximo, SAP, FDP, InTouch)."""

from __future__ import annotations

from agents.utils.synthetic_data import (
    load_fdp_configurations,
    load_intouch_index,
    load_maximo_inventory,
    load_sap_workforce,
    normalize_customer_id,
)


def query_maximo_availability(
    canonical_id: str,
    region_filter: str | None = None,
) -> list[dict]:
    """Return equipment instances of the given canonical asset.

    Each entry includes ``equipment_instance_id``, ``location``, ``status``,
    ``certification_hours_remaining``, ``workforce_attached``.

    Optional ``region_filter`` ('west_africa', 'north_america', etc.) limits
    the result to that region.
    """
    rows = [row for row in load_maximo_inventory() if row["canonical_id"] == canonical_id]
    if region_filter:
        rows = [r for r in rows if r["location"].get("region") == region_filter]
    return rows


def query_sap_workforce(basin: str) -> dict:
    """Return workforce availability for a basin.

    Returns ``{crew_count_available, specialist_count_available, on_call_count}``.
    If the basin is unknown, returns all-zeros.
    """
    return load_sap_workforce().get(
        basin,
        {"crew_count_available": 0, "specialist_count_available": 0, "on_call_count": 0},
    )


def query_fdp_customer_config(customer_id: str, canonical_id: str) -> dict:
    """Return the customer's FDP config for a given canonical asset.

    Accepts ``customer_id`` as either the slug ("gulf-petroleum") or the
    display name ("Gulf Petroleum"); normalizes before lookup.

    Returns ``{approved: bool, substitution_accepted: dict, notes: str|None}``
    or an empty dict if the customer has no entry for this asset.
    """
    customer_id = normalize_customer_id(customer_id)
    customers = load_fdp_configurations()
    by_asset = customers.get(customer_id, {})
    if canonical_id not in by_asset:
        return {}
    entry = by_asset[canonical_id]
    # Normalize substitution flags into a generic dict keyed by substitute canonical_id
    subs = {}
    for k, v in entry.items():
        if k.endswith("_substitution_accepted"):
            subs[k.replace("_substitution_accepted", "").upper()] = v
    return {
        "approved": entry.get("approved", False),
        "substitution_accepted": subs,
        "notes": entry.get("notes"),
    }


def query_intouch_specs(canonical_id: str) -> list[dict]:
    """Return relevant InTouch document IDs and titles for this canonical asset."""
    index = load_intouch_index()
    return [
        {"spec_id": spec_id, "title": doc["title"]}
        for spec_id, doc in index.items()
        if canonical_id in doc.get("applies_to", [])
    ]
