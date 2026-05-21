"""DEPRECATED — re-exports from `agents.utils.enterprise_data` for back-compat.

TASK-MCP-REFACTOR (2026-05-21): the MCP HTTP layer was retired. Skill
tools and Workflow nodes now query BigQuery directly via
`agents.utils.enterprise_data`, which mirrors the schema the MCP
backends used to read. This shim preserves the old import surface so
in-tree consumers (test fixtures, the `scripts/smoke_cargo_plane.py`
data-flow probe) keep working without code change. Prefer the
`enterprise_data` import in new code.

The deprecated `_do_get` / `_do_post` helpers are kept as no-op
stubs so the conftest fixture that monkey-patches them doesn't crash;
they will not be called by the new code path.

Will be removed in a follow-up task once the test fixtures + smoke
scripts have been updated to mock `bq_query` directly.
"""

from __future__ import annotations

import logging
import os
import warnings

from agents.utils.enterprise_data import (
    fdp_get_customer_config,
    fdp_list_approved_substitutions,
    fdp_list_customer_restrictions,
    maximo_get_open_workorders,
    maximo_get_start_date_distribution,
    maximo_query_assets_by_item,
    maximo_query_assets_by_region,
    sap_get_workforce_by_basin,
    sap_resolve_customer_by_name,
)

logger = logging.getLogger(__name__)


# Surfaced for backwards-compat with the deprecated conftest fixture's
# monkey-patches. The new BQ-direct path doesn't use these.
SAP_MCP_URL = os.environ.get("SAP_MCP_URL", "http://localhost:8001")
MAXIMO_MCP_URL = os.environ.get("MAXIMO_MCP_URL", "http://localhost:8002")
FDP_MCP_URL = os.environ.get("FDP_MCP_URL", "http://localhost:8003")


def _do_get(base_url, path, params=None):  # noqa: ARG001 — kept as a stub
    warnings.warn(
        "agents.utils.mcp_client._do_get is deprecated; use enterprise_data.* instead",
        DeprecationWarning,
        stacklevel=2,
    )


def _do_post(base_url, path, payload=None):  # noqa: ARG001 — kept as a stub
    warnings.warn(
        "agents.utils.mcp_client._do_post is deprecated; use enterprise_data.* instead",
        DeprecationWarning,
        stacklevel=2,
    )


__all__ = [
    "SAP_MCP_URL",
    "MAXIMO_MCP_URL",
    "FDP_MCP_URL",
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
