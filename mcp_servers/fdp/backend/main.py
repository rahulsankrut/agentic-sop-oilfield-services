"""Synthetic FDP (customer-configuration) backend for the FDP MCP server.

FDP holds customer-specific approval and substitution rules for canonical
assets. This FastAPI app mocks the responses an internal FDP would return
over HTTP; in production a real FDP system sits here, fronted by this
MCP server, registered with Agent Registry, reached through Agent Gateway.

Endpoints:
    GET  /health                       — Cloud Run health probe
    POST /fdp/customer_config          — customer + canonical_id → approval / substitution flags
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

from fastapi import FastAPI
from pydantic import BaseModel, Field

# DEMO NARRATION: "FDP holds the customer-specific approval and substitution
# rules. Same MCP pattern — the agent calls one tool; what's behind it is
# either a real FDP instance or our synthetic mock. Notice how the customer
# id can be either a slug or a display name; FDP normalizes both."

logger = logging.getLogger("fdp-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

_DEFAULT_DATA_DIR = (Path(__file__).resolve().parent.parent.parent.parent / "data").resolve()
DATA_DIR = Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA_DIR))).resolve()

LATENCY_MIN_MS = int(os.environ.get("LATENCY_MIN_MS", "50"))
LATENCY_MAX_MS = int(os.environ.get("LATENCY_MAX_MS", "200"))


def _load_json(filename: str) -> Any:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _fdp_configurations() -> dict[str, dict]:
    return _load_json("fdp_configurations.json")


@lru_cache(maxsize=1)
def _customers() -> list[dict]:
    return _load_json("customers.json")


def _normalize_customer_id(raw: str) -> str:
    """Slug-or-display-name → canonical slug.

    Re-implements the `normalize_customer_id` helper from
    `agents/utils/synthetic_data.py` so this MCP server has no dependency
    on the orchestrator-side `src/` package.
    """
    if not raw:
        return ""
    needle = raw.lower().strip()
    for c in _customers():
        if needle == c["customer_id"]:
            return c["customer_id"]
        name_lc = c["name"].lower()
        if needle == name_lc or needle in name_lc or name_lc in needle:
            return c["customer_id"]
    return raw  # unknown — pass through so the caller can fail explicitly


async def _simulate_latency() -> None:
    if LATENCY_MAX_MS <= 0:
        return
    await asyncio.sleep(random.uniform(LATENCY_MIN_MS, LATENCY_MAX_MS) / 1000.0)


app = FastAPI(
    title="FDP Customer Configuration (Synthetic)",
    description="Mocked FDP backend behind the FDP MCP server.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CustomerConfigRequest(BaseModel):
    """Lookup the FDP config for one (customer, canonical_id) pair."""

    customer_id: str = Field(
        ...,
        description=(
            "Customer slug or display name "
            "('gulf-petroleum' or 'Gulf Petroleum')."
        ),
    )
    canonical_id: str = Field(
        ...,
        description="Canonical asset id (e.g. 'TX-001').",
    )


class CustomerConfigResponse(BaseModel):
    """Normalized FDP response.

    Shape matches `query_fdp_customer_config` in the in-memory tool. Empty
    config (customer/asset not found) returns `approved=False`,
    `substitution_accepted={}`, `notes=None`, `found=False`.
    """

    customer_id: str
    customer_id_input: str
    canonical_id: str
    found: bool
    approved: bool = False
    substitution_accepted: dict[str, bool] = Field(default_factory=dict)
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "fdp-synthetic", "data_dir": str(DATA_DIR)}


@app.post("/fdp/customer_config", response_model=CustomerConfigResponse)
async def customer_config(req: CustomerConfigRequest) -> CustomerConfigResponse:
    """Return a customer's FDP configuration for a canonical asset.

    Mirrors `query_fdp_customer_config` from the in-memory tool. The raw
    JSON-side substitution flags (e.g. `v7_substitution_accepted`) are
    normalized into `substitution_accepted` keyed by the substitute
    canonical id segment uppercased (matches the legacy tool exactly).
    """
    await _simulate_latency()
    normalized = _normalize_customer_id(req.customer_id)
    by_asset = _fdp_configurations().get(normalized, {})
    entry = by_asset.get(req.canonical_id)

    if entry is None:
        logger.info(
            "customer_config customer=%s (raw=%s) canonical_id=%s -> NOT FOUND",
            normalized,
            req.customer_id,
            req.canonical_id,
        )
        return CustomerConfigResponse(
            customer_id=normalized,
            customer_id_input=req.customer_id,
            canonical_id=req.canonical_id,
            found=False,
        )

    subs: dict[str, bool] = {}
    for k, v in entry.items():
        if k.endswith("_substitution_accepted") and isinstance(v, bool):
            subs[k.replace("_substitution_accepted", "").upper()] = v

    logger.info(
        "customer_config customer=%s (raw=%s) canonical_id=%s -> approved=%s subs=%s",
        normalized,
        req.customer_id,
        req.canonical_id,
        entry.get("approved", False),
        subs,
    )
    return CustomerConfigResponse(
        customer_id=normalized,
        customer_id_input=req.customer_id,
        canonical_id=req.canonical_id,
        found=True,
        approved=bool(entry.get("approved", False)),
        substitution_accepted=subs,
        notes=entry.get("notes"),
    )
