# TASK-16: Backend migration — BigQuery extracts that mirror SAP + Maximo, MCP servers wired to BQ, public datasets where the shape matches

**Prerequisites:** TASK-05 (MCP servers) complete and TASK-06 (Knowledge Catalog) complete. Existing skill tools currently read `data/*.json` directly via `agents/utils/synthetic_data.py`. The MCP server backends (`mcp_servers/{sap,maximo,fdp}/backend/main.py`) also read those JSON files. This task moves the source of truth to BigQuery, with table layouts that mirror SAP S/4HANA + IBM Maximo extract dumps so a customer's ETL person recognizes them.

**Estimated effort:** 6-8 days for one engineer.

**Stream:** Backend (data layer + 3 MCP server backends + skill tools). No agent code changes outside the four `scripts/tools.py` migrations, the one-line `description` rename in `equivalence_lookup.py`, and (optionally) cleaner Pydantic response models.

---

## 1. Substitutability contract — the load-bearing claim

A customer (SLB / Halliburton / Baker Hughes / NOV) must be able to swap our synthetic backend with their real systems by doing exactly these things and nothing else:

1. **Extract from their SAP ECC / S/4HANA into BigQuery (or their preferred substrate)**: dump MARA, MAKT, MARC, MARD, MBEW, KNA1, KNVV, and `ZHR_WORKFORCE` (or their HR view). Field names and types match our `sap_extract.*` DDL exactly. The agent reads SAP data via our custom SAP MCP server (`mcp_servers/sap`), which queries BQ in our v1. **If the customer prefers live SAP via OData** — fork the SAP MCP server and swap the BQ query inside each tool for the OData call. **The tool surface (`sap.get_material_master(matnr)`) the agent sees stays identical.**
2. **Extract from their Maximo (MAS 9.x) into BigQuery (or fork to wrap live Maximo)**: dump ASSET, ITEM, INVENTORY, INVBALANCES, LOCATIONS, ASSETLOCATIONS, WORKORDER (and the `WO_HISTORY` view). Field names and types match our `maximo_extract.*` DDL exactly. Agent reads via our custom Maximo MCP server (`mcp_servers/maximo`). Same fork-and-rewire substitution path as SAP.
3. **Provide an FDP-equivalent extract** (or wrap their live FDP-equivalent): a flat table of (`customer_id`, `material_number`, `approved_flag`, `accepted_substitutes[]`, `notes`). FDP is the homegrown forecasting/customer-config tool — there's no public schema, so the contract is the columns. Agent reads via our custom FDP MCP server.
4. **Repoint env vars**: `BQ_PROJECT` (their project ID), `BQ_DATASET_PREFIX` (their dataset naming, defaults match ours), `SAP_MCP_URL` / `MAXIMO_MCP_URL` / `FDP_MCP_URL` (their three Cloud Run URLs).
5. **Populate Knowledge Catalog**: re-run `knowledge_catalog/setup.py` against their `sap_extract.MARA` extract so Catalog Entries reference real `MATNR` values instead of our `MAT-*` placeholders.

If a customer does only steps 1, 2, 4, and 5 and provides an empty FDP table, the cargo-plane scenario still runs (the customer-restriction matrix degrades to "no restrictions known"). That is the minimum-viable substitution.

**Why three custom Cloud Run MCP servers and not the managed BigQuery MCP:** The typed tool surface is the substitutability contract. `sap.get_material_master(matnr) -> SapMaterialMaster` is what the agent reasons against; what's inside the tool can be a BQ query (our demo), a live OData call (customer's prod), or a hybrid. With managed BigQuery MCP the agent's tool would be `execute_sql_readonly(...)` — that couples the agents to BigQuery as the source of truth forever, which is wrong for OFS majors who will have on-prem ECC + Maximo for years. Custom MCP servers also let us do per-tool IAM in Agent Gateway (allow `sap.get_workforce`, deny `sap.write_master`) which managed BQ MCP can't express at the same grain.

**Out of contract — what we explicitly do not promise:** that our equivalence graph (`oilfield_kc.functional_equivalences`) maps to anything in their world. Equivalences are engineering-curated content; the customer will replace it from their InTouch / spec repository.

---

## 2. Target architecture

```
        ┌─────────────────────────────────────────────────────────┐
        │              BigQuery (us-central1)                     │
        │  Project: vertex-ai-demos-468803                        │
        │                                                         │
        │  Datasets (each named after the source system):         │
        │    sap_extract           — MARA, MAKT, MARC, MARD,      │
        │                            MBEW, KNA1, KNVV,            │
        │                            ZHR_WORKFORCE                │
        │    maximo_extract        — ASSET, ITEM, INVENTORY,      │
        │                            INVBALANCES, LOCATIONS,      │
        │                            ASSETLOCATIONS, WORKORDER,   │
        │                            WO_HISTORY (view, see §3)    │
        │    fdp_extract           — CUSTOMER_CONFIG,             │
        │                            APPROVED_SUBSTITUTIONS       │
        │    bakerhughes_rig_count — weekly_basin, weekly_state   │
        │    worldport_index       — ports                        │
        │    eia_steo              — basin_production             │
        │    oilfield_kc           — canonical_assets,            │
        │                            cross_system_aliases,        │
        │                            functional_equivalences      │
        └────────────┬────────────────────────────────────────────┘
                     │ BQ jobs (read-only from MCP servers)
                     │ — customer swaps to live OData/REST by
                     │   forking the MCP server, no agent changes
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │   3 custom MCP servers (Cloud Run, FastAPI)                  │
   │                                                              │
   │   mcp_servers/sap/backend      → sap.* typed tools           │
   │     sap.get_material_master, sap.get_plant_data,             │
   │     sap.get_storage_location_stock, sap.get_standard_price,  │
   │     sap.get_customer, sap.resolve_customer_by_name,          │
   │     sap.get_workforce_by_basin                               │
   │                                                              │
   │   mcp_servers/maximo/backend   → maximo.* typed tools        │
   │     maximo.get_item, maximo.query_assets_by_item,            │
   │     maximo.query_assets_by_region, maximo.get_location,      │
   │     maximo.get_inventory_balances (Q2 — separate from ASSET),│
   │     maximo.get_open_workorders,                              │
   │     maximo.get_start_date_distribution (queries WO_HISTORY)  │
   │                                                              │
   │   mcp_servers/fdp/backend      → fdp.* typed tools           │
   │     fdp.get_customer_config, fdp.list_approved_substitutions,│
   │     fdp.list_customer_restrictions                           │
   └────────────┬─────────────────────────────────────────────────┘
                │ MCP (StreamableHTTP) via Agent Gateway
                │ (IAM per-tool + Model Armor + audit + Registry)
                ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ Knowledge Catalog MCP (managed, platform-provided)           │
   │ https://dataplex.googleapis.com/mcp                          │
   │   kc.lookup_context, kc.search_entries, kc.list_related...   │
   └────────────┬─────────────────────────────────────────────────┘
                │ all 4 MCP servers fronted by Agent Gateway
                ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ Agent skill tools (one tools.py per skill)                   │
   │                                                              │
   │ asset-equivalence       → KC MCP (lookup + relationships)    │
   │ enterprise-systems      → sap.* / maximo.* / fdp.* / kc.*    │
   │ sourcing-logistics      → Maps Grounding (TASK #46, GA tool) │
   │                            + maximo.* (blockers, recert)     │
   │                            + fdp.* (restrictions)            │
   │ procurement-prereqs     → pure functions (unchanged)         │
   │ forecast-rationale      → pure + sap.* (price cross-check)   │
   │ scheduling-probability  → maximo.get_start_date_distribution │
   └──────────────────────────────────────────────────────────────┘

Public-dataset loaders (one-shot scripts, run from venv):
  - scripts/load_bakerhughes.py        → bakerhughes_rig_count.weekly_*
  - scripts/load_worldport_index.py    → worldport_index.ports
  - scripts/load_eia_steo.py           → eia_steo.basin_production
```

**Four MCP servers in the path:** three custom Cloud Run (SAP, Maximo, FDP) wrapping BigQuery, plus the platform-provided Knowledge Catalog MCP. Plus Maps Grounding from TASK #46 (model-level, not registered with Gateway — wires through the Gemini API directly).

**Why all-custom and not managed BigQuery MCP:** the typed tool surface is the substitution boundary. `sap.get_material_master(matnr) -> SapMaterialMaster` stays identical whether the implementation queries BQ (our v1) or live SAP OData (customer prod) — agent code, prompts, and Pydantic schemas don't change. Managed BigQuery MCP exposes generic `execute_sql_readonly` to the agent, which (a) couples agents to BQ as the source of truth permanently, (b) widens LLM error surface (the LLM writes SQL), (c) makes Agent Gateway per-tool IAM coarse (only one tool to authorize, instead of fine-grained `allow sap.get_workforce, deny sap.write_master`).

**Auth flow:** Orchestrator runtime (Vertex AI Agent Engine) gets ADC and presents it as Bearer to Agent Gateway → Gateway validates IAM + applies per-tool policy + Model Armor → forwards to the right MCP server. The MCP servers run as Cloud Run services with their own service accounts that have `roles/bigquery.dataViewer` on the relevant dataset.

Maps Grounding (TASK #46) lives in `sourcing-logistics` and `plan_evaluator` and is untouched.

---

## 3. BigQuery DDL — mirroring SAP + Maximo

Region for every dataset: **us-central1**. Project: **vertex-ai-demos-468803**. Each table has a `_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()` audit column (suffix, not part of the source schema; customer ETLs can drop it).

Provenance legend per column: **(stub)** = mirrors the existing `data/*.json` content, **(public)** = comes from a public dataset loader, **(synth)** = synthesized with realistic distribution but no public source.

### `sap_extract.MARA` — General Material Data

| Column | Type | Source SAP field | Provenance | Notes |
|---|---|---|---|---|
| `MANDT` | STRING(3) | MANDT (Client) | (stub) constant `'100'` | SAP key prefix |
| `MATNR` | STRING(40) | MATNR (Material Number) | (stub) from `cross_system_aliases.json` `sap_material_number` | PK |
| `ERSDA` | DATE | ERSDA (Creation date) | (synth) | derived from `introduced_year` |
| `ERNAM` | STRING(12) | ERNAM (Created by) | (synth) constant `'SYSTEM'` | |
| `LAEDA` | DATE | LAEDA (Last change) | (synth) | |
| `AENAM` | STRING(12) | AENAM (Changed by) | (synth) | |
| `MTART` | STRING(4) | MTART (Material Type) | (synth) `'ROH'` raw, `'FERT'` finished | maps from `category` |
| `MBRSH` | STRING(1) | MBRSH (Industry Sector) | (synth) constant `'M'` (mechanical) | |
| `MATKL` | STRING(9) | MATKL (Material Group) | (synth) | derived from `subcategory` |
| `MEINS` | STRING(3) | MEINS (Base UoM) | (synth) constant `'EA'` | |
| `BISMT` | STRING(40) | BISMT (Old material #) | nullable (stub) | |
| `LVORM` | BOOL | LVORM (Deletion flag) | (synth) constant FALSE | |
| `_loaded_at` | TIMESTAMP | — | audit | |

Partition by `ERSDA` (DAY). Cluster by `MATNR`.

> Cross-ref: SAP MARA primary key is (MANDT, MATNR). MATNR is CHAR 18 in ECC, expanded to CHAR 40 in S/4 — we use CHAR 40 to be S/4-future-proof. Existing stub IDs (`MAT-67890`, etc.) are well under 40 chars so they remain valid.

### `sap_extract.MAKT` — Material Description (text table)

| Column | Type | Source | Provenance |
|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | (stub) `'100'` |
| `MATNR` | STRING(40) | MATNR | (stub) FK MARA |
| `SPRAS` | STRING(1) | SPRAS (Language) | (stub) `'E'` |
| `MAKTX` | STRING(40) | MAKTX (Description) | (stub) from `canonical_label` |

PK (MANDT, MATNR, SPRAS).

### `sap_extract.MARC` — Plant Data for Material

| Column | Type | Source | Provenance | Notes |
|---|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | (stub) `'100'` | |
| `MATNR` | STRING(40) | MATNR | (stub) FK MARA | |
| `WERKS` | STRING(4) | WERKS (Plant) | (synth) plant codes derived from region (`PT01`, `PT02`, ...) | PK |
| `DISPO` | STRING(3) | DISPO (MRP Controller) | (synth) `'001'` | |
| `DISMM` | STRING(2) | DISMM (MRP Type) | (synth) `'PD'` | |
| `BESKZ` | STRING(1) | BESKZ (Procurement Type) | (synth) `'F'` external | |
| `LVORM` | BOOL | LVORM (Plant deletion flag) | FALSE | |
| `_loaded_at` | TIMESTAMP | | | |

PK (MANDT, MATNR, WERKS). Cluster by (MATNR, WERKS).

### `sap_extract.MARD` — Storage Location Stock

| Column | Type | Source | Provenance |
|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | `'100'` |
| `MATNR` | STRING(40) | MATNR | (stub) |
| `WERKS` | STRING(4) | WERKS | (synth) |
| `LGORT` | STRING(4) | LGORT (Storage Location) | (synth) e.g. `'LAG1'`, `'HOU1'`, derived from Maximo `location.label` |
| `LABST` | NUMERIC(13,3) | LABST (Unrestricted stock) | (stub) — 1 per available equipment instance from `maximo_inventory.json` |
| `INSME` | NUMERIC(13,3) | INSME (Quality inspection stock) | 0 |
| `_loaded_at` | TIMESTAMP | | |

PK (MANDT, MATNR, WERKS, LGORT). This is where "is there inventory at a plant" answers come from on the SAP side. We deliberately keep this aligned with Maximo's view in §3.6 — that mirrors real customer environments where the two systems diverge by a few percent, which is exactly the substitutability story.

### `sap_extract.MBEW` — Material Valuation

| Column | Type | Source | Provenance |
|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | `'100'` |
| `MATNR` | STRING(40) | MATNR | (stub) |
| `BWKEY` | STRING(4) | BWKEY (Valuation area) | (synth) = WERKS |
| `VPRSV` | STRING(1) | VPRSV (Price control) | (synth) `'S'` standard |
| `STPRS` | NUMERIC(11,2) | STPRS (Standard price) | (synth) derived from subcategory class — downhole tools $250k-$1.2M, surface pumps $1.5M-$3M |
| `PEINH` | NUMERIC(5,0) | PEINH (Price unit) | `1` |
| `WAERS` | STRING(5) | WAERS (Currency) | `'USD'` |

This is what the procurement-prereqs `check_budget_threshold` tool will eventually pull real cost from instead of trusting whatever the LLM put in `estimated_cost_usd`.

### `sap_extract.KNA1` — Customer Master (General Data)

| Column | Type | Source | Provenance |
|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | `'100'` |
| `KUNNR` | STRING(10) | KUNNR (Customer #) | (stub) derived from `customer_id` slug (`gulf-petroleum` → `0000100001` etc.) |
| `NAME1` | STRING(35) | NAME1 | (stub) from `customers.json` `name` |
| `LAND1` | STRING(3) | LAND1 (Country) | (synth) `'AO'`, `'GB'`, `'US'`, `'CN'` based on `regions` |
| `ORT01` | STRING(35) | ORT01 (City) | (synth) |
| `STRAS` | STRING(35) | STRAS (Street) | (synth) |
| `_loaded_at` | TIMESTAMP | | |

### `sap_extract.KNVV` — Customer Sales Data

| Column | Type | Source | Provenance |
|---|---|---|---|
| `MANDT` | STRING(3) | MANDT | `'100'` |
| `KUNNR` | STRING(10) | KUNNR | FK KNA1 |
| `VKORG` | STRING(4) | VKORG (Sales Org) | (synth) `'OFS1'` |
| `VTWEG` | STRING(2) | VTWEG (Distribution channel) | (synth) `'10'` |
| `SPART` | STRING(2) | SPART (Division) | (synth) `'01'` |

### `sap_extract.ZHR_WORKFORCE` — Custom workforce-by-basin extract

(SAP has no standard table for this; every OFS major uses an HR custom Z-table or a CDS view. We model it as a custom Z-table — that's what the customer's ETL guy will recognize.)

| Column | Type | Provenance |
|---|---|---|
| `BASIN` | STRING(20) | (stub) from `sap_workforce.json` keys |
| `CREW_COUNT_AVAILABLE` | INT64 | (stub) |
| `SPECIALIST_COUNT_AVAILABLE` | INT64 | (stub) |
| `ON_CALL_COUNT` | INT64 | (stub) |
| `SNAPSHOT_DATE` | DATE | (synth) — most recent `CURRENT_DATE()` row used |

Partition by `SNAPSHOT_DATE`. Cluster by `BASIN`.

### `maximo_extract.ASSET` — Asset Master

| Column | Type | Source Maximo field | Provenance | Notes |
|---|---|---|---|---|
| `ASSETID` | INT64 | ASSETID | (synth) surrogate | PK |
| `ASSETNUM` | STRING(25) | ASSETNUM | (stub) from `equipment_instance_id` (e.g. `TX-007-LGS-001`) | unique within SITEID |
| `DESCRIPTION` | STRING(100) | DESCRIPTION | (stub) from canonical `canonical_label` |
| `STATUS` | STRING(16) | STATUS | (stub) `available`/`in_use`/`in_repair`/`available_after_recert` |
| `LOCATION` | STRING(25) | LOCATION | (stub) FK LOCATIONS |
| `SITEID` | STRING(16) | SITEID | (synth) derived from region (`LAGOS`, `HOU01`, `DARWIN`) |
| `ORGID` | STRING(8) | ORGID | (synth) constant `'OFS'` |
| `PARENT` | STRING(25) | PARENT | nullable (no hierarchy in our model) |
| `ASSETTYPE` | STRING(16) | ASSETTYPE | (synth) maps from canonical `category` |
| `ITEMNUM` | STRING(25) | ITEMNUM | (stub) FK ITEM |
| `SERIALNUM` | STRING(40) | SERIALNUM | (synth) |
| `INSTALLDATE` | DATE | INSTALLDATE | (synth) |
| `_loaded_at` | TIMESTAMP | | | |

PK (ASSETID). UNIQUE (SITEID, ASSETNUM) — Maximo's natural key.

### `maximo_extract.ITEM` — Item Master

| Column | Type | Source | Provenance |
|---|---|---|---|
| `ITEMNUM` | STRING(25) | ITEMNUM | (stub) — `maximo_equipment_id` from `cross_system_aliases.json` |
| `ITEMSETID` | STRING(16) | ITEMSETID | (synth) `'SET1'` |
| `DESCRIPTION` | STRING(100) | DESCRIPTION | (stub) from canonical label |
| `COMMODITYGROUP` | STRING(16) | COMMODITYGROUP | (synth) from category |
| `_loaded_at` | TIMESTAMP | | |

PK (ITEMSETID, ITEMNUM).

### `maximo_extract.INVENTORY` — Inventory Item-at-Location

| Column | Type | Source | Provenance |
|---|---|---|---|
| `ITEMNUM` | STRING(25) | ITEMNUM | (stub) FK |
| `ITEMSETID` | STRING(16) | ITEMSETID | (synth) `'SET1'` |
| `LOCATION` | STRING(25) | LOCATION | (stub) from Maximo inventory `location.label` slugified |
| `SITEID` | STRING(16) | SITEID | (synth) |
| `STATUS` | STRING(16) | STATUS | (stub) `'ACTIVE'` |
| `ABCTYPE` | STRING(1) | ABCTYPE | (synth) `'A'` |
| `_loaded_at` | TIMESTAMP | | |

PK (ITEMSETID, ITEMNUM, LOCATION, SITEID).

### `maximo_extract.INVBALANCES` — Storage Bin Balances

Per Maximo docs: PK is (SiteId, ItemSetID, Itemnum, Location, Binnum, Lotnum).

| Column | Type | Source | Provenance |
|---|---|---|---|
| `ITEMNUM` | STRING(25) | ITEMNUM | (stub) |
| `ITEMSETID` | STRING(16) | ITEMSETID | (synth) `'SET1'` |
| `LOCATION` | STRING(25) | LOCATION | (stub) |
| `SITEID` | STRING(16) | SITEID | (synth) |
| `BINNUM` | STRING(8) | BINNUM | (synth) `'A1'` |
| `LOTNUM` | STRING(8) | LOTNUM | nullable |
| `CONDITIONCODE` | STRING(10) | CONDITIONCODE | (synth) `'NEW'` / `'REFURB'` |
| `PHYSCNT` | NUMERIC(12,4) | PHYSCNT | (stub) 1 per available instance |
| `PHYSCNTDATE` | DATE | PHYSCNTDATE | (synth) |
| `CURBAL` | NUMERIC(12,4) | CURBAL | (stub) = PHYSCNT |

### `maximo_extract.LOCATIONS` — Location Master

| Column | Type | Source | Provenance | Notes |
|---|---|---|---|---|
| `LOCATION` | STRING(25) | LOCATION | (stub) slug of `location.label` | PK part |
| `SITEID` | STRING(16) | SITEID | (synth) | PK part |
| `ORGID` | STRING(8) | ORGID | (synth) `'OFS'` |
| `DESCRIPTION` | STRING(100) | DESCRIPTION | (stub) `location.label` |
| `TYPE` | STRING(16) | TYPE | (synth) `'STOREROOM'` / `'OPERATING'` |
| `STATUS` | STRING(16) | STATUS | `'OPERATING'` |
| `LATITUDE` | NUMERIC(9,6) | (custom — Maximo Spatial extension) | **(public — WPI for ports, stub for everything else)** | |
| `LONGITUDE` | NUMERIC(9,6) | (custom) | (public/stub) | |
| `REGION` | STRING(20) | (custom Z-attribute) | (stub) | |

PK (SITEID, LOCATION). Real Maximo Spatial moves geometry to a separate table in MAS 9.0; we keep lat/lon inline for demo simplicity and document the deviation.

### `maximo_extract.ASSETLOCATIONS` — Asset Location History

Slim version. PK (ASSETID, LOCATION, SITEID, EFFECTIVE_DATE).

### `maximo_extract.WORKORDER` — Work Order (recert + repair tracking)

| Column | Type | Provenance |
|---|---|---|
| `WONUM` | STRING(16) | (synth) |
| `SITEID` | STRING(16) | (synth) |
| `ASSETNUM` | STRING(25) | (stub) FK ASSET |
| `STATUS` | STRING(16) | (stub) `'WAPPR'`, `'INPRG'`, `'COMP'` |
| `WORKTYPE` | STRING(10) | (synth) `'RECERT'`, `'REPAIR'` |
| `REPORTDATE` | TIMESTAMP | (synth) |
| `ESTLABHRS` | NUMERIC(8,2) | (stub) from `certification_hours_remaining` |

This is where `certification_hours_remaining` actually lives in a real Maximo install — not on the ASSET row.

### `maximo_extract.WO_HISTORY` — Work-order completion history (view)

A BigQuery view, not a base table — derived from `WORKORDER` to expose schedule-vs-actual variance per asset class per basin. Replaces the previous `oilfield_kc.start_date_variance` table (Q7 resolution 2026-05-20: variance belongs at the source).

```sql
CREATE VIEW `maximo_extract.WO_HISTORY` AS
SELECT
  w.WONUM,
  w.SITEID,
  w.ASSETNUM,
  a.ITEMNUM,
  l.REGION,
  l.LATITUDE,
  l.LONGITUDE,
  w.WORKTYPE,
  w.SCHEDSTART        AS scheduled_start,
  w.ACTSTART          AS actual_start,
  TIMESTAMP_DIFF(w.ACTSTART, w.SCHEDSTART, DAY) AS variance_days,
  w.STATUS,
  w.REPORTDATE
FROM `maximo_extract.WORKORDER` w
JOIN `maximo_extract.ASSET`     a USING (ASSETNUM, SITEID)
JOIN `maximo_extract.LOCATIONS` l USING (SITEID, LOCATION)
WHERE w.STATUS = 'COMP' AND w.ACTSTART IS NOT NULL;
```

This is what `scheduling-probability.get_start_date_distribution(basin, customer_id?, asset_class?)` queries via the BigQuery MCP server. Substitution path: a customer points at their own Maximo WO dump and the view definition is portable — same SQL works against their data. No separate "start_date_variance" extract is needed.

Notes for the seeder: the existing `data/start_date_variance/*.json` files are *aggregated* (p10/p50/p90 already computed). To populate `WO_HISTORY` realistically, the seeder reverse-engineers individual WO rows from the distributions — generates N rows per basin/asset-class drawn from a lognormal fitted to the p10/p50/p90 triplet. The view then re-aggregates to the same p10/p50/p90 the agent expects. Round-trip test in §7 Step 11 confirms.

### `fdp_extract.CUSTOMER_CONFIG`

| Column | Type | Provenance |
|---|---|---|
| `CUSTOMER_ID` | STRING(40) | (stub) `customers.json` slug |
| `MATNR` | STRING(40) | (stub) maps to canonical via cross-aliases |
| `APPROVED` | BOOL | (stub) |
| `NOTES` | STRING(500) | (stub) |
| `EFFECTIVE_DATE` | DATE | (synth) |

### `fdp_extract.APPROVED_SUBSTITUTIONS`

| Column | Type | Provenance |
|---|---|---|
| `CUSTOMER_ID` | STRING(40) | (stub) |
| `MATNR_ORIGINAL` | STRING(40) | (stub) |
| `MATNR_SUBSTITUTE` | STRING(40) | (stub) |
| `ACCEPTED` | BOOL | (stub) |

This normalizes the awkward `v7_substitution_accepted` boolean from `fdp_configurations.json` into proper rows. Customer's ETL guy will produce this from FDP directly.

### `bakerhughes_rig_count.weekly_basin` (public)

Source: Baker Hughes North America Rig Count Pivot Excel (rigcount.bakerhughes.com).

| Column | Type | Provenance |
|---|---|---|
| `WEEK_ENDING_DATE` | DATE | (public) |
| `COUNTRY` | STRING(20) | (public) |
| `BASIN` | STRING(40) | (public) |
| `DRILL_FOR` | STRING(16) | (public) Oil / Gas / Misc |
| `TRAJECTORY` | STRING(16) | (public) Horizontal / Directional / Vertical |
| `WELL_TYPE` | STRING(16) | (public) |
| `RIG_COUNT` | INT64 | (public) |

Partition by WEEK_ENDING_DATE. Cluster by (COUNTRY, BASIN).

### `worldport_index.ports` (public)

Source: NGA Pub 150 `UpdatedPub150.csv` (msi.nga.mil). 3,818 ports, 106 fields — we keep a useful subset (~25 columns).

| Column | Type | Provenance |
|---|---|---|
| `WORLD_PORT_INDEX_NUMBER` | INT64 | (public) PK |
| `MAIN_PORT_NAME` | STRING(80) | (public) |
| `UN_LOCODE` | STRING(10) | (public) |
| `COUNTRY_CODE` | STRING(3) | (public) |
| `LATITUDE` | NUMERIC(9,6) | (public) |
| `LONGITUDE` | NUMERIC(9,6) | (public) |
| `HARBOR_TYPE` | STRING(20) | (public) |
| `HARBOR_SIZE` | STRING(10) | (public) |
| `OCEAN_BASIN` | STRING(20) | (public) |
| `MAX_VESSEL_LENGTH_M` | NUMERIC(7,2) | (public) |
| `MAX_VESSEL_DRAFT_M` | NUMERIC(5,2) | (public) |

The Capacity Orchestrator's sourcing-logistics flow can use this to anchor "nearest port to a target operating location" — Lagos has a real port entry, Luanda has a real port entry, distances become defensible rather than haversine off equipment labels.

### `eia_steo.basin_production` (public)

Source: `eia.gov/petroleum/drilling/xls/dpr-data.xlsx`.

| Column | Type | Provenance |
|---|---|---|
| `REPORT_MONTH` | DATE | (public) |
| `BASIN` | STRING(20) | (public) Permian, Bakken, Eagle Ford, Anadarko, Appalachia, Haynesville, Niobrara |
| `OIL_PROD_BPD` | INT64 | (public) |
| `GAS_PROD_MCFD` | INT64 | (public) |
| `RIG_PRODUCTIVITY_NEW_WELL_OIL_BPD` | INT64 | (public) |

Used to populate `forecast_history` and drive the Persona 1 narrative ("ML forecast says basin X production is trending Y because rig productivity Z"). For the demo it's read-only context for the forecast-rationale skill.

### `oilfield_kc.*` — Catalog-native tables (engineering content)

These three are what's already in `data/` minus their SAP/Maximo cross-references, which now live in `sap_extract` / `maximo_extract`. They join via `MATNR` (SAP material number) and `ITEMNUM` (Maximo item number) instead of the ad-hoc `canonical_id`.

`oilfield_kc.canonical_assets`:
| Column | Type | Provenance |
|---|---|---|
| `CANONICAL_ID` | STRING(20) | (stub) e.g. `'TX-001'` |
| `CANONICAL_LABEL` | STRING(60) | (stub) |
| `CATEGORY` | STRING(30) | (stub) |
| `SUBCATEGORY` | STRING(40) | (stub) |
| `OPERATING_TEMP_MAX_C` | INT64 | (stub) |
| `OPERATING_PRESSURE_MAX_PSI` | INT64 | (stub) |
| `OUTER_DIAMETER_IN` | NUMERIC(5,3) | (stub) |
| `MANUFACTURER` | STRING(20) | (stub) |
| `INTRODUCED_YEAR` | INT64 | (stub) |

`oilfield_kc.cross_system_aliases`:
| `CANONICAL_ID` | STRING | PK |
| `SAP_MATNR` | STRING(40) | → sap_extract.MARA.MATNR |
| `MAXIMO_ITEMNUM` | STRING(25) | → maximo_extract.ITEM.ITEMNUM |
| `FDP_CONFIG_ID` | STRING(40) | |
| `INTOUCH_SPEC_REFS` | ARRAY<STRING> | |

`oilfield_kc.functional_equivalences`:
| `CANONICAL_ID_A` | STRING |
| `CANONICAL_ID_B` | STRING |
| `CONFIDENCE` | FLOAT64 |
| `RATIONALE_SOURCE` | STRING |
| `CUSTOMER_OVERRIDES` | JSON |

### ~~`oilfield_kc.start_date_variance`~~ — moved to `maximo_extract.WO_HISTORY`

Per Q7 resolution (2026-05-20), start-date variance is derived from `maximo_extract.WORKORDER` via the `WO_HISTORY` view defined earlier in §3. There is no separate `oilfield_kc.start_date_variance` table — the customer doesn't have to bring one. The view definition is portable: their Maximo extract has the same `WORKORDER` columns, and the variance computation works as-is.

---

## 4. MCP server tool contracts (post-migration)

Three custom Cloud Run MCP servers (SAP, Maximo, FDP) + one managed (Knowledge Catalog). All four registered with Agent Registry, traffic flows through Agent Gateway with per-tool IAM and Model Armor.

**Why all three custom (and not BigQuery MCP for SAP+Maximo):** The typed tool surface (`sap.get_material_master`, `maximo.query_assets_by_region`) is the substitutability contract. A customer with on-prem SAP via OData forks our SAP MCP, swaps the BQ query inside for an OData call, and the *tool surface the agents see stays identical*. Generic `execute_sql_readonly` would couple the agents to BigQuery as the source of truth — bad for OFS majors who'll have on-prem ECC + Maximo for years. The custom MCP servers query BQ in our reference v1; in customer production they query whatever the customer has (live OData, REST API, BigQuery Omni, etc.).

Tool names follow what an enterprise integrator would naturally pick — `sap.<verb>_<entity>(...)`, `maximo.<verb>_<entity>(...)`. Transport: StreamableHTTP through Agent Gateway (TASK-05 pattern).

### SAP MCP server (`mcp_servers/sap`)

| Tool name | Args | BQ query (substantively) | Return |
|---|---|---|---|
| `sap.get_material_master(matnr)` | `matnr: str` | `SELECT m.MATNR, t.MAKTX, m.MTART, m.MATKL FROM sap_extract.MARA m JOIN sap_extract.MAKT t USING (MANDT, MATNR) WHERE m.MATNR = @matnr AND t.SPRAS = 'E'` | `SapMaterialMaster` Pydantic |
| `sap.get_plant_data(matnr, werks?)` | `matnr, werks (opt)` | `SELECT * FROM sap_extract.MARC WHERE MATNR=@matnr AND (@werks IS NULL OR WERKS=@werks)` | `list[SapPlantData]` |
| `sap.get_storage_location_stock(matnr)` | `matnr` | `SELECT MATNR, WERKS, LGORT, LABST FROM sap_extract.MARD WHERE MATNR=@matnr AND LABST > 0` | `list[SapStorageStock]` — replaces "is there inventory" |
| `sap.get_standard_price(matnr)` | `matnr` | `SELECT STPRS, PEINH, WAERS FROM sap_extract.MBEW WHERE MATNR=@matnr LIMIT 1` | `SapStandardPrice` |
| `sap.get_customer(kunnr)` | `kunnr` | `SELECT * FROM sap_extract.KNA1 WHERE KUNNR=@kunnr` | `SapCustomer` |
| `sap.resolve_customer_by_name(needle)` | `needle: str` | `SELECT KUNNR, NAME1 FROM sap_extract.KNA1 WHERE LOWER(NAME1) LIKE LOWER(CONCAT('%', @needle, '%'))` | `list[SapCustomer]` — replaces `normalize_customer_id` |
| `sap.get_workforce_by_basin(basin)` | `basin` | `SELECT * FROM sap_extract.ZHR_WORKFORCE WHERE BASIN=@basin ORDER BY SNAPSHOT_DATE DESC LIMIT 1` | `SapWorkforce` |

Backwards-compat: keep the legacy endpoints (`POST /sap/workforce/by_basin`, `GET /sap/material/{matnr}`) for one release as thin wrappers, then retire. Skill tools should call the new names from day one.

### Maximo MCP server (`mcp_servers/maximo`)

| Tool name | Args | BQ query | Return |
|---|---|---|---|
| `maximo.get_item(itemnum)` | `itemnum` | `SELECT * FROM maximo_extract.ITEM WHERE ITEMNUM=@itemnum` | `MaximoItem` |
| `maximo.query_assets_by_item(itemnum, status?, siteid?)` | filters | `SELECT a.*, l.LATITUDE, l.LONGITUDE, l.DESCRIPTION AS location_label, l.REGION FROM maximo_extract.ASSET a JOIN maximo_extract.LOCATIONS l USING (SITEID, LOCATION) WHERE a.ITEMNUM=@itemnum AND (@status IS NULL OR a.STATUS=@status) AND (@siteid IS NULL OR a.SITEID=@siteid)` | `list[MaximoAssetWithLocation]` |
| `maximo.get_inventory_balances(itemnum, siteid?)` | filters | `SELECT * FROM maximo_extract.INVBALANCES WHERE ITEMNUM=@itemnum AND (@siteid IS NULL OR SITEID=@siteid)` | `list[InvBalance]` — bin-level stock (Q2: separate from ASSET) |
| `maximo.get_location(siteid, location)` | keys | `SELECT * FROM maximo_extract.LOCATIONS WHERE SITEID=@siteid AND LOCATION=@location` | `MaximoLocation` |
| `maximo.get_open_workorders(assetnum, siteid)` | keys | `SELECT * FROM maximo_extract.WORKORDER WHERE ASSETNUM=@assetnum AND SITEID=@siteid AND STATUS != 'COMP'` | `list[MaximoWorkOrder]` |
| `maximo.query_assets_by_region(itemnum, region)` | convenience | joins LOCATIONS on REGION | `list[MaximoAssetWithLocation]` |
| `maximo.get_start_date_distribution(basin, customer_id?, asset_class?)` | filters | `SELECT APPROX_QUANTILES(variance_days, 100)[OFFSET(10/50/90)] FROM maximo_extract.WO_HISTORY WHERE REGION=@basin AND ...` | `StartDateDistribution` (queries WO_HISTORY view per Q7) |

`query_assets_by_region` is the substitution for the current `query_maximo_availability(canonical_id, region_filter)`. The shift is: skill calls Maximo by **Maximo's natural keys** (ITEMNUM, SITEID, REGION). The canonical-id translation happens upstream in the Catalog/MCP layer, not inside Maximo's tool surface.

`get_start_date_distribution` is intentionally on the Maximo MCP (not a separate skill-side BQ client) — variance comes from WO completion data, which is Maximo-domain. This makes the substitution story clean: customer with live Maximo writes the OData equivalent of the WO_HISTORY query, no separate plumbing.

### FDP MCP server (`mcp_servers/fdp`)

| Tool name | Args | BQ query | Return |
|---|---|---|---|
| `fdp.get_customer_config(customer_id, matnr)` | keys | `SELECT * FROM fdp_extract.CUSTOMER_CONFIG WHERE CUSTOMER_ID=@cid AND MATNR=@matnr` | `FdpCustomerConfig` |
| `fdp.list_approved_substitutions(customer_id, matnr_original)` | keys | `SELECT MATNR_SUBSTITUTE, ACCEPTED FROM fdp_extract.APPROVED_SUBSTITUTIONS WHERE CUSTOMER_ID=@cid AND MATNR_ORIGINAL=@matnr` | `list[FdpSubstitution]` |
| `fdp.list_customer_restrictions(customer_id)` | `cid` | derived view over `APPROVED_SUBSTITUTIONS WHERE ACCEPTED=FALSE` | `list[Restriction]` |

### Knowledge Catalog MCP (platform-provided, see TASK-06)

These are unchanged — TASK-06 already wires them. Skill tools call:
- `kc.lookup_context(entry_name)` to fetch a canonical entry + aspects
- `kc.search_entries(...)` to find by category / subcategory / property

### New Pydantic response schemas (additive to `agents/schemas.py`)

Per the constraint not to break existing wire formats, **add** new schemas; don't modify existing ones. Add a new section to `agents/schemas.py`:

```python
class SapMaterialMaster(BaseModel):
    matnr: str
    description: str | None
    material_type: str
    material_group: str
    base_uom: str = "EA"

class SapPlantData(BaseModel):
    matnr: str
    werks: str
    mrp_controller: str | None
    mrp_type: str | None

class SapStorageStock(BaseModel):
    matnr: str
    werks: str
    lgort: str
    unrestricted_stock: float

class SapStandardPrice(BaseModel):
    matnr: str
    stprs: float
    peinh: int
    waers: str = "USD"

class SapWorkforce(BaseModel):
    basin: str
    crew_count_available: int
    specialist_count_available: int
    on_call_count: int
    snapshot_date: date

class MaximoLocation(BaseModel):
    siteid: str
    location: str
    description: str | None
    latitude: float | None
    longitude: float | None
    region: str | None

class MaximoAssetWithLocation(BaseModel):
    assetnum: str
    itemnum: str
    status: str
    siteid: str
    location: MaximoLocation
    description: str | None
    serialnum: str | None

class MaximoWorkOrder(BaseModel):
    wonum: str
    assetnum: str
    status: str
    worktype: str
    est_lab_hrs: float | None

class FdpCustomerConfig(BaseModel):
    customer_id: str
    matnr: str
    approved: bool
    notes: str | None
```

`agents/schemas.py` currently uses string ids for everything (see CLAUDE.md gotcha) — these models follow that convention.

---

## 5. Skill-tool migration table

Every existing tool function and its post-migration call path. "Real-SAP/Maximo-expressible" means the new call is something a customer with their actual systems can reproduce — that's the substitutability test.

Every existing tool function and its post-migration call path. "Real-SAP/Maximo-expressible" means the new call is something a customer with their actual systems can reproduce — that's the substitutability test.

| Skill | Tool | Current behavior | Post-migration | SAP/Maximo-expressible? | Notes |
|---|---|---|---|---|---|
| asset-equivalence | `resolve_canonical_asset(local_identifier, source_system?)` | reads `cross_system_aliases.json` + `canonical_assets.json` | `kc.lookup_context()` first, then `kc.search_entries()` substring match. | Yes — customer populates KC from their own MARA + Maximo ITEM extracts. | substring-on-label kept; "Tool X" → `TX-001` still works |
| asset-equivalence | `find_functional_equivalents(canonical_id)` | reads `functional_equivalences.json` | `kc.list_related_entries(canonical_id, relation_type='functionally_equivalent')` (KC MCP). | Yes — engineering content, customer brings their InTouch equivalence table. | |
| asset-equivalence | `score_equivalence_confidence(src, sub, customer_id)` | reads `functional_equivalences.json` + `customers.json` | `find_functional_equivalents` + `fdp.list_customer_restrictions(customer_id)` (FDP MCP). 0.3 penalty stays as policy code. | Yes — customer restrictions are an FDP-equivalent extract. | |
| enterprise-systems | `query_maximo_availability(canonical_id, region_filter?)` | reads `maximo_inventory.json` | (1) resolve `canonical_id` → `itemnum` via `kc.lookup_context()`. (2) `maximo.query_assets_by_region(itemnum, region)`. Returns `list[MaximoAssetWithLocation]`. `certification_hours_remaining` stays on the response (extract-layer view). | Yes — `canonical_id` is *our* construct; in production the agent reasons on KC entry name, which the platform maps to ITEMNUM. | Shape changes: `location.label` becomes `description`. `equivalence_lookup` prompt + Pydantic refs get edited. |
| enterprise-systems | `query_sap_workforce(basin)` | reads `sap_workforce.json` | `sap.get_workforce_by_basin(basin)` | Yes — though no standard SAP table; we model as ZHR_WORKFORCE custom table. | flagged: **synthesized-signature-not-from-real-systems**. Customer maps to their HR view. |
| enterprise-systems | `query_fdp_customer_config(customer_id, canonical_id)` | reads `fdp_configurations.json` | (1) resolve `canonical_id` → `matnr` via KC. (2) `fdp.get_customer_config(customer_id_normalized, matnr)` + `fdp.list_approved_substitutions(...)`. Customer-name normalization calls `sap.resolve_customer_by_name`. | Yes — FDP is the homegrown system; customer provides an equivalent extract. | the brittle `v7_substitution_accepted` boolean explodes into rows in `APPROVED_SUBSTITUTIONS` |
| enterprise-systems | `query_intouch_specs(canonical_id)` | reads `intouch_index.json` | `kc.search_entries(applies_to=canonical_id, entry_type='intouch_spec')`. | Yes — InTouch is internal docs, customer provides their own KC entries. | |
| sourcing-logistics | `estimate_transit(...)` | pure haversine + thresholds | unchanged. Maps Grounding (TASK #46) already wired. | n/a — pure compute | |
| sourcing-logistics | `calculate_sourcing_cost(...)` | pure | unchanged. Optional enrich: `sap.get_standard_price(matnr)` for charter base rate. | n/a | |
| sourcing-logistics | `identify_blockers(canonical_id_sub, customer_id, source_equipment_instance_id?)` | reads `customers.json` + `maximo_inventory.json` | (1) `fdp.list_customer_restrictions(customer_id)`. (2) If `equipment_instance_id` present, `maximo.query_assets_by_item(itemnum, ...)` + `maximo.get_open_workorders(assetnum, siteid)`. | Yes | `workforce_attached` flagged **synthesized-signature**; in production derived from `MAXIMO.LABTRANS`. |
| procurement-prerequisites | `check_budget_threshold(plan_json, tier)` | pure | unchanged. Optional enrich: `sap.get_standard_price(matnr) * qty` to guard against LLM hallucinating cost. | n/a | |
| procurement-prerequisites | `check_certification_chain(plan_json)` | pure | optional enrich: pull spec refs from `kc.lookup_context()`. | Yes (when enriched) | |
| procurement-prerequisites | `check_regulatory_clearance(plan_json)` | pure | unchanged (deny-list policy code, no system of record). | n/a | the deny-list (`iran`/`russia`) stays in code — it's policy, not data |
| forecast-rationale | `extract_rationale_tags(text)` | pure keyword scan | unchanged for TASK-16. | n/a | |
| forecast-rationale | `compute_override_significance(orig, override, vol)` | pure | unchanged. Optionally compute `historical_volatility_pct` from `eia_steo.basin_production` rolling stddev. | Public-data-grounded | |
| scheduling-probability | `get_start_date_distribution(basin, customer_id?, asset_class?)` | reads `start_date_variance/{basin}.json` | `maximo.get_start_date_distribution(basin, customer_id?, asset_class?)` — queries `maximo_extract.WO_HISTORY` view (Q7) with `APPROX_QUANTILES(variance_days, 100)[OFFSET(10/50/90)]`. | Yes — variance computed from the customer's own Maximo WO completion history. | Q7 resolution: variance lives on the Maximo MCP, not as a separate skill-side BQ client. |
| scheduling-probability | `compute_optimal_buffer(p10, p50, p90, risk)` | pure | unchanged | n/a | |
| scheduling-probability | `compute_fleet_utilization_impact(basin, rec, current)` | pure | unchanged. Optional enrich: `bakerhughes_rig_count.weekly_basin` for actual rig activity. | Public-data-grounded option | |

**Signatures that can't be expressed in real-SAP/Maximo terms** (must be flagged in code as `# SYNTHESIZED SIGNATURE: not from real systems`):

1. `query_sap_workforce(basin)` — no standard SAP table for workforce-by-basin. Real customers will map to their HR view (e.g. `PA0001` org assignment joined to a Z-basin mapping). We model as `ZHR_WORKFORCE` custom Z-table — visible in the demo as "this is the customer's HR view, here in our reference solution it's synthesized."
2. `MaximoAsset.workforce_attached: bool` — Maximo doesn't have a single boolean for this; it's derived from `LABTRANS` (labor transactions) joined to current work orders. We collapse to a bool for skill compatibility but document the derivation.
_(removed 2026-05-20)_ `MaximoAsset.certification_hours_remaining` was previously listed here as a synthesized signature. **It is not synthesized in v1** — it stays on the response shape, derived at extract/view time from `MAX(ESTLABHRS - ACTLABHRS)` over open RECERT WOs joined to ASSET. Real-world Maximo ETL routinely materializes derived fields like this at the extract layer; "data massaging" pre-load is not uncommon. Do not flag as `# SYNTHESIZED` in code.

---

## 6. Public-dataset loader plan

Three Python scripts under `scripts/`, each idempotent, all written to BQ via `google-cloud-bigquery`. Refresh cadence noted; for v1 they're one-shot, but each has a Cloud Scheduler hook stub for Phase 2.

**Baker Hughes Rig Count** (`scripts/load_bakerhughes.py`)
- Source: `https://rigcount.bakerhughes.com/static-files/<latest>.xlsx` — the "North America Rotary Rig Count Pivot Table" Excel file. Released Friday noon Central US, weekly.
- Process: download Excel, sheet "NA Rotary Rig Count Pivot Table", filter to country=USA, then load to `bakerhughes_rig_count.weekly_basin`.
- Refresh: weekly (Phase 2 — Cloud Scheduler Friday 14:00 CT).
- License: Baker Hughes makes the data "free to download" but attribution required ("Source: Baker Hughes Rig Count"). Include attribution in `docs/architecture.md` and in any UI surface that shows the data.

**World Port Index** (`scripts/load_worldport_index.py`)
- Source: `https://msi.nga.mil/api/publications/download?key=...&type=download` for `UpdatedPub150.csv`. NGA, US Govt — public domain.
- Process: download CSV, project to the ~25-column subset, load to `worldport_index.ports`.
- Refresh: monthly (NGA update cadence).
- License: US Government work, public domain. No attribution required but good practice.

**EIA Drilling Productivity Report** (`scripts/load_eia_steo.py`)
- Source: `https://www.eia.gov/petroleum/drilling/xls/dpr-data.xlsx`. EIA — US Govt public domain.
- Process: download Excel, parse the "Region production" sheet (one per basin), unpivot into long format, load to `eia_steo.basin_production`.
- Note: EIA retired the dedicated DPR portal in 2024 and rolled the data into STEO. Loader should fall back to STEO endpoints if `dpr-data.xlsx` 404s.
- Refresh: monthly.

Each loader writes a row to a `meta.dataset_loads` audit table on success: `{dataset, source_url, row_count, load_started_at, load_completed_at}`. That row is what the demo references when narrating "this is real Baker Hughes data, refreshed weekly."

---

## 7. Step-by-step rollout

Each step is a confirmation point per CLAUDE.md cadence. After each, summarize what changed and wait.

### Step 1 — Create BigQuery datasets

Deliverable: 7 datasets in `vertex-ai-demos-468803`, region `us-central1`: `sap_extract`, `maximo_extract`, `fdp_extract`, `bakerhughes_rig_count`, `worldport_index`, `eia_steo`, `oilfield_kc`.

Verification: `bq ls --project_id=vertex-ai-demos-468803` shows all 7.

Done = all datasets created, empty, with description set.

### Step 2 — Author DDL files + run table creation

Deliverable: `scripts/bq/ddl/sap_extract.sql`, `scripts/bq/ddl/maximo_extract.sql`, `scripts/bq/ddl/fdp_extract.sql`, `scripts/bq/ddl/oilfield_kc.sql`, `scripts/bq/ddl/public_datasets.sql`. One `make bq-create-tables` target.

Verification: `bq show vertex-ai-demos-468803:sap_extract.MARA` returns the schema.

Done = all tables created, partitioning + clustering set per §3.

### Step 3 — Write the JSON-to-BQ seeder

Deliverable: `scripts/seed_bq_from_json.py` that reads every file under `data/` and writes to the corresponding BQ table per the mapping in §3. Idempotent (truncate + insert).

Verification: `bq query "SELECT COUNT(*) FROM sap_extract.MARA"` returns 30 (matches `canonical_assets.json` length); `bq query "SELECT COUNT(*) FROM maximo_extract.ASSET"` returns 11 (matches `maximo_inventory.json`).

Done = every JSON file under `data/` (excluding `intouch_docs/` and `start_date_variance/`) has loaded a corresponding BQ table with row count matching JSON length.

### Step 4 — Public-dataset loaders

Three sub-steps (separate confirmations because each touches an external service):

- 4a. `scripts/load_bakerhughes.py` — download the Excel, write `bakerhughes_rig_count.weekly_basin`. Verify with `bq query "SELECT BASIN, MAX(WEEK_ENDING_DATE) FROM bakerhughes_rig_count.weekly_basin GROUP BY BASIN"`.
- 4b. `scripts/load_worldport_index.py` — download the CSV, write `worldport_index.ports`. Verify with `bq query "SELECT MAIN_PORT_NAME, LATITUDE, LONGITUDE FROM worldport_index.ports WHERE MAIN_PORT_NAME LIKE '%LAGOS%'"`.
- 4c. `scripts/load_eia_steo.py` — download the Excel, write `eia_steo.basin_production`. Verify with `bq query "SELECT BASIN, MAX(REPORT_MONTH), SUM(OIL_PROD_BPD) FROM eia_steo.basin_production GROUP BY BASIN"`.

Done = each table populated with current production data, attribution noted in `docs/architecture.md`.

### Step 5 — MCP server backend migration: SAP

Deliverable: `mcp_servers/sap/backend/main.py` migrated to query BQ via `google-cloud-bigquery`. Add new typed endpoints per §4 (`sap.get_material_master`, `sap.get_plant_data`, `sap.get_storage_location_stock`, `sap.get_standard_price`, `sap.get_customer`, `sap.resolve_customer_by_name`, `sap.get_workforce_by_basin`). Legacy `POST /sap/workforce/by_basin` + `GET /sap/material/{matnr}` kept as thin wrappers. Add `BQ_PROJECT` and `BQ_DATASET_SAP` env vars (defaults `vertex-ai-demos-468803`, `sap_extract`).

Verification: run locally — `curl http://localhost:8080/sap/v2/material_master/MAT-67890` returns the new `SapMaterialMaster` shape; legacy `GET /sap/material/MAT-67890` returns the old shape. Integration: cargo-plane scenario integration test passes against the BQ-backed local SAP MCP.

Done = local SAP MCP container against BQ passes existing `tests/integration/test_sap_mcp.py` (TASK-05) plus new endpoint tests.

### Step 6 — MCP server backend migration: Maximo

Same drill for Maximo. New typed endpoints per §4 (including `maximo.get_inventory_balances` per Q2 and `maximo.get_start_date_distribution` querying the `WO_HISTORY` view per Q7). Legacy `POST /maximo/availability` kept as a thin wrapper. Add `BQ_DATASET_MAXIMO` env var.

Verification: cargo-plane scenario integration test passes against the local Maximo MCP backend pointed at BQ. Quantile call returns p10/p50/p90 within ±2 days of the previous JSON-backed values (seeder's lognormal reverse-engineering tolerance).

### Step 7 — MCP server backend migration: FDP

Same. Add `BQ_DATASET_FDP` env var. Legacy `POST /fdp/customer_config` kept as thin wrapper. New typed endpoints per §4.

Verification: `curl http://localhost:8080/fdp/v2/customer_config?customer_id=gulf-petroleum&matnr=MAT-67890` returns the `FdpCustomerConfig` shape.

### Step 8 — Skill tool migration: asset-equivalence

Deliverable: `agents/orchestrator_agent/skills/asset-equivalence/scripts/tools.py` updated. `resolve_canonical_asset` calls KC MCP first, falls back to BQ MCP `execute_sql_readonly` against `oilfield_kc.cross_system_aliases` for the substring-on-label case (the LLM's "Tool X" lookup path). `find_functional_equivalents` and `score_equivalence_confidence` go through KC MCP + FDP MCP. Remove the `agents.utils.synthetic_data` imports.

Verification: `pytest agents/tests/unit/test_skills.py::test_resolve_canonical_asset*` passes against mocked KC + BQ MCP clients. Integration: cargo-plane scenario locally still resolves "Tool X" → `TX-001`.

Done = no `load_canonical_assets()` / `load_cross_system_aliases()` calls remaining in the asset-equivalence skill.

### Step 9 — Skill tool migration: enterprise-systems

Deliverable: `agents/orchestrator_agent/skills/enterprise-systems/scripts/tools.py` updated per §5. The query functions now wrap BQ MCP `execute_sql_readonly` (for SAP + Maximo) and FDP MCP (for FDP) calls. New typed wrappers `get_workforce_by_basin`, `query_assets_by_region`, `resolve_customer_by_name` per §4. Helper `_resolve_matnr_from_canonical(canonical_id) -> str` calls KC MCP.

Verification: `pytest agents/tests/unit/test_skills.py::test_query_*` passes. Integration: cargo-plane scenario shows the agent receiving `MaximoAssetWithLocation` shape.

Concurrent edit: `equivalence_lookup` prompt + downstream Pydantic field refs migrate from `label` to `description` (Q8 resolved). Search-and-replace across `agents/orchestrator_agent/nodes/equivalence_lookup.py` and any node that reads `location.label`.

Done = no `data/*.json` reads in `enterprise-systems/scripts/tools.py`.

### Step 10 — Skill tool migration: sourcing-logistics

Deliverable: `identify_blockers` migrated per §5 — replaces `load_maximo_inventory()` and `get_customer()` with FDP MCP + BQ MCP wrapper calls. `estimate_transit` and `calculate_sourcing_cost` unchanged.

Verification: unit tests pass.

### Step 11 — Skill tool migration: scheduling-probability

Deliverable: `get_start_date_distribution` migrated to a typed BQ MCP wrapper that runs `APPROX_QUANTILES(variance_days, 100)[OFFSET(10/50/90)]` against `maximo_extract.WO_HISTORY` (the view from §3, Q7 resolution).

Verification: `pytest agents/tests/unit/test_skills.py::test_get_start_date_distribution*` passes; quantiles match the previous JSON-backed outputs within ±2 days (the lognormal reverse-engineering from the seeder introduces controlled variance).

### Step 12 — KC population

Deliverable: re-run `knowledge_catalog/setup.py` so Catalog Entries reference `oilfield_kc.canonical_assets` content. Existing Aspect Type schemas in `knowledge_catalog/aspect_types/*.yaml` unchanged. New `relationships` registration for `functionally_equivalent` if not already present (TASK-06).

Verification: KC MCP `lookup_context('TX-001')` returns canonical entry + asset_specification aspect + cross_system_aliases aspect + relationships to TX-007.

### Step 13 — End-to-end smoke

Deliverable: re-run `make demo-cargo-plane` against the new BQ-backed MCP stack. Verify in Cloud Trace that:
1. No skill tool reads `data/*.json` at runtime.
2. SAP MCP shows BQ jobs in its trace.
3. Maximo MCP shows BQ jobs (including the `WO_HISTORY` view for `get_start_date_distribution`).
4. FDP MCP shows BQ jobs.
5. KC MCP returns canonical entries with all aliases.
6. The output `SourcingPlan` is structurally identical to pre-migration (primary_option is Lagos, avoided_cost ~$380k).

Verification command: `make demo-cargo-plane && python scripts/verify_no_json_reads.py` (a static grep over skill tools that fails if any of them imports from `agents.utils.synthetic_data`).

Done = cargo-plane scenario completes end-to-end with all four MCP servers visibly hitting BQ.

### Step 14 — Documentation

Deliverable: `docs/architecture.md` updated with §2's architecture diagram. New `docs/data_layer.md` documenting per-table provenance (the §3 content, cleaned up). Update `mcp_servers/{sap,maximo,fdp}/README.md` with new env vars + endpoint surface.

### Step 15 — Commit

`feat: backend migration — BQ extracts mirroring SAP+Maximo, 3 MCP servers BQ-backed, public datasets loaded (TASK-16)`

---

## 8. What stays synthesized + why

Five categories can't be grounded in public data; they remain synthesized but with shapes mirroring what an OFS major would have:

1. **Customer-restriction matrices (`fdp_extract.APPROVED_SUBSTITUTIONS`)** — these are highly confidential CRM/contract data. No public source. The *shape* matches what a customer's FDP equivalent extract would look like (per-customer, per-MATNR, with a substitute and an accepted flag). Customer plugs in their data; demo works.

2. **Functional-equivalence graph (`oilfield_kc.functional_equivalences`)** — engineering content owned in InTouch / spec repositories. No public source. The shape matches: pairs of canonical IDs with confidence and a source citation. This is the core IP of the customer's operations team.

3. **InTouch document index (KC entries referencing internal docs)** — internal technical documentation, no public source. Shape matches.

4. **Workforce-by-basin (`sap_extract.ZHR_WORKFORCE`)** — not a standard SAP table. Every customer rolls their own Z-table or CDS view. The shape we model is the lowest-common-denominator (basin, three counts, snapshot date) that any customer can derive from their HR data.

5. **Start-date variance history (`oilfield_kc.start_date_variance`)** — customer's own operational history. No public source. Shape matches what a BQ analyst would produce from work-order completion data.

For each of these, the demo narration says: *"This table is shape-faithful to what you'd extract from your <system>. We've populated it with industry-credible synthetic data because the real data is yours."*

What we deliberately did **not** synthesize when reality was the shape-wrong choice:
- **Port locations** — we use WPI's real coordinates. The 50km Lagos→Luanda transit math in the cargo-plane scenario is now defensible against a map.
- **Basin rig counts** — Baker Hughes' real weekly numbers go in `bakerhughes_rig_count`. The Forecast Review Agent's "rig count decline" narrative becomes verifiable.
- **Basin production trends** — EIA DPR's real monthly numbers. Same defensibility argument.

---

## 9. Open questions for the user

1. ~~**MATNR width — 18 or 40?**~~ **RESOLVED 2026-05-20: 40 char (S/4 future-proof).** All DDL in §3 reflects `STRING(40)`. Stub IDs (`MAT-67890`, etc.) remain valid.

2. ~~**Maximo INVBALANCES vs INVENTORY-level stock?**~~ **RESOLVED 2026-05-20: Both — separate tools.** `maximo.query_assets_by_region(itemnum, region)` returns ASSET rows (specific instances — used by the cargo-plane scenario). New tool `maximo.get_inventory_balances(itemnum, siteid)` returns INVBALANCES rows (bin-level stock counts — used by procurement-style queries). Faithful to real Maximo where both tables exist and serve different questions. §4 Maximo MCP tool surface updated.

3. ~~**Workforce table — Z-table vs CDS view?**~~ **RESOLVED 2026-05-20: Z-table (`ZHR_WORKFORCE`).** Lowest common denominator — ECC + S/4 + RISE customers all understand Z-tables. No CDS view DDL ships in v1.

4. ~~**EIA DPR availability post-2024.**~~ **RESOLVED 2026-05-20: STEO-only from day one.** Skip the legacy DPR Excel URL entirely. Loader (`scripts/load_eia_steo.py`) parses STEO's monthly basin production data and reshapes to match our `eia_steo.basin_production` DDL (dataset renamed from `eia_dpr`). More durable. §3, §4, §7-Step 4c references updated accordingly.

5. ~~**`certification_hours_remaining` — keep on response shape?**~~ **RESOLVED 2026-05-20: Keep, don't flag as synthesized.** Customer is expected to materialize this via a SQL view at extract time (`MAX(ESTLABHRS - ACTLABHRS)` over open RECERT WOs joined to ASSET) — common pre-load denormalization. The §5 entry marking this `# SYNTHESIZED SIGNATURE` is removed.

6. ~~**FDP MCP server — keep it at all?**~~ **RESOLVED 2026-05-20: Keep.** FDP is the only custom Cloud Run MCP server in this plan. Demonstrates the wrapping pattern customers will need for any non-BQ system.

7. ~~**Where do `start_date_variance` rows logically belong?**~~ **RESOLVED 2026-05-20: `maximo_extract.WO_HISTORY` (derived view).** Stronger substitutability — customer doesn't bring a separate table; the view computes over their existing Maximo WORKORDER dump. §3 includes the view definition; §7 Step 10 wires it.

8. ~~**Skill prompts edit budget.**~~ **RESOLVED 2026-05-20: Edit the prompt + downstream Pydantic refs to use `description`** (real Maximo column). No legacy-key shim. Step 9 includes the prompt edit.

9. ~~**MCP architecture — Cloud Run for all 3, BigQuery MCP only, or hybrid?**~~ **RESOLVED 2026-05-20 (reversed from earlier hybrid decision): All 3 custom Cloud Run MCP servers (SAP, Maximo, FDP).** Reasoning: the typed tool surface (`sap.get_material_master`, `maximo.query_assets_by_region`) is the substitutability contract. A customer can fork our MCP server and swap the BQ query for a live OData/REST call — the tool surface stays identical, no agent changes. With managed BigQuery MCP the agent's tool becomes `execute_sql_readonly` and the agents are coupled to BQ as the source of truth permanently. Also enables per-tool IAM in Agent Gateway. §4 has typed tool tables for all 3 servers; §7 Steps 5-7 are the 3 MCP server migrations.

---

## Critical Files for Implementation

- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/mcp_servers/sap/backend/main.py
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/mcp_servers/maximo/backend/main.py
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/mcp_servers/fdp/backend/main.py
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/agents/orchestrator_agent/skills/enterprise-systems/scripts/tools.py
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/agents/orchestrator_agent/skills/asset-equivalence/scripts/tools.py
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/agents/utils/synthetic_data.py (the import surface to retire from production code paths; stays for tests)
- /Users/rahulkasanagottu/Desktop/agentic-sop-oilfield-services/agents/schemas.py (additive new schemas)

---

# Summary back to you

**Note on file output:** I'm in read-only planning mode and cannot write `tasks/TASK-16-backend-migration.md` — the full spec is above for you to paste in.

(1) **Task number picked: TASK-16.** Tasks 01–15 are all occupied (`TASK-12-demo-runner.md` already exists). TASK-16 is the next free slot.

(2) **3-bullet executive summary:**
- BigQuery becomes the source of truth with seven datasets (`sap_extract`, `maximo_extract`, `fdp_extract`, plus three public-data datasets and `oilfield_kc`); SAP and Maximo tables mirror their real source-system schemas (MARA/MARC/MARD/MBEW/KNA1 + ASSET/INVENTORY/INVBALANCES/LOCATIONS/WORKORDER) column-for-column so a customer's ETL person recognizes them.
- The three MCP server backends (`mcp_servers/{sap,maximo,fdp}/backend/main.py`) get repointed from JSON-file reads to BQ queries, gaining a richer tool surface (`sap.get_material_master`, `maximo.query_assets_by_region`, etc.) while keeping the legacy endpoints as thin wrappers so the cargo-plane integration test stays green.
- Skill tools migrate one at a time (asset-equivalence → enterprise-systems → sourcing-logistics → scheduling-probability), each removing its `agents.utils.synthetic_data` imports and routing through MCP or BQ; the final smoke test re-runs `make demo-cargo-plane` and a static check (`verify_no_json_reads.py`) proves no production code path reads JSON.

(3) **Top 3 open questions I flagged:**
- (Q1) MATNR width — 18 char (ECC-style) or 40 char (S/4-style)? I picked 18.
- (Q5) Do we drop `certification_hours_remaining` from the migrated Maximo return shape (forcing an extra `get_open_workorders` MCP call, more faithful) or keep the synthetic field?
- (Q8) Are we OK touching the equivalence_lookup prompt to match the new `MaximoAssetWithLocation` field names (`description` vs `label`), or do we need a shim that preserves legacy keys?

(4) **Research findings that conflict with stated assumptions** — three:

- **Maximo INVBALANCES PK includes BINNUM and LOTNUM**, not just (SITEID, ITEMSETID, ITEMNUM, LOCATION). The user's framing ("INVENTORY, INVBALANCES, ASSETLOCATIONS") implied INVBALANCES is a simple item-at-location stock table — actually it's at bin/lot granularity. Doesn't break the plan but I documented the full PK in §3 so the customer's ETL doesn't get surprised.

- **Maximo geometry (lat/lon) moved to a separate table in MAS 9.0.** The user said "ASSETLOCATIONS" for location; reality is `LOCATIONS` (or `LOCATION` depending on Maximo version) holds the location master, and as of MAS 9.0 the Spatial extension moved geometry to a side table. I keep lat/lon inline in `LOCATIONS` for demo simplicity (faithful to <9.0) and document the deviation.

- **EIA DPR portal was retired in mid-2024** and the data was rolled into STEO (Short-Term Energy Outlook). The Excel URL `dpr-data.xlsx` may still work but is on borrowed time. The plan includes a fallback note; this could become a real problem if it 404s mid-demo.

There's also one minor pattern note: real SAP doesn't have a standard "workforce by basin" table — every OFS customer uses an HR Z-table or CDS view. Our `ZHR_WORKFORCE` is shape-faithful to that pattern but flagged as **synthesized-signature** in §5 because there's no MARA-equivalent canonical table to point a customer at.