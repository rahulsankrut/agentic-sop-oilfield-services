"""FDP (Forecast Demand Planner) backend for the FDP MCP server — BQ-backed (TASK-16 Step 7).

This FastAPI app exposes FDP-shaped endpoints that query the
`fdp_extract.*` BigQuery dataset (CUSTOMER_CONFIG /
APPROVED_SUBSTITUTIONS). It is fronted by the genai-toolbox MCP server
(`../config.yaml`) which exposes these endpoints as typed MCP tools to
the Orchestrator.

Substitution path: a customer with their own FDP-equivalent extract just
re-points `BQ_DATASET_FDP` (or swaps the BQ queries below for live FDP
REST calls). The tool surface stays identical — agent prompts and
Pydantic schemas never see the implementation change.

Endpoints (v2 — typed, matched 1:1 to the §4 tool surface):

  GET  /health
  GET  /fdp/v2/customer_config?customer_id=&matnr=             → FdpCustomerConfig
  GET  /fdp/v2/approved_substitutions?customer_id=&matnr_original=
                                                                → list[FdpSubstitution]
  GET  /fdp/v2/customer_restrictions/{customer_id}             → list[FdpRestriction]

Legacy (kept as a thin wrapper per spec §7 Step 7; retire after one release):

  POST /fdp/customer_config        → CustomerConfigResponse (the in-memory shape)

Environment:
  BQ_PROJECT / GOOGLE_CLOUD_PROJECT  — defaults to vertex-ai-demos-468803
  BQ_DATASET_FDP                     — defaults to fdp_extract
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from google.cloud import bigquery
from pydantic import BaseModel, Field

from agents.schemas import (
    FdpCustomerConfig,
    FdpRestriction,
    FdpSubstitution,
)

# DEMO NARRATION: "FDP holds the customer-specific approval and substitution
# rules. Same MCP pattern — the agent calls one tool; what's behind it is
# either the customer's own FDP-equivalent extract in their data warehouse or,
# in this reference solution, a BigQuery table the customer ETL'd from their
# homegrown system. Either way, the agent sees the same FdpCustomerConfig."

logger = logging.getLogger("fdp-mcp-backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

BQ_PROJECT = (
    os.environ.get("BQ_PROJECT")
    or os.environ.get("GOOGLE_CLOUD_PROJECT", "vertex-ai-demos-468803")
)
BQ_DATASET = os.environ.get("BQ_DATASET_FDP", "fdp_extract")


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
    title="FDP Customer Configuration (BQ-backed)",
    description="BQ-backed FDP backend behind the FDP MCP server.",
    version="2.0.0",
)


# Legacy response shape — kept so existing wrappers / TASK-05 integration
# tests don't break while skill tools migrate to the v2 typed shape.
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
    """Normalized FDP response — the legacy in-memory tool's shape.

    Shape matches `query_fdp_customer_config` in the in-memory tool. Empty
    config (customer/asset not found) returns ``approved=False``,
    ``substitution_accepted={}``, ``notes=None``, ``found=False``.
    """

    customer_id: str
    customer_id_input: str
    canonical_id: str
    found: bool
    approved: bool = False
    substitution_accepted: dict[str, bool] = Field(default_factory=dict)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "fdp-bq",
        "project": BQ_PROJECT,
        "dataset": BQ_DATASET,
    }


# ---------------------------------------------------------------------------
# /fdp/v2/* — typed endpoints (the tool surface per spec §4)
# ---------------------------------------------------------------------------


@app.get("/fdp/v2/customer_config", response_model=FdpCustomerConfig)
async def get_customer_config(
    customer_id: str = Query(..., description="Customer slug (e.g. 'gulf-petroleum')."),
    matnr: str = Query(..., description="SAP material number (MATNR)."),
) -> FdpCustomerConfig:
    rows = _run_query(
        f"""
        SELECT CUSTOMER_ID, MATNR, APPROVED, NOTES, EFFECTIVE_DATE
        FROM {_qualified("CUSTOMER_CONFIG")}
        WHERE CUSTOMER_ID = @cid AND MATNR = @matnr
        LIMIT 1
        """,
        {"cid": customer_id, "matnr": matnr},
    )
    if not rows:
        raise HTTPException(
            404,
            f"No FDP customer config for customer_id={customer_id} matnr={matnr}",
        )
    r = rows[0]
    return FdpCustomerConfig(
        customer_id=r["CUSTOMER_ID"],
        matnr=r["MATNR"],
        approved=bool(r["APPROVED"]),
        notes=(r["NOTES"] or None),
        effective_date=(r["EFFECTIVE_DATE"].isoformat() if r["EFFECTIVE_DATE"] else None),
    )


@app.get("/fdp/v2/approved_substitutions", response_model=list[FdpSubstitution])
async def list_approved_substitutions(
    customer_id: str = Query(..., description="Customer slug."),
    matnr_original: str = Query(..., description="Original SAP material number."),
) -> list[FdpSubstitution]:
    rows = _run_query(
        f"""
        SELECT CUSTOMER_ID, MATNR_ORIGINAL, MATNR_SUBSTITUTE, ACCEPTED
        FROM {_qualified("APPROVED_SUBSTITUTIONS")}
        WHERE CUSTOMER_ID = @cid AND MATNR_ORIGINAL = @matnr
        ORDER BY MATNR_SUBSTITUTE
        """,
        {"cid": customer_id, "matnr": matnr_original},
    )
    return [
        FdpSubstitution(
            customer_id=r["CUSTOMER_ID"],
            matnr_original=r["MATNR_ORIGINAL"],
            matnr_substitute=r["MATNR_SUBSTITUTE"],
            accepted=bool(r["ACCEPTED"]),
        )
        for r in rows
    ]


@app.get(
    "/fdp/v2/customer_restrictions/{customer_id}",
    response_model=list[FdpRestriction],
)
async def list_customer_restrictions(customer_id: str) -> list[FdpRestriction]:
    """Derived view: substitutions this customer has REJECTED (ACCEPTED=FALSE).

    Restrictions = the substitutes a customer will NOT accept. The
    sourcing-logistics + asset-equivalence skills apply the 0.3 confidence
    penalty when an LLM-proposed substitute appears here.
    """
    rows = _run_query(
        f"""
        SELECT CUSTOMER_ID, MATNR_ORIGINAL, MATNR_SUBSTITUTE
        FROM {_qualified("APPROVED_SUBSTITUTIONS")}
        WHERE CUSTOMER_ID = @cid AND ACCEPTED = FALSE
        ORDER BY MATNR_ORIGINAL, MATNR_SUBSTITUTE
        """,
        {"cid": customer_id},
    )
    return [
        FdpRestriction(
            customer_id=r["CUSTOMER_ID"],
            matnr_original=r["MATNR_ORIGINAL"],
            matnr_substitute_rejected=r["MATNR_SUBSTITUTE"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Legacy endpoint — thin wrapper so TASK-05's integration test passes
# unchanged during the migration. Retire after one release per spec §4.
#
# The legacy in-memory tool keyed by (customer_id, canonical_id) and
# returned a `substitution_accepted` dict keyed by substitute-canonical-id
# segment uppercased. The v2 tables key by MATNR — the bridge from
# canonical_id → MATNR lives in `oilfield_kc.cross_system_aliases`, so this
# wrapper joins through there to preserve the legacy shape end-to-end.
# ---------------------------------------------------------------------------


def _resolve_canonical_to_matnr(canonical_id: str) -> str | None:
    rows = _run_query(
        f"""
        SELECT SAP_MATNR
        FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases`
        WHERE CANONICAL_ID = @cid
        LIMIT 1
        """,
        {"cid": canonical_id},
    )
    return rows[0]["SAP_MATNR"] if rows else None


def _resolve_matnr_to_canonical(matnr: str) -> str | None:
    rows = _run_query(
        f"""
        SELECT CANONICAL_ID
        FROM `{BQ_PROJECT}.oilfield_kc.cross_system_aliases`
        WHERE SAP_MATNR = @matnr
        LIMIT 1
        """,
        {"matnr": matnr},
    )
    return rows[0]["CANONICAL_ID"] if rows else None


@app.post("/fdp/customer_config", response_model=CustomerConfigResponse)
async def customer_config_legacy(req: CustomerConfigRequest) -> CustomerConfigResponse:
    """Bridge the legacy (customer_id, canonical_id) shape to the v2 tables.

    Customer-id normalization (slug-or-display-name) is now the SAP MCP's
    job (`sap.resolve_customer_by_name`). The legacy contract accepted a
    raw slug too, so for backwards compat we treat the input as a slug and
    pass it through; the orchestrator-side caller is responsible for any
    name → slug step.
    """
    matnr = _resolve_canonical_to_matnr(req.canonical_id)
    if matnr is None:
        logger.info(
            "customer_config customer=%s canonical_id=%s -> CANONICAL UNRESOLVED",
            req.customer_id,
            req.canonical_id,
        )
        return CustomerConfigResponse(
            customer_id=req.customer_id,
            customer_id_input=req.customer_id,
            canonical_id=req.canonical_id,
            found=False,
        )

    config_rows = _run_query(
        f"""
        SELECT APPROVED, NOTES
        FROM {_qualified("CUSTOMER_CONFIG")}
        WHERE CUSTOMER_ID = @cid AND MATNR = @matnr
        LIMIT 1
        """,
        {"cid": req.customer_id, "matnr": matnr},
    )
    if not config_rows:
        logger.info(
            "customer_config customer=%s canonical_id=%s matnr=%s -> NOT FOUND",
            req.customer_id,
            req.canonical_id,
            matnr,
        )
        return CustomerConfigResponse(
            customer_id=req.customer_id,
            customer_id_input=req.customer_id,
            canonical_id=req.canonical_id,
            found=False,
        )

    sub_rows = _run_query(
        f"""
        SELECT MATNR_SUBSTITUTE, ACCEPTED
        FROM {_qualified("APPROVED_SUBSTITUTIONS")}
        WHERE CUSTOMER_ID = @cid AND MATNR_ORIGINAL = @matnr
        """,
        {"cid": req.customer_id, "matnr": matnr},
    )

    # Rehydrate the legacy `substitution_accepted` map keyed by the
    # substitute's canonical-id segment uppercased (matches the legacy
    # in-memory tool exactly).
    subs: dict[str, bool] = {}
    for s in sub_rows:
        canonical_sub = _resolve_matnr_to_canonical(s["MATNR_SUBSTITUTE"])
        if canonical_sub is None:
            continue
        # "TX-007" -> "TX_007" so the legacy contract sees an identifier
        # token, not a hyphenated string. The original code split on "-" and
        # uppercased the segment after the dash; preserve that behaviour.
        segment = canonical_sub.split("-", 1)[-1].upper()
        subs[segment] = bool(s["ACCEPTED"])

    r = config_rows[0]
    logger.info(
        "customer_config customer=%s canonical_id=%s matnr=%s -> approved=%s subs=%s",
        req.customer_id,
        req.canonical_id,
        matnr,
        r["APPROVED"],
        subs,
    )
    return CustomerConfigResponse(
        customer_id=req.customer_id,
        customer_id_input=req.customer_id,
        canonical_id=req.canonical_id,
        found=True,
        approved=bool(r["APPROVED"]),
        substitution_accepted=subs,
        notes=(r["NOTES"] or None),
    )
