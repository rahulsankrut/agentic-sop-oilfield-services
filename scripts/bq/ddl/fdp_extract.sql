-- fdp_extract — FDP (Forecast Demand Planner) homegrown extract.
--
-- FDP is the OFS major's homegrown forecasting/customer-config tool.
-- There is no public schema for FDP — the contract is the columns, not
-- source-system fidelity. Customer brings their FDP-equivalent extract
-- as a flat table of (customer_id, material_number, approved_flag,
-- accepted_substitutes[], notes).
--
-- APPROVED_SUBSTITUTIONS replaces the awkward `v7_substitution_accepted`
-- boolean from data/fdp_configurations.json with proper rows so the
-- restriction-matrix join is clean.

CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.fdp_extract.CUSTOMER_CONFIG` (
  CUSTOMER_ID     STRING(40)  NOT NULL,
  MATNR           STRING(40)  NOT NULL,
  APPROVED        BOOL,
  NOTES           STRING(500),
  EFFECTIVE_DATE  DATE,
  _loaded_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CUSTOMER_ID, MATNR) NOT ENFORCED
)
CLUSTER BY CUSTOMER_ID, MATNR
OPTIONS (description = 'FDP customer + material approval config. Customer brings their own extract.');

CREATE TABLE IF NOT EXISTS `vertex-ai-demos-468803.fdp_extract.APPROVED_SUBSTITUTIONS` (
  CUSTOMER_ID       STRING(40)  NOT NULL,
  MATNR_ORIGINAL    STRING(40)  NOT NULL,
  MATNR_SUBSTITUTE  STRING(40)  NOT NULL,
  ACCEPTED          BOOL,
  _loaded_at        TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
  PRIMARY KEY (CUSTOMER_ID, MATNR_ORIGINAL, MATNR_SUBSTITUTE) NOT ENFORCED
)
CLUSTER BY CUSTOMER_ID
OPTIONS (description = 'FDP approved substitutions matrix. ACCEPTED=FALSE rows are the restrictions.');
