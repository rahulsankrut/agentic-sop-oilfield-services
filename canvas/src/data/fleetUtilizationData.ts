/**
 * Fleet utilization synthetic data for Persona 2 (Tomas, Permian).
 *
 * 12-week probabilistic forecast for the ExxonMobil-Permian frac-pump
 * fleet. Each week carries a p10/p50/p90 demand triple and a fleet
 * capacity baseline. Three buffer options (conservative / balanced /
 * aggressive) encode the agent's recommendations across the
 * risk-tolerance space.
 *
 * Numbers chosen to make the W27 demand spike visible — p90 reaches 56
 * units against a 40-unit fleet, which is where the buffer conversation
 * starts. Costs are illustrative (not from real ExxonMobil contracts).
 *
 * Static for the demo; the live-data variant lives in TASK-10's SSE
 * stream.
 */

export interface FleetUtilizationPoint {
  week: string; // "W22" .. "W33"
  weekStartDate: string; // ISO date
  demand_p10: number;
  demand_p50: number;
  demand_p90: number;
  fleet_capacity: number;
  buffered_capacity: number; // fleet_capacity + (buffer_pct/100 * fleet_capacity)
}

export interface BufferOption {
  risk_tolerance: "conservative" | "balanced" | "aggressive";
  buffer_pct: number;
  expected_idle_cost_usd: number;
  expected_late_start_cost_usd: number;
  on_time_probability: number; // 0..1
  description: string;
}

export interface BufferPlanScenario {
  equipment_class: string;
  customer: string;
  timeline: FleetUtilizationPoint[];
  buffer_options: BufferOption[];
  current_recommendation: BufferOption["risk_tolerance"];
}

const FLEET_CAPACITY = 40;
// Default timeline carries buffered_capacity at the conservative (18%) preset;
// the page recomputes buffered_capacity per slider position.
const CONSERVATIVE_MULTIPLIER = 1.18;

function buffered(units: number): number {
  return Math.round(units * CONSERVATIVE_MULTIPLIER * 10) / 10;
}

// Twelve weeks of demand. Spike at W27 (p90 hits 56) is the dramatic
// moment of the storyboard.
const TIMELINE: FleetUtilizationPoint[] = [
  { week: "W22", weekStartDate: "2026-05-25", demand_p10: 32, demand_p50: 38, demand_p90: 46, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W23", weekStartDate: "2026-06-01", demand_p10: 34, demand_p50: 41, demand_p90: 49, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W24", weekStartDate: "2026-06-08", demand_p10: 33, demand_p50: 40, demand_p90: 48, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W25", weekStartDate: "2026-06-15", demand_p10: 36, demand_p50: 43, demand_p90: 51, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W26", weekStartDate: "2026-06-22", demand_p10: 38, demand_p50: 45, demand_p90: 53, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W27", weekStartDate: "2026-06-29", demand_p10: 40, demand_p50: 48, demand_p90: 56, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W28", weekStartDate: "2026-07-06", demand_p10: 37, demand_p50: 44, demand_p90: 52, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W29", weekStartDate: "2026-07-13", demand_p10: 35, demand_p50: 42, demand_p90: 50, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W30", weekStartDate: "2026-07-20", demand_p10: 34, demand_p50: 41, demand_p90: 48, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W31", weekStartDate: "2026-07-27", demand_p10: 33, demand_p50: 39, demand_p90: 47, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W32", weekStartDate: "2026-08-03", demand_p10: 31, demand_p50: 37, demand_p90: 44, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
  { week: "W33", weekStartDate: "2026-08-10", demand_p10: 30, demand_p50: 36, demand_p90: 43, fleet_capacity: FLEET_CAPACITY, buffered_capacity: buffered(FLEET_CAPACITY) },
];

const BUFFER_OPTIONS: BufferOption[] = [
  {
    risk_tolerance: "conservative",
    buffer_pct: 18,
    expected_idle_cost_usd: 1_240_000,
    expected_late_start_cost_usd: 180_000,
    on_time_probability: 0.96,
    description:
      "High buffer — favors reliability. Higher idle fleet cost but very low late-start risk. Tomas's profile default.",
  },
  {
    risk_tolerance: "balanced",
    buffer_pct: 12,
    expected_idle_cost_usd: 820_000,
    expected_late_start_cost_usd: 410_000,
    on_time_probability: 0.88,
    description:
      "Balanced — moderate buffer. Lower idle cost; modest late-start exposure. Lands ~$830K total expected cost.",
  },
  {
    risk_tolerance: "aggressive",
    buffer_pct: 6,
    expected_idle_cost_usd: 410_000,
    expected_late_start_cost_usd: 940_000,
    on_time_probability: 0.74,
    description:
      "Lean buffer — favors capital efficiency. Low idle cost but real late-start risk; only sensible if the customer has explicit slack.",
  },
];

export const fracPumpScenario: BufferPlanScenario = {
  equipment_class: "Frac Pumps — Permian",
  customer: "ExxonMobil",
  timeline: TIMELINE,
  buffer_options: BUFFER_OPTIONS,
  current_recommendation: "conservative",
};

/**
 * Recompute `buffered_capacity` for every week given a buffer percentage.
 * Used by the page to drive the green overlay line reactively from the
 * slider position.
 */
export function withBuffer(
  timeline: FleetUtilizationPoint[],
  bufferPct: number,
): FleetUtilizationPoint[] {
  const multiplier = 1 + bufferPct / 100;
  return timeline.map((pt) => ({
    ...pt,
    buffered_capacity: Math.round(pt.fleet_capacity * multiplier * 10) / 10,
  }));
}

export function bufferOptionFor(
  risk: BufferOption["risk_tolerance"],
): BufferOption {
  const found = BUFFER_OPTIONS.find((o) => o.risk_tolerance === risk);
  if (!found) {
    throw new Error(`Unknown risk_tolerance: ${risk}`);
  }
  return found;
}
