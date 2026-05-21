"""Thin synchronous BigQuery wrapper for skill tools that need direct BQ access.

TASK-16 Step 8 — used when the data lives in a Knowledge Catalog-native BQ
table (``oilfield_kc.*``) which doesn't have its own MCP server in v1.
The SAP / Maximo / FDP MCP server backends do their own BQ I/O inside
``mcp_servers/*/backend/main.py``; the skill tools route through HTTP via
``agents.utils.mcp_client``. For KC tables (no MCP layer) the skill tools
call ``bq_query`` directly.

Substitution path: a customer who wants their KC behind an MCP server too
can stand one up and the skill tool swaps this import for an
``agents.utils.mcp_client.kc_*`` helper. Tool surface stays identical.

``BQ_PROJECT`` defaults to ``vertex-ai-demos-468803`` via env var (falling
back to ``GOOGLE_CLOUD_PROJECT``).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from google.cloud import bigquery

logger = logging.getLogger(__name__)

def _resolve_project() -> str:
    """Resolve the BQ project at call time (not import time)."""
    return os.environ.get("BQ_PROJECT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT", "vertex-ai-demos-468803"
    )


# Module-level convenience for callers that want to interpolate the project
# into SQL (read once at import — fine for production where env doesn't
# change mid-process, but use `_resolve_project()` in any code that's
# expected to honor a `monkeypatch.setenv("BQ_PROJECT", ...)` in tests).
BQ_PROJECT = _resolve_project()


@lru_cache(maxsize=1)
def _client_cached(project: str) -> bigquery.Client:
    return bigquery.Client(project=project)


def _client() -> bigquery.Client:
    """Lazy BQ client — keyed by project so a monkey-patched env var in
    tests gives a fresh client (code-review MED #21)."""
    return _client_cached(_resolve_project())


def _bq_type(v: object) -> str:
    """Map a Python scalar to a BQ scalar parameter type name."""
    if isinstance(v, bool):
        return "BOOL"
    if isinstance(v, int):
        return "INT64"
    if isinstance(v, float):
        return "FLOAT64"
    return "STRING"


def bq_query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a parameterized SELECT and return rows as plain dicts.

    Args:
        sql: A BigQuery Standard SQL query. Use ``@name`` placeholders for
            parameters; do NOT inline user input via f-string.
        params: Mapping of parameter name → scalar value. The BQ type is
            inferred from the Python type (bool / int / float / str).

    Returns:
        List of row dicts (column name → value). Empty list if no rows.
    """
    params = params or {}
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(k, _bq_type(v), v) for k, v in params.items()
        ],
    )
    job = _client().query(sql, job_config=job_config)
    return [dict(r) for r in job.result()]
