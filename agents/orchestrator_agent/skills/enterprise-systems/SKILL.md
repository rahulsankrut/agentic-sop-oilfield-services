---
name: enterprise-systems
description: >
  Use when the agent needs read-only data from a customer's enterprise source
  systems — Maximo equipment availability and certification status, SAP
  workforce snapshots by basin, FDP customer configuration / approval flags,
  or InTouch technical-spec document citations. Use when assembling a
  SourcingPlan that must be grounded in concrete inventory, workforce, or
  customer-config facts. Always called by canonical_id, so resolve the asset
  via the asset-equivalence skill first.
license: Apache-2.0
metadata:
  adk_additional_tools:
    - query_maximo_availability
    - query_sap_workforce
    - query_fdp_customer_config
    - query_intouch_specs
---

# Enterprise Systems

The skill the Orchestrator uses to look across the customer's existing source
systems without the planner needing to log into each one. Always called by
canonical_id (never by SAP material number / Maximo equipment id), so the
asset-equivalence skill must have resolved the asset first.

## Tools

- **`query_maximo_availability(canonical_id, region_filter=None)`** — equipment
  instances of this canonical asset, with location, status, certification
  hours remaining, and whether workforce is attached. Filter by region for
  proximity scoping.

- **`query_sap_workforce(basin)`** — workforce snapshot for a basin: crew,
  specialist, on-call counts.

- **`query_fdp_customer_config(customer_id, canonical_id)`** — customer's
  approval flag for this canonical asset and whether they accept the known
  substitution variant.

- **`query_intouch_specs(canonical_id)`** — list of relevant InTouch document
  IDs and their titles, for citation in the SourcingPlan.
