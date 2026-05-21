# TASK-17: Unstructured data — RAG corpora for incident reports, contracts, specs

> **Status (2026-05-20):** Phase 1 ✅ shipped. Phase 2 prep ✅ in `scripts/setup_vertex_ai_search.py` (script ready; run when deploying RAG). All 37 PDFs across the 3 corpora are uploaded to `gs://oilfield-services-unstructured/` with anchor manifests committed; the skill tools attach real-GCS citations to their structured outputs.


**Prerequisites:** TASK-16 (backend migration to BigQuery + custom MCP servers) complete. Skill tools already structured against real SAP/Maximo extracts; this task adds the unstructured pillar via Vertex AI Search + GCS + KC.

**Stream:** Backend (corpus ingest + Vertex AI Search data store + KC entries linking structured assets to docs) + skill-tool RAG calls.

**Status:** Drafted 2026-05-20. Detailed spec pending. Captures the priority corpora the user picked + the public sources scouted while pausing TASK-16 Step 4a.

---

## Priority corpora (user picked 2026-05-20)

1. **InTouch technical specs (PDFs)** — drives `equivalence_lookup` quality. The cargo-plane scenario benefits most.
2. **Customer contracts (PDFs)** — restriction-matrix grounding. Procurement persona win.
3. **Incident / safety reports (PDFs)** — `safety_compliance` criterion in `plan_evaluator`. Strong for compliance-conscious buyers.

(Deferred: operational history / engineer notes — lower demo impact.)

---

## Public sources scouted

### Incident / safety reports

- **BSEE Data Center** — https://www.data.bsee.gov/ — Bureau of Safety and Environmental Enforcement. Panel Investigation Reports + District Investigation Reports since 1992, direct PDF download. US federal public domain. **Highest credibility for offshore O&G incidents.** Each PDF runs 20–80 pages, narrative + findings + recommendations.
- **PHMSA** — Pipeline & Hazardous Materials Safety Administration. Pipeline incidents (less relevant for the rig-floor scenario but broad coverage).
- **OSHA** — workplace incidents, broader than OFS.

### Customer contracts

- **Material Contracts Corpus (MCC)** — https://mcc.law.stanford.edu/download/contracts/ — Stanford Law. ~1M+ contracts filed as "material contracts" with SEC 2000–2023. Compiled by Adelson & Nyarko (2024, arXiv:2504.02864). Includes Master Service Agreements from oilfield services majors (Halliburton, SLB, NOV, etc.). **Best single source for this corpus.** Citation: Adelson, P. & Nyarko, J. (2024). The Material Contracts Corpus.
- **SEC EDGAR direct** — https://www.sec.gov/edgar — free, public. Examples already cited: Master Field Services Agreement (Mammoth Energy), Master Services Agreement (multiple OFS filers). Useful as a fallback / for targeted picks.

### InTouch technical specs

- **GainEnergy/oilandgas-engineering-dataset** on Hugging Face — https://huggingface.co/datasets/GainEnergy/oilandgas-engineering-dataset — engineering content (well spacing, permeability, formation factors). Spec-like, structured.
- **Equinor Volve dataset** — https://www.equinor.com/energy/volve-data-sharing — 5TB / 40,000 files from a North Sea field (2008–2016). Well logs, reservoir simulation models, production data, *plus* technical reports. Equinor Open Data License. Available on Kaggle + Equinor portal. **Closest single source to "real InTouch-style spec docs."**
- **USPTO patents** — image-ppubs.uspto.gov. Public domain. Real spec PDFs for MWD/wireline/downhole tools. Specific patents already found in earlier search:
  - 5,348,091 Self-adjusting centralizer
  - 8,510,052 / 8,204,691 MWD sensor + diagnostic events
  - 12,291,962 Wireline parameter estimation runtime
  - 10,301,892 Wireline performance profile analysis
  - 7,025,130 Downhole tool control
- **OSTI.GOV** — https://www.osti.gov — DOE scientific & technical reports. Big repository of public O&G research.
- **API standards** — partially paywalled but key standards have public summaries.

### Bonus / structured-side complements (TASK-16 follow-ons)

- **Equinor Volve production data** on Kaggle — https://www.kaggle.com/datasets/lamyalbert/volve-production-data — could supplement TASK-16's `eia_steo.basin_production` for non-US basins (North Sea is highly relevant for the cargo-plane scenario's Lagos→Luanda paths).

---

## Proposed architecture (sketch)

```
                ┌───────────────────────────────────────────────┐
                │  GCS bucket: oilfield-services-unstructured/  │
                │    bsee_incidents/*.pdf                       │
                │    mcc_contracts/*.pdf                        │
                │    intouch_specs/*.pdf  (Volve + USPTO subset)│
                └────────────┬──────────────────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────┐
        │  Vertex AI Search — data store per corpus              │
        │    oilfield-bsee-incidents                             │
        │    oilfield-mcc-contracts                              │
        │    oilfield-intouch-specs                              │
        └────────────┬───────────────────────────────────────────┘
                     │ Vertex AI Search MCP (platform-provided)
                     ▼
        ┌────────────────────────────────────────────────────────┐
        │  Knowledge Catalog entries link structured ↔ documents │
        │    each canonical_asset → InTouch spec refs            │
        │    each customer → contract refs                       │
        │    each WORKORDER → incident-report refs (if any)      │
        └────────────────────────────────────────────────────────┘
```

Skill-tool integration (post-TASK-17):

- `asset-equivalence.find_functional_equivalents(canonical_id)` calls Vertex AI Search MCP on the intouch-specs corpus to retrieve the rationale PDF + the specific paragraph asserting the equivalence. Output includes a citation.
- `procurement-prerequisites.check_certification_chain(plan_json)` searches mcc-contracts for the cited section.
- `plan_evaluator` safety_compliance criterion grounds in bsee-incidents matching the asset class.

---

## Substitutability story (the load-bearing claim, mirrors TASK-16)

A customer (SLB / Halliburton / Baker Hughes / NOV) substitutes their unstructured data by:

1. Dumping their SharePoint / Box / S3 doc corpus to a GCS bucket (one-time bulk + ongoing).
2. Pointing a Vertex AI Search data store at the bucket (their own — not ours).
3. Repointing `INTOUCH_SEARCH_DATASTORE_ID`, `CONTRACTS_SEARCH_DATASTORE_ID`, `INCIDENTS_SEARCH_DATASTORE_ID` env vars.
4. Re-running `knowledge_catalog/setup.py` so KC entries link to the new doc URIs.

No skill-tool changes. Tool surface (`search_intouch_specs(canonical_id, query) -> list[SearchHit]`) stays identical.

---

## Open questions (to resolve before drafting full spec)

1. **Vertex AI Search vs. a custom RAG?** Vertex AI Search is GA, managed, has its own MCP. Custom RAG via Vector Search + Document AI is more flexible but lots more code. Default to Vertex AI Search.
2. **Where do citations live in the agent output?** Probably a new `citations` field on `SourcingPlan` / `PlanEvaluation` schemas — additive, doesn't break existing wire format.
3. **MCC corpus filter strategy.** 1M contracts is too many — we need to pre-filter to OFS-relevant contracts (filter by SIC code 1389 — "Oil and Gas Field Services" + 1311 — "Crude Petroleum and Natural Gas"). Pre-compute the subset; store curated picks in GCS.
4. **BSEE PDFs as evidence of "safety_compliance"?** Each BSEE report is *one incident at one operator at one well*. Need to think about how to make these meaningful to a generic agent decision. Likely: vector-search retrieves "incidents involving same asset class" rather than specific company.
5. **InTouch source attribution.** Equinor Volve is real and Open License; USPTO patents are public domain; but "InTouch" is a SLB-trademarked system. Naming: keep `intouch_specs/` as the dataset name (it's our internal naming, not Equinor's) and document the source clearly.

---

## Estimated effort

3–5 days for one engineer once TASK-16 is shipped. Most of the cost is corpus curation (picking ~50–100 BSEE reports + ~50 MSAs from MCC + 20–30 spec PDFs from Volve/USPTO), not the Vertex AI Search wiring (which is GA and well-documented).

---

## Critical files (post-implementation)

- `scripts/load_unstructured_corpora.py` — downloads BSEE PDFs + MCC subset + Volve subset to GCS
- `scripts/setup_vertex_ai_search.py` — creates the 3 data stores
- `agents/utils/vertex_search_client.py` — thin wrapper around Vertex AI Search MCP
- Updates to `knowledge_catalog/setup.py` — new aspects linking structured assets to doc URIs
