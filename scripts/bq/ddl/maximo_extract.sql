-- maximo_extract — IBM Maximo (MAS 9.x) extract mirror.
--
-- Real Maximo column names + types from ASSET / ITEM / INVENTORY /
-- INVBALANCES / LOCATIONS / ASSETLOCATIONS / WORKORDER. WO_HISTORY is a
-- view that backs scheduling-probability.get_start_date_distribution
-- (Q7 resolution).
--
-- Deviation from real Maximo (documented in spec §3): LATITUDE/LONGITUDE
-- kept inline on LOCATIONS for demo simplicity. MAS 9.0 moved geometry
-- to a separate Spatial extension table.
--
-- WORKORDER includes SCHEDSTART, ACTSTART, ACTLABHRS which are real
-- Maximo columns referenced by the WO_HISTORY view + the
-- certification_hours_remaining derivation (Q5 resolution: customer's
-- extract layer materializes via MAX(ESTLABHRS - ACTLABHRS) on open
-- RECERT WOs). Spec §3 table omitted them; adding here so the view
-- compiles and the downstream queries work end-to-end.

-- Asset Master
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.ASSET` (
  ASSETID      INT64        NOT NULL,
  ASSETNUM     STRING(25)   NOT NULL,
  DESCRIPTION  STRING(100),
  STATUS       STRING(16),
  LOCATION     STRING(25),
  SITEID       STRING(16),
  ORGID        STRING(8),
  PARENT       STRING(25),
  ASSETTYPE    STRING(16),
  ITEMNUM      STRING(25),
  SERIALNUM    STRING(40),
  INSTALLDATE  DATE,
  _loaded_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ASSETID) NOT ENFORCED
)
CLUSTER BY SITEID, ASSETNUM
OPTIONS (description = 'Maximo ASSET — Asset Master. UNIQUE (SITEID, ASSETNUM) natural key.');

-- Item Master
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.ITEM` (
  ITEMNUM         STRING(25)  NOT NULL,
  ITEMSETID       STRING(16)  NOT NULL,
  DESCRIPTION     STRING(100),
  COMMODITYGROUP  STRING(16),
  _loaded_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ITEMSETID, ITEMNUM) NOT ENFORCED
)
CLUSTER BY ITEMNUM
OPTIONS (description = 'Maximo ITEM — Item Master.');

-- Inventory Item-at-Location
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.INVENTORY` (
  ITEMNUM     STRING(25)  NOT NULL,
  ITEMSETID   STRING(16)  NOT NULL,
  LOCATION    STRING(25)  NOT NULL,
  SITEID      STRING(16)  NOT NULL,
  STATUS      STRING(16),
  ABCTYPE     STRING(1),
  _loaded_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ITEMSETID, ITEMNUM, LOCATION, SITEID) NOT ENFORCED
)
CLUSTER BY ITEMNUM, SITEID
OPTIONS (description = 'Maximo INVENTORY — Item-at-Location stocking record.');

-- Storage Bin Balances. PK is (SiteId, ItemSetID, Itemnum, Location, Binnum, Lotnum) per Maximo docs.
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.INVBALANCES` (
  ITEMNUM        STRING(25)   NOT NULL,
  ITEMSETID      STRING(16)   NOT NULL,
  LOCATION       STRING(25)   NOT NULL,
  SITEID         STRING(16)   NOT NULL,
  BINNUM         STRING(8)    NOT NULL,
  LOTNUM         STRING(8),
  CONDITIONCODE  STRING(10),
  PHYSCNT        NUMERIC(12,4),
  PHYSCNTDATE    DATE,
  CURBAL         NUMERIC(12,4),
  _loaded_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY ITEMNUM, SITEID
OPTIONS (description = 'Maximo INVBALANCES — Storage Bin Balances. Per-bin/per-lot stock.');

-- Location Master. LATITUDE/LONGITUDE inline (demo simplification — MAS 9.0
-- Spatial extension moves geometry to a separate table).
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.LOCATIONS` (
  LOCATION     STRING(25)    NOT NULL,
  SITEID       STRING(16)    NOT NULL,
  ORGID        STRING(8),
  DESCRIPTION  STRING(100),
  TYPE         STRING(16),
  STATUS       STRING(16),
  LATITUDE     NUMERIC(9,6),
  LONGITUDE    NUMERIC(9,6),
  REGION       STRING(20),
  _loaded_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (SITEID, LOCATION) NOT ENFORCED
)
CLUSTER BY REGION, SITEID
OPTIONS (description = 'Maximo LOCATIONS — Location Master with inline lat/lon.');

-- Asset Location History. Slim version.
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.ASSETLOCATIONS` (
  ASSETID         INT64       NOT NULL,
  LOCATION        STRING(25)  NOT NULL,
  SITEID          STRING(16)  NOT NULL,
  EFFECTIVE_DATE  DATE        NOT NULL,
  _loaded_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (ASSETID, LOCATION, SITEID, EFFECTIVE_DATE) NOT ENFORCED
)
CLUSTER BY ASSETID
OPTIONS (description = 'Maximo ASSETLOCATIONS — Asset Location History.');

-- Work Order (recert + repair tracking). SCHEDSTART/ACTSTART/ACTLABHRS
-- added beyond §3's spec table because they're real Maximo columns and
-- the WO_HISTORY view (below) + the cert_hours_remaining derivation
-- depend on them.
CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.maximo_extract.WORKORDER` (
  WONUM       STRING(16)    NOT NULL,
  SITEID      STRING(16)    NOT NULL,
  ASSETNUM    STRING(25),
  LOCATION    STRING(25),
  STATUS      STRING(16),
  WORKTYPE    STRING(10),
  REPORTDATE  TIMESTAMP,
  SCHEDSTART  TIMESTAMP,
  ACTSTART    TIMESTAMP,
  ESTLABHRS   NUMERIC(8,2),
  ACTLABHRS   NUMERIC(8,2),
  _loaded_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (SITEID, WONUM) NOT ENFORCED
)
CLUSTER BY ASSETNUM, SITEID
OPTIONS (description = 'Maximo WORKORDER — Recert + repair tracking. Source for WO_HISTORY view.');

-- WO_HISTORY view — schedule-vs-actual variance per asset / region.
-- Backs scheduling-probability.get_start_date_distribution (Q7 resolution).
-- Substitution path: customer's Maximo WORKORDER dump has the same columns,
-- the view definition is portable as-is.
CREATE OR REPLACE VIEW `vertex-ai-demos-468803.maximo_extract.WO_HISTORY` AS
SELECT
  w.WONUM,
  w.SITEID,
  w.ASSETNUM,
  a.ITEMNUM,
  l.REGION,
  l.LATITUDE,
  l.LONGITUDE,
  w.WORKTYPE,
  w.SCHEDSTART AS scheduled_start,
  w.ACTSTART   AS actual_start,
  TIMESTAMP_DIFF(w.ACTSTART, w.SCHEDSTART, DAY) AS variance_days,
  w.STATUS,
  w.REPORTDATE
FROM `vertex-ai-demos-468803.maximo_extract.WORKORDER` w
JOIN `vertex-ai-demos-468803.maximo_extract.ASSET`     a
  ON  a.ASSETNUM = w.ASSETNUM AND a.SITEID = w.SITEID
JOIN `vertex-ai-demos-468803.maximo_extract.LOCATIONS` l
  ON  l.SITEID   = a.SITEID   AND l.LOCATION = a.LOCATION
WHERE w.STATUS = 'COMP' AND w.ACTSTART IS NOT NULL;
