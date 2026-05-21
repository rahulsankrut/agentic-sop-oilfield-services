-- oilfield_kc — Knowledge Catalog native tables.
--
-- Engineering content the customer brings from their InTouch / spec
-- repository. Three tables — canonical_assets (the asset taxonomy),
-- cross_system_aliases (the SAP↔Maximo↔FDP↔InTouch identifier map),
-- functional_equivalences (the "Tool X ↔ Tool X variant" pairs the
-- equivalence_lookup agent reasons over).
--
-- Per the Q7 resolution, start_date_variance is NOT in this dataset;
-- it's the maximo_extract.WO_HISTORY view (variance lives at source).

CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.oilfield_kc.canonical_assets` (
  CANONICAL_ID                STRING(20)    NOT NULL,
  CANONICAL_LABEL             STRING(60),
  CATEGORY                    STRING(30),
  SUBCATEGORY                 STRING(40),
  OPERATING_TEMP_MAX_C        INT64,
  OPERATING_PRESSURE_MAX_PSI  INT64,
  OUTER_DIAMETER_IN           NUMERIC(5,3),
  MANUFACTURER                STRING(20),
  INTRODUCED_YEAR             INT64,
  _loaded_at                  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CANONICAL_ID) NOT ENFORCED
)
CLUSTER BY CATEGORY, CANONICAL_ID
OPTIONS (description = 'KC native — canonical asset taxonomy (replaces data/canonical_assets.json).');

CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.oilfield_kc.cross_system_aliases` (
  CANONICAL_ID        STRING(20)      NOT NULL,
  SAP_MATNR           STRING(40),
  MAXIMO_ITEMNUM      STRING(25),
  FDP_CONFIG_ID       STRING(40),
  INTOUCH_SPEC_REFS   ARRAY<STRING>,
  _loaded_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CANONICAL_ID) NOT ENFORCED
)
CLUSTER BY SAP_MATNR
OPTIONS (description = 'KC native — cross-system identifier map. Joins SAP/Maximo/FDP/InTouch IDs.');

CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.oilfield_kc.functional_equivalences` (
  CANONICAL_ID_A      STRING(20)  NOT NULL,
  CANONICAL_ID_B      STRING(20)  NOT NULL,
  CONFIDENCE          FLOAT64,
  RATIONALE_SOURCE    STRING,
  CUSTOMER_OVERRIDES  JSON,
  _loaded_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CANONICAL_ID_A, CANONICAL_ID_B) NOT ENFORCED
)
CLUSTER BY CANONICAL_ID_A
OPTIONS (description = 'KC native — functional equivalence pairs with confidence + customer overrides.');
