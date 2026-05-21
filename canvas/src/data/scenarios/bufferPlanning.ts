/**
 * bufferPlanning.ts — Persona 2 (Tomas, West Texas Fleet Scheduler) beats.
 *
 * Storyboard:
 *
 *   Beat 0 — chat at rest: Tomas asks for Permian fleet utilization and
 *            the 14→8 day buffer trade-off. Canvas pre-renders the 30-day
 *            fleet timeline at the current 14-day buffer.
 *   Beat 1 — current state surfaced: 14-day buffer, 92% on-time, 68%
 *            utilization, $0 capex deferred. Risk tolerance at 0.5.
 *   Beat 2 — model the buffer drop: agent runs the 14→8 day scenario.
 *            On-time falls to 65%, utilization climbs to 84%, capex
 *            deferred = $4.5M. Daily timeline tightens (deployed line
 *            climbs).
 *   Beat 3 — risk tolerance up to 0.7: agent recommends a 10-day buffer
 *            instead. On-time = 78%, utilization = 76%, capex deferred =
 *            $3.2M. A safer compromise.
 *   Beat 4 — Tomas accepts: BufferCostReconciliation commit banner
 *            appears at the bottom of the canvas.
 *   Beat 5 — final: confirmation toast, persona timer rolls.
 *
 * Target time: ~3 minutes. Each Space press = next beat.
 *
 * All persona-shared spatial fields (assets, arcs, drawer, costBanner)
 * are zeroed because this scenario is chart-driven, not map-driven.
 * The `FleetTimelineChart` consumes `fleetTimelineData`; the
 * `RiskToleranceSlider` (continuous mode) consumes `riskTolerance`;
 * the `BufferCostReconciliation` reads the numeric buffer / on-time /
 * utilization / capex tiles.
 */

import type {
  Beat,
  FleetTimelineDayPoint,
  ScenarioState,
} from "@/data/demoScenarios";

// Permian (Midland) centroid — defensive, in case any sub-component falls
// back to map mode. The canvas page doesn't render a map for this scenario.
const PERMIAN_CENTER: [number, number] = [-102.1, 31.92];

/**
 * Generate a 30-day Permian fleet timeline with realistic variance.
 *
 * `bufferDays` controls how the `deployed` line tracks vs `active_rigs`:
 *   - Larger buffer → deployed line stays comfortably below the basin's
 *     active-rig count (lots of slack).
 *   - Smaller buffer → deployed line creeps closer to active rigs (less
 *     slack, more risk).
 *
 * Active-rig counts hover 280-330 to roughly match Baker Hughes Permian
 * data. Weekend (day % 7 === 0 or 6) dips by ~5-8% to reflect reality.
 * Deterministic — no `Math.random()` so the chart is stable across
 * reloads / reset.
 */
function buildTimeline(bufferDays: number): FleetTimelineDayPoint[] {
  const out: FleetTimelineDayPoint[] = [];

  // Base active-rigs profile: gentle climb week 1, dip mid-cycle, rebound
  // for the final stretch. Hand-picked offsets so the chart "looks alive".
  const baseProfile = [
    302, 305, 308, 311, 309, 297, 290, // week 1, weekend dip last two
    304, 312, 318, 322, 319, 308, 301, // week 2
    314, 320, 326, 324, 321, 309, 303, // week 3 (mid-cycle peak)
    317, 321, 318, 315, 312, 301, 294, // week 4
    308, 315, // partial week 5
  ];

  // Buffer ratio: 14d → deployed sits at ~68% of active; 8d → ~84%; 10d → ~76%.
  // Continuous mapping so non-canonical buffer values still render sensibly.
  const utilization = utilizationForBuffer(bufferDays) / 100;

  for (let i = 0; i < 30; i++) {
    const day = i + 1;
    const active = baseProfile[i] ?? 300;
    // Add a small day-to-day jitter on the deployed line that's NOT random —
    // a deterministic sin wave so reloads are stable.
    const jitter = Math.round(Math.sin(i * 0.7) * 3);
    const deployed = Math.round(active * utilization + jitter);
    out.push({ day, active_rigs: active, deployed });
  }

  return out;
}

/**
 * Closed-form mapping from buffer-days → utilization%. Calibrated so the
 * three canonical buffer values (14, 10, 8) hit the demo's headline
 * numbers (68%, 76%, 84%).
 */
function utilizationForBuffer(bufferDays: number): number {
  // Linear between (14d, 68%) and (8d, 84%) — slope = (84 - 68) / (8 - 14) = -2.67%/day
  const slope = (84 - 68) / (8 - 14);
  return Math.round(68 + slope * (bufferDays - 14));
}

/**
 * Closed-form mapping from buffer-days → on-time start rate%. Same
 * calibration: 14d → 92%, 10d → 78%, 8d → 65%. Curved (not linear) so
 * the safety drop accelerates near 8d.
 */
function onTimeForBuffer(bufferDays: number): number {
  // Quadratic fit through (14, 92), (10, 78), (8, 65).
  // y = a*x^2 + b*x + c. Solving:
  //   196a + 14b + c = 92
  //   100a + 10b + c = 78
  //    64a +  8b + c = 65
  // → a = 0.25, b = -2.0, c = 81
  const a = 0.25;
  const b = -2.0;
  const c = 81;
  return Math.round(a * bufferDays * bufferDays + b * bufferDays + c);
}

/**
 * Closed-form mapping from buffer-days → capex deferred (USD).
 * Anchored at 14d → 0 (status quo), 10d → $3.2M, 8d → $4.5M.
 */
function capexForBuffer(bufferDays: number): number {
  if (bufferDays >= 14) return 0;
  // Concave: most capex deferral comes from the first few days of buffer
  // removed; the last few days yield diminishing returns.
  const removed = 14 - bufferDays;
  // 4d removed → $3.2M; 6d removed → $4.5M.
  return Math.round(removed * 0.85e6 + Math.sqrt(removed) * 0.4e6);
}

// Exposed so the page can recompute the timeline reactively if needed
// (e.g. if a manual override surfaced between beats — not used in v1).
export { buildTimeline, utilizationForBuffer, onTimeForBuffer, capexForBuffer };

/** Convenience helper for stat tiles. */
export function fleetStatsForBuffer(bufferDays: number) {
  return {
    bufferDays,
    onTimeRatePct: onTimeForBuffer(bufferDays),
    utilizationPct: utilizationForBuffer(bufferDays),
    capexDeferredUsd: capexForBuffer(bufferDays),
  };
}

function baseState(overrides: Partial<ScenarioState>): ScenarioState {
  return {
    mapCenter: PERMIAN_CENTER,
    mapZoom: 6,
    assets: [],
    arcs: [],
    drawer: { open: false },
    costBanner: { visible: false },
    ...overrides,
  };
}

// DEMO NARRATION: chat-side cues the demoer says out loud per beat.
// The narration field is the LLM-grade summary that also shows up in the
// chat panel + backstage panel; longer prose lives in the demo handbook.
export const bufferPlanningBeats: Beat[] = [
  // ---- Beat 0: chat at rest, timeline shown at current 14-day buffer ----
  {
    id: "beat-0-permian-overview",
    narration:
      'Tomas: "Show me Permian fleet utilization and the buffer trade-off — I want to drop the buffer from 14 to 8 days and see what the on-time rate does." Canvas opens to the basin\'s 30-day fleet timeline at the status-quo 14-day buffer.',
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.5,
      ...fleetStatsForBuffer(14),
      fleetTimelineData: buildTimeline(14),
      commitBannerVisible: false,
    }),
  },

  // ---- Beat 1: current-state stats land in the side tiles ----
  {
    id: "beat-1-current-state",
    narration:
      "Capacity Planning Agent pulled the last quarter's actuals from BigQuery. At the current 14-day buffer, the Permian fleet runs at 68% utilization and lands 92% of jobs on time. Risk tolerance sits at the basin default — 0.5.",
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.5,
      ...fleetStatsForBuffer(14),
      fleetTimelineData: buildTimeline(14),
      commitBannerVisible: false,
    }),
  },

  // ---- Beat 2: model the 14→8 buffer drop ----
  {
    id: "beat-2-buffer-drop",
    narration:
      "Agent models the aggressive plan: 14-day buffer down to 8. Utilization climbs to 84% — but projected on-time collapses to 65%, and we'd defer $4.5M of replacement-tool CapEx. Watch the deployed line tighten against active rigs.",
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.5,
      ...fleetStatsForBuffer(8),
      fleetTimelineData: buildTimeline(8),
      commitBannerVisible: false,
    }),
  },

  // ---- Beat 3: risk-tolerance bumped to 0.7, agent counter-proposes 10d ----
  {
    id: "beat-3-risk-tolerance-up",
    narration:
      "Tomas nudges risk tolerance from 0.5 to 0.7. The Capacity Planning Agent re-runs the optimization and counter-proposes a 10-day buffer instead. 78% on-time, 76% utilization, $3.2M deferred — the right compromise for an XOM commitment.",
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.7,
      ...fleetStatsForBuffer(10),
      fleetTimelineData: buildTimeline(10),
      commitBannerVisible: false,
    }),
  },

  // ---- Beat 4: Tomas accepts; BufferCostReconciliation banner appears ----
  {
    id: "beat-4-commit",
    narration:
      'Tomas accepts the 10-day buffer. The plan is saved as "Q4 Permian fleet schedule v3", $3.2M of CapEx is deferred, and the Capacity Planning Agent writes the outcome back to Memory Bank under buffer_outcomes.',
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.7,
      ...fleetStatsForBuffer(10),
      fleetTimelineData: buildTimeline(10),
      commitBannerVisible: true,
      commitBannerHeadline:
        "Recommendation accepted. Buffer 14d → 10d. CapEx deferred $3.2M.",
    }),
  },

  // ---- Beat 5: confirmation toast, persona timer rolls ----
  {
    id: "beat-5-confirmed",
    narration:
      'Saved as Q4 fleet schedule v3. Capacity Planning Agent notified the basin team, synced the new buffer to Maximo, and queued the next-quarter review. Three minutes, end to end.',
    state: baseState({
      showTimeline: true,
      riskTolerance: 0.7,
      ...fleetStatsForBuffer(10),
      fleetTimelineData: buildTimeline(10),
      commitBannerVisible: true,
      commitBannerHeadline:
        "Saved · Q4 fleet schedule v3 · Permian · ExxonMobil",
    }),
  },
];
