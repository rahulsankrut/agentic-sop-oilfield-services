"""Tools for the scheduling-probability skill."""

from __future__ import annotations

import statistics

from agents.utils.synthetic_data import load_start_date_variance

# Default static buffer (days) most basins run on without the agent.
DEFAULT_STATIC_BUFFER_DAYS = 14.0
# CapEx allocated per buffer-day removed, USD.
CAPEX_PER_BUFFER_DAY = 320_000.0
# Fleet-utilization uplift per buffer-day removed, percentage points.
UTIL_UPLIFT_PCT_PER_DAY = 2.0


def get_start_date_distribution(
    basin: str,
    customer_id: str | None = None,
    asset_class: str | None = None,
) -> dict:
    """Return p10/p50/p90 actual-vs-requested offsets in days for a basin.

    Filters by ``customer_id`` and ``asset_class`` if provided. If the basin
    has no recorded data the returned distribution is the conservative
    default (14d offset across percentiles).
    """
    try:
        rows = load_start_date_variance(basin)
    except FileNotFoundError:
        return {
            "p10_offset_days": 14,
            "p50_offset_days": 14,
            "p90_offset_days": 14,
            "sample_size": 0,
            "note": f"No variance history for basin '{basin}' — returning default 14d.",
        }

    if customer_id:
        rows = [r for r in rows if r.get("customer_id") == customer_id]
    if asset_class:
        rows = [r for r in rows if r.get("asset_class") == asset_class]
    if not rows:
        return {
            "p10_offset_days": 14,
            "p50_offset_days": 14,
            "p90_offset_days": 14,
            "sample_size": 0,
            "note": "No records match the given filters; returning default 14d.",
        }

    offsets = sorted(r["actual_start_offset_days"] for r in rows)
    quantiles = (
        statistics.quantiles(offsets, n=10, method="inclusive")
        if len(offsets) > 1
        else [offsets[0]] * 9
    )
    return {
        "p10_offset_days": offsets[0] if len(offsets) == 1 else quantiles[0],
        "p50_offset_days": statistics.median(offsets),
        "p90_offset_days": offsets[-1] if len(offsets) == 1 else quantiles[8],
        "sample_size": len(offsets),
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
