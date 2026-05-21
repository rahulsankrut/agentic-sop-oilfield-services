-- public_datasets — schemas for the public-dataset loaders.
--
-- Three datasets, one table each. Loaders in scripts/load_bakerhughes.py,
-- scripts/load_worldport_index.py, scripts/load_eia_steo.py populate
-- them. Loading is Step 4 of TASK-16; this file is just the DDL.
--
-- Attribution:
--   bakerhughes_rig_count — Baker Hughes ("Source: Baker Hughes Rig Count").
--   worldport_index       — NGA Pub 150, US Govt public domain.
--   eia_steo              — EIA Short-Term Energy Outlook, US Govt public domain.

-- Baker Hughes weekly rig count by basin (US only for v1).
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.bakerhughes_rig_count.weekly_basin` (
  WEEK_ENDING_DATE  DATE        NOT NULL,
  COUNTRY           STRING(20)  NOT NULL,
  BASIN             STRING(40)  NOT NULL,
  DRILL_FOR         STRING(16),
  TRAJECTORY        STRING(16),
  WELL_TYPE         STRING(16),
  RIG_COUNT         INT64,
  _loaded_at        TIMESTAMP   DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY WEEK_ENDING_DATE
CLUSTER BY COUNTRY, BASIN
OPTIONS (description = 'Baker Hughes weekly rig count by basin. Attribution: "Source: Baker Hughes Rig Count".');

-- NGA World Port Index — 25-column subset of UpdatedPub150.csv.
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.worldport_index.ports` (
  WORLD_PORT_INDEX_NUMBER  INT64         NOT NULL,
  MAIN_PORT_NAME           STRING(80),
  UN_LOCODE                STRING(10),
  COUNTRY_CODE             STRING(3),
  LATITUDE                 NUMERIC(9,6),
  LONGITUDE                NUMERIC(9,6),
  HARBOR_TYPE              STRING(20),
  HARBOR_SIZE              STRING(10),
  OCEAN_BASIN              STRING(20),
  MAX_VESSEL_LENGTH_M      NUMERIC(7,2),
  MAX_VESSEL_DRAFT_M       NUMERIC(5,2),
  _loaded_at               TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (WORLD_PORT_INDEX_NUMBER) NOT ENFORCED
)
CLUSTER BY COUNTRY_CODE, OCEAN_BASIN
OPTIONS (description = 'NGA Pub 150 World Port Index subset. US Govt public domain.');

-- Audit table records the meta data for each loader run.
-- Referenced by demo narration ("this is real Baker Hughes data, refreshed weekly").
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.bakerhughes_rig_count.dataset_loads` (
  dataset            STRING NOT NULL,
  source_url         STRING,
  row_count          INT64,
  load_started_at    TIMESTAMP,
  load_completed_at  TIMESTAMP
)
OPTIONS (description = 'Loader audit table (shared across the public-dataset loaders).');

-- EIA STEO basin production (oil/gas + rig productivity).
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.eia_steo.basin_production` (
  REPORT_MONTH                       DATE        NOT NULL,
  BASIN                              STRING(20)  NOT NULL,
  OIL_PROD_BPD                       INT64,
  GAS_PROD_MCFD                      INT64,
  RIG_PRODUCTIVITY_NEW_WELL_OIL_BPD  INT64,
  _loaded_at                         TIMESTAMP   DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY REPORT_MONTH
CLUSTER BY BASIN
OPTIONS (description = 'EIA Short-Term Energy Outlook — monthly basin production. US Govt public domain.');
