"""Thin HTTP client for the SAP / Maximo / FDP MCP server backends.

TASK-16 Steps 8-11 — the skill tools call MCP server endpoints over HTTP
via these helpers instead of reading data/*.json directly. Each helper
hits the v2 typed endpoint surface on the corresponding FastAPI backend
(see mcp_servers/{sap,maximo,fdp}/backend/main.py).

Backend URLs come from environment variables. Defaults point at the
localhost ports used in the README's local-dev recipe:

  SAP_MCP_URL      default http://localhost:8001
  MAXIMO_MCP_URL   default http://localhost:8002
  FDP_MCP_URL      default http://localhost:8003

In production (Cloud Run), the deploy pipeline sets these to the actual
service URLs. In unit tests, conftest.py monkey-patches the backends via
FastAPI's TestClient so no socket I/O happens.

Substitution path for a customer: change the env vars to point at their
own MCP servers wrapping their real SAP/Maximo/FDP. Tool surface
(`sap_get_material_master(...)`) stays identical.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SAP_MCP_URL = os.environ.get("SAP_MCP_URL", "http://localhost:8001")
MAXIMO_MCP_URL = os.environ.get("MAXIMO_MCP_URL", "http://localhost:8002")
FDP_MCP_URL = os.environ.get("FDP_MCP_URL", "http://localhost:8003")

_DEFAULT_TIMEOUT = float(os.environ.get("MCP_HTTP_TIMEOUT", "10"))


def _do_get(base_url: str, path: str, params: dict | None = None) -> Any:
    """GET base_url + path with params. Returns parsed JSON or raises."""
    url = base_url.rstrip("/") + path
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        resp = client.get(url, params=params or {})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _do_post(base_url: str, path: str, payload: dict | None = None) -> Any:
    """POST base_url + path with JSON body. Returns parsed JSON or raises."""
    url = base_url.rstrip("/") + path
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        resp = client.post(url, json=payload or {})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# SAP MCP (mcp_servers/sap/backend/main.py — v2 typed endpoints)
# ---------------------------------------------------------------------------


def sap_get_material_master(matnr: str) -> dict | None:
    return _do_get(SAP_MCP_URL, f"/sap/v2/material_master/{matnr}")


def sap_get_plant_data(matnr: str, werks: str | None = None) -> list[dict]:
    params = {"werks": werks} if werks else None
    return _do_get(SAP_MCP_URL, f"/sap/v2/plant_data/{matnr}", params) or []


def sap_get_storage_location_stock(matnr: str) -> list[dict]:
    return _do_get(SAP_MCP_URL, f"/sap/v2/storage_location_stock/{matnr}") or []


def sap_get_standard_price(matnr: str) -> dict | None:
    return _do_get(SAP_MCP_URL, f"/sap/v2/standard_price/{matnr}")


def sap_get_customer(kunnr: str) -> dict | None:
    return _do_get(SAP_MCP_URL, f"/sap/v2/customer/{kunnr}")


def sap_resolve_customer_by_name(name_like: str) -> list[dict]:
    return _do_get(SAP_MCP_URL, "/sap/v2/customers", {"name_like": name_like}) or []


def sap_get_workforce_by_basin(basin: str) -> dict:
    """Returns the zero-filled SapWorkforce when the basin is unknown."""
    return _do_get(SAP_MCP_URL, f"/sap/v2/workforce/by_basin/{basin}") or {}


# ---------------------------------------------------------------------------
# Maximo MCP (mcp_servers/maximo/backend/main.py — v2 typed endpoints)
# ---------------------------------------------------------------------------


def maximo_get_item(itemnum: str) -> dict | None:
    return _do_get(MAXIMO_MCP_URL, f"/maximo/v2/item/{itemnum}")


def maximo_query_assets_by_item(
    itemnum: str, status: str | None = None, siteid: str | None = None
) -> list[dict]:
    params = {k: v for k, v in {"status": status, "siteid": siteid}.items() if v}
    return _do_get(MAXIMO_MCP_URL, f"/maximo/v2/assets/by_item/{itemnum}", params or None) or []


def maximo_query_assets_by_region(itemnum: str, region: str) -> list[dict]:
    return (
        _do_get(MAXIMO_MCP_URL, f"/maximo/v2/assets/by_region/{itemnum}", {"region": region}) or []
    )


def maximo_get_inventory_balances(itemnum: str, siteid: str | None = None) -> list[dict]:
    params = {"siteid": siteid} if siteid else None
    return _do_get(MAXIMO_MCP_URL, f"/maximo/v2/inventory_balances/{itemnum}", params) or []


def maximo_get_location(siteid: str, location: str) -> dict | None:
    return _do_get(MAXIMO_MCP_URL, f"/maximo/v2/location/{siteid}/{location}")


def maximo_get_open_workorders(assetnum: str, siteid: str) -> list[dict]:
    return _do_get(MAXIMO_MCP_URL, f"/maximo/v2/open_workorders/{assetnum}/{siteid}") or []


def maximo_get_start_date_distribution(
    basin: str, customer_id: str | None = None, asset_class: str | None = None
) -> dict:
    params = {
        k: v for k, v in {"customer_id": customer_id, "asset_class": asset_class}.items() if v
    }
    return (
        _do_get(MAXIMO_MCP_URL, f"/maximo/v2/start_date_distribution/{basin}", params or None) or {}
    )


# ---------------------------------------------------------------------------
# FDP MCP (mcp_servers/fdp/backend/main.py — v2 typed endpoints)
# ---------------------------------------------------------------------------


def fdp_get_customer_config(customer_id: str, matnr: str) -> dict | None:
    return _do_get(
        FDP_MCP_URL, "/fdp/v2/customer_config", {"customer_id": customer_id, "matnr": matnr}
    )


def fdp_list_approved_substitutions(customer_id: str, matnr_original: str) -> list[dict]:
    return (
        _do_get(
            FDP_MCP_URL,
            "/fdp/v2/approved_substitutions",
            {"customer_id": customer_id, "matnr_original": matnr_original},
        )
        or []
    )


def fdp_list_customer_restrictions(customer_id: str) -> list[dict]:
    return _do_get(FDP_MCP_URL, f"/fdp/v2/customer_restrictions/{customer_id}") or []
