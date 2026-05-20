---
name: sourcing-logistics
description: >
  Use when the agent needs to estimate transit mode (ground / sea freight /
  cargo charter), transit hours, and fully-loaded sourcing cost for moving
  an asset between two locations, or to identify blockers (missing
  workforce, certification overdue, customs / export-control, customer
  config restrictions) for a candidate sourcing option. Use when filling a
  SourcingOption Pydantic schema with concrete logistics figures.
license: Apache-2.0
metadata:
  adk_additional_tools:
    - estimate_transit
    - calculate_sourcing_cost
    - identify_blockers
---

# Sourcing Logistics

## Workflow

1. **`estimate_transit(from_location, to_location, asset_size_class)`** —
   returns transit mode, hours, and a raw cost estimate. Uses haversine
   distance + the thresholds in `references/transit_modes.md`.

2. **`calculate_sourcing_cost(option)`** — fully-loaded cost: transit + any
   certification labor (re-qualification before deployment) + cross-border
   customs fees. Wraps `estimate_transit` and adds the loaded components.

3. **`identify_blockers(option, customer_id)`** — surfaces issues:
   missing workforce, certification overdue, customs / export-control,
   customer config restriction (cross-checked via the asset-equivalence
   skill's customer override list).

## Output for the agent

After these tools, the agent has everything needed to fill a `SourcingOption`
Pydantic schema: source, destination, mode, hours, cost, blockers, and the
two booleans (`customer_compatibility`, `workforce_available`).
