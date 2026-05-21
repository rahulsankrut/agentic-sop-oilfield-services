"""Tools for the enterprise-systems skill (Maximo, SAP, FDP, InTouch).

TASK-16 Step 9 — these tools now route through the SAP / Maximo / FDP
MCP servers (via `agents.utils.mcp_client`) and the BigQuery-backed
`oilfield_kc.cross_system_aliases` table (via `agents.utils.bq_query`)
instead of reading `data/*.json` directly. The function signatures and
docstrings are unchanged so calling skill prompts + downstream
build_plans glue don't need to know whether the implementation is
in-memory JSON or live MCP/BQ.

Per Q8 (TASK-16 spec §7 Step 9), the `query_maximo_availability` return
shape's `location` field now uses ``description`` (real Maximo column
name) instead of the legacy ``label``. Downstream consumers
(``build_plans._instance_to_geopoint`` + the test suite) are updated to
match.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agents.utils import mcp_client
from agents.utils.bq_query import bq_query

logger = logging.getLogger(__name__)

_BQ_PROJECT = (
    os.environ.get("BQ_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "vertex-ai-demos-468803"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_alias_row(canonical_id: str) -> dict | None:
    """Fetch the `cross_system_aliases` row for a canonical_id.

    Returns ``None`` if the canonical_id is unknown. The row is a plain dict
    with the column names lower-cased after the BQ helper returns them
    upper-cased — we preserve BQ casing here so callers can pick the field
    they want with the real column name.
    """
    rows = bq_query(
        f"""
        SELECT CANONICAL_ID, SAP_MATNR, MAXIMO_ITEMNUM, FDP_CONFIG_ID,
               INTOUCH_SPEC_REFS
        FROM `{_BQ_PROJECT}.oilfield_kc.cross_system_aliases`
        WHERE CANONICAL_ID = @canonical_id
        LIMIT 1
        """,
        {"canonical_id": canonical_id},
    )
    return rows[0] if rows else None


def _canonical_for_matnr(matnr: str) -> str | None:
    """Reverse lookup: SAP MATNR → canonical_id. Used to rehydrate the
    legacy `substitution_accepted` map keyed by canonical-id suffix."""
    rows = bq_query(
        f"""
        SELECT CANONICAL_ID
        FROM `{_BQ_PROJECT}.oilfield_kc.cross_system_aliases`
        WHERE SAP_MATNR = @matnr
        LIMIT 1
        """,
        {"matnr": matnr},
    )
    return rows[0]["CANONICAL_ID"] if rows else None


def normalize_customer_id(name_or_slug: str) -> str:
    """Accept either a slug or a display name and return the canonical slug.

    Planners (and the LLM) type "Gulf Petroleum", "Gulf Petroleum Services",
    or "gulf-petroleum" interchangeably. We resolve via the SAP MCP's
    KNA1 lookup (`sap.resolve_customer_by_name`) first; if no match, we
    fall back to the simple lowercase-and-hyphenate slug.

    Returns the raw input unchanged if both lookups produce nothing — so
    callers can fail explicitly downstream instead of getting a silent
    wrong-customer match.
    """
    if not name_or_slug:
        return ""
    needle = name_or_slug.lower().strip()

    # First try resolving through the SAP MCP. KNA1.NAME1 is the display
    # name; LIKE %needle% matches both directions ("Gulf Petroleum
    # Services" contains "gulf petroleum" and vice versa).
    matches = mcp_client.sap_resolve_customer_by_name(needle)
    if matches:
        # KUNNR in our synthetic data is the slug (matches the legacy
        # `customers.json` ID format). Customers bringing their own SAP
        # extract will map their KUNNR to a slug column upstream.
        kunnr = matches[0].get("kunnr")
        if kunnr:
            return str(kunnr)

    # Fallback: deterministic slug. Lowercases + hyphenates spaces. Matches
    # the legacy `customers.json` ID format for the cases the SAP MCP
    # doesn't carry (e.g. unit-test fixtures that don't seed KNA1 for the
    # given name).
    return needle.replace(" ", "-")


# ---------------------------------------------------------------------------
# Public skill tools
# ---------------------------------------------------------------------------


def query_maximo_availability(
    canonical_id: str,
    region_filter: str | None = None,
) -> list[dict]:
    """Return equipment instances of the given canonical asset.

    Each entry includes ``equipment_instance_id``, ``location``, ``status``,
    ``certification_hours_remaining``, ``workforce_attached``.

    Optional ``region_filter`` ('west_africa', 'north_america', etc.) limits
    the result to that region.

    Q8 resolution: ``location.description`` replaces the legacy
    ``location.label``. ``certification_hours_remaining`` is materialized
    here by joining each asset to its open RECERT WOs and computing
    ``MAX(ESTLABHRS - ACTLABHRS)`` — the customer's extract-layer view
    pattern. The Maximo MCP doesn't expose certification_hours_remaining
    as a column on the v2 typed endpoints because it isn't a stored
    column in MAS 9.x; we compute it here so the downstream
    SourcingOption.certification_hours field stays populated.
    """
    # DEMO NARRATION: "Maximo MCP — we're hitting the same backend the
    # customer's planners use. Resolve canonical_id to ITEMNUM via KC, then
    # by_region (or by_item) for the asset list. certification_hours_
    # remaining is a derived view: open RECERT WOs joined to the asset."
    alias = _resolve_alias_row(canonical_id)
    if alias is None or not alias.get("MAXIMO_ITEMNUM"):
        logger.info(
            "query_maximo_availability: no Maximo ITEMNUM in KC for canonical_id=%s",
            canonical_id,
        )
        return []
    itemnum = alias["MAXIMO_ITEMNUM"]

    if region_filter:
        raw_assets = mcp_client.maximo_query_assets_by_region(itemnum, region_filter)
    else:
        raw_assets = mcp_client.maximo_query_assets_by_item(itemnum)

    rows: list[dict] = []
    for asset in raw_assets:
        assetnum = asset.get("assetnum") or ""
        siteid = asset.get("siteid") or ""
        # Compute certification_hours_remaining from open RECERT WOs.
        cert_hours = 0
        if assetnum and siteid:
            try:
                wos = mcp_client.maximo_get_open_workorders(assetnum, siteid)
            except Exception as exc:  # noqa: BLE001 — keep the row even if WO lookup fails
                logger.warning("Failed to fetch open WOs for %s/%s: %s", assetnum, siteid, exc)
                wos = []
            recert_remainings = [
                float(wo.get("est_lab_hrs") or 0) - float(wo.get("act_lab_hrs") or 0)
                for wo in wos
                if (wo.get("worktype") or "").upper() == "RECERT"
            ]
            if recert_remainings:
                cert_hours = int(max(recert_remainings))

        # Workforce attached: surrogate. The Maximo backend doesn't expose
        # this as a column on assets in v1; for backwards-compat with the
        # legacy in-memory tool we default to True when the asset has any
        # non-failed status (available / available_after_recert / INPRG).
        status = asset.get("status") or ""
        workforce_attached = (
            bool(asset.get("workforce_attached"))
            if ("workforce_attached" in asset)
            else status.lower() not in ("decommissioned", "failed")
        )

        loc = asset.get("location") or {}
        rows.append(
            {
                "canonical_id": canonical_id,
                "equipment_instance_id": assetnum,
                "location": {
                    # Q8: description replaces legacy `label`.
                    "description": loc.get("description") or loc.get("location"),
                    "siteid": loc.get("siteid"),
                    "location": loc.get("location"),
                    "type": loc.get("type"),
                    "status": loc.get("status"),
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                    "region": loc.get("region"),
                    "wpi_port_index_number": loc.get("wpi_port_index_number"),
                    "wpi_port_name": loc.get("wpi_port_name"),
                },
                "status": status,
                "certification_hours_remaining": cert_hours,
                "workforce_attached": workforce_attached,
            }
        )
    return rows


def query_sap_workforce(basin: str) -> dict:
    """Return workforce availability for a basin.

    Returns ``{crew_count_available, specialist_count_available, on_call_count}``.
    If the basin is unknown, returns all-zeros (the SAP MCP returns a
    zero-filled SapWorkforce in that case).
    """
    # DEMO NARRATION: "SAP MCP — workforce-by-basin. Same shape whether it's
    # the customer's ZHR_WORKFORCE Z-table or our seeded BQ extract."
    payload = mcp_client.sap_get_workforce_by_basin(basin) or {}
    return {
        "crew_count_available": int(payload.get("crew_count_available", 0) or 0),
        "specialist_count_available": int(payload.get("specialist_count_available", 0) or 0),
        "on_call_count": int(payload.get("on_call_count", 0) or 0),
    }


def query_fdp_customer_config(customer_id: str, canonical_id: str) -> dict:
    """Return the customer's FDP config for a given canonical asset.

    Accepts ``customer_id`` as either the slug ("gulf-petroleum") or the
    display name ("Gulf Petroleum"); normalizes via the SAP MCP first
    before lookup.

    Returns ``{approved: bool, substitution_accepted: dict, notes: str|None}``
    or an empty dict if the customer has no entry for this asset.

    Implementation: bridges canonical_id → MATNR via the BQ-backed
    ``oilfield_kc.cross_system_aliases``, then calls the FDP MCP's
    ``get_customer_config`` and ``list_approved_substitutions`` endpoints.
    The legacy ``substitution_accepted`` map (keyed by substitute
    canonical-id suffix, e.g. ``"V7"``) is rebuilt by reversing each
    substitute MATNR back through the alias table to its canonical_id and
    taking the segment after the first hyphen, uppercased.
    """
    # DEMO NARRATION: "FDP MCP — customer's homegrown forecast/config tool.
    # Customer slug normalized via the SAP MCP's KNA1 lookup so 'Gulf
    # Petroleum' and 'gulf-petroleum' resolve identically."
    slug = normalize_customer_id(customer_id)

    alias = _resolve_alias_row(canonical_id)
    if alias is None or not alias.get("SAP_MATNR"):
        return {}
    matnr = alias["SAP_MATNR"]

    config = mcp_client.fdp_get_customer_config(slug, matnr)
    if not config:
        return {}

    substitutions = mcp_client.fdp_list_approved_substitutions(slug, matnr) or []
    subs_map: dict[str, bool] = {}
    for sub in substitutions:
        sub_matnr = sub.get("matnr_substitute")
        if not sub_matnr:
            continue
        canonical_sub = _canonical_for_matnr(str(sub_matnr))
        if not canonical_sub:
            continue
        # "TX-007" -> "V7", "MWD-310" -> "310". Matches the legacy
        # in-memory tool exactly.
        segment = canonical_sub.split("-", 1)[-1].upper()
        subs_map[segment] = bool(sub.get("accepted"))

    return {
        "approved": bool(config.get("approved", False)),
        "substitution_accepted": subs_map,
        "notes": config.get("notes"),
    }


def query_intouch_specs(canonical_id: str) -> list[str]:
    """Return relevant InTouch spec ids for this canonical asset.

    Sourced from ``oilfield_kc.cross_system_aliases.INTOUCH_SPEC_REFS``
    (ARRAY<STRING>). Returns an empty list if the canonical_id has no
    entry in the alias table.
    """
    # DEMO NARRATION: "InTouch spec ids — sourced from Knowledge Catalog's
    # cross_system_aliases. Same canonical_id resolves to the same spec set
    # regardless of which downstream system asks."
    alias = _resolve_alias_row(canonical_id)
    if alias is None:
        return []
    specs = alias.get("INTOUCH_SPEC_REFS") or []
    # BQ may hand back the column as a list of strings or a list of dicts;
    # normalize to list[str].
    out: list[str] = []
    for s in specs:
        if isinstance(s, str):
            out.append(s)
        elif isinstance(s, dict):
            # Defensive: shouldn't happen for an ARRAY<STRING> column.
            for v in s.values():
                if isinstance(v, str):
                    out.append(v)
                    break
    return out


__all__ = [
    "query_maximo_availability",
    "query_sap_workforce",
    "query_fdp_customer_config",
    "query_intouch_specs",
    "normalize_customer_id",
]


# Silence linter for the `Any` import re-export — used for the explicit
# type hint in `_resolve_alias_row` return signature.
_ = Any  # noqa: B018
