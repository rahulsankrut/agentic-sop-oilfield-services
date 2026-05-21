"""SAP S/4HANA backend for the SAP MCP server — BQ-backed (TASK-16 Step 5).

This FastAPI app exposes SAP-shaped endpoints that query the
`sap_extract.*` BigQuery dataset (MARA / MAKT / MARC / MARD / MBEW /
KNA1 / KNVV / ZHR_WORKFORCE). It is fronted by the genai-toolbox MCP
server (`../config.yaml`) which exposes these endpoints as typed MCP
tools to the Orchestrator.

Substitution path: a customer with live SAP via OData replaces the BQ
queries below with OData calls. The tool surface stays identical —
agent prompts and Pydantic schemas never see the implementation change.

Endpoints (v2 — typed, matched 1:1 to the §4 tool surface):

  GET  /health
  GET  /sap/v2/material_master/{matnr}                  → SapMaterialMaster
  GET  /sap/v2/plant_data/{matnr}?werks=...             → list[SapPlantData]
  GET  /sap/v2/storage_location_stock/{matnr}           → list[SapStorageStock]
  GET  /sap/v2/standard_price/{matnr}                   → SapStandardPrice
  GET  /sap/v2/customer/{kunnr}                         → SapCustomer
  GET  /sap/v2/customers?name_like=<needle>             → list[SapCustomer]
  GET  /sap/v2/workforce/by_basin/{basin}               → SapWorkforce

Legacy (kept as thin wrappers per spec §7 Step 5; retire after one release):

  POST /sap/workforce/by_basin     → WorkforceByBasinResponse
  GET  /sap/material/{matnr}       → MaterialResolveResponse

Environment:
  BQ_PROJECT / GOOGLE_CLOUD_PROJECT  — defaults to vertex-ai-demos-468803
  BQ_DATASET_SAP                     — defaults to sap_extract
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from google.cloud import bigquery
from pydantic import BaseModel, Field

from agents.schemas import (
    SapCustomer,
    SapMaterialMaster,
    SapPlantData,
    SapStandardPrice,
    SapStorageStock,
    SapWorkforce,
)

logger = logging.getLogger("sap-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

BQ_PROJECT = (
    os.environ.get("BQ_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT", "vertex-ai-demos-468803")
)
BQ_DATASET = os.environ.get("BQ_DATASET_SAP", "sap_extract")


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


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SAP S/4HANA (BQ-backed)",
    description="BQ-backed SAP backend behind the SAP MCP server.",
    version="2.0.0",
)


# Legacy response shapes — kept so existing wrappers don't break TASK-05
# integration tests while skill tools migrate to the v2 typed shapes.
class WorkforceByBasinRequest(BaseModel):
    basin: str = Field(..., description="Basin slug.")


class WorkforceByBasinResponse(BaseModel):
    basin: str
    crew_count_available: int
    specialist_count_available: int
    on_call_count: int


class MaterialResolveResponse(BaseModel):
    sap_material_number: str
    canonical_id: str
    canonical_label: str
    category: str
    subcategory: str
    manufacturer: str
    plant: str = "PT01"
    storage_location: str = "LAG01"


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "sap-bq",
        "project": BQ_PROJECT,
        "dataset": BQ_DATASET,
    }


# ---------------------------------------------------------------------------
# /sap/v2/* — typed endpoints (the tool surface per spec §4)
# ---------------------------------------------------------------------------


@app.get("/sap/v2/material_master/{matnr}", response_model=SapMaterialMaster)
async def get_material_master(matnr: str) -> SapMaterialMaster:
    rows = _run_query(
        f"""
        SELECT m.MATNR, t.MAKTX AS description, m.MTART AS material_type,
               m.MATKL AS material_group, m.MEINS AS base_uom
        FROM {_qualified("MARA")} m
        LEFT JOIN {_qualified("MAKT")} t USING (MANDT, MATNR)
        WHERE m.MATNR = @matnr AND (t.SPRAS = 'E' OR t.SPRAS IS NULL)
        LIMIT 1
        """,
        {"matnr": matnr},
    )
    if not rows:
        raise HTTPException(404, f"No SAP material for MATNR={matnr}")
    r = rows[0]
    return SapMaterialMaster(
        matnr=r["MATNR"],
        description=r["description"],
        material_type=r["material_type"],
        material_group=r["material_group"],
        base_uom=r["base_uom"] or "EA",
    )


@app.get("/sap/v2/plant_data/{matnr}", response_model=list[SapPlantData])
async def get_plant_data(matnr: str, werks: str | None = None) -> list[SapPlantData]:
    sql = (
        f"SELECT MATNR, WERKS, DISPO, DISMM, BESKZ FROM {_qualified('MARC')} "
        f"WHERE MATNR = @matnr"
    )
    params: dict = {"matnr": matnr}
    if werks:
        sql += " AND WERKS = @werks"
        params["werks"] = werks
    rows = _run_query(sql, params)
    return [
        SapPlantData(
            matnr=r["MATNR"], werks=r["WERKS"],
            mrp_controller=r["DISPO"], mrp_type=r["DISMM"],
            procurement_type=r["BESKZ"],
        )
        for r in rows
    ]


@app.get("/sap/v2/storage_location_stock/{matnr}", response_model=list[SapStorageStock])
async def get_storage_location_stock(matnr: str) -> list[SapStorageStock]:
    rows = _run_query(
        f"""
        SELECT MATNR, WERKS, LGORT, LABST, INSME
        FROM {_qualified("MARD")}
        WHERE MATNR = @matnr AND LABST > 0
        """,
        {"matnr": matnr},
    )
    return [
        SapStorageStock(
            matnr=r["MATNR"], werks=r["WERKS"], lgort=r["LGORT"],
            unrestricted_stock=float(r["LABST"] or 0),
            quality_inspection_stock=float(r["INSME"] or 0),
        )
        for r in rows
    ]


@app.get("/sap/v2/standard_price/{matnr}", response_model=SapStandardPrice)
async def get_standard_price(matnr: str) -> SapStandardPrice:
    rows = _run_query(
        f"SELECT MATNR, STPRS, PEINH, WAERS FROM {_qualified('MBEW')} "
        f"WHERE MATNR = @matnr LIMIT 1",
        {"matnr": matnr},
    )
    if not rows:
        raise HTTPException(404, f"No SAP standard price for MATNR={matnr}")
    r = rows[0]
    return SapStandardPrice(
        matnr=r["MATNR"],
        stprs=float(r["STPRS"]),
        peinh=int(r["PEINH"] or 1),
        waers=r["WAERS"] or "USD",
    )


@app.get("/sap/v2/customer/{kunnr}", response_model=SapCustomer)
async def get_customer(kunnr: str) -> SapCustomer:
    rows = _run_query(
        f"SELECT KUNNR, NAME1, LAND1, ORT01, STRAS FROM {_qualified('KNA1')} "
        f"WHERE KUNNR = @kunnr LIMIT 1",
        {"kunnr": kunnr},
    )
    if not rows:
        raise HTTPException(404, f"No SAP customer for KUNNR={kunnr}")
    r = rows[0]
    return SapCustomer(
        kunnr=r["KUNNR"], name1=r["NAME1"],
        land1=r["LAND1"], ort01=r["ORT01"], stras=r["STRAS"],
    )


@app.get("/sap/v2/customers", response_model=list[SapCustomer])
async def resolve_customer_by_name(
    name_like: str = Query(..., description="Substring of NAME1, case-insensitive."),
) -> list[SapCustomer]:
    """Replaces the synthetic-data `normalize_customer_id` helper.

    Returns customers whose NAME1 contains the substring (case-insensitive).
    """
    rows = _run_query(
        f"""
        SELECT KUNNR, NAME1, LAND1, ORT01, STRAS
        FROM {_qualified("KNA1")}
        WHERE LOWER(NAME1) LIKE LOWER(CONCAT('%', @needle, '%'))
        ORDER BY KUNNR
        """,
        {"needle": name_like},
    )
    return [
        SapCustomer(
            kunnr=r["KUNNR"], name1=r["NAME1"],
            land1=r["LAND1"], ort01=r["ORT01"], stras=r["STRAS"],
        )
        for r in rows
    ]


@app.get("/sap/v2/workforce/by_basin/{basin}", response_model=SapWorkforce)
async def get_workforce_by_basin(basin: str) -> SapWorkforce:
    rows = _run_query(
        f"""
        SELECT BASIN, CREW_COUNT_AVAILABLE, SPECIALIST_COUNT_AVAILABLE,
               ON_CALL_COUNT, NAICS_211_STATE_EMPLOYMENT, DATA_SOURCE,
               SNAPSHOT_DATE
        FROM {_qualified("ZHR_WORKFORCE")}
        WHERE BASIN = @basin
        ORDER BY SNAPSHOT_DATE DESC
        LIMIT 1
        """,
        {"basin": basin},
    )
    if not rows:
        # Unknown basin — match legacy behavior of returning zeros so
        # downstream skill tools don't have to special-case a 404.
        return SapWorkforce(
            basin=basin,
            crew_count_available=0,
            specialist_count_available=0,
            on_call_count=0,
            snapshot_date="1970-01-01",
        )
    r = rows[0]
    return SapWorkforce(
        basin=r["BASIN"],
        crew_count_available=int(r["CREW_COUNT_AVAILABLE"] or 0),
        specialist_count_available=int(r["SPECIALIST_COUNT_AVAILABLE"] or 0),
        on_call_count=int(r["ON_CALL_COUNT"] or 0),
        snapshot_date=r["SNAPSHOT_DATE"].isoformat(),
        naics_211_state_employment=(
            int(r["NAICS_211_STATE_EMPLOYMENT"]) if r["NAICS_211_STATE_EMPLOYMENT"] is not None else None
        ),
        data_source=r["DATA_SOURCE"],
    )


# ---------------------------------------------------------------------------
# Legacy endpoints — thin wrappers so TASK-05's integration test passes
# unchanged during the migration. Retire after one release per spec §4.
# ---------------------------------------------------------------------------


@app.post("/sap/workforce/by_basin", response_model=WorkforceByBasinResponse)
async def workforce_by_basin_legacy(req: WorkforceByBasinRequest) -> WorkforceByBasinResponse:
    w = await get_workforce_by_basin(req.basin)
    return WorkforceByBasinResponse(
        basin=w.basin,
        crew_count_available=w.crew_count_available,
        specialist_count_available=w.specialist_count_available,
        on_call_count=w.on_call_count,
    )


@app.get("/sap/material/{sap_material_number}", response_model=MaterialResolveResponse)
async def resolve_material_legacy(sap_material_number: str) -> MaterialResolveResponse:
    """Bridge SAP MATNR → canonical via oilfield_kc.cross_system_aliases."""
    rows = _run_query(
        f"""
        SELECT
          a.CANONICAL_ID, ca.CANONICAL_LABEL, ca.CATEGORY, ca.SUBCATEGORY, ca.MANUFACTURER
        FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases` a
        JOIN `{BQ_PROJECT}.oilfield_kc.canonical_assets`     ca USING (CANONICAL_ID)
        WHERE a.SAP_MATNR = @matnr
        LIMIT 1
        """,
        {"matnr": sap_material_number},
    )
    if not rows:
        raise HTTPException(404, f"SAP material number '{sap_material_number}' not found")
    r = rows[0]
    return MaterialResolveResponse(
        sap_material_number=sap_material_number,
        canonical_id=r["CANONICAL_ID"],
        canonical_label=r["CANONICAL_LABEL"] or r["CANONICAL_ID"],
        category=r["CATEGORY"] or "unknown",
        subcategory=r["SUBCATEGORY"] or "unknown",
        manufacturer=r["MANUFACTURER"] or "unknown",
    )
