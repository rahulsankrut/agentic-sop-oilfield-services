# Risk-tolerance calibration

`risk_tolerance` ∈ [0, 1] determines which percentile of the actual-vs-
requested start-date distribution becomes the buffer recommendation.

| Tolerance | Approx. buffer percentile | Projected on-time rate | Use case |
|---|---|---|---|
| 0.20 | p25 | ~25% | Aggressive — high-volume basins where idle fleet is the bigger cost |
| 0.40 | p40 | ~40% | Balanced — most basins |
| 0.65 | p65 | ~65% | Standard recommendation for mid-tier customers |
| 0.85 | p85 | ~85% | Strict — high-priority customers / regulated regions |

Defaults baked into the agent's prompt: 0.65 for "Standard," 0.85 for "Strict."

Coefficients (TASK-05 will refine):

- ~2% fleet-utilization uplift per buffer-day reduced
- ~$320K deferred CapEx per buffer-day reduced (one less spare tool needs
  to be allocated to absorb variance)
