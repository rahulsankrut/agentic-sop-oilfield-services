# Rationale tag taxonomy

The Forecast Review Agent extracts one or more of the following structured
tags from a basin leader's freeform override explanation. The taxonomy is
designed to be small enough for the next ML retrain to absorb as a
categorical feature.

| Tag | Definition | Keywords |
|---|---|---|
| `rig_count_decline` | Operator(s) have demobilized rigs | rig count, rig drop, fewer rigs |
| `operator_delay` | Customer program slipped right | operator delay, deferred, delayed program |
| `weather_disruption` | Weather-driven outage | hurricane, storm, winter shutdown, freeze-off |
| `regulatory_change` | New rule or permit issue | regulatory, permit, compliance |
| `demand_shift` | Macro demand / price change | demand, spot price, commodity price, macro |
| `customer_program_pause` | Customer specifically paused | program pause, customer pause |
| `geopolitical` | Sanctions / tariffs / export | sanctions, geopolitical, tariff |
| `pricing_shift` | Service-price change | pricing, service price, rate cut |

Override significance is computed by `compute_override_significance` —
overrides ≥ 4× historical volatility carry a significance of 1.0.
