# `knowledge_catalog/` — Dataplex Knowledge Catalog setup

This package builds the **Knowledge Catalog content** that grounds Issue 4
of the demo (taxonomic chaos across SAP, Maximo, FDP, InTouch). It moves
`data/canonical_assets.json`, `data/cross_system_aliases.json`, and
`data/functional_equivalences.json` into real Knowledge Catalog Entries
backed by three custom Aspect Types we author for the oilfield domain.

This is the source of truth at runtime — once setup runs, the Orchestrator's
`equivalence_lookup` node calls the prebuilt `lookup_context` MCP tool
against this catalog, not against the JSON files.

---

## Layout

```
knowledge_catalog/
├── __init__.py
├── setup.py                              # Idempotent ingestion script (entry point)
├── aspect_types/
│   ├── asset_specification.yaml          # oilfield-asset-specification schema
│   ├── cross_system_aliases.yaml         # oilfield-cross-system-aliases schema
│   └── functional_equivalence.yaml       # oilfield-functional-equivalence schema
└── README.md
```

---

## What setup.py does

1. Creates one **Entry Group** `oilfield-canonical-assets` (if missing).
2. Creates three custom **Aspect Types** (schemas loaded from `aspect_types/*.yaml`):
   - `oilfield-asset-specification` — physical/operational specs
   - `oilfield-cross-system-aliases` — SAP / Maximo / FDP / InTouch alias bundle
   - `oilfield-functional-equivalence` — substitution graph with per-customer overrides
3. Creates one **Entry Type** `oilfield-canonical-asset` requiring all three Aspects.
4. For every row in `data/canonical_assets.json`, upserts an **Entry** with the
   three Aspects populated by joining `cross_system_aliases.json` and
   `functional_equivalences.json` (symmetric — both `A → B` and `B → A` are
   indexed).
5. Prints a summary block at the end:
   counts of created / updated / unchanged per resource type, plus runtime.

Every step performs `get_*` first, then `update_*` or `create_*`. Re-runs
print `unchanged` rather than failing on duplicate creates.

---

## Prerequisites

1. **Dataplex API enabled** in the target GCP project:
   ```bash
   gcloud services enable dataplex.googleapis.com --project=<PROJECT>
   ```
2. **Application Default Credentials** present and authorized:
   ```bash
   gcloud auth application-default login
   ```
3. **IAM roles** on the project for the running principal:
   - `roles/dataplex.editor` (covers create/update of entry groups, aspect
     types, entry types, entries)
   - Or finer-grained equivalents: `roles/dataplex.catalogEditor` +
     `roles/dataplex.entryGroupOwner`
4. **Python deps** installed (`poetry install` from repo root). The script
   needs `google-cloud-dataplex>=2.0.0` and `pyyaml`, both pinned in
   `pyproject.toml`.

---

## Run

```bash
KNOWLEDGE_CATALOG_PROJECT=vertex-ai-demos-468803 \
KNOWLEDGE_CATALOG_LOCATION=us-central1 \
python knowledge_catalog/setup.py
```

Env vars:

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `KNOWLEDGE_CATALOG_PROJECT` | yes | — | GCP project id |
| `KNOWLEDGE_CATALOG_LOCATION` | no | `us-central1` | Region for the catalog |

Or via the project Makefile target (TASK-06 step 3):

```bash
make setup-knowledge-catalog
```

---

## Idempotency guarantee

The script is safe to re-run. Each resource is read first; if it exists, the
script either:

- skips it (Entry Group), or
- updates with an explicit `update_mask` (Aspect Type, Entry Type, Entry).

Aspect Types compare the full proto (`description`, `display_name`,
`metadata_template`) and stay "unchanged" when the YAML hasn't moved. There
are no destructive operations — the script never deletes anything. If you
need to delete a stale resource, do it manually from the Console.

A race between concurrent runs is handled by catching `AlreadyExists` on
`create_*` calls and falling through to `update_*`.

---

## Expected runtime

- ~30 canonical assets in `data/canonical_assets.json`
- ~5 control-plane API calls (Entry Group + 3 Aspect Types + Entry Type)
- ~30 data-plane API calls (one per Entry)

Cold run: **~30 seconds** end-to-end. Re-runs with no changes (everything
"unchanged"): **~10-15 seconds** (mostly `get_*` round-trips).

If runtime balloons past a minute, check that you're hitting `us-central1`
from a nearby network (a cross-region client adds ~100ms per call).

---

## Verifying in the Console

After `setup.py` finishes:

1. Open the [Dataplex Console](https://console.cloud.google.com/dataplex)
   in the same project.
2. Navigate to **Universal Catalog → Entry Groups**.
3. Open `oilfield-canonical-assets`. You should see ~30 entries
   (one per canonical asset).
4. Click into `TX-001` (Tool X). Verify all three Aspects render:
   - `oilfield-asset-specification` — category `downhole_tool`,
     subcategory `drilling_motor`, operating_temp_max_c `175`, etc.
   - `oilfield-cross-system-aliases` — sap_material_number `MAT-67890`,
     maximo_equipment_id `EQ-12345`, fdp_config_id `TX-CONFIG-A`,
     intouch_spec_refs `["spec-3.2-2024", "compatibility-cc-204"]`.
   - `oilfield-functional-equivalence` — one entry pointing at `TX-007`
     with confidence `0.92` and rationale_source
     `InTouch spec-3.2-2024 §3.2`.

If the canonical Tool X entry looks right end-to-end, the catalog is
demo-ready.

---

## Troubleshooting

**`PermissionDenied`** — the principal running the script lacks
`roles/dataplex.editor`. Add the role or run as a service account that has
it.

**`InvalidArgument: Invalid metadata_template`** — an Aspect Type YAML
has a misspelled type name. Allowed types are `record`, `enum`, `string`,
`integer`, `double`, `boolean`, `array`. Check the YAML and re-run.

**`NotFound` on `get_aspect_type` after creation** — propagation delay.
Wait ~5 seconds and re-run; the create is idempotent.

**Entries missing in the Console** — the Console is region-scoped. Confirm
the URL region matches `KNOWLEDGE_CATALOG_LOCATION` (default
`us-central1`).

**MCP `lookup_context` returns empty** — the prebuilt MCP toolbox reads
`DATAPLEX_PROJECT`. Confirm that env var on the MCP server matches
`KNOWLEDGE_CATALOG_PROJECT` used here (cross-project lookups silently
return zero results).

---

## Where the data goes after this

| Source file | Lands as |
|---|---|
| `data/canonical_assets.json[N]` | One Entry in `oilfield-canonical-assets`, plus its `oilfield-asset-specification` Aspect |
| `data/cross_system_aliases.json[canonical_id]` | The Entry's `oilfield-cross-system-aliases` Aspect |
| `data/functional_equivalences.json` (symmetric) | The Entry's `oilfield-functional-equivalence` Aspect on both `canonical_id_a` and `canonical_id_b` |
| `data/customers.json` | _Not_ ingested here — customer-specific overrides ride on the equivalence Aspect's `customer_overrides` field. Customer profiles themselves live in Memory Bank (TASK-07). |
