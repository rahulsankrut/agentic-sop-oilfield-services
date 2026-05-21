"""BQ-direct data access for the 4 composer skill tools.

TASK-MCP-REFACTOR (2026-05-21) — replaces the 4 MCP-mediated calls used
by the KEEP-BQ skill composers (`identify_blockers`,
`query_maximo_availability`, `query_fdp_customer_config`,
`get_start_date_distribution`) with direct BigQuery queries against the
same datasets the MCP backends read from.

Why: the MCP servers are BQ-backed; routing through Cloud Run added
HTTP latency + containerization surface for no incremental value when
the caller is Python code (not the LLM). McpToolset registration on
the agents preserves the LLM's MCP path for cases the composers don't
cover.

The schema this module owns:

    sap_resolve_customer_by_name(name_like)    →  list[{kunnr,name1,…}]
    fdp_list_customer_restrictions(customer_id)→  list[{matnr_substitute_rejected,…}]
    fdp_get_customer_config(customer_id, matnr)→  dict | None
    fdp_list_approved_substitutions(…)         →  list[{matnr_substitute,accepted}]
    maximo_query_assets_by_item(itemnum)       →  list[asset]
    maximo_query_assets_by_region(itemnum, region) → list[asset]
    maximo_get_open_workorders(assetnum, siteid)→  list[wo]
    maximo_get_start_date_distribution(basin)  →  {p10_days,p50_days,p90_days,n}

Each function is a thin SQL → list[dict] mapping, copied from the MCP
backends in mcp_servers/{sap,maximo,fdp}/backend/main.py.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agents.utils.bq_query import bq_query

logger = logging.getLogger(__name__)

_BQ_PROJECT = (
    os.environ.get("BQ_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "vertex-ai-demos-468803"
)
_DS_SAP = os.environ.get("BQ_DATASET_SAP", "sap_extract")
_DS_MAXIMO = os.environ.get("BQ_DATASET_MAXIMO", "maximo_extract")
_DS_FDP = os.environ.get("BQ_DATASET_FDP", "fdp_extract")


def _q(dataset: str, table: str) -> str:
    return f"`{_BQ_PROJECT}.{dataset}.{table}`"


# ---------------------------------------------------------------------------
# SAP — KNA1 customer master
# ---------------------------------------------------------------------------


def sap_get_workforce_by_basin(basin: str) -> dict[str, Any]:
    """ZHR_WORKFORCE snapshot for one basin (zero-filled if unknown)."""
    rows = bq_query(
        f"""
        SELECT BASIN, CREW_COUNT_AVAILABLE, SPECIALIST_COUNT_AVAILABLE,
               ON_CALL_COUNT, NAICS_211_STATE_EMPLOYMENT, DATA_SOURCE,
               SNAPSHOT_DATE
        FROM {_q(_DS_SAP, "ZHR_WORKFORCE")}
        WHERE BASIN = @basin
        LIMIT 1
        """,
        {"basin": basin},
    )
    if not rows:
        return {
            "basin": basin,
            "crew_count_available": 0,
            "specialist_count_available": 0,
            "on_call_count": 0,
            "naics_211_state_employment": None,
            "data_source": None,
            "snapshot_date": "1970-01-01",
        }
    r = rows[0]
    return {
        "basin": r["BASIN"],
        "crew_count_available": int(r["CREW_COUNT_AVAILABLE"] or 0),
        "specialist_count_available": int(r["SPECIALIST_COUNT_AVAILABLE"] or 0),
        "on_call_count": int(r["ON_CALL_COUNT"] or 0),
        # BQ NUMERIC arrives as Decimal which json.dumps can't serialize.
        "naics_211_state_employment": (
            int(r["NAICS_211_STATE_EMPLOYMENT"])
            if r["NAICS_211_STATE_EMPLOYMENT"] is not None
            else None
        ),
        "data_source": r["DATA_SOURCE"],
        "snapshot_date": _iso(r["SNAPSHOT_DATE"]) or "1970-01-01",
    }


def sap_resolve_customer_by_name(name_like: str) -> list[dict[str, Any]]:
    """Substring match (case-insensitive) over KNA1.NAME1."""
    rows = bq_query(
        f"""
        SELECT KUNNR, NAME1, LAND1, ORT01, STRAS
        FROM {_q(_DS_SAP, "KNA1")}
        WHERE LOWER(NAME1) LIKE LOWER(CONCAT('%', @needle, '%'))
        ORDER BY KUNNR
        """,
        {"needle": name_like},
    )
    return [
        {
            "kunnr": r["KUNNR"],
            "name1": r["NAME1"],
            "land1": r["LAND1"],
            "ort01": r["ORT01"],
            "stras": r["STRAS"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# FDP — Customer config + substitutions + restrictions
# ---------------------------------------------------------------------------


def fdp_get_customer_config(customer_id: str, matnr: str) -> dict[str, Any] | None:
    rows = bq_query(
        f"""
        SELECT CUSTOMER_ID, MATNR, APPROVED, NOTES, EFFECTIVE_DATE
        FROM {_q(_DS_FDP, "CUSTOMER_CONFIG")}
        WHERE CUSTOMER_ID = @cid AND MATNR = @matnr
        LIMIT 1
        """,
        {"cid": customer_id, "matnr": matnr},
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "customer_id": r["CUSTOMER_ID"],
        "matnr": r["MATNR"],
        "approved": bool(r["APPROVED"]),
        "notes": r["NOTES"] or None,
        "effective_date": (
            r["EFFECTIVE_DATE"].isoformat() if r["EFFECTIVE_DATE"] else None
        ),
    }


def fdp_list_approved_substitutions(
    customer_id: str, matnr_original: str
) -> list[dict[str, Any]]:
    rows = bq_query(
        f"""
        SELECT CUSTOMER_ID, MATNR_ORIGINAL, MATNR_SUBSTITUTE, ACCEPTED
        FROM {_q(_DS_FDP, "APPROVED_SUBSTITUTIONS")}
        WHERE CUSTOMER_ID = @cid AND MATNR_ORIGINAL = @matnr
        ORDER BY MATNR_SUBSTITUTE
        """,
        {"cid": customer_id, "matnr": matnr_original},
    )
    return [
        {
            "customer_id": r["CUSTOMER_ID"],
            "matnr_original": r["MATNR_ORIGINAL"],
            "matnr_substitute": r["MATNR_SUBSTITUTE"],
            "accepted": bool(r["ACCEPTED"]),
        }
        for r in rows
    ]


def fdp_list_customer_restrictions(customer_id: str) -> list[dict[str, Any]]:
    """Substitutions a customer has REJECTED (ACCEPTED=FALSE)."""
    rows = bq_query(
        f"""
        SELECT CUSTOMER_ID, MATNR_ORIGINAL, MATNR_SUBSTITUTE
        FROM {_q(_DS_FDP, "APPROVED_SUBSTITUTIONS")}
        WHERE CUSTOMER_ID = @cid AND ACCEPTED = FALSE
        ORDER BY MATNR_ORIGINAL, MATNR_SUBSTITUTE
        """,
        {"cid": customer_id},
    )
    return [
        {
            "customer_id": r["CUSTOMER_ID"],
            "matnr_original": r["MATNR_ORIGINAL"],
            "matnr_substitute_rejected": r["MATNR_SUBSTITUTE"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Maximo — ASSET / LOCATIONS / WORKORDER / WO_HISTORY
# ---------------------------------------------------------------------------


_ASSET_SELECT = """
    a.ASSETNUM, a.SITEID, a.ITEMNUM, a.STATUS,
    l.LOCATION, l.DESCRIPTION, l.TYPE AS LOC_TYPE,
    l.STATUS AS LOC_STATUS,
    l.LATITUDE, l.LONGITUDE, l.REGION,
    l.WPI_PORT_INDEX_NUMBER, l.WPI_PORT_NAME
"""


def _asset_row_to_dict(r: dict) -> dict[str, Any]:
    return {
        "assetnum": r["ASSETNUM"],
        "siteid": r["SITEID"],
        "itemnum": r["ITEMNUM"],
        "status": r["STATUS"],
        "location": {
            "description": r["DESCRIPTION"],
            "location": r["LOCATION"],
            "siteid": r["SITEID"],
            "type": r["LOC_TYPE"],
            "status": r["LOC_STATUS"],
            # BQ NUMERIC arrives as `Decimal` which json.dumps can't
            # serialize; cast eagerly to float for downstream consumers.
            "latitude": _f(r["LATITUDE"]) if r["LATITUDE"] is not None else None,
            "longitude": _f(r["LONGITUDE"]) if r["LONGITUDE"] is not None else None,
            "region": r["REGION"],
            "wpi_port_index_number": (
                int(r["WPI_PORT_INDEX_NUMBER"])
                if r["WPI_PORT_INDEX_NUMBER"] is not None
                else None
            ),
            "wpi_port_name": r["WPI_PORT_NAME"],
        },
    }


def maximo_query_assets_by_item(itemnum: str) -> list[dict[str, Any]]:
    rows = bq_query(
        f"""
        SELECT {_ASSET_SELECT}
        FROM {_q(_DS_MAXIMO, "ASSET")} a
        JOIN {_q(_DS_MAXIMO, "LOCATIONS")} l USING (SITEID, LOCATION)
        WHERE a.ITEMNUM = @itemnum
        """,
        {"itemnum": itemnum},
    )
    return [_asset_row_to_dict(r) for r in rows]


def maximo_query_assets_by_region(
    itemnum: str, region: str
) -> list[dict[str, Any]]:
    rows = bq_query(
        f"""
        SELECT {_ASSET_SELECT}
        FROM {_q(_DS_MAXIMO, "ASSET")} a
        JOIN {_q(_DS_MAXIMO, "LOCATIONS")} l USING (SITEID, LOCATION)
        WHERE a.ITEMNUM = @itemnum AND l.REGION = @region
        """,
        {"itemnum": itemnum, "region": region},
    )
    return [_asset_row_to_dict(r) for r in rows]


def maximo_get_open_workorders(
    assetnum: str, siteid: str
) -> list[dict[str, Any]]:
    rows = bq_query(
        f"""
        SELECT WONUM, SITEID, ASSETNUM, LOCATION, STATUS, WORKTYPE,
               REPORTDATE, SCHEDSTART, ACTSTART, ESTLABHRS, ACTLABHRS,
               BSEE_LEASE_REF, BSEE_INCIDENT_DATE
        FROM {_q(_DS_MAXIMO, "WORKORDER")}
        WHERE ASSETNUM = @assetnum AND SITEID = @siteid AND STATUS != 'COMP'
        ORDER BY REPORTDATE DESC
        """,
        {"assetnum": assetnum, "siteid": siteid},
    )
    return [
        {
            "wonum": r["WONUM"],
            "siteid": r["SITEID"],
            "assetnum": r["ASSETNUM"],
            "location": r["LOCATION"],
            "status": r["STATUS"],
            "worktype": r["WORKTYPE"],
            "reportdate": _iso(r["REPORTDATE"]),
            "schedstart": _iso(r["SCHEDSTART"]),
            "actstart": _iso(r["ACTSTART"]),
            "est_lab_hrs": _f(r["ESTLABHRS"]),
            "act_lab_hrs": _f(r["ACTLABHRS"]),
            "bsee_lease_ref": r["BSEE_LEASE_REF"],
            "bsee_incident_date": _iso(r["BSEE_INCIDENT_DATE"]),
        }
        for r in rows
    ]


def maximo_get_start_date_distribution(basin: str) -> dict[str, Any]:
    """Schedule-vs-actual variance quantiles from WO_HISTORY for a basin."""
    rows = bq_query(
        f"""
        SELECT
          APPROX_QUANTILES(variance_days, 100)[OFFSET(10)] AS p10_days,
          APPROX_QUANTILES(variance_days, 100)[OFFSET(50)] AS p50_days,
          APPROX_QUANTILES(variance_days, 100)[OFFSET(90)] AS p90_days,
          COUNT(*) AS n
        FROM {_q(_DS_MAXIMO, "WO_HISTORY")}
        WHERE REGION = @basin
        """,
        {"basin": basin},
    )
    if not rows or rows[0]["n"] == 0 or rows[0]["p50_days"] is None:
        return {"p10_days": 0.0, "p50_days": 0.0, "p90_days": 0.0, "n": 0}
    r = rows[0]
    return {
        "p10_days": float(r["p10_days"]) if r["p10_days"] is not None else 0.0,
        "p50_days": float(r["p50_days"]) if r["p50_days"] is not None else 0.0,
        "p90_days": float(r["p90_days"]) if r["p90_days"] is not None else 0.0,
        "n": int(r["n"]),
    }


def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _f(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "sap_resolve_customer_by_name",
    "sap_get_workforce_by_basin",
    "fdp_get_customer_config",
    "fdp_list_approved_substitutions",
    "fdp_list_customer_restrictions",
    "maximo_query_assets_by_item",
    "maximo_query_assets_by_region",
    "maximo_get_open_workorders",
    "maximo_get_start_date_distribution",
]
