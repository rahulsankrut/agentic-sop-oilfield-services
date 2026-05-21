"""Tools for the scheduling-probability skill.

TASK-16 Step 11 — `get_start_date_distribution` now calls the Maximo MCP
(`maximo.get_start_date_distribution`) instead of reading
`data/start_date_variance/{basin}.json` directly. The Maximo MCP queries
the `maximo_extract.WO_HISTORY` BigQuery view per Q7 resolution.

The other two functions (`compute_optimal_buffer`,
`compute_fleet_utilization_impact`) remain pure-compute and unchanged.
"""

from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime
from pathlib import Path

from agents.utils.enterprise_data import maximo_get_start_date_distribution

logger = logging.getLogger(__name__)

# Default static buffer (days) most basins run on without the agent.
DEFAULT_STATIC_BUFFER_DAYS = 14.0
# CapEx allocated per buffer-day removed, USD.
CAPEX_PER_BUFFER_DAY = 320_000.0
# Fleet-utilization uplift per buffer-day removed, percentage points.
UTIL_UPLIFT_PCT_PER_DAY = 2.0

# Repo root for the legacy-JSON fallback. tools.py lives at
# <repo>/agents/capacity_planning_agent/skills/scheduling-probability/scripts/tools.py
# → 6 parents up = <repo>.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_LEGACY_VARIANCE_DIR = _REPO_ROOT / "data" / "start_date_variance"


def _parse_iso(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    # FastAPI serializes datetimes as ISO 8601 strings.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _offset_days(reference: datetime, target: datetime) -> float:
    return (target - reference).total_seconds() / 86_400.0


# TODO: remove when WO_HISTORY is fully seeded with reverse-engineered COMP WOs.
# Until then, the Maximo MCP's `start_date_distribution` endpoint returns
# confidence=0.0 with zero-variance dates because `maximo_extract.WO_HISTORY`
# filters STATUS='COMP' and the v1 seed has only INPRG WOs. For basins where
# we still have legacy aggregated JSON (`data/start_date_variance/*.json`),
# fall back to reverse-engineering the distribution from those records so
# the cargo-plane Persona-3 scenario keeps producing meaningful p10/p50/p90.
def _synthesize_from_legacy_json(
    basin: str,
    customer_id: str | None,
    asset_class: str | None,
) -> dict | None:
    """Compute p10/p50/p90 offsets from the aggregated JSON, or None if absent."""
    json_path = _LEGACY_VARIANCE_DIR / f"{basin}.json"
    if not json_path.exists():
        return None
    try:
        rows = json.loads(json_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read legacy variance JSON %s: %s", json_path, exc)
        return None

    if customer_id:
        rows = [r for r in rows if r.get("customer_id") == customer_id]
    if asset_class:
        rows = [r for r in rows if r.get("asset_class") == asset_class]
    if not rows:
        return None

    offsets = sorted(r["actual_start_offset_days"] for r in rows)
    if len(offsets) == 1:
        p10 = p90 = offsets[0]
    else:
        quantiles = statistics.quantiles(offsets, n=10, method="inclusive")
        p10, p90 = quantiles[0], quantiles[8]
    return {
        "p10_offset_days": p10,
        "p50_offset_days": statistics.median(offsets),
        "p90_offset_days": offsets[-1] if len(offsets) == 1 else p90,
        "sample_size": len(offsets),
        "source": "legacy_json_fallback",
    }


def get_start_date_distribution(
    basin: str,
    customer_id: str | None = None,
    asset_class: str | None = None,
) -> dict:
    """Return p10/p50/p90 actual-vs-requested offsets in days for a basin.

    Calls the Maximo MCP (`maximo.get_start_date_distribution`), which
    queries `maximo_extract.WO_HISTORY` for `APPROX_QUANTILES(variance_days,
    100)[OFFSET(10/50/90)]`. Filters by ``customer_id`` and ``asset_class``
    are forwarded (currently no-ops on the MCP side until WO_HISTORY
    carries those join keys).

    The MCP returns `StartDateDistribution` (a date-shaped payload with
    `requested_date` + p10/p50/p90 `*_actual_date` + `confidence`). We
    convert back to day-offsets so `compute_optimal_buffer` keeps working.

    Fallback chain:
      1. MCP with `confidence > 0`  →  use MCP quantiles.
      2. MCP zero-variance/empty + legacy JSON exists  →  reverse-engineer
         from the aggregated `data/start_date_variance/{basin}.json` so the
         cargo-plane scenario keeps working before WO_HISTORY is seeded.
      3. Neither  →  conservative 14d default across percentiles.
    """
    # TASK-MCP-REFACTOR: was the Maximo MCP endpoint; now direct-BQ via
    # `enterprise_data.maximo_get_start_date_distribution`. Returns day-
    # offset quantiles directly instead of date-shaped payload, so no
    # date conversion needed.
    bq_payload = maximo_get_start_date_distribution(basin)

    if bq_payload and bq_payload.get("n", 0) > 0:
        return {
            "p10_offset_days": round(float(bq_payload["p10_days"]), 2),
            "p50_offset_days": round(float(bq_payload["p50_days"]), 2),
            "p90_offset_days": round(float(bq_payload["p90_days"]), 2),
            "sample_size": int(bq_payload["n"]),
            "confidence": min(1.0, 0.25 + 0.25 * (float(bq_payload["n"]) ** 0.5) / 10.0),
            "source": "maximo_bq",
        }

    # BQ returned zero rows (WO_HISTORY empty for this basin). Try the
    # legacy JSON fallback before defaulting to the static 14d.
    fallback = _synthesize_from_legacy_json(basin, customer_id, asset_class)
    if fallback is not None:
        return fallback

    return {
        "p10_offset_days": 14,
        "p50_offset_days": 14,
        "p90_offset_days": 14,
        "sample_size": 0,
        "note": f"No variance history for basin '{basin}' — returning default 14d.",
    }


def compute_optimal_buffer(
    p10_offset_days: float,
    p50_offset_days: float,
    p90_offset_days: float,
    risk_tolerance: float = 0.65,
) -> dict:
    """Recommend a buffer (days) and projected on-time rate.

    risk_tolerance ∈ [0,1]: 0.0 = pick smallest buffer (high risk), 1.0 = pick
    p90 (low risk). Linear interp between p10 and p90.

    Returns ``{recommended_buffer_days, projected_on_time_rate}``.
    """
    risk_tolerance = max(0.0, min(1.0, risk_tolerance))
    buffer = p10_offset_days + risk_tolerance * (p90_offset_days - p10_offset_days)

    # Projected on-time rate from the percentile this buffer corresponds to.
    # 0 risk tolerance → ~p10 → 10% on-time; 1.0 → ~p90 → 90% on-time.
    projected_on_time = 0.10 + risk_tolerance * 0.80

    return {
        "recommended_buffer_days": round(buffer, 1),
        "projected_on_time_rate": round(projected_on_time, 2),
    }


def compute_fleet_utilization_impact(
    basin: str,
    recommended_buffer_days: float,
    current_buffer_days: float = DEFAULT_STATIC_BUFFER_DAYS,
) -> dict:
    """Quantify utilization uplift and deferred CapEx from reducing buffer.

    Returns ``{fleet_utilization_uplift_pct, deferred_capex_usd}``.
    """
    _ = basin  # reserved for per-basin coefficients (TASK-05)
    delta = max(0.0, current_buffer_days - recommended_buffer_days)
    return {
        "fleet_utilization_uplift_pct": round(delta * UTIL_UPLIFT_PCT_PER_DAY, 1),
        "deferred_capex_usd": int(delta * CAPEX_PER_BUFFER_DAY),
    }
