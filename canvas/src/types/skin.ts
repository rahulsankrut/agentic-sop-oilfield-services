/**
 * skin.ts — Type contract for the customer skin loaded from
 * `skins/<slug>/customer.yaml` and compiled to
 * `canvas/src/data/skin.generated.ts` by `scripts/compile_skin.py`.
 *
 * Source of truth: `skins/schema/customer.schema.json`. Keep this TS file
 * in sync if the JSON Schema is extended.
 *
 * The skin is the contract between the customer-agnostic core (canvas
 * components, agent code) and the customer-specific configuration (brand,
 * persona names, hero scenario data, terminology, KPI labels).
 */

export interface SkinMeta {
  customer_slug: string;
  customer_name: string;
  customer_display_name: string;
  short_name?: string;
  color_primary: string;
  color_secondary: string;
  color_accent: string;
  logo_path: string;
  hero_path: string;
  tagline?: string;
}

export type PersonaId =
  | "david"
  | "tomas"
  | "maria"
  | "priya"
  | "rafael"
  | "ayesha";

export interface SkinPersona {
  id: PersonaId;
  number: 1 | 2 | 3 | 4 | 5 | 6;
  name: string;
  role: string;
  region: string;
  sop_stage: string;
  scenario_slug: string;
  target_time_minutes: number;
  opening_line: string;
  memory_profile_user_id: string;
  session_id: string;
}

export interface AssetEntry {
  canonical_id: string;
  canonical_label: string;
  category: string;
  manufacturer: string;
  equivalent_canonical_id?: string;
  equivalent_canonical_label?: string;
}

export interface SkinTaxonomy {
  hero_asset: AssetEntry;
  secondary_assets?: AssetEntry[];
}

export interface ScenarioConfig {
  customer_account_slug: string;
  customer_account_name: string;
  customer_account_short?: string;
  location_focus_label: string;
  location_focus_lng?: number;
  location_focus_lat?: number;
  naive_origin_label?: string;
  naive_origin_lng?: number;
  naive_origin_lat?: number;
  recommended_origin_label?: string;
  recommended_origin_lng?: number;
  recommended_origin_lat?: number;
  asset_focus_canonical_id?: string;
  asset_focus_label: string;
  naive_cost_usd?: number;
  recommended_cost_usd?: number;
  avoided_cost_usd?: number;
  deadline_phrase?: string;
  opening_prompt: string;
  regulatory_reference?: string;
}

export interface SkinTerminology {
  occ_label: string;
  occ_short?: string;
  basin_unit_label?: string;
  crew_unit_label?: string;
  fleet_unit_singular: string;
  fleet_unit_plural: string;
  capacity_gap_term?: string;
  sourcing_plan_term?: string;
  regulatory_repository: string;
  audit_registry_label?: string;
}

export interface KpiLabel {
  id: string;
  label: string;
  short_label: string;
  units: "percent" | "usd" | "count" | "hours" | "days";
  target_value: number | null;
}

export interface CustomerSkin {
  meta: SkinMeta;
  personas: SkinPersona[];
  taxonomy: SkinTaxonomy;
  scenarios: Record<string, ScenarioConfig>;
  terminology: SkinTerminology;
  kpi_labels: KpiLabel[];
}
