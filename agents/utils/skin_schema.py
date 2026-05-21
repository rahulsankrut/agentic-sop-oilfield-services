"""Pydantic mirror of `skins/schema/customer.schema.json` (TASK-13 Step 5).

This is the Python-side typed view of the customer skin YAML. The canvas
already consumes the same schema via TypeScript (`canvas/src/types/skin.ts`
+ `canvas/src/data/skin.generated.ts`); this module gives the deployed
agents the same shape so they can read persona names / hero asset
labels / scenario fixtures from the active skin.

Field names match the JSON Schema exactly (snake_case throughout). The
JSON Schema stays authoritative for cross-language validation; this
module just gives the Python side a typed dataclass to bind against.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkinMeta(BaseModel):
    customer_slug: str
    customer_name: str
    customer_display_name: str
    short_name: str | None = None
    color_primary: str
    color_secondary: str
    color_accent: str
    logo_path: str
    hero_path: str
    tagline: str | None = None


class SkinPersona(BaseModel):
    id: str  # david | tomas | maria | priya | rafael | ayesha
    number: int
    name: str
    role: str
    region: str
    sop_stage: str
    scenario_slug: str
    target_time_minutes: float
    opening_line: str
    memory_profile_user_id: str
    session_id: str


class SkinAssetEntry(BaseModel):
    canonical_id: str
    canonical_label: str
    category: str
    manufacturer: str
    equivalent_canonical_id: str | None = None
    equivalent_canonical_label: str | None = None


class SkinTaxonomy(BaseModel):
    hero_asset: SkinAssetEntry
    secondary_assets: list[SkinAssetEntry] = Field(default_factory=list)


class SkinScenarioConfig(BaseModel):
    customer_account_slug: str
    customer_account_name: str
    customer_account_short: str | None = None
    location_focus_label: str
    location_focus_lng: float | None = None
    location_focus_lat: float | None = None
    naive_origin_label: str | None = None
    naive_origin_lng: float | None = None
    naive_origin_lat: float | None = None
    recommended_origin_label: str | None = None
    recommended_origin_lng: float | None = None
    recommended_origin_lat: float | None = None
    asset_focus_canonical_id: str | None = None
    asset_focus_label: str
    naive_cost_usd: float | None = None
    recommended_cost_usd: float | None = None
    avoided_cost_usd: float | None = None
    deadline_phrase: str | None = None
    opening_prompt: str
    regulatory_reference: str | None = None


class SkinTerminology(BaseModel):
    occ_label: str
    occ_short: str | None = None
    basin_unit_label: str | None = None
    crew_unit_label: str | None = None
    fleet_unit_singular: str
    fleet_unit_plural: str
    capacity_gap_term: str | None = None
    sourcing_plan_term: str | None = None
    regulatory_repository: str
    audit_registry_label: str | None = None


class SkinKPILabel(BaseModel):
    id: str
    label: str
    short_label: str
    units: str  # percent | usd | count | hours | days
    target_value: float | None = None


class CustomerSkin(BaseModel):
    meta: SkinMeta
    personas: list[SkinPersona]
    taxonomy: SkinTaxonomy
    scenarios: dict[str, SkinScenarioConfig]
    terminology: SkinTerminology
    kpi_labels: list[SkinKPILabel]

    def persona(self, id_or_number: str | int) -> SkinPersona:
        """Lookup a persona by `id` slug or `number` (1-6)."""
        for p in self.personas:
            if isinstance(id_or_number, int) and p.number == id_or_number:
                return p
            if p.id == id_or_number:
                return p
        raise KeyError(f"No persona matching {id_or_number!r}")

    def scenario(self, slug: str) -> SkinScenarioConfig:
        if slug not in self.scenarios:
            raise KeyError(f"No scenario named {slug!r}")
        return self.scenarios[slug]
