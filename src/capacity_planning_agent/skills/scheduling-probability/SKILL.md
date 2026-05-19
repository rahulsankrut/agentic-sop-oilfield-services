---
name: scheduling-probability
description: >
  Probabilistic reasoning over historical start-date variance per basin /
  customer / asset class. Produces start-date distributions (p10/p50/p90),
  recommends risk-calibrated buffer days, and projects fleet-utilization
  uplift + deferred CapEx for the chosen buffer.
metadata:
  adk_additional_tools:
    - get_start_date_distribution
    - compute_optimal_buffer
    - compute_fleet_utilization_impact
---

# Scheduling Probability

## Workflow

1. **`get_start_date_distribution(basin, customer_id, asset_class)`** —
   returns p10 / p50 / p90 actual-vs-requested offsets in days. Backed by
   `data/start_date_variance/{basin}.json`.
2. **`compute_optimal_buffer(distribution, risk_tolerance)`** —
   risk_tolerance ∈ [0,1] selects a percentile of the distribution as the
   buffer; e.g., 0.65 ≈ p65 (closer to p90 = larger buffer = less risk).
   Returns ``{recommended_buffer_days, projected_on_time_rate}``.
3. **`compute_fleet_utilization_impact(basin, buffer_days_delta)`** —
   compares the recommended buffer against the current static buffer (~14d
   default) and quantifies the fleet-utilization uplift % and the deferred-
   CapEx USD that no longer needs to be allocated for replacement tools.

## Output for the agent

After running these the agent has everything for a `BufferOptimization`:
basin, risk_tolerance, current_buffer_days, recommended_buffer_days,
projected_on_time_rate, fleet_utilization_uplift_pct, deferred_capex_usd.
