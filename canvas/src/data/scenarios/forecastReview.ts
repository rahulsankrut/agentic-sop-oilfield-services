/**
 * forecastReview.ts
 *
 * Beat-by-beat storyboard for Persona 1 (David, Permian Basin Director) —
 * demand-sensing / Q4 forecast review. Six beats over ~3 minutes inside
 * his Gemini Enterprise segment.
 *
 * The canvas surface for David is NOT a Mapbox globe (cargo-plane's spatial
 * canvas) and NOT a Recharts timeline (Tomas's buffer chart) — it's a grid
 * of basin tiles, each showing a baseline forecast, YoY delta, model
 * confidence, and (after override) David's revised number plus the
 * structured rationale tags the Forecast Review Agent extracted from his
 * note. The bottom of the canvas surfaces a ForecastDeltaBanner that rolls
 * up the total Δ-vs-baseline once both overrides are applied.
 *
 * Source of truth for the choreography:
 *   docs/planning/agentic_sop_oilfield_services_brief.md §"Persona 1"
 *
 * Like the other scenarios, the beat state is the COMPLETE intended canvas
 * snapshot — `useScenario` just hands the current beat's `state` to the
 * renderer. Most ScenarioState fields (assets, arcs, drawer, costBanner)
 * are inert for this view; only `basinTiles`, `forecastDelta`, and
 * `forecastToast` matter.
 */

import type {
  BasinTileData,
  Beat,
  ForecastDeltaBannerState,
  ScenarioState,
} from "@/data/demoScenarios";

// Permian centroid — only matters if a stray map renders. Inert here.
const PERMIAN_CENTER: [number, number] = [-102.1, 31.92];

// ---------------------------------------------------------------------------
// Synthetic Q4 baseline forecast — realistic for an oilfield services major's
// quarterly P&L. Total ≈ $655M across the seven basins. Permian dominates;
// the long tail (Bohai, Asia-Pacific) is small but model-confident.
// ---------------------------------------------------------------------------

const BASELINE_TILES: BasinTileData[] = [
  {
    id: "permian",
    label: "Permian",
    baseline_usd: 215_000_000,
    yoy_pct: 4,
    confidence: "high",
  },
  {
    id: "gulf_of_mexico",
    label: "Gulf of Mexico",
    baseline_usd: 145_000_000,
    yoy_pct: 1,
    confidence: "high",
  },
  {
    id: "west_africa",
    label: "West Africa",
    baseline_usd: 95_000_000,
    yoy_pct: -3,
    confidence: "medium",
  },
  {
    id: "north_sea",
    label: "North Sea",
    baseline_usd: 80_000_000,
    yoy_pct: -1,
    confidence: "medium",
  },
  {
    id: "south_china_sea",
    label: "South China Sea",
    baseline_usd: 50_000_000,
    yoy_pct: 2,
    confidence: "low",
  },
  {
    id: "bohai",
    label: "Bohai",
    baseline_usd: 40_000_000,
    yoy_pct: 0,
    confidence: "low",
  },
  {
    id: "asia_pacific",
    label: "Asia-Pacific",
    baseline_usd: 30_000_000,
    yoy_pct: 5,
    confidence: "medium",
  },
];

// David's two overrides: Permian -13% (rig count slowdown not captured in
// the Q3 cut) and Gulf of Mexico -10% (three operator programs deferred to
// 2026 Q1). We use Gulf of Mexico as the second override target rather than
// adding a separate "Eagle Ford" tile — keeps the basin set aligned with
// `data/sap_workforce.json` and avoids dragging in an off-list basin.
const PERMIAN_OVERRIDE_USD = 186_000_000; // 215 → 186 ≈ -13%
const GULF_OVERRIDE_USD = 130_000_000; // 145 → 130 ≈ -10%

const PERMIAN_TAGS = [
  "rig_count_decline",
  "operator_pause",
  "permian_specific",
];
const GULF_TAGS = ["operator_delays", "program_deferral", "gulf_specific"];

// Total Δ-vs-baseline once both overrides land.
const BASELINE_TOTAL = BASELINE_TILES.reduce(
  (acc, t) => acc + t.baseline_usd,
  0,
);
const REVISED_TOTAL =
  BASELINE_TOTAL -
  (215_000_000 - PERMIAN_OVERRIDE_USD) -
  (145_000_000 - GULF_OVERRIDE_USD);
const TOTAL_DELTA_USD = REVISED_TOTAL - BASELINE_TOTAL; // negative

// ---------------------------------------------------------------------------
// State helpers
// ---------------------------------------------------------------------------

function baseState(overrides: Partial<ScenarioState>): ScenarioState {
  return {
    mapCenter: PERMIAN_CENTER,
    mapZoom: 5,
    assets: [],
    arcs: [],
    drawer: { open: false },
    costBanner: { visible: false },
    ...overrides,
  };
}

function tilesWith(
  patches: Record<string, Partial<BasinTileData>>,
): BasinTileData[] {
  return BASELINE_TILES.map((t) => {
    const patch = patches[t.id];
    return patch ? { ...t, ...patch } : { ...t };
  });
}

const DELTA_HIDDEN: ForecastDeltaBannerState = { visible: false };
const DELTA_APPLIED: ForecastDeltaBannerState = {
  visible: true,
  delta_usd: TOTAL_DELTA_USD,
  baseline_total_usd: BASELINE_TOTAL,
  revised_total_usd: REVISED_TOTAL,
  overrides_count: 2,
};

// ---------------------------------------------------------------------------
// The six beats
// ---------------------------------------------------------------------------

export const forecastReviewBeats: Beat[] = [
  // ---- Beat 0: at rest. David's chat message visible; no tiles loaded. ----
  // DEMO NARRATION: "David is the Permian Basin Director. He owns the Q4
  // completions revenue forecast for his region — and he's about to argue
  // with the model. The canvas is empty; the ML forecast tile in the corner
  // is what BigQuery ML produced overnight."
  {
    id: "beat-0-pre-demo",
    narration:
      'David: "Show me Q4 by basin — I want to override two basins where the model is missing the rig-count slowdown." The Forecast Review Agent is spinning up; the canvas is at rest.',
    state: baseState({
      basinTiles: [],
      forecastDelta: DELTA_HIDDEN,
    }),
  },

  // ---- Beat 1: forecast loaded — all seven basin tiles render. ----
  // DEMO NARRATION: "The agent pulled the Q4 baseline from the BigQuery
  // measure. Seven basins, confidence pills from the model itself.
  // Permian and Gulf are 'high' — the model is sure. South China Sea
  // and Bohai are 'low' — the model is hedging."
  {
    id: "beat-1-forecast-loaded",
    narration:
      "Capacity Planning Agent pulled the Q4 baseline from BigQuery ML. Seven basins on screen with YoY delta and model-confidence pills. Permian + Gulf of Mexico anchor the forecast at $360M combined.",
    state: baseState({
      basinTiles: tilesWith({}),
      forecastDelta: DELTA_HIDDEN,
    }),
  },

  // ---- Beat 2: override prompt appears next to the Permian tile. ----
  // DEMO NARRATION: "David clicks Permian. Agent Inbox surfaces a prompt
  // from the Forecast Review Agent: 'Why is the model wrong here?' He
  // picks one of the structured options — rig count declined 8% MoM,
  // not captured in the Q3 cut."
  {
    id: "beat-2-override-prompt",
    narration:
      'David selects Permian. The Forecast Review Agent surfaces a structured prompt — "Why is the model wrong here?" — next to the tile. David picks: "Rig count declined 8% MoM, not captured in the Q3 cut."',
    state: baseState({
      basinTiles: tilesWith({
        permian: { active: true, promptOpen: true },
      }),
      forecastDelta: DELTA_HIDDEN,
    }),
  },

  // ---- Beat 3: rationale extracted → chips render on Permian tile. ----
  // DEMO NARRATION: "Gemini extracts structured rationale tags from the
  // freeform note. These aren't just labels — they're how the model learns.
  // Knowledge Catalog routes them into the Forecast Review agent's
  // Memory Bank 'rationale_patterns' topic."
  {
    id: "beat-3-rationale-extracted",
    narration:
      "The Forecast Review Agent extracts structured rationale tags from David's note — rig_count_decline, operator_pause, permian_specific. The chips render under the Permian tile. Same flow runs for Gulf of Mexico: operator_delays, program_deferral.",
    state: baseState({
      basinTiles: tilesWith({
        permian: {
          active: true,
          promptOpen: false,
          rationaleTags: PERMIAN_TAGS,
        },
        gulf_of_mexico: {
          active: true,
          rationaleTags: GULF_TAGS,
        },
      }),
      forecastDelta: DELTA_HIDDEN,
    }),
  },

  // ---- Beat 4: overrides applied. Tiles re-render with new numbers. ----
  // DEMO NARRATION: "And the overrides land. Permian drops from $215M to
  // $186M. Gulf of Mexico from $145M to $130M. The delta banner at the
  // bottom rolls up: $44M off the Q4 plan — and the model is being
  // re-ingested with David's rationale so next quarter it learns."
  {
    id: "beat-4-overrides-applied",
    narration:
      "Overrides applied. Permian baseline drops from $215M to $186M. Gulf of Mexico from $145M to $130M. Δ vs baseline rolls up at the bottom — and the agent re-ingests the rationale-tagged overrides into BigQuery ML for next quarter's run.",
    state: baseState({
      basinTiles: tilesWith({
        permian: {
          active: false,
          override_usd: PERMIAN_OVERRIDE_USD,
          rationaleTags: PERMIAN_TAGS,
        },
        gulf_of_mexico: {
          active: false,
          override_usd: GULF_OVERRIDE_USD,
          rationaleTags: GULF_TAGS,
        },
      }),
      forecastDelta: DELTA_APPLIED,
    }),
  },

  // ---- Beat 5: confirmation toast — forecast v2 saved. ----
  // DEMO NARRATION: "The agent saves the revised forecast as v2. The
  // override rationale is now structured signal living in Memory Bank
  // and Knowledge Catalog. The boundary between David's regional
  // knowledge and the model is closed."
  {
    id: "beat-5-saved-v2",
    narration:
      "Two overrides applied + re-ingested into the model. Q4 forecast saved as v2. The 'model improving' indicator on David's profile ticks up — historical override magnitude is shrinking quarter over quarter as the model learns from prior rationale.",
    state: baseState({
      basinTiles: tilesWith({
        permian: {
          override_usd: PERMIAN_OVERRIDE_USD,
          rationaleTags: PERMIAN_TAGS,
        },
        gulf_of_mexico: {
          override_usd: GULF_OVERRIDE_USD,
          rationaleTags: GULF_TAGS,
        },
      }),
      forecastDelta: DELTA_APPLIED,
      forecastToast: {
        visible: true,
        message:
          "Two overrides applied + re-ingested into the model. Q4 forecast saved as v2.",
      },
    }),
  },
];
