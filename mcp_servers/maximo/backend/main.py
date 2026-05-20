"""Synthetic Maximo backend for the Maximo MCP server.

Mocks the responses of an IBM Maximo equipment-management system over HTTP.
Fronted by the genai-toolbox MCP server (see `../config.yaml`).

In production a real Maximo instance replaces this backend. The MCP
server is registered with Agent Registry and only reachable through
Agent Gateway — no third-party gateway. The MCP interface is identical
either way; agents don't know or care which side they're talking to.

Endpoints:
    GET  /health                                       — Cloud Run health probe
    POST /maximo/availability                          — equipment availability by canonical_id + region
    GET  /maximo/equipment/{equipment_instance_id}     — full instance lookup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# DEMO NARRATION: "This is the Maximo MCP server backend. In production it
# sits in front of the customer's actual IBM Maximo install — registered
# with Agent Registry, reached only through Agent Gateway, scanned by
# Model Armor on the way in. The synthetic responses here are shaped
# exactly like Maximo's REST API so the MCP layer above never has to know."

logger = logging.getLogger("maximo-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_DEFAULT_DATA_DIR = (Path(__file__).resolve().parent.parent.parent.parent / "data").resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA_DIR))).resolve()

LATENCY_MIN_MS = int(os.environ.get("LATENCY_MIN_MS", "50"))
LATENCY_MAX_MS = int(os.environ.get("LATENCY_MAX_MS", "200"))


def _load_json(filename: str) -> Any:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _maximo_inventory() -> list[dict]:
    return _load_json("maximo_inventory.json")


async def _simulate_latency() -> None:
    if LATENCY_MAX_MS <= 0:
        return
    await asyncio.sleep(random.uniform(LATENCY_MIN_MS, LATENCY_MAX_MS) / 1000.0)


app = FastAPI(
    title="IBM Maximo (Synthetic)",
    description="Mocked Maximo backend behind the Maximo MCP server.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AvailabilityRequest(BaseModel):
    """Inputs for an equipment-availability lookup."""

    canonical_id: str = Field(
        ...,
        description="Canonical asset id (e.g. 'TX-001').",
    )
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
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "maximo-synthetic", "data_dir": str(DATA_DIR)}


@app.post("/maximo/availability", response_model=AvailabilityResponse)
async def availability(req: AvailabilityRequest) -> AvailabilityResponse:
    """List Maximo-tracked equipment instances of a canonical asset.

    Mirrors `query_maximo_availability` in
    `agents/orchestrator_agent/skills/enterprise-systems/scripts/tools.py`.
    """
    await _simulate_latency()
    rows = [row for row in _maximo_inventory() if row["canonical_id"] == req.canonical_id]
    if req.region_filter:
        rows = [r for r in rows if r["location"].get("region") == req.region_filter]
    instances = [EquipmentInstance(**r) for r in rows]
    logger.info(
        "availability canonical_id=%s region=%s -> %d instances",
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
async def get_equipment(equipment_instance_id: str) -> EquipmentInstance:
    """Fetch a single Maximo equipment instance by instance id."""
    await _simulate_latency()
    for row in _maximo_inventory():
        if row["equipment_instance_id"] == equipment_instance_id:
            return EquipmentInstance(**row)
    raise HTTPException(
        status_code=404,
        detail=f"Equipment instance '{equipment_instance_id}' not found",
    )
