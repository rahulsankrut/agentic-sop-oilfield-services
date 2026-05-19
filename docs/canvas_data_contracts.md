# Canvas Data Contracts

Shape of the structured events the Operations Canvas frontend consumes from
the Capacity Orchestrator. Each section names a canvas beat (see
`docs/planning/persona3_canvas_storyboard.md`), the orchestrator node that
emits the payload, and the JSON shape the canvas should render.

The canvas team owns the rendering; the orchestrator team owns the shape. If
either side wants to evolve a field, change it here first and ping the other
team.

---

## Knowledge Catalog entity payload (canvas Beat 5, 8)

**Beats:** Beat 5 ("the pivot to equivalence") and Beat 8 ("how did it
know?" drill-down) in `persona3_canvas_storyboard.md`.

**Orchestrator node:** `equivalence_lookup` (see
`src/orchestrator_agent/core/nodes/equivalence_lookup.py`). The node calls
the managed Knowledge Catalog MCP server (`https://dataplex.googleapis.com/mcp`)
through Agent Gateway and reasons over the response. The canvas does not
receive the raw MCP response — the orchestrator projects the relevant slice
into the shape below before emitting it as a structured event.

**Shape:** the canvas drawer for the canonical entity receives one JSON
object per canonical asset surfaced by the equivalence lookup:

```json
{
  "canonical_id": "TX-001",
  "canonical_label": "Tool X",
  "entry_name": "projects/<PROJECT>/locations/us-central1/entryGroups/oilfield-canonical-assets/entries/TX-001",
  "aspects": {
    "asset_specification": {
      "category": "downhole_tool",
      "subcategory": "rotary_steerable",
      "operating_temp_max_c": 175,
      "operating_pressure_max_psi": 25000,
      "outer_diameter_in": 6.75,
      "manufacturer": "Acme Downhole",
      "introduced_year": 2019
    },
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
          "equivalent_canonical_label": "Tool X-V7",
          "confidence": 0.92,
          "rationale_source": "InTouch Spec §3.2",
          "customer_compatibility_overrides": [
            {
              "customer_id": "gulf-petroleum",
              "override_confidence": 0.95
            }
          ]
        }
      ]
    }
  }
}
```

### Field notes

- **`canonical_id`** — the catalog-canonical id (e.g. `TX-001`). Stable, used
  by every downstream node to refer back to the asset.
- **`canonical_label`** — human label for the drawer header ("Tool X").
- **`entry_name`** — the full Knowledge Catalog resource name. Optional for
  rendering; useful for a "View in Knowledge Catalog console" deep link.
- **`aspects.asset_specification`** — physical/operational specs, as defined
  by `knowledge_catalog/aspect_types/asset_specification.yaml`. Render as a
  compact spec table in the drawer body.
- **`aspects.cross_system_aliases`** — the headline content for Beat 5 and
  Beat 8. Render each non-null alias as a row, prefixed with the system logo
  (SAP, Maximo, FDP, InTouch). `intouch_spec_refs` is an array; render as a
  bulleted list. This is the visualization of "Issue 4 dissolved".
- **`aspects.functional_equivalence.equivalents`** — array; for the cargo-plane
  scenario there's one entry (`TX-007`). Render each as a card under
  "Functionally equivalent variants" with `confidence` as a small indicator
  ("0.92 — high confidence — same operating envelope") and `rationale_source`
  as the citation. `customer_compatibility_overrides` is optional; when
  present for the active customer, render the override confidence instead of
  the base confidence.

### Render-when-missing rules

- If an Aspect is absent on the entry, omit the section from the drawer
  rather than rendering an empty placeholder. The Aspect Types are loose
  (most fields nullable), so partial entries are expected during early
  ingestion.
- If `aspects.functional_equivalence.equivalents` is `[]`, render the
  "Functionally equivalent variants" header with the text "No catalogued
  substitutes" — this signals to the demoer that the agent will have to fall
  back to the naive baseline (Darwin cargo charter) for the scenario.

### Beat 5 vs Beat 8

The same payload backs both beats; the canvas decides the depth of the
render:

- **Beat 5** (auto): drawer shows `canonical_label`, the four
  `cross_system_aliases` rows collapsed, and a single-line summary of the
  top-confidence equivalent.
- **Beat 8** (interactive, demoer-triggered): drawer expands to show all
  Aspects, including the full `functional_equivalence` rationale and any
  customer-specific overrides. No new event is emitted; the canvas just
  re-renders the same payload at a deeper level of detail.
