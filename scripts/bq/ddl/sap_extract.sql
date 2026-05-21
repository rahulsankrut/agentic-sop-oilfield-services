-- sap_extract — SAP S/4HANA extract mirror.
--
-- Tables mirror real SAP table layouts (MARA / MAKT / MARC / MARD / MBEW /
-- KNA1 / KNVV) with original SAP column names and types. ZHR_WORKFORCE is
-- a Z-table for the workforce-by-basin extract pattern every OFS major has
-- — there's no standard SAP table for it (per §9 Q3 resolution).
--
-- Provenance per column is documented in tasks/TASK-16-backend-migration.md
-- §3. MATNR is STRING(40) per the §9 Q1 resolution (S/4-future-proof).
--
-- Project: vertex-ai-demos-468803, Region: us-central1.

-- General Material Data
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.MARA` (
  MANDT      STRING(3)    NOT NULL,
  MATNR      STRING(40)   NOT NULL,
  ERSDA      DATE,
  ERNAM      STRING(12),
  LAEDA      DATE,
  AENAM      STRING(12),
  MTART      STRING(4),
  MBRSH      STRING(1),
  MATKL      STRING(9),
  MEINS      STRING(3),
  BISMT      STRING(40),
  LVORM      BOOL,
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, MATNR) NOT ENFORCED
)
PARTITION BY ERSDA
CLUSTER BY MATNR
OPTIONS (description = 'SAP MARA — General Material Data. Mirror of real SAP table.');

-- Material Description (text table)
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.MAKT` (
  MANDT      STRING(3)    NOT NULL,
  MATNR      STRING(40)   NOT NULL,
  SPRAS      STRING(1)    NOT NULL,
  MAKTX      STRING(40),
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, MATNR, SPRAS) NOT ENFORCED
)
CLUSTER BY MATNR
OPTIONS (description = 'SAP MAKT — Material Description (text per language).');

-- Plant Data for Material
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.MARC` (
  MANDT      STRING(3)    NOT NULL,
  MATNR      STRING(40)   NOT NULL,
  WERKS      STRING(4)    NOT NULL,
  DISPO      STRING(3),
  DISMM      STRING(2),
  BESKZ      STRING(1),
  LVORM      BOOL,
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, MATNR, WERKS) NOT ENFORCED
)
CLUSTER BY MATNR, WERKS
OPTIONS (description = 'SAP MARC — Plant Data for Material.');

-- Storage Location Stock
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.MARD` (
  MANDT      STRING(3)    NOT NULL,
  MATNR      STRING(40)   NOT NULL,
  WERKS      STRING(4)    NOT NULL,
  LGORT      STRING(4)    NOT NULL,
  LABST      NUMERIC(13,3),
  INSME      NUMERIC(13,3),
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, MATNR, WERKS, LGORT) NOT ENFORCED
)
CLUSTER BY MATNR, WERKS
OPTIONS (description = 'SAP MARD — Storage Location Stock (unrestricted + quality-inspection).');

-- Material Valuation
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.MBEW` (
  MANDT      STRING(3)    NOT NULL,
  MATNR      STRING(40)   NOT NULL,
  BWKEY      STRING(4)    NOT NULL,
  VPRSV      STRING(1),
  STPRS      NUMERIC(11,2),
  PEINH      NUMERIC(5,0),
  WAERS      STRING(5),
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, MATNR, BWKEY) NOT ENFORCED
)
CLUSTER BY MATNR
OPTIONS (description = 'SAP MBEW — Material Valuation (standard price).');

-- Customer Master (General Data)
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.KNA1` (
  MANDT      STRING(3)    NOT NULL,
  KUNNR      STRING(10)   NOT NULL,
  NAME1      STRING(35),
  LAND1      STRING(3),
  ORT01      STRING(35),
  STRAS      STRING(35),
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, KUNNR) NOT ENFORCED
)
OPTIONS (description = 'SAP KNA1 — Customer Master General Data.');

-- Customer Sales Data
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.KNVV` (
  MANDT      STRING(3)    NOT NULL,
  KUNNR      STRING(10)   NOT NULL,
  VKORG      STRING(4)    NOT NULL,
  VTWEG      STRING(2)    NOT NULL,
  SPART      STRING(2)    NOT NULL,
  _loaded_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (MANDT, KUNNR, VKORG, VTWEG, SPART) NOT ENFORCED
)
OPTIONS (description = 'SAP KNVV — Customer Sales Data.');

-- Custom workforce-by-basin Z-table (no standard SAP table for this).
-- Synthesized-signature per §5; customer maps to their HR view.
--
-- Columns NAICS_211_STATE_EMPLOYMENT + DATA_SOURCE added in TASK-16
-- Step 4d.3 (Mode C real-data enrichment). For US basins these carry
-- real BLS QCEW Oil & Gas Extraction (NAICS 211) state employment
-- aggregated to basin via the curated state-share map in
-- scripts/build_bls_qcew_anchors.py. For foreign basins the field is
-- NULL — BLS QCEW only covers US states.
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.sap_extract.ZHR_WORKFORCE` (
  BASIN                          STRING(20) NOT NULL,
  CREW_COUNT_AVAILABLE           INT64,
  SPECIALIST_COUNT_AVAILABLE     INT64,
  ON_CALL_COUNT                  INT64,
  NAICS_211_STATE_EMPLOYMENT     INT64,
  DATA_SOURCE                    STRING(80),
  SNAPSHOT_DATE                  DATE       NOT NULL,
  _loaded_at                     TIMESTAMP  DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (BASIN, SNAPSHOT_DATE) NOT ENFORCED
)
PARTITION BY SNAPSHOT_DATE
CLUSTER BY BASIN
OPTIONS (description = 'SAP Z-table — workforce by basin snapshot. Custom Z-table pattern.');
