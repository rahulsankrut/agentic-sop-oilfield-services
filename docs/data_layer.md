# Data layer

This is the customer-facing reference for what's in BigQuery, where each
column comes from, and what a customer would have to do to point the
demo at their own data.

Generated as part of **TASK-16 Step 14**. Source-of-truth specs live in
`tasks/TASK-16-backend-migration.md` (architecture + decisions) and the
DDL files under `scripts/bq/ddl/`.

## The substitutability contract

Every agent reads through one of three places:
- **3 custom MCP servers** (SAP / Maximo / FDP) running on Cloud Run.
- **`agents/utils/bq_query.py`** for Knowledge Catalog–native tables.
- **Knowledge Catalog MCP** (platform-managed) for semantic lookups.

A customer swaps in their own data by doing exactly this:
1. Dump SAP S/4HANA tables to BigQuery — field names + types match
   `sap_extract.*` DDL exactly.
2. Dump Maximo (MAS 9.x) tables to BigQuery — field names + types match
   `maximo_extract.*` DDL exactly.
3. Provide an FDP-equivalent extract (or fork the FDP MCP server and
   wrap their own homegrown forecasting tool).
4. Repoint env vars: `BQ_PROJECT`, `SAP_MCP_URL`, `MAXIMO_MCP_URL`,
   `FDP_MCP_URL`.
5. Re-run `knowledge_catalog/setup.py` so KC entries reference real
   MATNRs instead of our `MAT-*` placeholders.

No agent code, prompt, or Pydantic schema needs to change.

## Datasets at a glance

```
vertex-ai-demos-468803 (us-central1)
├── sap_extract              — SAP S/4HANA mirror
├── maximo_extract           — Maximo MAS 9.x mirror
├── fdp_extract              — homegrown forecasting/customer-config
├── oilfield_kc              — Knowledge Catalog native (canonical taxonomy)
├── bakerhughes_rig_count    — Baker Hughes public weekly rig count
├── worldport_index          — NGA Pub 150 (3,804 real world ports)
└── eia_steo                 — EIA Short-Term Energy Outlook (monthly basin)
```

## Provenance — column-by-column

Every column carries a label: **real** (sourced from a real public
dataset), **stub** (from the demo's hand-authored `data/*.json` kernel),
**synth** (synthesized by the seeder; documented), or **derived** (a
view over other tables).

### `oilfield_kc.canonical_assets` — 30 OFS assets

| Column | Provenance |
|---|---|
| `CANONICAL_ID`, `CANONICAL_LABEL` | stub — demo IDs kept for scenario continuity |
| `CATEGORY`, `SUBCATEGORY` | stub |
| `OPERATING_TEMP_MAX_C`, `OPERATING_PRESSURE_MAX_PSI`, `OUTER_DIAMETER_IN` | stub |
| `MANUFACTURER` | **real** — USPTO patent assignee (`scripts/build_uspto_anchors.py`) |
| `INTRODUCED_YEAR` | **real** — USPTO patent filing year |

### `oilfield_kc.cross_system_aliases` — 30 entries

| Column | Provenance |
|---|---|
| `CANONICAL_ID` | stub |
| `SAP_MATNR`, `MAXIMO_ITEMNUM`, `FDP_CONFIG_ID` | stub — demo identifiers |
| `INTOUCH_SPEC_REFS` | stub |

### `oilfield_kc.functional_equivalences` — 12 pairs

| Column | Provenance |
|---|---|
| `CANONICAL_ID_A`, `CANONICAL_ID_B`, `CONFIDENCE`, `RATIONALE_SOURCE`, `CUSTOMER_OVERRIDES` | stub (engineering content — customer brings their InTouch equivalence pairs) |

### `sap_extract.MARA` — 30 materials

| Column | Provenance |
|---|---|
| `MANDT` | synth (`'100'` — SAP client code convention) |
| `MATNR` | stub |
| `ERSDA`, `LAEDA` | **real** — derived from USPTO patent filing date |
| `MTART`, `MBRSH`, `MATKL`, `MEINS` | synth (SAP control fields with no public counterpart) |
| `BISMT`, `LVORM` | synth |
| `ERNAM`, `AENAM` | synth (`'SYSTEM'`) |

### `sap_extract.MAKT` — 30 rows (English only)

| Column | Provenance |
|---|---|
| `MANDT`, `SPRAS` | synth |
| `MATNR` | stub |
| `MAKTX` | **real** — USPTO patent title (40-char truncated) |

### `sap_extract.MARC` / `MARD` / `MBEW` — per-plant data

Mostly synth — SAP control fields. STPRS (standard price) in MBEW is
synth but stratified by category to match real OFS-equipment ranges
($250k–$3M).

### `sap_extract.KNA1` — 7 customers

| Column | Provenance |
|---|---|
| `MANDT` | synth |
| `KUNNR` | synth (`0000100001` style sequential, SAP-conventional) |
| `NAME1` | stub — demo names kept (scenario references) |
| `LAND1` | **real** — ISO-2 country code from curated anchor (`scripts/build_sec_edgar_anchors.py`) |
| `ORT01`, `STRAS` | **real** — SEC EDGAR submission addresses for 7 real OFS-relevant operators (Murphy Oil, Hess, CNOOC, Diamondback, Equinor, Petrobras, Woodside) |

### `sap_extract.KNVV` — Customer sales view, 7 rows

All synth (SAP control fields).

### `sap_extract.ZHR_WORKFORCE` — 7 basins

| Column | Provenance |
|---|---|
| `BASIN` | stub |
| `CREW_COUNT_AVAILABLE`, `SPECIALIST_COUNT_AVAILABLE`, `ON_CALL_COUNT` | stub (operational counts kept; agent reasons on these) |
| `NAICS_211_STATE_EMPLOYMENT` | **real** — BLS QCEW Oil & Gas Extraction state employment rolled up to basin (`scripts/build_bls_qcew_anchors.py`). US basins only — foreign basins NULL. |
| `DATA_SOURCE` | label string indicating real vs. synthesized |
| `SNAPSHOT_DATE` | synth (today) |

### `maximo_extract.ASSET` — 11 instances

| Column | Provenance |
|---|---|
| `ASSETID` | synth (surrogate) |
| `ASSETNUM`, `DESCRIPTION`, `STATUS`, `LOCATION`, `SITEID`, `ITEMNUM` | stub |
| `INSTALLDATE` | **real** — derived from USPTO patent filing year |
| `SERIALNUM` | synth |

### `maximo_extract.ITEM` — 30 items

| Column | Provenance |
|---|---|
| `ITEMNUM`, `ITEMSETID` | stub |
| `DESCRIPTION` | **real** — USPTO patent title (100-char) |
| `COMMODITYGROUP` | stub |

### `maximo_extract.LOCATIONS` — 6 facility locations

| Column | Provenance |
|---|---|
| `LOCATION`, `SITEID`, `ORGID`, `DESCRIPTION`, `TYPE`, `STATUS`, `REGION` | stub |
| `LATITUDE`, `LONGITUDE` | stub (already realistic lat/lons in the demo kernel) |
| `WPI_PORT_INDEX_NUMBER`, `WPI_PORT_NAME` | **real** — nearest port from NGA Pub 150 World Port Index, within 200km. Inland locations (Midland TX) → NULL. |

### `maximo_extract.WORKORDER` — 2 open WOs

| Column | Provenance |
|---|---|
| `WONUM`, `SITEID`, `ASSETNUM`, `LOCATION`, `STATUS`, `WORKTYPE` | stub |
| `REPORTDATE` | **real** — anchored to a real BSEE incident date |
| `ESTLABHRS`, `ACTLABHRS` | derived (so `MAX(EST-ACT)` equals the per-asset cert-hours remaining) |
| `BSEE_LEASE_REF`, `BSEE_INCIDENT_DATE` | **real** — BSEE Incident Investigations raw data (`scripts/build_bsee_anchors.py`) |

### `maximo_extract.WO_HISTORY` — VIEW

Derived from `WORKORDER` filtered to STATUS='COMP'. Used by
`scheduling-probability.get_start_date_distribution`. Currently empty
because all seeded WOs are INPRG — see fallback in the skill tool.

### `fdp_extract.CUSTOMER_CONFIG` — 13 rows

All stub. Customer-restriction matrices are confidential commercial
data; we synthesize the shape, the customer brings their own content.

### `fdp_extract.APPROVED_SUBSTITUTIONS` — 11 rows

Same — stub. Derived from the demo kernel's
`v?_substitution_accepted` boolean flattening.

### `bakerhughes_rig_count.weekly_basin` — 20 rows

| Column | Provenance |
|---|---|
| All columns | **real** — publicly-known recent US-basin rig counts (Permian 313, Eagle Ford 52, etc.) via `scripts/load_bakerhughes.py --seed-demo` |

Production customers replace `--seed-demo` with `--file <bh_pivot.xlsb>` —
Baker Hughes' weekly pivot Excel.

### `worldport_index.ports` — 3,804 ports

| Column | Provenance |
|---|---|
| All columns | **real** — NGA Pub 150 World Port Index, US Government public domain |

### `eia_steo.basin_production` — 1,008 rows (72 months × 14 basins)

| Column | Provenance |
|---|---|
| All columns | **real** — EIA Short-Term Energy Outlook Table 10a (active rigs) + Table 10b (tight oil + shale gas) |

## Real-data anchor builders

These one-shot scripts populate `data/anchors/*.json` with real public-source
records that the seeder then merges into BQ:

| Script | Source | Anchor file |
|---|---|---|
| `scripts/build_uspto_anchors.py` | Google Patents Public BQ Dataset | `data/anchors/uspto_patents.json` |
| `scripts/build_sec_edgar_anchors.py` | SEC EDGAR submissions API | `data/anchors/sec_edgar_customers.json` |
| `scripts/build_bls_qcew_anchors.py` | BLS QCEW NAICS 211 CSV | `data/anchors/bls_qcew_workforce.json` |
| `scripts/build_bsee_anchors.py` | BSEE Incident Investigations ZIP | `data/anchors/bsee_workorders.json` |

Public-dataset loaders (loaded by `make` targets, not the JSON seeder):

| Script | Source | Target table |
|---|---|---|
| `scripts/load_bakerhughes.py` | Baker Hughes weekly pivot (manual download) | `bakerhughes_rig_count.weekly_basin` |
| `scripts/load_worldport_index.py` | NGA Pub 150 CSV (direct) | `worldport_index.ports` |
| `scripts/load_eia.py` | EIA STEO bulk Excel (direct) | `eia_steo.basin_production` |

## Verification

`make verify` includes the `scripts/verify_no_json_reads.py` static
check — fails if any agent production module reads from
`agents.utils.synthetic_data`. Plus `make smoke-cargo-plane` runs the
10-assertion data-flow smoke that exercises every migrated skill tool
end-to-end against the live BQ.

## What stays synthetic — and why

The five categories that have no public counterpart, documented per
TASK-16 §8:

1. **`fdp_extract.CUSTOMER_CONFIG` + `APPROVED_SUBSTITUTIONS`** — customer-
   restriction matrices are confidential commercial data. No public
   source. Shape is faithful to what an FDP equivalent would produce.
2. **`oilfield_kc.functional_equivalences`** — engineering content owned
   in InTouch / spec repositories. Customer IP.
3. **`oilfield_kc.intouch_spec_refs`** — internal technical doc
   references. Customer's own KC entries.
4. **`sap_extract.ZHR_WORKFORCE`** crew/specialist counts (NAICS_211
   reference is real). Workforce-by-basin Z-table has no standard SAP
   equivalent; every customer rolls their own from HR data.
5. **SAP control fields** (MANDT, MTART, MARC.DISPO/DISMM/BESKZ, MBEW
   pricing details) — SAP system-internal codes with no public source.

Each demo narration line for these tables says: "This table is
shape-faithful to what you'd extract from your system. We populated it
with industry-credible synthetic data because the real data is yours."
