# Vertex AI Search — manual setup runbook

TASK-17 Phase 2. Programmatic creation of Discovery Engine data stores
isn't viable in our environment, so the operator creates the 3 data
stores + search apps by hand in the Cloud Console. The PDFs are already
in GCS (Phase 1, committed); this runbook just wires the indexer.

> `scripts/setup_vertex_ai_search.py` is retained as a *reference* for
> what each manual step is doing under the hood (resource shapes, IAM
> verbs, region) — but it is **not expected to be run**. If you ever
> need to recreate the data stores in a fresh project, this runbook is
> the source of truth.

## Inputs (already in place)

GCS bucket `gs://oilfield-services-unstructured/` in `us-central1`:

| Prefix | Content | Bytes |
|---|---|---|
| `bsee_incidents/`    | 12 BSEE Panel + District Investigation PDFs    | 5.3 MB  |
| `mcc_contracts/`     | 12 SEC EDGAR MSA + MFSA contracts (HTML)        | 3.5 MB  |
| `intouch_specs/`     | 13 USPTO/Equinor/OSTI technical PDFs            | 22.3 MB |

Verify the bucket + prefixes:

```bash
gsutil ls gs://oilfield-services-unstructured/
gsutil ls gs://oilfield-services-unstructured/bsee_incidents/  | wc -l   # → 12
gsutil ls gs://oilfield-services-unstructured/mcc_contracts/   | wc -l   # → 12
gsutil ls gs://oilfield-services-unstructured/intouch_specs/   | wc -l   # → 13
```

## 1. Open the right Console surface

Vertex AI Search (a.k.a. **AI Applications** / Agent Builder) lives at:

> https://console.cloud.google.com/gen-app-builder/data-stores?project=vertex-ai-demos-468803

Region: leave the dropdown at **global** (Discovery Engine for
unstructured corpora doesn't follow Agent Engine's `us-central1` rule).

## 2. Create three data stores

For each row below, click **CREATE DATA STORE** in the Console, pick
**Cloud Storage** as the source, then fill in:

| Data store ID                | Display name                                  | Source URI                                                          | Files |
|------------------------------|-----------------------------------------------|---------------------------------------------------------------------|-------|
| `oilfield-bsee-incidents`    | BSEE Offshore Incident Investigations         | `gs://oilfield-services-unstructured/bsee_incidents/*`              | PDFs  |
| `oilfield-mcc-contracts`     | OFS Master Service Agreements (SEC EDGAR)     | `gs://oilfield-services-unstructured/mcc_contracts/*`               | HTML  |
| `oilfield-intouch-specs`     | OFS Technical Specs (USPTO + Volve + OSTI)    | `gs://oilfield-services-unstructured/intouch_specs/*`               | PDFs  |

Settings for all three:
- **Content type**: Unstructured documents
- **Synchronization**: One-time (the corpus is curated, not streaming)
- **Parse / chunk**: Default (layout-aware OCR + ~500-token chunks)
- **Industry**: Generic
- **Location**: `global`

Ingestion runs async; each store takes 5–15 min for our small
corpora. The Console shows a progress chip on the data store row.

## 3. Create a search app per data store

Once each data store finishes ingestion, click **SEARCH APPS → CREATE
APP** → **Search** and bind to one data store:

| App ID                              | Bound data store              | Search tier | LLM add-on |
|-------------------------------------|-------------------------------|-------------|------------|
| `oilfield-bsee-incidents-engine`    | `oilfield-bsee-incidents`     | Standard    | Enabled    |
| `oilfield-mcc-contracts-engine`     | `oilfield-mcc-contracts`      | Standard    | Enabled    |
| `oilfield-intouch-specs-engine`     | `oilfield-intouch-specs`      | Standard    | Enabled    |

Why LLM add-on: enables generative answer with snippet-grounded
citations, which the canvas can surface as "Source: …".

## 4. IAM grants

The deployed Orchestrator's service account
(`orchestrator-agent-sa@vertex-ai-demos-468803.iam.gserviceaccount.com`,
per the deploy pattern in `agents/orchestrator_agent/deploy.py`) needs:

- `roles/discoveryengine.viewer` on the project (or per-app), so the
  agent can query the search apps.
- `roles/storage.objectViewer` on `gs://oilfield-services-unstructured/`
  if the agent ever needs to fetch the source PDF directly (the canvas
  already has a separate signed-URL path for that).

Add both via:

> https://console.cloud.google.com/iam-admin/iam?project=vertex-ai-demos-468803

## 5. Wire env vars into the deployed Orchestrator

Once apps are live, set these env vars on the Orchestrator's Agent
Engine deploy (`agents/orchestrator_agent/deploy.py` → `env_vars`):

```
DISCOVERY_ENGINE_PROJECT=vertex-ai-demos-468803
DISCOVERY_ENGINE_LOCATION=global
BSEE_ENGINE_ID=oilfield-bsee-incidents-engine
MCC_ENGINE_ID=oilfield-mcc-contracts-engine
INTOUCH_ENGINE_ID=oilfield-intouch-specs-engine
```

A future Phase 2.5 commit (when needed) will extend
`agents/utils/corpus_manifests.py` to *also* hit Discovery Engine
`SearchService.search()` and merge the returned snippet into the
existing static `Citation` dict. Until then, citations carry the GCS
URI + manifest metadata — sufficient for the canvas chip + the demo's
"view source" click-through.

## 6. Verify

After each app's ingestion finishes:

```bash
# Quick smoke from a Cloud Shell with discoveryengine API access:
curl -sL -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"query": "drilling motor", "pageSize": 3}' \
  "https://discoveryengine.googleapis.com/v1/projects/vertex-ai-demos-468803/locations/global/collections/default_collection/engines/oilfield-intouch-specs-engine/servingConfigs/default_search:search"
```

Expect a JSON response with 3 `results[]`, each with a `document.uri`
matching one of the GCS PDFs.

Also verify in Console: each data store row should show
"Documents: 12" (or 13 for intouch), "Indexed: 12" / "Indexed: 13".

## What happens before step 5 is done

The skill tools already return citations today (Phase 1) using the
static manifest under `data/anchors/*_corpus.json`. The canvas renders
the GCS URI as a click-through. So even before Discovery Engine is
ingested, the demo shows "agent grounded in this real PDF" — Phase 2
just adds *semantic retrieval* on top so the agent picks the most
relevant snippet within each document rather than always citing the
manifest-anchored entry.

## If you ever need to refresh the corpus

1. Re-run the builder scripts (`scripts/build_{bsee,sec_edgar,intouch}_corpus.py`)
   — idempotent, only uploads new PDFs.
2. In each data store row in Console, click **SYNC** to re-index from GCS.
