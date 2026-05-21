"""IBM Maximo backend for the Maximo MCP server — BQ-backed (TASK-16 Step 6).

This FastAPI app exposes Maximo-shaped endpoints that query the
`maximo_extract.*` BigQuery dataset (ASSET / ITEM / INVENTORY /
INVBALANCES / LOCATIONS / WORKORDER + the WO_HISTORY view). It is
fronted by the genai-toolbox MCP server (`../config.yaml`) which exposes
these endpoints as typed MCP tools to the Orchestrator.

Substitution path: a customer with live Maximo via the MAS REST API
replaces the BQ queries below with REST calls. The tool surface stays
identical — agent prompts and Pydantic schemas never see the
implementation change.

Endpoints (v2 — typed, matched 1:1 to the §4 tool surface):

  GET  /health
  GET  /maximo/v2/item/{itemnum}                                 → MaximoItem
  GET  /maximo/v2/assets/by_item/{itemnum}?status=&siteid=       → list[MaximoAssetWithLocation]
  GET  /maximo/v2/assets/by_region/{itemnum}?region=             → list[MaximoAssetWithLocation]
  GET  /maximo/v2/inventory_balances/{itemnum}?siteid=           → list[InvBalance]
  GET  /maximo/v2/location/{siteid}/{location}                   → MaximoLocation
  GET  /maximo/v2/open_workorders/{assetnum}/{siteid}            → list[MaximoWorkOrder]
  GET  /maximo/v2/start_date_distribution/{basin}?customer_id=&asset_class=  → StartDateDistribution

Legacy (kept as thin wrappers per spec §7 Step 6; retire after one release):

  POST /maximo/availability                                      → AvailabilityResponse
  GET  /maximo/equipment/{equipment_instance_id}                 → EquipmentInstance

Environment:
  BQ_PROJECT / GOOGLE_CLOUD_PROJECT  — defaults to vertex-ai-demos-468803
  BQ_DATASET_MAXIMO                  — defaults to maximo_extract
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from google.cloud import bigquery
from pydantic import BaseModel, Field

from agents.schemas import (
    InvBalance,
    MaximoAssetWithLocation,
    MaximoItem,
    MaximoLocation,
    MaximoWorkOrder,
    StartDateDistribution,
)

# DEMO NARRATION: "This is the Maximo MCP server backend. In production it
# sits in front of the customer's actual IBM Maximo install — registered
# with Agent Registry, reached only through Agent Gateway, scanned by
# Model Armor on the way in. In our reference solution it queries the
# `maximo_extract.*` BigQuery dataset; the tool surface above doesn't
# change when a customer swaps in their live MAS REST endpoint."

logger = logging.getLogger("maximo-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

BQ_PROJECT = (
    os.environ.get("BQ_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT", "vertex-ai-demos-468803")
)
BQ_DATASET = os.environ.get("BQ_DATASET_MAXIMO", "maximo_extract")


@lru_cache(maxsize=1)
def _bq() -> bigquery.Client:
    """Lazy BQ client — created once per process."""
    return bigquery.Client(project=BQ_PROJECT)


def _qualified(table: str) -> str:
    return f"`{BQ_PROJECT}.{BQ_DATASET}.{table}`"


def _bq_type(v: object) -> str:
    if isinstance(v, bool):
        return "BOOL"
    if isinstance(v, int):
        return "INT64"
    if isinstance(v, float):
        return "FLOAT64"
    return "STRING"


def _run_query(sql: str, params: dict) -> list[dict]:
    """Run a parameterized SELECT and return rows as dicts."""
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(k, _bq_type(v), v) for k, v in params.items()
        ],
    )
    job = _bq().query(sql, job_config=job_config)
    return [dict(r) for r in job.result()]


def _f(v) -> float | None:
    """Decimal/None → float coercion (BQ NUMERIC arrives as decimal.Decimal)."""
    return float(v) if v is not None else None


def _iso(v) -> str | None:
    """date/datetime → ISO string; None passes through."""
    return v.isoformat() if v is not None else None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="IBM Maximo (BQ-backed)",
    description="BQ-backed Maximo backend behind the Maximo MCP server.",
    version="2.0.0",
)


# Legacy response shapes — kept so existing TASK-05 integration callers
# don't break while skill tools migrate to the v2 typed shapes.
class AvailabilityRequest(BaseModel):
    canonical_id: str = Field(..., description="Canonical asset id (e.g. 'TX-001').")
    region_filter: Optional[str] = Field(
        default=None,
        description=(
            "Optional region slug to narrow the list "
            "('north_america', 'europe', 'asia_pacific', 'west_africa', ...)."
        ),
    )


class EquipmentLocation(BaseModel):
    label: str
    latitude: float
    longitude: float
    region: str


class EquipmentInstance(BaseModel):
    canonical_id: str
    equipment_instance_id: str
    location: EquipmentLocation
    status: str
    certification_hours_remaining: int
    workforce_attached: bool


class AvailabilityResponse(BaseModel):
    canonical_id: str
    region_filter: Optional[str] = None
    count: int
    instances: list[EquipmentInstance]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_location(r: dict) -> MaximoLocation:
    return MaximoLocation(
        siteid=r["SITEID"],
        location=r["LOCATION"],
        description=r.get("DESCRIPTION"),
        type=r.get("TYPE"),
        status=r.get("STATUS"),
        latitude=_f(r.get("LATITUDE")),
        longitude=_f(r.get("LONGITUDE")),
        region=r.get("REGION"),
        wpi_port_index_number=(
            int(r["WPI_PORT_INDEX_NUMBER"]) if r.get("WPI_PORT_INDEX_NUMBER") is not None else None
        ),
        wpi_port_name=r.get("WPI_PORT_NAME"),
    )


def _row_to_asset_with_location(r: dict) -> MaximoAssetWithLocation:
    """Map a row from `ASSET ⋈ LOCATIONS` (USING SITEID, LOCATION) to the
    typed shape. Location columns are aliased `loc_*` in the SELECT to avoid
    column-name collisions with ASSET's STATUS / LOCATION."""
    loc = MaximoLocation(
        siteid=r["SITEID"],
        location=r["LOCATION"],
        description=r.get("loc_description"),
        type=r.get("loc_type"),
        status=r.get("loc_status"),
        latitude=_f(r.get("loc_latitude")),
        longitude=_f(r.get("loc_longitude")),
        region=r.get("loc_region"),
        wpi_port_index_number=(
            int(r["loc_wpi_port_index_number"])
            if r.get("loc_wpi_port_index_number") is not None
            else None
        ),
        wpi_port_name=r.get("loc_wpi_port_name"),
    )
    return MaximoAssetWithLocation(
        assetnum=r["ASSETNUM"],
        itemnum=r.get("ITEMNUM"),
        status=r["STATUS"],
        siteid=r["SITEID"],
        description=r.get("DESCRIPTION"),
        serialnum=r.get("SERIALNUM"),
        assettype=r.get("ASSETTYPE"),
        installdate=_iso(r.get("INSTALLDATE")),
        location=loc,
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "maximo-bq",
        "project": BQ_PROJECT,
        "dataset": BQ_DATASET,
    }


# ---------------------------------------------------------------------------
# /maximo/v2/* — typed endpoints (the tool surface per spec §4)
# ---------------------------------------------------------------------------


@app.get("/maximo/v2/item/{itemnum}", response_model=MaximoItem)
async def get_item(itemnum: str) -> MaximoItem:
    rows = _run_query(
        f"""
        SELECT ITEMNUM, ITEMSETID, DESCRIPTION, COMMODITYGROUP
        FROM {_qualified("ITEM")}
        WHERE ITEMNUM = @itemnum
        LIMIT 1
        """,
        {"itemnum": itemnum},
    )
    if not rows:
        raise HTTPException(404, f"No Maximo item for ITEMNUM={itemnum}")
    r = rows[0]
    return MaximoItem(
        itemnum=r["ITEMNUM"],
        itemsetid=r["ITEMSETID"] or "SET1",
        description=r["DESCRIPTION"],
        commoditygroup=r["COMMODITYGROUP"],
    )


# Shared SELECT list for ASSET ⋈ LOCATIONS — used by both by_item and
# by_region. Location columns aliased to `loc_*` (see _row_to_asset_with_location).
_ASSET_WITH_LOCATION_SELECT = """
    a.ASSETNUM, a.ITEMNUM, a.STATUS, a.SITEID, a.LOCATION,
    a.DESCRIPTION, a.SERIALNUM, a.ASSETTYPE, a.INSTALLDATE,
    l.DESCRIPTION           AS loc_description,
    l.TYPE                  AS loc_type,
    l.STATUS                AS loc_status,
    l.LATITUDE              AS loc_latitude,
    l.LONGITUDE             AS loc_longitude,
    l.REGION                AS loc_region,
    l.WPI_PORT_INDEX_NUMBER AS loc_wpi_port_index_number,
    l.WPI_PORT_NAME         AS loc_wpi_port_name
"""


@app.get(
    "/maximo/v2/assets/by_item/{itemnum}",
    response_model=list[MaximoAssetWithLocation],
)
async def query_assets_by_item(
    itemnum: str,
    status: str | None = None,
    siteid: str | None = None,
) -> list[MaximoAssetWithLocation]:
    sql = (
        f"SELECT {_ASSET_WITH_LOCATION_SELECT} "
        f"FROM {_qualified('ASSET')} a "
        f"JOIN {_qualified('LOCATIONS')} l USING (SITEID, LOCATION) "
        f"WHERE a.ITEMNUM = @itemnum"
    )
    params: dict = {"itemnum": itemnum}
    if status:
        sql += " AND a.STATUS = @status"
        params["status"] = status
    if siteid:
        sql += " AND a.SITEID = @siteid"
        params["siteid"] = siteid
    rows = _run_query(sql, params)
    return [_row_to_asset_with_location(r) for r in rows]


@app.get(
    "/maximo/v2/assets/by_region/{itemnum}",
    response_model=list[MaximoAssetWithLocation],
)
async def query_assets_by_region(
    itemnum: str,
    region: str = Query(..., description="Region slug (e.g. 'west_africa')."),
) -> list[MaximoAssetWithLocation]:
    """Substitutes the legacy `query_maximo_availability(canonical_id, region)`.

    Joins ASSET ⋈ LOCATIONS on (SITEID, LOCATION) and filters by
    `l.REGION`. Skill tools resolve canonical_id → ITEMNUM upstream via KC
    before calling.
    """
    rows = _run_query(
        f"""
        SELECT {_ASSET_WITH_LOCATION_SELECT}
        FROM {_qualified("ASSET")} a
        JOIN {_qualified("LOCATIONS")} l USING (SITEID, LOCATION)
        WHERE a.ITEMNUM = @itemnum AND l.REGION = @region
        """,
        {"itemnum": itemnum, "region": region},
    )
    return [_row_to_asset_with_location(r) for r in rows]


@app.get(
    "/maximo/v2/inventory_balances/{itemnum}",
    response_model=list[InvBalance],
)
async def get_inventory_balances(
    itemnum: str, siteid: str | None = None
) -> list[InvBalance]:
    sql = (
        "SELECT ITEMNUM, ITEMSETID, LOCATION, SITEID, BINNUM, LOTNUM, "
        "       CONDITIONCODE, PHYSCNT, PHYSCNTDATE, CURBAL "
        f"FROM {_qualified('INVBALANCES')} "
        "WHERE ITEMNUM = @itemnum"
    )
    params: dict = {"itemnum": itemnum}
    if siteid:
        sql += " AND SITEID = @siteid"
        params["siteid"] = siteid
    rows = _run_query(sql, params)
    return [
        InvBalance(
            itemnum=r["ITEMNUM"],
            itemsetid=r["ITEMSETID"] or "SET1",
            location=r["LOCATION"],
            siteid=r["SITEID"],
            binnum=r["BINNUM"],
            lotnum=r["LOTNUM"],
            conditioncode=r["CONDITIONCODE"],
            physcnt=_f(r["PHYSCNT"]),
            physcntdate=_iso(r["PHYSCNTDATE"]),
            curbal=_f(r["CURBAL"]),
        )
        for r in rows
    ]


@app.get("/maximo/v2/location/{siteid}/{location}", response_model=MaximoLocation)
async def get_location(siteid: str, location: str) -> MaximoLocation:
    rows = _run_query(
        f"""
        SELECT LOCATION, SITEID, ORGID, DESCRIPTION, TYPE, STATUS,
               LATITUDE, LONGITUDE, REGION,
               WPI_PORT_INDEX_NUMBER, WPI_PORT_NAME
        FROM {_qualified("LOCATIONS")}
        WHERE SITEID = @siteid AND LOCATION = @location
        LIMIT 1
        """,
        {"siteid": siteid, "location": location},
    )
    if not rows:
        raise HTTPException(404, f"No Maximo location for SITEID={siteid}, LOCATION={location}")
    return _row_to_location(rows[0])


@app.get(
    "/maximo/v2/open_workorders/{assetnum}/{siteid}",
    response_model=list[MaximoWorkOrder],
)
async def get_open_workorders(assetnum: str, siteid: str) -> list[MaximoWorkOrder]:
    rows = _run_query(
        f"""
        SELECT WONUM, SITEID, ASSETNUM, LOCATION, STATUS, WORKTYPE,
               REPORTDATE, SCHEDSTART, ACTSTART, ESTLABHRS, ACTLABHRS,
               BSEE_LEASE_REF, BSEE_INCIDENT_DATE
        FROM {_qualified("WORKORDER")}
        WHERE ASSETNUM = @assetnum AND SITEID = @siteid AND STATUS != 'COMP'
        ORDER BY REPORTDATE DESC
        """,
        {"assetnum": assetnum, "siteid": siteid},
    )
    return [
        MaximoWorkOrder(
            wonum=r["WONUM"],
            siteid=r["SITEID"],
            assetnum=r["ASSETNUM"],
            location=r["LOCATION"],
            status=r["STATUS"],
            worktype=r["WORKTYPE"],
            reportdate=_iso(r["REPORTDATE"]),
            schedstart=_iso(r["SCHEDSTART"]),
            actstart=_iso(r["ACTSTART"]),
            est_lab_hrs=_f(r["ESTLABHRS"]),
            act_lab_hrs=_f(r["ACTLABHRS"]),
            bsee_lease_ref=r["BSEE_LEASE_REF"],
            bsee_incident_date=_iso(r["BSEE_INCIDENT_DATE"]),
        )
        for r in rows
    ]


@app.get(
    "/maximo/v2/start_date_distribution/{basin}",
    response_model=StartDateDistribution,
)
async def get_start_date_distribution(
    basin: str,
    customer_id: str | None = None,
    asset_class: str | None = None,
) -> StartDateDistribution:
    """Schedule-vs-actual variance quantiles from the WO_HISTORY view.

    Queries `maximo_extract.WO_HISTORY` (defined in scripts/bq/ddl/maximo_extract.sql),
    which is `WORKORDER` ⋈ `ASSET` ⋈ `LOCATIONS` filtered to STATUS='COMP'
    + ACTSTART IS NOT NULL. The view exposes `variance_days = ACTSTART -
    SCHEDSTART` in days. We compute APPROX_QUANTILES at offsets 10/50/90
    over `variance_days` filtered by `REGION = @basin`. The optional
    `customer_id` / `asset_class` filters are reserved for future
    expansion (no WO ↔ customer / asset-class join in v1 — WO_HISTORY
    doesn't yet carry them); accepted as no-ops so the tool signature
    stays stable.

    Per Q7 resolution: variance lives on the Maximo MCP, not a separate
    skill-side BQ client. Substitution path: customer's Maximo dump has
    the same WORKORDER columns; the view definition is portable as-is.

    Returns dates derived by adding (p10/p50/p90 in days) to a reference
    `requested_date` (today, UTC) — `StartDateDistribution` is shaped as
    actual datetimes, not raw day counts.
    """
    rows = _run_query(
        f"""
        SELECT
          APPROX_QUANTILES(variance_days, 100)[OFFSET(10)] AS p10_days,
          APPROX_QUANTILES(variance_days, 100)[OFFSET(50)] AS p50_days,
          APPROX_QUANTILES(variance_days, 100)[OFFSET(90)] AS p90_days,
          COUNT(*) AS n
        FROM {_qualified("WO_HISTORY")}
        WHERE REGION = @basin
        """,
        {"basin": basin},
    )
    # No completed-WO history for the basin yet (e.g. v1 seed has only
    # INPRG workorders for some basins). Match TASK-05 behavior: return a
    # tight zero-variance distribution rather than 404 so downstream
    # skills don't have to special-case.
    requested_date = datetime.now(timezone.utc)
    if not rows or rows[0]["n"] == 0 or rows[0]["p50_days"] is None:
        logger.info("start_date_distribution basin=%s -> no history, returning zeros", basin)
        return StartDateDistribution(
            requested_date=requested_date,
            p10_actual_date=requested_date,
            p50_actual_date=requested_date,
            p90_actual_date=requested_date,
            confidence=0.0,
        )
    r = rows[0]
    n = int(r["n"])
    # Heuristic confidence: log-scaled count, capped at 0.95. 10 WOs → ~0.5;
    # 100 → ~0.85; 1000 → ~0.95.
    confidence = min(0.95, max(0.1, 0.25 + 0.25 * (n**0.5) / 10))
    return StartDateDistribution(
        requested_date=requested_date,
        p10_actual_date=requested_date + timedelta(days=float(r["p10_days"])),
        p50_actual_date=requested_date + timedelta(days=float(r["p50_days"])),
        p90_actual_date=requested_date + timedelta(days=float(r["p90_days"])),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Legacy endpoints — thin wrappers so existing callers don't break during
# the migration. Retire after one release per spec §4 / §7 Step 6.
# ---------------------------------------------------------------------------


@app.post("/maximo/availability", response_model=AvailabilityResponse)
async def availability_legacy(req: AvailabilityRequest) -> AvailabilityResponse:
    """Bridge canonical_id → Maximo ITEMNUM via cross_system_aliases, then
    re-shape the v2 `MaximoAssetWithLocation` rows to the legacy
    `EquipmentInstance` wire format. New skill tools should call
    `/maximo/v2/assets/by_region` directly.
    """
    alias_rows = _run_query(
        f"""
        SELECT MAXIMO_ITEMNUM
        FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases`
        WHERE CANONICAL_ID = @canonical_id
        LIMIT 1
        """,
        {"canonical_id": req.canonical_id},
    )
    if not alias_rows or not alias_rows[0]["MAXIMO_ITEMNUM"]:
        return AvailabilityResponse(
            canonical_id=req.canonical_id,
            region_filter=req.region_filter,
            count=0,
            instances=[],
        )
    itemnum = alias_rows[0]["MAXIMO_ITEMNUM"]
    if req.region_filter:
        assets = await query_assets_by_region(itemnum, req.region_filter)
    else:
        assets = await query_assets_by_item(itemnum)
    # Legacy shape: certification_hours_remaining + workforce_attached are
    # extract-layer materializations (see CLAUDE.md gotcha — derived from
    # MAX(ESTLABHRS-ACTLABHRS) over open RECERT WOs joined to LABTRANS).
    # Not yet materialized in BQ; surface zeros / False so legacy callers
    # still get a well-formed response.
    instances = [
        EquipmentInstance(
            canonical_id=req.canonical_id,
            equipment_instance_id=a.assetnum,
            location=EquipmentLocation(
                label=a.location.description or a.location.location,
                latitude=a.location.latitude or 0.0,
                longitude=a.location.longitude or 0.0,
                region=a.location.region or "",
            ),
            status=a.status,
            certification_hours_remaining=0,
            workforce_attached=False,
        )
        for a in assets
    ]
    logger.info(
        "legacy availability canonical_id=%s region=%s -> %d instances",
        req.canonical_id,
        req.region_filter,
        len(instances),
    )
    return AvailabilityResponse(
        canonical_id=req.canonical_id,
        region_filter=req.region_filter,
        count=len(instances),
        instances=instances,
    )


@app.get(
    "/maximo/equipment/{equipment_instance_id}",
    response_model=EquipmentInstance,
)
async def get_equipment_legacy(equipment_instance_id: str) -> EquipmentInstance:
    """Fetch a single Maximo asset by ASSETNUM and reshape to the legacy
    EquipmentInstance contract. Bridges canonical_id back via
    cross_system_aliases."""
    rows = _run_query(
        f"""
        SELECT a.ASSETNUM, a.ITEMNUM, a.STATUS, a.SITEID, a.LOCATION,
               a.DESCRIPTION,
               l.DESCRIPTION AS loc_description,
               l.LATITUDE    AS loc_latitude,
               l.LONGITUDE   AS loc_longitude,
               l.REGION      AS loc_region,
               c.CANONICAL_ID
        FROM {_qualified("ASSET")} a
        JOIN {_qualified("LOCATIONS")} l USING (SITEID, LOCATION)
        LEFT JOIN `{BQ_PROJECT}.oilfield_kc.cross_system_aliases` c
          ON c.MAXIMO_ITEMNUM = a.ITEMNUM
        WHERE a.ASSETNUM = @assetnum
        LIMIT 1
        """,
        {"assetnum": equipment_instance_id},
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment instance '{equipment_instance_id}' not found",
        )
    r = rows[0]
    return EquipmentInstance(
        canonical_id=r["CANONICAL_ID"] or r["ITEMNUM"] or "",
        equipment_instance_id=r["ASSETNUM"],
        location=EquipmentLocation(
            label=r["loc_description"] or r["LOCATION"],
            latitude=_f(r["loc_latitude"]) or 0.0,
            longitude=_f(r["loc_longitude"]) or 0.0,
            region=r["loc_region"] or "",
        ),
        status=r["STATUS"],
        certification_hours_remaining=0,
        workforce_attached=False,
    )
