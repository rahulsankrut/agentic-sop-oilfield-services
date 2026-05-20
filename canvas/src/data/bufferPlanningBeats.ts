/**
 * Beat-by-beat storyboard for Persona 2 (Tomas, Permian) — 6 beats over
 * roughly 3 minutes within his 5-minute Gemini Enterprise segment.
 *
 * Reuses the existing ``Beat`` + ``ScenarioState`` shape from
 * ``demoScenarios.ts`` so the same ``useScenario`` hook and
 * ``CanvasShell`` from TASK-08 can drive this view without changes.
 *
 * Most ScenarioState fields (assets, arcs, drawer entity, cost banner,
 * map center/zoom) are unused for buffer planning — populated with
 * inert defaults. The fields that matter for this view:
 * - ``showTimeline`` — whether the Recharts ComposedChart is rendered
 * - ``bufferOption`` — which BufferOption the slider snaps to
 * - ``highlightWeek`` — optional W## label to draw a reference line
 * - ``drawerOpen`` — whether the cost reconciliation panel is visible
 */

import type { Beat, ScenarioState } from "./demoScenarios";

// Permian (Midland) centroid — only matters if the page accidentally
// renders a map; it doesn't, so this is purely defensive.
const PERMIAN_CENTER: [number, number] = [-102.1, 31.92];

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

export const bufferPlanningBeats: Beat[] = [
  {
    id: "beat-0-pre-demo",
    narration:
      'Tomas: "Frac pump Q3 buffer plan for ExxonMobil-Permian." Canvas at rest; agent is loading.',
    state: baseState({
      showTimeline: false,
      bufferOption: "conservative",
      drawerOpen: false,
    }),
  },
  {
    id: "beat-1-forecast-loaded",
    narration:
      "Capacity Planning Agent fetched the 12-week probabilistic forecast from BigQuery. p10/p50/p90 demand bands and the 40-unit fleet capacity baseline are on screen.",
    state: baseState({
      showTimeline: true,
      bufferOption: "conservative",
      drawerOpen: false,
    }),
  },
  {
    id: "beat-2-spike-highlighted",
    narration:
      "Agent flags the W27 spike: p90 demand reaches 56 units against a 40-unit fleet. Buffer planning needed.",
    state: baseState({
      showTimeline: true,
      bufferOption: "conservative",
      highlightWeek: "W27",
      drawerOpen: false,
    }),
  },
  {
    id: "beat-3-conservative-default",
    narration:
      "Memory Bank surfaced Tomas's default risk tolerance: Conservative. Agent recommends 18% buffer. Buffered-capacity overlay (green) sits ~7 units above fleet baseline.",
    state: baseState({
      showTimeline: true,
      bufferOption: "conservative",
      highlightWeek: "W27",
      drawerOpen: true,
    }),
  },
  {
    id: "beat-4-slider-to-balanced",
    narration:
      "Tomas drags the slider to Balanced. Buffer drops to 12%. Idle cost falls $420K; late-start exposure rises $230K. On-time probability: 88%.",
    state: baseState({
      showTimeline: true,
      bufferOption: "balanced",
      highlightWeek: "W27",
      drawerOpen: true,
    }),
  },
  {
    id: "beat-5-approved",
    narration:
      'Approved: 12% buffer for Q3 ExxonMobil-Permian. Capacity Planning Agent syncs to Maximo and notifies the basin team. Decision saved to Memory Bank ("buffer_outcomes" topic).',
    state: baseState({
      showTimeline: true,
      bufferOption: "balanced",
      drawerOpen: true,
    }),
  },
];
