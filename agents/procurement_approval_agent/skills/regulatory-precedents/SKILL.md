---
name: regulatory-precedents
description: >
  Use when the Procurement Approval agent needs to ground a safety,
  certification, or contract-authorization decision in document-level
  evidence — BSEE accident investigation reports for safety/regulatory
  precedents, or customer Master Service Agreement clauses for indemnity,
  liability, and authorization context. Returns clean snippets and
  extractive segments with URIs suitable for direct citation in an
  ApprovalDecision rationale. Use only when the structured procurement
  checks (budget threshold, certification chain) need supporting evidence
  the planner can present back to Maria.
license: Apache-2.0
metadata:
  adk_additional_tools:
    - search_bsee_incidents
    - search_mcc_contracts
---

# Regulatory Precedents

Vertex AI Search retrieval over two pre-ingested Discovery Engine apps,
reused from the Orchestrator's `deep-research` skill but scoped to the
two corpora the procurement approval flow cares about. (InTouch
technical specs are deliberately omitted — those are the Orchestrator's
domain, not procurement's.)

## Tools

- **`search_bsee_incidents(query, page_size=5)`** — BSEE accident
  investigation reports. Use when an approval involves a previously
  flagged safety condition (e.g., kick, blowout, hydrogen sulfide
  exposure) and you need a citable precedent.

- **`search_mcc_contracts(query, page_size=5)`** — OFS Master Service
  Agreements (SEC EDGAR filings). Use to ground authorization +
  indemnity language in the customer's actual contract template.

## Return shape

Same as the Orchestrator's `deep-research` skill — list of dicts with
`document_id`, `title`, `uri`, `snippet`, `extractive_segment`.
