---
name: deep-research
description: >
  Use when the Orchestrator needs to ground a sourcing or compatibility decision
  in authoritative document citations from external corpora — historical BSEE
  offshore incident investigations (safety/regulatory precedents), customer
  Master Service Agreement clauses (contract authorization context), or
  technical specifications for downhole tools (USPTO patents, Volve well
  completions, OSTI reports). The skill returns clean snippets + extractive
  segments with URIs, suitable for direct citation in a SourcingPlan's
  rationale. Use sparingly — these calls are paid Vertex AI Search queries.
license: Apache-2.0
metadata:
  adk_additional_tools:
    - search_bsee_incidents
    - search_mcc_contracts
    - search_intouch_specs
---

# Deep Research

Vertex AI Search retrieval over three pre-ingested Discovery Engine apps.
Each tool takes a free-text `query` and returns up to `page_size`
(default 5) citations.

## Tools

- **`search_bsee_incidents(query, page_size=5)`** — BSEE Bureau of Safety
  and Environmental Enforcement accident investigation reports (offshore
  Gulf of Mexico, 2010+). Use for safety precedents, equipment-failure
  histories, regulatory clearance context.

- **`search_mcc_contracts(query, page_size=5)`** — Oilfield-services
  Master Service Agreements filed with SEC EDGAR. Use to ground
  customer-authorization, indemnification, or liability clauses.

- **`search_intouch_specs(query, page_size=5)`** — Downhole tool technical
  specifications from USPTO patents, the Volve well-completion dataset
  (Statoil), and OSTI reports. Use for equipment-compatibility and
  spec-matching context that the Knowledge Catalog alias table doesn't
  cover.

## Return shape (every tool)

A list of dicts::

    [
      {
        "document_id": "<hash>",
        "title": "Accident Investigation Report",
        "uri": "gs://oilfield-services-unstructured/bsee_incidents/hi-a-379-b-wt-offshore-20-apr-2015.pdf",
        "snippet": "... query terms in context ...",
        "extractive_segment": "First clean paragraph from the doc."
      },
      ...
    ]

Empty list = no hits (or transient API error, logged server-side).
