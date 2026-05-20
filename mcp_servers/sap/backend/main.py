"""Synthetic SAP S/4HANA backend for the SAP MCP server.

This FastAPI app mocks the responses of a real SAP S/4HANA system over HTTP.
It is fronted by the genai-toolbox MCP server (see `../config.yaml`), which
exposes these endpoints as MCP tools to the Orchestrator.

In production, a real SAP S/4HANA instance sits here. The MCP server is
registered with Agent Registry and reached only through Agent Gateway —
no third-party gateway is in the path. The MCP interface is identical
either way; that's the entire point of the abstraction.

Endpoints:
    GET  /health                              — Cloud Run health probe
    POST /sap/workforce/by_basin              — workforce counts by basin
    GET  /sap/material/{sap_material_number}  — material → canonical resolution

The data lives in JSON files under DATA_DIR (default `../../data` relative
to this file). Each request adds a small artificial latency (~50-200ms) to
simulate a real enterprise system.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# DEMO NARRATION: "This is the SAP MCP server backend. In production the
# customer's actual SAP S/4HANA system sits here — fronted by this MCP
# layer, registered with Agent Registry, reached only via Agent Gateway
# with Model Armor in the path. For the demo we mock the responses, but
# the MCP-facing interface is identical to what we'd connect to a real
# RISE-on-Google-Cloud SAP instance."

logger = logging.getLogger("sap-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Resolve DATA_DIR — default is `../../data` relative to this file (repo data/).
_DEFAULT_DATA_DIR = (Path(__file__).resolve().parent.parent.parent.parent / "data").resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA_DIR))).resolve()

# Latency simulation (milliseconds). Override via env for tests.
LATENCY_MIN_MS = int(os.environ.get("LATENCY_MIN_MS", "50"))
LATENCY_MAX_MS = int(os.environ.get("LATENCY_MAX_MS", "200"))


def _load_json(filename: str) -> Any:
    path = DATA_DIR / filename
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _sap_workforce() -> dict[str, dict]:
    return _load_json("sap_workforce.json")


@lru_cache(maxsize=1)
def _cross_system_aliases() -> dict[str, dict]:
    return _load_json("cross_system_aliases.json")


@lru_cache(maxsize=1)
def _canonical_assets() -> list[dict]:
    return _load_json("canonical_assets.json")


async def _simulate_latency() -> None:
    """Add 50-200ms random jitter to simulate a real enterprise system."""
    if LATENCY_MAX_MS <= 0:
        return
    delay_ms = random.uniform(LATENCY_MIN_MS, LATENCY_MAX_MS)
    await asyncio.sleep(delay_ms / 1000.0)


app = FastAPI(
    title="SAP S/4HANA (Synthetic)",
    description="Mocked SAP backend behind the SAP MCP server.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class WorkforceByBasinRequest(BaseModel):
    """Inputs for workforce-by-basin lookup."""

    basin: str = Field(
        ...,
        description="Basin slug (e.g. 'permian', 'west_africa', 'north_sea').",
    )


class WorkforceByBasinResponse(BaseModel):
    """Workforce counts for a basin."""

    basin: str
    crew_count_available: int
    specialist_count_available: int
    on_call_count: int


class MaterialResolveResponse(BaseModel):
    """Resolution of a SAP material number to its canonical asset."""

    sap_material_number: str
    canonical_id: str
    canonical_label: str
    category: str
    subcategory: str
    manufacturer: str
    plant: str = "PT01"
    storage_location: str = "LAG01"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Cloud Run health probe."""
    return {"status": "ok", "service": "sap-synthetic", "data_dir": str(DATA_DIR)}


@app.post("/sap/workforce/by_basin", response_model=WorkforceByBasinResponse)
async def workforce_by_basin(req: WorkforceByBasinRequest) -> WorkforceByBasinResponse:
    """Return workforce availability counts for a basin.

    Mirrors `query_sap_workforce` in
    `agents/orchestrator_agent/skills/enterprise-systems/scripts/tools.py`.
    Unknown basins return all-zeros (matches the in-memory tool behavior).
    """
    await _simulate_latency()
    record = _sap_workforce().get(
        req.basin,
        {"crew_count_available": 0, "specialist_count_available": 0, "on_call_count": 0},
    )
    logger.info("workforce_by_basin basin=%s -> %s", req.basin, record)
    return WorkforceByBasinResponse(basin=req.basin, **record)


@app.get(
    "/sap/material/{sap_material_number}",
    response_model=MaterialResolveResponse,
)
async def resolve_material(sap_material_number: str) -> MaterialResolveResponse:
    """Resolve a SAP material number to the canonical asset.

    Walks the cross-system alias table to find the canonical_id whose
    `sap_material_number` matches, then joins with the canonical-asset
    record for descriptive fields.
    """
    await _simulate_latency()
    aliases = _cross_system_aliases()
    assets_by_id = {a["canonical_id"]: a for a in _canonical_assets()}

    for canonical_id, alias in aliases.items():
        if alias.get("sap_material_number") == sap_material_number:
            asset = assets_by_id.get(canonical_id, {})
            return MaterialResolveResponse(
                sap_material_number=sap_material_number,
                canonical_id=canonical_id,
                canonical_label=asset.get("canonical_label", canonical_id),
                category=asset.get("category", "unknown"),
                subcategory=asset.get("subcategory", "unknown"),
                manufacturer=asset.get("manufacturer", "unknown"),
            )

    raise HTTPException(
        status_code=404,
        detail=f"SAP material number '{sap_material_number}' not found",
    )
