# TASK-13: Customer skin templating and `customer.yaml` system

**Prerequisites:** TASK-12 complete. Demo runs end-to-end for the default customer (synthetic SLB-pattern). Six personas, three modes, full keyboard control surface.

**Estimated effort:** 2-3 days for one engineer.

**Stream:** Both

---

## Context

The brief calls this a **Reference Solution**, not a customer-specific deliverable. Targets all five tier-one oilfield services majors: SLB, Halliburton, Baker Hughes, NOV, Weatherford. The architectural principle from SPECS.md is "configuration over code for customer skinning" — about 90% of the system is customer-agnostic core, about 10% is the customer skin.

This task builds the skin system: a single `customer.yaml` file plus a small set of asset files that, when changed, transform the demo from "SLB-pattern" to "Halliburton-pattern" or "Baker Hughes-pattern" in under an hour. Brand, persona names, hero asset taxonomy, customer-account names in the scenarios, KPI labels, terminology — all parameterized from `customer.yaml`.

This matters for two reasons. First, **distribution**: if the CE community can hand a partner or another CE a one-page config and they deploy "their" version of the demo, the Reference Solution scales. Second, **trust**: a customer who sees a demo with their own brand and terminology engages differently than one who sees a generic demo. The skin is not cosmetic; it's the difference between "interesting platform demo" and "this is what your company looks like with agentic AI."

The discipline: **no customer-specific logic in code**. If something varies by customer, it goes in `customer.yaml`. If a customer requires logic the config doesn't express, the config schema gets extended — not the code branched. This keeps the core healthy as we accumulate skins.

---

## Inputs

- TASK-12 complete (default-customer demo runs end-to-end)
- Strategic brief: `agentic_sop_oilfield_services_brief.md` — target customer profiles section
- Default customer's synthetic data: `data/canonical_assets.json`, `customers.json`, etc.

---

## Deliverables

When this task is complete:

1. **`customer.yaml` schema** defined with Pydantic; covers brand, personas, scenarios, terminology, KPIs, regulatory references
2. **Default customer skin** (`customers/default/customer.yaml` + brand assets) — the SLB-pattern shown in the demo to date
3. **One alternate skin** — `customers/halliburton-pattern/customer.yaml` + brand assets — demonstrating the swap works
4. **Backend skin loader** — agents and Memory Profiles read from `customer.yaml`; templated prompts substitute customer-specific terms
5. **Frontend skin loader** — canvas reads `customer.yaml` at build/runtime, applies brand theme via CSS variables, persona display names, scenario terminology
6. **Skin switch command** — `make swap-customer CUSTOMER=halliburton-pattern` re-themes everything in under a minute
7. **Test suite** — same demo runs against both skins; cargo-plane scenario produces the right output in each customer's vocabulary
8. **Documentation** — `docs/customer-skinning.md` for partners adapting the Reference Solution

---

## Step-by-step instructions

### Step 1 — Design the `customer.yaml` schema

Carefully. This schema is the contract; getting it right means we don't have to refactor when adding the fourth or fifth skin.

`src/skin/customer_schema.py`:

```python
"""customer.yaml schema. The contract between the customer-agnostic core
and the customer-specific skin."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl


class Brand(BaseModel):
    """Brand identity for the customer."""
    name: str                         # "Halliburton-pattern"
    display_name: str                 # "Halliburton" (for narration; pattern note for legal)
    short_name: str                   # "HAL"
    primary_color: str                # hex, used as theme accent
    secondary_color: str
    logo_path: str                    # path under customers/{skin}/assets/
    favicon_path: str
    tagline: Optional[str] = None


class Persona(BaseModel):
    """Per-customer persona configuration. Maps to a Memory Profile."""
    id: str                          # "david", "maria", etc. — stable across customers
    display_name: str                # "David Okeke" → "David Tepper" for different customer
    role: str                        # role title
    region: str                      # operating region
    customer_portfolio_examples: list[str] = Field(default_factory=list)


class HeroScenario(BaseModel):
    """The cargo-plane scenario, parameterized."""
    requested_asset_canonical_id: str   # "TX-001" — taxonomy is customer-specific
    requested_asset_terminology: str    # "Tool X" → "Spear Y" or whatever
    gap_location_label: str             # "Luanda, Angola" or wherever the customer's portfolio includes
    gap_location_lng: float
    gap_location_lat: float
    naive_origin_label: str             # "Australia"
    naive_origin_lng: float
    naive_origin_lat: float
    recommended_origin_label: str       # "Lagos, Nigeria"
    recommended_origin_lng: float
    recommended_origin_lat: float
    customer_account_name: str          # "Chevron" — the customer's customer
    naive_cost_usd: float               # the doomed plan cost — $420K
    recommended_cost_usd: float         # the smart plan cost — $40K


class Terminology(BaseModel):
    """Customer-specific terminology overlay."""
    occ_label: str = "Operations Control Center"         # may be "Mission Control" elsewhere
    fleet_unit_singular: str = "tool"                    # may be "rig", "frac unit", etc.
    fleet_unit_plural: str = "tools"
    basin_unit_label: str = "basin"
    capacity_gap_term: str = "capacity gap"
    sourcing_plan_term: str = "sourcing plan"


class KPI(BaseModel):
    label: str
    short_label: str
    units: str
    target_value: Optional[float] = None


class RegulatoryReference(BaseModel):
    name: str                            # "InTouch" → "WellSite Hub" for another customer
    document_repository: str             # where specs come from
    canonical_aspect_type_id: str        # how it appears in Knowledge Catalog


class CustomerSkin(BaseModel):
    """Top-level customer skin config."""
    skin_version: str = "1.0"
    brand: Brand
    personas: list[Persona]              # always six in same order
    hero_scenario: HeroScenario
    terminology: Terminology = Terminology()
    kpis: list[KPI]
    regulatory_reference: RegulatoryReference
```

### Step 2 — Build the default skin

`customers/default/customer.yaml`:

```yaml
skin_version: "1.0"

brand:
  name: "default"
  display_name: "Demo Major"   # Use a clearly synthetic name for default
  short_name: "DEMO"
  primary_color: "#3b82f6"
  secondary_color: "#1e293b"
  logo_path: "customers/default/assets/logo.svg"
  favicon_path: "customers/default/assets/favicon.ico"
  tagline: "Agentic S&OP for oilfield services"

personas:
  - id: "david"
    display_name: "David Okeke"
    role: "Basin Leader"
    region: "West Africa"
    customer_portfolio_examples: ["Chevron-Lagos", "Shell-Angola Block 17"]

  - id: "tomas"
    display_name: "Tomas Reyes"
    role: "Fleet Scheduler"
    region: "Permian"
    customer_portfolio_examples: ["ExxonMobil-Permian Frac Pump Fleet"]

  - id: "maria"
    display_name: "Maria Adeyemi"
    role: "OCC Planner"
    region: "West Africa"
    customer_portfolio_examples: ["Chevron-Lagos Deepwater"]

  - id: "priya"
    display_name: "Priya Krishnan"
    role: "Operations VP"
    region: "Global"

  - id: "rafael"
    display_name: "Rafael Santos"
    role: "Citizen Developer"
    region: "Permian"

  - id: "ayesha"
    display_name: "Ayesha Khan"
    role: "Audit Director"
    region: "Global"

hero_scenario:
  requested_asset_canonical_id: "TX-001"
  requested_asset_terminology: "Tool X"
  gap_location_label: "Luanda, Angola"
  gap_location_lng: 13.2894
  gap_location_lat: -8.8390
  naive_origin_label: "Perth, Australia"
  naive_origin_lng: 115.86
  naive_origin_lat: -31.95
  recommended_origin_label: "Lagos, Nigeria"
  recommended_origin_lng: 3.3792
  recommended_origin_lat: 6.5244
  customer_account_name: "Chevron"
  naive_cost_usd: 420000
  recommended_cost_usd: 40000

terminology:
  occ_label: "Operations Control Center"
  fleet_unit_singular: "tool"
  fleet_unit_plural: "tools"

kpis:
  - label: "On-time start rate"
    short_label: "OTS"
    units: "percent"
    target_value: 0.90
  - label: "Fleet utilization"
    short_label: "Util"
    units: "percent"
    target_value: 0.85
  - label: "Avoided logistics cost"
    short_label: "Avoided"
    units: "usd"

regulatory_reference:
  name: "InTouch"
  document_repository: "intouch-specs"
  canonical_aspect_type_id: "oilfield-functional-equivalence"
```

Save brand assets to `customers/default/assets/`:
- `logo.svg` — generic synthetic logo (no real-customer branding)
- `favicon.ico`

### Step 3 — Build the Halliburton-pattern skin

`customers/halliburton-pattern/customer.yaml`:

```yaml
skin_version: "1.0"

brand:
  name: "halliburton-pattern"
  display_name: "Halliburton-pattern"   # NOTE: this is a synthetic skin modeled on but not representing the actual company
  short_name: "HAL-P"
  primary_color: "#d62733"               # Halliburton-style red
  secondary_color: "#1a1a1a"
  logo_path: "customers/halliburton-pattern/assets/logo.svg"
  favicon_path: "customers/halliburton-pattern/assets/favicon.ico"
  tagline: "Agentic S&OP — Halliburton-pattern reference"

personas:
  - id: "david"
    display_name: "David Tepper"
    role: "Region Manager"   # Halliburton uses "Region Manager" terminology
    region: "MENA"
    customer_portfolio_examples: ["Saudi Aramco-Manifa", "ADNOC-Upper Zakum"]

  - id: "tomas"
    display_name: "Tomas Bauer"
    role: "Frac Fleet Scheduler"
    region: "Permian"
    customer_portfolio_examples: ["Pioneer-Wolfcamp Frac Stages"]

  - id: "maria"
    display_name: "Maria Vasquez"
    role: "Mission Operations Center Planner"   # Halliburton-pattern: "MOC" not "OCC"
    region: "Latin America"
    customer_portfolio_examples: ["Petrobras-Búzios"]

  - id: "priya"
    display_name: "Priya Iyer"
    role: "VP Operations"
    region: "Global"

  - id: "rafael"
    display_name: "Rafael Mendoza"
    role: "Digital Operations Engineer"
    region: "Permian"

  - id: "ayesha"
    display_name: "Ayesha Hassan"
    role: "Director of Operational Risk"
    region: "Global"

hero_scenario:
  requested_asset_canonical_id: "SPR-Y-002"
  requested_asset_terminology: "Spear Y"   # Halliburton-pattern: their downhole tool naming
  gap_location_label: "Búzios Pre-salt, Brazil"
  gap_location_lng: -42.62
  gap_location_lat: -22.84
  naive_origin_label: "Singapore"
  naive_origin_lng: 103.82
  naive_origin_lat: 1.35
  recommended_origin_label: "Macaé, Brazil"
  recommended_origin_lng: -41.79
  recommended_origin_lat: -22.37
  customer_account_name: "Petrobras"
  naive_cost_usd: 380000
  recommended_cost_usd: 35000

terminology:
  occ_label: "Mission Operations Center"   # "MOC" not "OCC"
  fleet_unit_singular: "tool string"
  fleet_unit_plural: "tool strings"
  basin_unit_label: "operating region"

kpis:
  - label: "Stage completion rate"
    short_label: "Stage"
    units: "percent"
    target_value: 0.94
  - label: "Frac fleet utilization"
    short_label: "Util"
    units: "percent"
    target_value: 0.88
  - label: "Logistics cost avoidance"
    short_label: "Avoided"
    units: "usd"

regulatory_reference:
  name: "WellSite Hub"   # Halliburton-pattern equivalent of InTouch
  document_repository: "wellsite-specs"
  canonical_aspect_type_id: "oilfield-functional-equivalence"
```

The two skins differ in: brand colors, persona display names, hero asset name and location, customer-account name, terminology, KPI labels, regulatory document repository name. Same canonical asset taxonomy (those are operationally real categories that span vendors), same scenario structure, same six personas, same Workflow nodes.

### Step 4 — Build the backend skin loader

`src/skin/skin_loader.py`:

```python
"""Load and validate customer.yaml at startup. Inject into agent context."""

import os
from pathlib import Path
import yaml

from .customer_schema import CustomerSkin

_skin_cache: CustomerSkin | None = None


def get_active_skin() -> CustomerSkin:
    """Return the loaded skin. Loaded once at process start."""
    global _skin_cache
    if _skin_cache is None:
        _skin_cache = _load_active_skin()
    return _skin_cache


def _load_active_skin() -> CustomerSkin:
    """Resolve the active customer from CUSTOMER_SKIN env var; load YAML; validate."""
    skin_name = os.environ.get("CUSTOMER_SKIN", "default")
    skin_dir = Path(__file__).parent.parent.parent / "customers" / skin_name
    yaml_path = skin_dir / "customer.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(f"Customer skin not found: {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    return CustomerSkin(**data)


def render_template(template: str, **extras) -> str:
    """Substitute customer-specific terms into a template string.

    Available variables:
    - {brand.display_name}, {brand.short_name}, ...
    - {hero.requested_asset_terminology}, {hero.gap_location_label}, ...
    - {terminology.occ_label}, ...
    - {persona.maria.display_name}, ...
    - Plus any extras passed in
    """
    skin = get_active_skin()
    ctx = {
        "brand": skin.brand,
        "hero": skin.hero_scenario,
        "terminology": skin.terminology,
        "persona": {p.id: p for p in skin.personas},
        **extras,
    }
    # Use a structured templating engine (Jinja2) for nested access
    from jinja2 import Template
    return Template(template).render(**ctx)
```

### Step 5 — Template the agents' prompts and Memory Profiles

Where prompts mentioned specific customer terms or asset names, replace with template variables.

`src/orchestrator_agent/core/prompts.py` (excerpts):

```python
from ...skin.skin_loader import render_template


_EQUIVALENCE_LOOKUP_TEMPLATE = """You determine the best functional equivalent for a canonical
{{ terminology.fleet_unit_singular }} using Knowledge Catalog.

1. Use the Knowledge Catalog lookup_entry tool with the canonical_id of the requested
   {{ terminology.fleet_unit_singular }}.
2. Review the functional_equivalence aspect data.
3. For each candidate, check the customer_compatibility_overrides for {{ hero.customer_account_name }}.
4. Return the highest-confidence equivalent that {{ hero.customer_account_name }} accepts.

Return a structured EquivalentAssetCandidate.
"""


EQUIVALENCE_LOOKUP_INSTRUCTION = render_template(_EQUIVALENCE_LOOKUP_TEMPLATE)
```

Similarly, the Memory Profile setup script reads from `customer.yaml`:

```python
# memory_bank/setup.py
from src.skin.skin_loader import get_active_skin

def maria_profile() -> PersonaMemoryProfile:
    skin = get_active_skin()
    maria = next(p for p in skin.personas if p.id == "maria")
    return PersonaMemoryProfile(
        user_id=f"{maria.id}-{maria.region.lower().replace(' ', '-')}",
        display_name=maria.display_name,
        role=maria.role,
        region_context=RegionContext(primary_basin=maria.region, ...),
        # ... rest derived from skin
    )
```

### Step 6 — Build the frontend skin loader

`canvas/lib/skin.ts`:

```typescript
import type { CustomerSkin } from "./customer-schema";   // generated from Python schema

let _skin: CustomerSkin | null = null;

export async function loadSkin(): Promise<CustomerSkin> {
  if (_skin) return _skin;

  // Skin selection comes from env var at build time, exposed as NEXT_PUBLIC_CUSTOMER_SKIN
  const skinName = process.env.NEXT_PUBLIC_CUSTOMER_SKIN ?? "default";
  const response = await fetch(`/skins/${skinName}/customer.json`);
  if (!response.ok) throw new Error(`Failed to load skin ${skinName}`);

  _skin = await response.json();
  applyBrandTheme(_skin);
  return _skin;
}


function applyBrandTheme(skin: CustomerSkin) {
  const root = document.documentElement;
  root.style.setProperty("--color-brand-primary", skin.brand.primary_color);
  root.style.setProperty("--color-brand-secondary", skin.brand.secondary_color);

  // Favicon
  const favicon = document.querySelector('link[rel="icon"]') as HTMLLinkElement;
  if (favicon) favicon.href = `/skins/${skin.brand.name}/assets/favicon.ico`;
}


export function useSkin(): CustomerSkin {
  // React hook — assumes skin has been loaded once at app startup
  const [skin, setSkin] = useState<CustomerSkin | null>(_skin);
  useEffect(() => {
    if (!skin) loadSkin().then(setSkin);
  }, []);
  return skin!;
}
```

A small `next.config.ts` step copies the active skin's YAML to a public JSON file at build time:

```typescript
// canvas/scripts/build-skin.ts
import yaml from "js-yaml";
import fs from "fs";

const skinName = process.env.NEXT_PUBLIC_CUSTOMER_SKIN ?? "default";
const yamlContent = fs.readFileSync(`../customers/${skinName}/customer.yaml`, "utf-8");
const json = yaml.load(yamlContent);
fs.mkdirSync(`public/skins/${skinName}`, { recursive: true });
fs.writeFileSync(`public/skins/${skinName}/customer.json`, JSON.stringify(json, null, 2));
fs.cpSync(`../customers/${skinName}/assets`, `public/skins/${skinName}/assets`, { recursive: true });
console.log(`Skin built: ${skinName}`);
```

### Step 7 — Use the skin in canvas components

`canvas/components/canvas/CostRollupBanner.tsx` updated to use skin:

```tsx
import { useSkin } from "@/lib/skin";

export function CostRollupBanner({ visible }: { visible: boolean }) {
  const skin = useSkin();
  const hero = skin?.hero_scenario;

  if (!visible || !hero) return null;

  // DEMO NARRATION: "The cost numbers come from the customer skin. For the
  // default-customer scenario, $380K avoided. For the Halliburton-pattern
  # skin, the location, customer name, and dollar figures change. The agent
  # logic and Workflow graph don't change — only the skin does."
  const avoided = hero.naive_cost_usd - hero.recommended_cost_usd;

  return (
    <div className="...">
      <span className="line-through text-cost-avoided">
        ${hero.naive_cost_usd.toLocaleString()} air freight from {hero.naive_origin_label}
      </span>
      <div>${hero.recommended_cost_usd.toLocaleString()} ground transit from {hero.recommended_origin_label}</div>
      <div className="text-3xl font-bold text-cost-saved">${avoided.toLocaleString()} avoided</div>
    </div>
  );
}
```

Similarly: the persona launcher uses `skin.personas` for display names; the canvas map centers on `skin.hero_scenario.gap_location_lat/lng`; the Knowledge Catalog drawer titles use `skin.terminology.fleet_unit_singular`; demo handbook text is generated from skin (via a build step).

### Step 8 — Build the skin swap command

`Makefile`:

```makefile
.PHONY: swap-customer

# Usage: make swap-customer CUSTOMER=halliburton-pattern
swap-customer:
	@if [ -z "$(CUSTOMER)" ]; then echo "Usage: make swap-customer CUSTOMER=<skin-name>"; exit 1; fi
	@if [ ! -d "customers/$(CUSTOMER)" ]; then echo "Skin not found: customers/$(CUSTOMER)"; exit 1; fi
	@echo "Swapping to customer skin: $(CUSTOMER)"
	@echo "CUSTOMER_SKIN=$(CUSTOMER)" > .env.skin
	@echo "NEXT_PUBLIC_CUSTOMER_SKIN=$(CUSTOMER)" >> .env.skin
	# Re-populate Memory Bank with the new skin's persona profiles
	$(MAKE) setup-memory-bank
	# Re-seed deterministic demo sessions
	$(MAKE) seed-demo-sessions
	# Rebuild the canvas with the new skin
	cd canvas && NEXT_PUBLIC_CUSTOMER_SKIN=$(CUSTOMER) npm run build
	# Re-deploy the canvas
	cd canvas && gcloud builds submit --substitutions=_CUSTOMER_SKIN=$(CUSTOMER) --tag gcr.io/$$PROJECT_ID/operations-canvas
	@echo "Customer skin $(CUSTOMER) deployed. Refresh the canvas to see changes."
```

Total time end-to-end: ~10 minutes (most of that is the Cloud Build canvas rebuild). Within the under-an-hour target.

### Step 9 — Test both skins

`tests/integration/test_skin_swap.py`:

```python
@pytest.mark.parametrize("skin_name", ["default", "halliburton-pattern"])
async def test_cargo_plane_scenario_works_per_skin(skin_name: str):
    """The cargo-plane scenario should produce skin-appropriate output."""
    os.environ["CUSTOMER_SKIN"] = skin_name
    skin = get_active_skin()

    # Run the orchestrator
    response = await run_orchestrator(
        user_input=f"I need {skin.hero_scenario.requested_asset_terminology} in {skin.hero_scenario.gap_location_label}",
        user_id=f"maria-{skin.brand.name}",
        session_id=f"test-skin-{skin_name}",
    )

    plan = response.output
    
    # Verify location is correct for this skin
    assert plan["primary_option"]["source_location"]["label"] == skin.hero_scenario.recommended_origin_label
    # Verify customer-account is correct
    assert plan["customer_account"] == skin.hero_scenario.customer_account_name
    # Verify avoided cost is right magnitude
    expected_avoided = skin.hero_scenario.naive_cost_usd - skin.hero_scenario.recommended_cost_usd
    assert abs(plan["avoided_cost_usd"] - expected_avoided) < 1000


def test_no_hardcoded_customer_references():
    """Grep the codebase for hardcoded references that should be in customer.yaml."""
    forbidden = ["Chevron", "Halliburton", "Tool X", "Spear Y", "Luanda"]
    src_files = list(Path("src").rglob("*.py")) + list(Path("canvas/components").rglob("*.tsx"))
    for term in forbidden:
        for f in src_files:
            content = f.read_text()
            # Skip docstrings/comments
            if term in content:
                # Allow in test files and skin loader
                if "test_" in f.name or "skin" in str(f):
                    continue
                pytest.fail(f"Hardcoded '{term}' in {f}")
```

### Step 10 — Document for partners

`docs/customer-skinning.md`:

```markdown
# Customer skinning guide

This Reference Solution is designed to be re-themed per customer. Targets
all five tier-one oilfield services majors. To produce a new customer skin
takes 30-60 minutes for someone familiar with the system.

## Anatomy of a customer skin

Each skin is a folder under `customers/{skin-name}/`:

```
customers/{skin-name}/
├── customer.yaml          # the skin config — schema documented below
└── assets/
    ├── logo.svg           # customer brand logo
    └── favicon.ico
```

That is the entire skin. No code changes.

## Creating a new skin

1. Copy an existing skin as starting point:
   ```bash
   cp -r customers/default customers/baker-hughes-pattern
   ```

2. Edit `customers/baker-hughes-pattern/customer.yaml`:
   - Brand block: company name (use "-pattern" suffix for legal safety), colors, logo path
   - Personas: display names, roles, regions
   - Hero scenario: customer-specific asset terminology, locations, customer-account name, costs
   - Terminology: OCC vs. MOC, fleet unit terminology, regulatory reference
   - KPIs: customer-specific KPI labels

3. Replace `assets/logo.svg` and `assets/favicon.ico` with the customer's brand assets.

4. Verify:
   ```bash
   make swap-customer CUSTOMER=baker-hughes-pattern
   make test-skin
   ```

5. Test the demo end-to-end:
   ```bash
   make demo-preflight
   # Then run the canvas at /demo
   ```

## Legal notes

- All skins are "pattern" skins — synthetic representations modeled on tier-one
  major patterns. They are not endorsed by or representative of any specific
  company.
- Logos used in pattern skins should be CLEARLY MARKED as illustrative.
- Customer account names in scenarios (Chevron, Petrobras, etc.) are real
  end-user companies but the data is synthetic.
- Do not commit real customer-specific data into a skin folder. If a customer
  engagement produces customer-specific data, keep it in a separate
  customer-engagement repo that includes this Reference Solution as a
  dependency.

## What can vary across skins

[full list documented from the schema]

## What cannot vary across skins

These are core platform/architecture decisions; if a customer needs them
different, that's a code change, not a skin change:

- The six personas and their S&OP stages (Demand sensing → Demand-to-supply
  → Supply response → Strategic review → Self-service → Governance)
- The Workflow graph structure for the Capacity Orchestrator
- The Knowledge Catalog Aspect Type schema
- The MCP server interface (tool surface)
- The governance posture (Identity, Gateway, Model Armor configuration)
```

### Step 11 — Commit

```bash
git add customers/ src/skin/ canvas/lib/skin.ts canvas/scripts/build-skin.ts \
        tests/integration/test_skin_swap.py docs/customer-skinning.md Makefile
git commit -m "feat: customer skin templating with default + halliburton-pattern (TASK-13)"
git push
```

---

## Acceptance criteria

- [ ] `customer.yaml` schema defined and validated with Pydantic
- [ ] Default skin exists and works (regression test: cargo-plane still produces $380K avoided)
- [ ] Halliburton-pattern skin exists with different brand, personas, locations, terminology
- [ ] Backend skin loader reads `customer.yaml`, templates prompts and Memory Profiles
- [ ] Frontend skin loader applies brand theme via CSS variables, uses skin data in components
- [ ] `make swap-customer CUSTOMER=halliburton-pattern` re-themes everything in <10 minutes
- [ ] Test suite verifies both skins produce skin-appropriate output
- [ ] Lint test verifies no hardcoded customer references in production code paths
- [ ] `docs/customer-skinning.md` written for partner consumption
- [ ] Commit pushed

---

## Common pitfalls

**Skin-specific logic creeping into code.** Tempting to write `if skin_name == "halliburton-pattern": do_something_different`. Don't. If the skin needs to vary behavior, extend the schema to express the variation as data. Code branching on skin name is the road to unmaintainable skins.

**Locked-in canonical taxonomy.** The canonical asset IDs (TX-001 vs SPR-Y-002) are intentionally different across skins, but they refer to the same physical asset *class*. Don't reuse the same canonical_id across skins with different meanings — that breaks Knowledge Catalog content and downstream reasoning.

**Brand color contrast.** Halliburton's red (#d62733) has different contrast against the dark canvas background than the default blue. Test legibility of every accent-colored element when applying a new skin. Don't ship a skin where the cost banner is unreadable.

**Halliburton-pattern legal risk.** The "Halliburton-pattern" naming is shorthand; the actual skin is synthetic and not endorsed. Be careful in customer conversations — never represent it as approved by or representative of the actual company. If a customer asks for an "official Halliburton skin," that's a separate engagement.

**Logo asset quality.** SVG logos render at any size; bitmap logos at the wrong resolution look amateur on a projector. Insist on SVG. If only a bitmap is available, render at 2x for the canvas.

**Translation/internationalization not yet supported.** Current skin only varies terminology in English. Adding a French or Arabic skin is a larger task — full i18n with message catalogs, not just `customer.yaml`.

**Memory Profile drift.** When you swap skins, the old skin's Memory Profiles remain in Memory Bank with their old user IDs. Either: (a) namespace user IDs by skin (`maria-default` vs `maria-halliburton-pattern`), or (b) explicitly purge profiles before switching. Default to (a); it's more forgiving.

**Pattern naming embarrassment.** "Halliburton-pattern" sounds awkward when said aloud. In customer narration, the demoer should say "a Halliburton-style customer profile" or "our reference major" rather than reading the skin's `name` field literally.

---

## References

- Jinja2 templating: `https://jinja.palletsprojects.com/`
- Pydantic schema validation: `https://docs.pydantic.dev/`
- Next.js public assets: `https://nextjs.org/docs/app/api-reference/file-conventions/public-folder`

---

*When TASK-13 is complete, the Reference Solution earns its name. Distributing it to another CE or partner means handing them one config file plus brand assets, and they have a customer-specific demo within an hour. Next: end-to-end deployment via Terraform or agents-cli.*
