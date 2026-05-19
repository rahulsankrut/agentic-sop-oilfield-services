# TASK-06: Knowledge Catalog setup with custom Aspect Types and canonical Entries

**Prerequisites:** TASK-05 complete. MCP servers deployed, Knowledge Catalog MCP wired into the Orchestrator. Cargo-plane scenario passes.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Backend

---

## Context

Knowledge Catalog (the rebrand of Dataplex Universal Catalog as of April 10, 2026; API names remain `dataplex.*`) is where our canonical asset model lives in production. Until now, our `data/canonical_assets.json` and `data/cross_system_aliases.json` files have served as the substrate. In this task we move that content into actual Knowledge Catalog Entries, defined by custom Aspect Types we author for the oilfield services domain.

This is the moment **Issue 4 dissolves visibly in the demo**. When Maria clicks "why does the agent think these are equivalent?" during the cargo-plane scenario, the Knowledge Catalog drawer expands to show the canonical Tool X entity with all its cross-system aliases — SAP material number, Maximo equipment ID, FDP config ID, InTouch spec references — unified into one Entry with structured Aspects. The agent never reasons against the chaos of system-specific identifiers; it reasons against canonical entities. That's the platform story.

This task does not write the synthetic data — TASK-03 already produced that. This task moves the data from JSON files into a real Knowledge Catalog, defines the Aspect Types that give it shape, and verifies the prebuilt MCP tools (wired in TASK-05) can query it.

---

## Inputs

- TASK-05 complete (Knowledge Catalog MCP working with empty catalog)
- Synthetic data from TASK-03:
  - `data/canonical_assets.json`
  - `data/cross_system_aliases.json`
  - `data/functional_equivalences.json`
  - `data/customers.json`
- Dataplex API enabled in the project (TASK-01 prerequisite)
- Knowledge Catalog docs: `https://docs.cloud.google.com/dataplex/docs/catalog-overview`
- Metadata import docs: `https://docs.cloud.google.com/dataplex/docs/ingest-custom-sources`

---

## Deliverables

When this task is complete:

1. Three custom **Aspect Types** defined in Knowledge Catalog:
   - `oilfield.asset_specification` — physical/operational specs of a canonical asset
   - `oilfield.cross_system_aliases` — SAP material number, Maximo equipment ID, FDP config ID, InTouch spec refs
   - `oilfield.functional_equivalence` — equivalence relationships with confidence and rationale
2. One custom **Entry Group** for oilfield canonical assets
3. **Canonical Entries** for every asset in `data/canonical_assets.json` (target: 80-120 entries), each with the relevant Aspects applied
4. Functional equivalence relationships expressed as Aspect data on the relevant Entries
5. Knowledge Catalog ingestion script (`knowledge_catalog/setup.py`) that builds the catalog from the JSON data files — idempotent, re-runnable
6. The prebuilt MCP `lookup_context` and `search_entries` tools return our canonical entities with all aliases
7. Cargo-plane integration test now uses real Knowledge Catalog (not JSON files) for equivalence reasoning
8. Demo drill-down: when the canvas shows the Knowledge Catalog drawer for Tool X, it displays the actual catalog entry with all aliases

---

## Step-by-step instructions

### Step 1 — Define the oilfield Aspect Types

Aspect Types in Knowledge Catalog are schema definitions for the metadata that gets attached to Entries. Think of them as Pydantic models for catalog metadata. Create three for our domain:

`knowledge_catalog/aspect_types/asset_specification.yaml`:

```yaml
name: oilfield-asset-specification
description: |
  Physical and operational specifications of a canonical oilfield asset.
  Captures the equipment-class-level properties that drive substitution,
  procurement, and operational decisions.
metadata_template:
  type: record
  recordFields:
    - name: category
      type: enum
      enumValues:
        - downhole_tool
        - completions_equipment
        - drilling_tool
        - mwd_lwd
        - mud_motor
        - wireline_tool
        - surface_equipment
    - name: subcategory
      type: string
    - name: operating_temp_max_c
      type: integer
    - name: operating_pressure_max_psi
      type: integer
    - name: outer_diameter_in
      type: double
    - name: manufacturer
      type: string
    - name: introduced_year
      type: integer
```

`knowledge_catalog/aspect_types/cross_system_aliases.yaml`:

```yaml
name: oilfield-cross-system-aliases
description: |
  Cross-system identifiers for a canonical asset. Maps SAP, Maximo, FDP, and
  InTouch references to a single canonical Entry. This Aspect is the resolution
  point for Issue 4 — taxonomic chaos across enterprise systems.
metadata_template:
  type: record
  recordFields:
    - name: sap_material_number
      type: string
    - name: maximo_equipment_id
      type: string
    - name: fdp_config_id
      type: string
    - name: intouch_spec_refs
      type: array
      arrayItems:
        type: string
```

`knowledge_catalog/aspect_types/functional_equivalence.yaml`:

```yaml
name: oilfield-functional-equivalence
description: |
  Functional equivalence relationships between canonical assets. Captures
  which assets can substitute for one another, with confidence score and
  rationale citation (typically an InTouch spec reference).
metadata_template:
  type: record
  recordFields:
    - name: equivalent_canonical_id
      type: string
    - name: confidence
      type: double
    - name: rationale_source
      type: string
    - name: customer_compatibility_overrides
      type: array
      arrayItems:
        type: record
        recordFields:
          - name: customer_id
            type: string
          - name: override_confidence
            type: double
```

### Step 2 — Build the ingestion script

`knowledge_catalog/setup.py`:

```python
"""Ingest synthetic data files into Knowledge Catalog as Entries with Aspects.

Idempotent: re-running this script updates existing Entries rather than
duplicating them. Safe to run multiple times during development.
"""

import json
import os
from pathlib import Path

from google.cloud import dataplex_v1
from google.cloud.dataplex_v1.types import (
    AspectType,
    Entry,
    EntryGroup,
    EntryType,
)

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
DATA_DIR = Path(__file__).parent.parent / "data"

client = dataplex_v1.CatalogServiceClient()


def ensure_entry_group():
    """Create or update the oilfield canonical assets Entry Group."""
    parent = f"projects/{PROJECT}/locations/{LOCATION}"
    entry_group_id = "oilfield-canonical-assets"
    name = f"{parent}/entryGroups/{entry_group_id}"

    # DEMO NARRATION: "We're loading the entire canonical asset taxonomy into
    # Knowledge Catalog under one Entry Group. This becomes the single source
    # of truth for what Tool X means, regardless of how SAP, Maximo, or FDP
    # name it internally."

    try:
        client.get_entry_group(name=name)
        print(f"Entry Group {entry_group_id} exists")
    except Exception:
        client.create_entry_group(
            parent=parent,
            entry_group_id=entry_group_id,
            entry_group=EntryGroup(
                display_name="Oilfield Canonical Assets",
                description="Canonical entity model for oilfield service assets",
            ),
        )
        print(f"Created Entry Group {entry_group_id}")
    return name


def ensure_aspect_types():
    """Create or update the three custom Aspect Types from YAML definitions."""
    parent = f"projects/{PROJECT}/locations/{LOCATION}"
    aspect_type_files = [
        ("asset_specification.yaml", "oilfield-asset-specification"),
        ("cross_system_aliases.yaml", "oilfield-cross-system-aliases"),
        ("functional_equivalence.yaml", "oilfield-functional-equivalence"),
    ]
    for filename, aspect_type_id in aspect_type_files:
        # Load YAML, convert to AspectType proto, create-or-update via API
        # (Implementation: use Dataplex AspectType create or replace pattern)
        print(f"Aspect Type {aspect_type_id} ensured")
    return [f"{parent}/aspectTypes/{atid}" for _, atid in aspect_type_files]


def ensure_entry_type():
    """Create the canonical asset Entry Type that uses our Aspect Types."""
    parent = f"projects/{PROJECT}/locations/{LOCATION}"
    entry_type_id = "oilfield-canonical-asset"
    # Create Entry Type that requires our three Aspect Types
    print(f"Entry Type {entry_type_id} ensured")
    return f"{parent}/entryTypes/{entry_type_id}"


def load_data() -> tuple[list[dict], dict, list[dict]]:
    """Load the synthetic data files."""
    with open(DATA_DIR / "canonical_assets.json") as f:
        canonical_assets = json.load(f)
    with open(DATA_DIR / "cross_system_aliases.json") as f:
        cross_system_aliases = json.load(f)
    with open(DATA_DIR / "functional_equivalences.json") as f:
        functional_equivalences = json.load(f)
    return canonical_assets, cross_system_aliases, functional_equivalences


def build_equivalences_by_canonical_id(
    equivalences: list[dict],
) -> dict[str, list[dict]]:
    """Index equivalences by canonical_id for fast lookup during Entry creation."""
    indexed: dict[str, list[dict]] = {}
    for eq in equivalences:
        a, b = eq["canonical_id_a"], eq["canonical_id_b"]
        indexed.setdefault(a, []).append({
            "equivalent_canonical_id": b,
            "confidence": eq["confidence"],
            "rationale_source": eq["rationale_source"],
            "customer_compatibility_overrides": eq.get("customer_compatibility_overrides", []),
        })
        # Symmetric — also index from b's perspective
        indexed.setdefault(b, []).append({
            "equivalent_canonical_id": a,
            "confidence": eq["confidence"],
            "rationale_source": eq["rationale_source"],
            "customer_compatibility_overrides": eq.get("customer_compatibility_overrides", []),
        })
    return indexed


def create_entry_for_asset(
    asset: dict,
    aliases: dict,
    equivalents: list[dict],
    entry_group: str,
    entry_type: str,
) -> Entry:
    """Build the Entry proto for a single canonical asset."""
    canonical_id = asset["canonical_id"]
    alias_data = aliases.get(canonical_id, {})

    aspects = {
        f"projects/{PROJECT}/locations/{LOCATION}/aspectTypes/oilfield-asset-specification": {
            "data": {
                "category": asset["category"],
                "subcategory": asset.get("subcategory"),
                "operating_temp_max_c": asset["specifications"].get("operating_temp_max_c"),
                "operating_pressure_max_psi": asset["specifications"].get("operating_pressure_max_psi"),
                "outer_diameter_in": asset["specifications"].get("outer_diameter_in"),
                "manufacturer": asset.get("manufacturer"),
                "introduced_year": asset.get("introduced_year"),
            }
        },
        f"projects/{PROJECT}/locations/{LOCATION}/aspectTypes/oilfield-cross-system-aliases": {
            "data": {
                "sap_material_number": alias_data.get("sap_material_number"),
                "maximo_equipment_id": alias_data.get("maximo_equipment_id"),
                "fdp_config_id": alias_data.get("fdp_config_id"),
                "intouch_spec_refs": alias_data.get("intouch_spec_refs", []),
            }
        },
    }
    if equivalents:
        aspects[f"projects/{PROJECT}/locations/{LOCATION}/aspectTypes/oilfield-functional-equivalence"] = {
            "data": {"equivalents": equivalents}
        }

    return Entry(
        entry_type=entry_type,
        aspects=aspects,
        entry_source={
            "display_name": asset["canonical_label"],
            "description": f"Canonical {asset['category']}: {asset['canonical_label']}",
            "labels": {"category": asset["category"]},
        },
    )


def main():
    """End-to-end Knowledge Catalog setup."""
    print(f"Setting up Knowledge Catalog in {PROJECT}/{LOCATION}")

    entry_group = ensure_entry_group()
    aspect_types = ensure_aspect_types()
    entry_type = ensure_entry_type()

    canonical_assets, cross_system_aliases, functional_equivalences = load_data()
    equivalences_by_id = build_equivalences_by_canonical_id(functional_equivalences)

    print(f"Ingesting {len(canonical_assets)} canonical assets...")
    for asset in canonical_assets:
        canonical_id = asset["canonical_id"]
        equivalents = equivalences_by_id.get(canonical_id, [])
        entry = create_entry_for_asset(
            asset, cross_system_aliases, equivalents, entry_group, entry_type,
        )
        entry_name = f"{entry_group}/entries/{canonical_id}"

        try:
            client.get_entry(name=entry_name)
            client.update_entry(entry=entry)
            print(f"  Updated {canonical_id}: {asset['canonical_label']}")
        except Exception:
            client.create_entry(parent=entry_group, entry_id=canonical_id, entry=entry)
            print(f"  Created {canonical_id}: {asset['canonical_label']}")

    print("Knowledge Catalog setup complete.")


if __name__ == "__main__":
    main()
```

This is a skeleton — the actual Dataplex SDK call signatures need to be verified against the current Python client. Claude Code should consult `https://cloud.google.com/python/docs/reference/dataplex/latest` for exact method signatures.

### Step 3 — Add Makefile target

```makefile
.PHONY: setup-knowledge-catalog

setup-knowledge-catalog:
	uv run python knowledge_catalog/setup.py
```

### Step 4 — Run the setup and verify

```bash
make setup-knowledge-catalog
```

After running, verify via the Knowledge Catalog console:

1. Open the Dataplex section of the GCP Console
2. Navigate to Catalog → Entry Groups → oilfield-canonical-assets
3. Verify the entries exist with the right Aspect data
4. Click into Tool X (canonical_id = TX-001) and confirm:
   - Asset specification Aspect with category=downhole_tool
   - Cross-system aliases Aspect with sap_material_number=MAT-67890, maximo_equipment_id=EQ-12345, fdp_config_id=TX-CONFIG-A
   - Functional equivalence Aspect listing TX-007 as equivalent

### Step 5 — Refactor the orchestrator's equivalence lookup

The `equivalence_lookup_agent` LLM node (built in TASK-04) currently queries synthetic data through the `asset-equivalence` skill. Now it queries Knowledge Catalog through the prebuilt MCP tools.

Update `src/orchestrator_agent/core/nodes/equivalence_lookup.py`:

```python
"""LLM node: reason about functional equivalence using Knowledge Catalog MCP."""

from google.adk import Agent
from google.adk.tools.mcp import MCPClient

from ....schemas import EquivalentAssetCandidate

# Knowledge Catalog MCP client — prebuilt tools from genai-toolbox
kc_mcp = MCPClient(server_url="http://localhost:8100")


# DEMO NARRATION: "This is where Issue 4 dissolves visibly. The equivalence
# agent is calling Knowledge Catalog's lookup_context — a prebuilt MCP tool
# that ships with the platform. We didn't build that. The catalog returns
# the canonical Tool X entry with all its aliases — SAP material number,
# Maximo equipment ID, FDP config ID — and the functional equivalence Aspect
# listing Tool X-V7 as a substitute per InTouch spec §3.2. One call. One
# canonical entity. No taxonomic chaos."
equivalence_lookup_agent = Agent(
    name="equivalence_lookup",
    model="gemini-3-1-pro-preview",
    instruction="""You determine the best functional equivalent for a canonical
asset using Knowledge Catalog.

1. Call lookup_context with the canonical_id of the requested asset.
2. Review the functional_equivalence aspect data.
3. For each candidate, check the customer_compatibility_overrides for the
   specific customer.
4. Return the highest-confidence equivalent that the customer accepts.

Return a structured EquivalentAssetCandidate.""",
    output_schema=EquivalentAssetCandidate,
    tools=[
        kc_mcp.tool("lookup_context"),
        kc_mcp.tool("search_entries"),
    ],
)
```

### Step 6 — Update integration test

```python
async def test_cargo_plane_uses_knowledge_catalog():
    """Cargo-plane scenario should call Knowledge Catalog's prebuilt MCP tools."""
    response = await root_agent.run_async(user_input="...", session_id="test-kc")
    plan = SourcingPlan.model_validate(response.output)

    # Verify trace shows Knowledge Catalog MCP calls
    trace = response.cloud_trace
    kc_spans = [s for s in trace.spans if "lookup_context" in s.name or "search_entries" in s.name]
    assert len(kc_spans) >= 1, "Expected at least one Knowledge Catalog MCP call"

    # Verify the canonical entity was retrieved with all aliases
    lookup_span = next(s for s in kc_spans if "lookup_context" in s.name)
    response_data = lookup_span.attributes.get("response_body")
    assert "sap_material_number" in response_data
    assert "maximo_equipment_id" in response_data

    # Scenario still works
    assert plan.primary_option.source_location.label == "Lagos, Nigeria"
    assert plan.avoided_cost_usd > 300_000
```

### Step 7 — Document for the canvas team

The Operations Canvas needs to render the Knowledge Catalog entity drawer (Beat 5 and Beat 8 of `persona3_canvas_storyboard.md`). The data structure it receives is what the prebuilt `lookup_context` tool returns. Add to `docs/canvas_data_contracts.md`:

```markdown
## Knowledge Catalog entity payload (canvas Beat 5, 8)

When the canvas needs to render the entity drawer, it receives a payload
from the Orchestrator's equivalence_lookup node containing:

{
  "canonical_id": "TX-001",
  "canonical_label": "Tool X",
  "aspects": {
    "asset_specification": { ... },
    "cross_system_aliases": {
      "sap_material_number": "MAT-67890",
      "maximo_equipment_id": "EQ-12345",
      "fdp_config_id": "TX-CONFIG-A",
      "intouch_spec_refs": ["spec-3.2-2024", "compatibility-cc-204"]
    },
    "functional_equivalence": {
      "equivalents": [
        {
          "equivalent_canonical_id": "TX-007",
          "confidence": 0.92,
          "rationale_source": "InTouch Spec §3.2"
        }
      ]
    }
  }
}

This is the data the canvas drawer should render visually.
```

### Step 8 — Commit

```bash
git add .
git commit -m "feat: Knowledge Catalog setup with custom Aspect Types and canonical Entries (TASK-06)"
git push
```

---

## Acceptance criteria

- [ ] Three Aspect Types created in Knowledge Catalog (verifiable in console)
- [ ] One Entry Group `oilfield-canonical-assets` created
- [ ] 80-120 canonical Entries created with Aspects applied
- [ ] `knowledge_catalog/setup.py` is idempotent (running twice produces the same state)
- [ ] `make setup-knowledge-catalog` runs clean from a fresh clone
- [ ] Knowledge Catalog console shows the entries with correct Aspect data
- [ ] Prebuilt `lookup_context` MCP tool returns canonical Tool X entry with all aliases when queried
- [ ] Orchestrator's `equivalence_lookup_agent` uses Knowledge Catalog MCP (not synthetic JSON)
- [ ] Cargo-plane integration test passes against Knowledge Catalog-backed setup
- [ ] Cloud Trace shows distinct spans for `lookup_context` and `search_entries`
- [ ] `docs/canvas_data_contracts.md` documents the entity payload shape
- [ ] Commit pushed

---

## Common pitfalls

**Dataplex API signature drift.** The Python client for Dataplex evolves. Verify method signatures against the current docs before writing `setup.py`. The skeleton above shows the intent; the actual API calls may need adjustment.

**Aspect Type metadata template format.** Knowledge Catalog uses Apache Avro-style schemas for Aspect Types. Get the type names right (`record`, `enum`, `string`, `integer`, `double`, `array`, `boolean`). Wrong types cause silent failures during Entry creation.

**Idempotency.** The setup script must handle re-runs. Use try-except patterns to either get-and-update or create. Without idempotency, every run during development pollutes the catalog with duplicates.

**Permissions.** The script needs `roles/dataplex.editor` (or finer-grained admin roles) on the project. The agent at runtime needs `roles/dataplex.catalogViewer` to call the prebuilt MCP tools.

**Long latency on first ingestion.** Creating 100+ entries with multiple aspects each takes time (each is an API call). The script should print progress so a developer can tell it's making forward progress.

**Symmetric equivalence relationships.** If `TX-001 ≡ TX-007`, both directions need to be queryable. The `build_equivalences_by_canonical_id` function above handles this — each equivalence row produces two index entries.

**Knowledge Catalog regions.** Knowledge Catalog is regional. Ensure `GOOGLE_CLOUD_LOCATION` is `us-central1` consistently, or all queries from agents in other regions fail.

**DATAPLEX_PROJECT env var on the MCP toolbox.** From TASK-05: the prebuilt dataplex toolbox reads `DATAPLEX_PROJECT`. If it's set to a different project than where Knowledge Catalog content lives, `lookup_context` returns empty results. Cross-check both project IDs match.

---

## References

- Knowledge Catalog overview: `https://docs.cloud.google.com/dataplex/docs/catalog-overview`
- Manage entries and aspects: `https://docs.cloud.google.com/dataplex/docs/enrich-entries-metadata`
- Custom source ingestion: `https://docs.cloud.google.com/dataplex/docs/ingest-custom-sources`
- Dataplex Python client: `https://cloud.google.com/python/docs/reference/dataplex/latest`
- Prebuilt MCP tools: `https://docs.cloud.google.com/dataplex/docs/pre-built-tools-with-mcp-toolbox`

---

*When TASK-06 is complete, the cargo-plane scenario runs entirely on real platform components — Workflow on Agent Runtime, MCP servers via genai-toolbox, real Knowledge Catalog with custom Aspect Types. The next batch of tasks moves to Memory Bank, the Operations Canvas frontend, and governance.*
