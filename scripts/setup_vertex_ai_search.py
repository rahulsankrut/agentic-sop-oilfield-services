"""Create Vertex AI Search data stores over the 3 unstructured corpora.

TASK-17 Phase 2 — set up RAG retrieval over the BSEE / MCC / InTouch PDFs
already in GCS (Phase 1 corpus upload is in
`scripts/build_{bsee,sec_edgar,intouch}_corpus.py`).

Substitutability: a customer with their own PDF corpus in their own GCS
bucket re-runs this script pointed at their bucket. Data store IDs +
default search config stay the same; only the source bucket changes.

What this creates (idempotently — Vertex AI Search supports `get_*`
followed by `create_*` if missing):

  3 unstructured data stores in `discoveryengine.googleapis.com`:
    - oilfield-bsee-incidents      gs://oilfield-services-unstructured/bsee_incidents/*
    - oilfield-mcc-contracts       gs://oilfield-services-unstructured/mcc_contracts/*
    - oilfield-intouch-specs       gs://oilfield-services-unstructured/intouch_specs/*

  Plus 3 default Search Engines bound to each data store so queries
  return ranked passages.

Async note: ingestion runs as a long-running operation (5-15 min for
~10MB corpora). This script kicks it off and reports the operation
name; check Cloud Console (or `gcloud discoveryengine operations
describe ...`) for completion.

Prerequisites:
  - `gcloud services enable discoveryengine.googleapis.com` (already
    verified enabled on vertex-ai-demos-468803).
  - `roles/discoveryengine.admin` or equivalent on the project.
  - ADC: `gcloud auth application-default login` (per CLAUDE.md).

Region: Vertex AI Search data stores live in `global` by default; we
use that to match the canonical pattern (Discovery Engine for unstructured
isn't us-central1-regional in the same way Agent Engine is).
"""

from __future__ import annotations

import logging
import sys

from google.cloud import discoveryengine_v1 as de

PROJECT_ID = "vertex-ai-demos-468803"
LOCATION = "global"
BUCKET = "oilfield-services-unstructured"

DATA_STORES = [
    ("oilfield-bsee-incidents", "BSEE Offshore Incident Investigations", "bsee_incidents"),
    ("oilfield-mcc-contracts", "OFS Master Service Agreements (SEC EDGAR)", "mcc_contracts"),
    ("oilfield-intouch-specs", "OFS Technical Specs (USPTO + Volve + OSTI)", "intouch_specs"),
]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def _create_data_store(client: de.DataStoreServiceClient, store_id: str, display_name: str) -> str:
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection"
    name = f"{parent}/dataStores/{store_id}"
    try:
        existing = client.get_data_store(name=name)
        log.info("  data store %s exists (id=%s)", store_id, existing.name)
        return existing.name
    except Exception:  # noqa: BLE001 — NotFound surfaces here
        pass
    store = de.DataStore(
        display_name=display_name,
        industry_vertical=de.IndustryVertical.GENERIC,
        solution_types=[de.SolutionType.SOLUTION_TYPE_SEARCH],
        content_config=de.DataStore.ContentConfig.CONTENT_REQUIRED,  # unstructured PDFs
    )
    op = client.create_data_store(
        parent=parent,
        data_store=store,
        data_store_id=store_id,
    )
    log.info("  creating data store %s (op=%s)", store_id, op.operation.name)
    result = op.result(timeout=300)
    return result.name


def _ingest_gcs_prefix(client: de.DocumentServiceClient, data_store_name: str, prefix: str) -> str:
    branch = f"{data_store_name}/branches/default_branch"
    op = client.import_documents(
        de.ImportDocumentsRequest(
            parent=branch,
            gcs_source=de.GcsSource(
                input_uris=[f"gs://{BUCKET}/{prefix}/*"],
                data_schema="content",
            ),
            reconciliation_mode=de.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        )
    )
    log.info("    ingestion op=%s — async (poll Cloud Console)", op.operation.name)
    return op.operation.name


def _create_engine(
    client: de.EngineServiceClient, store_name: str, engine_id: str, display_name: str
) -> str:
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/collections/default_collection"
    name = f"{parent}/engines/{engine_id}"
    try:
        existing = client.get_engine(name=name)
        log.info("  search engine %s exists", engine_id)
        return existing.name
    except Exception:  # noqa: BLE001
        pass
    engine = de.Engine(
        display_name=display_name,
        data_store_ids=[store_name.rsplit("/", 1)[-1]],
        solution_type=de.SolutionType.SOLUTION_TYPE_SEARCH,
        search_engine_config=de.Engine.SearchEngineConfig(
            search_tier=de.SearchTier.SEARCH_TIER_STANDARD,
            search_add_ons=[de.SearchAddOn.SEARCH_ADD_ON_LLM],
        ),
    )
    op = client.create_engine(parent=parent, engine=engine, engine_id=engine_id)
    log.info("  creating search engine %s (op=%s)", engine_id, op.operation.name)
    result = op.result(timeout=300)
    return result.name


def main() -> int:
    ds_client = de.DataStoreServiceClient()
    doc_client = de.DocumentServiceClient()
    en_client = de.EngineServiceClient()

    log.info("=== Creating data stores + ingesting from GCS ===")
    for store_id, display_name, prefix in DATA_STORES:
        log.info("[%s]", store_id)
        store_name = _create_data_store(ds_client, store_id, display_name)
        _ingest_gcs_prefix(doc_client, store_name, prefix)
        _create_engine(en_client, store_name, f"{store_id}-engine", display_name)

    log.info("")
    log.info("✓ Data stores + engines created. Ingestion runs async (~5-15 min).")
    log.info(
        "  Verify status: gcloud discoveryengine operations list "
        f"--project={PROJECT_ID} --location={LOCATION}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
