# TASK-09: Operations Canvas Fleet Utilization View

**Prerequisites:** TASK-08 complete. Canvas scaffold exists, Global Asset View renders Maria's cargo-plane scenario, design tokens and layout shell are in place.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Frontend

---

## Context

Persona 2 is Tomas Reyes, the Fleet Scheduler for the Permian basin. His view answers a fundamentally different question than Maria's. Maria asks "how do I respond *now* to a capacity gap?" — she works in supply response with reactive logistics. Tomas asks "how much buffer should I plan for the next 12 weeks?" — he works in demand-to-supply planning with probabilistic forecasts and explicit risk tolerance.

The Fleet Utilization View is the canvas for that conversation. It shows:

- A **multi-week timeline** of demand-vs-fleet-capacity per equipment class
- **Probabilistic forecast bands** around the demand line (p10, p50, p90)
- A **capacity buffer Pareto frontier** — for any risk-tolerance setting, what's the optimal buffer that balances over-buffering cost against late-start cost
- An interactive **risk-tolerance slider** (Conservative ←→ Aggressive) that reactively recomputes the buffer and updates the timeline overlay
- A **buffer-cost-vs-late-cost reconciliation panel** showing the dollar tradeoff at the current slider position

The narration moment: Tomas drags the slider from Conservative (his default per his Memory Profile preference) to Balanced. He watches the buffer line drop from 18% to 12%, watches the late-start risk increase modestly, watches the dollar tradeoff update in real time. The agent's recommendation updates with each slider move. By the end of the 3-minute segment, Tomas has visibility into a tradeoff that previously lived in a 40-cell Excel sheet that only his predecessor understood.

This task builds the Fleet Utilization View on top of the canvas scaffold from TASK-08. Same three-panel shell, same design tokens, same demo runner with keyboard controls — only the canvas center renders differently.

---

## Inputs

- TASK-08 complete (canvas scaffold, design tokens, layout shell, demo runner pattern)
- Brief: `agentic_sop_oilfield_services_brief.md` — Persona 2 section, Fleet Utilization view description
- Synthetic data: `data/fleet_utilization_synthetic.json` (generated in TASK-03 — verify it has 12-week probabilistic forecast bands for at least three equipment classes)

---

## Deliverables

When this task is complete:

1. **Fleet Utilization View** rendering at `/scenarios/buffer-planning`
2. **Multi-week timeline chart** showing demand line + p10/p90 confidence band + fleet capacity line
3. **Capacity buffer overlay** that updates reactively as the risk-tolerance slider moves
4. **Risk-tolerance slider** with three discrete stops (Conservative / Balanced / Aggressive) plus continuous dragging
5. **Buffer-cost-vs-late-cost reconciliation panel** in the side drawer showing dollar tradeoff
6. **Beat-by-beat choreography** for Tomas's 3-minute segment (5-6 beats)
7. **Static demo data** matching the synthetic fleet utilization data (WebSocket arrives in TASK-10)
8. **Integration with the existing canvas shell** from TASK-08 — same keyboard controls, same beat indicator, same chat panel

---

## Step-by-step instructions

### Step 1 — Choose the charting library

The cargo-plane view uses Mapbox for geography. Fleet utilization needs a time-series chart. Two viable choices:

- **Recharts** — React-first, declarative, good defaults, easy to style with Tailwind classes. Less control over animation polish.
- **D3 + SVG** — full control over visual choreography. More code; more flexibility.

For this build, **Recharts** is the right choice. It handles probabilistic bands cleanly via `<Area>` components, it integrates with Framer Motion for the slider-driven transitions, and it ships with reasonable defaults that match our design tokens with minimal customization. We can drop to D3 later if we need a specific effect Recharts can't deliver.

```bash
cd canvas
npm install recharts
```

### Step 2 — Define the fleet utilization data shape

`canvas/data/fleetUtilizationData.ts`:

```typescript
export interface FleetUtilizationPoint {
  week: string;              // e.g. "W23"
  weekStartDate: string;     // ISO date
  demand_p10: number;        // 10th percentile forecast (low)
  demand_p50: number;        // median forecast
  demand_p90: number;        // 90th percentile forecast (high)
  fleet_capacity: number;    // current fleet capacity in same units
  buffered_capacity: number; // fleet_capacity + current buffer recommendation
}

export interface BufferOption {
  risk_tolerance: "conservative" | "balanced" | "aggressive";
  buffer_pct: number;
  expected_idle_cost_usd: number;
  expected_late_start_cost_usd: number;
  on_time_probability: number;
  description: string;
}

export interface BufferPlanScenario {
  equipment_class: string;          // e.g. "Frac Pumps — Permian"
  customer: string;                 // e.g. "ExxonMobil"
  timeline: FleetUtilizationPoint[];
  buffer_options: BufferOption[];
  current_recommendation: "conservative" | "balanced" | "aggressive";
}

// Hardcoded for static demo mode; replaced with live data from TASK-03 synthetic file
export const fracPumpScenario: BufferPlanScenario = {
  equipment_class: "Frac Pumps — Permian",
  customer: "ExxonMobil",
  timeline: [
    // 12 weeks of data
    { week: "W22", weekStartDate: "2026-05-25", demand_p10: 32, demand_p50: 38, demand_p90: 46, fleet_capacity: 40, buffered_capacity: 47 },
    { week: "W23", weekStartDate: "2026-06-01", demand_p10: 34, demand_p50: 41, demand_p90: 49, fleet_capacity: 40, buffered_capacity: 47 },
    // ... 10 more weeks
  ],
  buffer_options: [
    {
      risk_tolerance: "conservative",
      buffer_pct: 18,
      expected_idle_cost_usd: 1_240_000,
      expected_late_start_cost_usd: 180_000,
      on_time_probability: 0.96,
      description: "High buffer — favors reliability. Higher idle fleet cost but very low late-start risk.",
    },
    {
      risk_tolerance: "balanced",
      buffer_pct: 12,
      expected_idle_cost_usd: 820_000,
      expected_late_start_cost_usd: 410_000,
      on_time_probability: 0.88,
      description: "Balanced — moderate buffer. Lower idle cost; modest late-start exposure.",
    },
    {
      risk_tolerance: "aggressive",
      buffer_pct: 6,
      expected_idle_cost_usd: 410_000,
      expected_late_start_cost_usd: 940_000,
      on_time_probability: 0.74,
      description: "Lean buffer — favors capital efficiency. Low idle cost but real late-start risk.",
    },
  ],
  current_recommendation: "conservative",
};
```

### Step 3 — Build the FleetTimelineChart component

`canvas/components/canvas/FleetTimelineChart.tsx`:

```tsx
"use client";

import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from "recharts";
import { motion } from "framer-motion";

import type { FleetUtilizationPoint } from "@/data/fleetUtilizationData";

interface FleetTimelineChartProps {
  timeline: FleetUtilizationPoint[];
  bufferedCapacity?: number;   // overlay line for the currently-selected buffer
  highlightWeek?: string;
}

// DEMO NARRATION (Beat 2): "Here's the 12-week forecast. The shaded band
// is the demand probability — p10 to p90. The solid orange line is the
// median forecast. The white line is fleet capacity. Notice in Week 27,
// demand is forecast to spike. Tomas's job: decide how much buffer to
// add. Too much, he's paying for idle fleet. Too little, he's missing
// on-time starts. The agent is going to help him reason about it."
export function FleetTimelineChart({ timeline, bufferedCapacity, highlightWeek }: FleetTimelineChartProps) {
  return (
    <div className="h-[480px] w-full rounded-2xl bg-white/5 p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-lg font-medium">12-week fleet utilization</h3>
        <div className="flex gap-4 text-xs">
          <LegendDot color="rgb(245, 158, 11)" label="Demand p10–p90" />
          <LegendDot color="rgb(245, 158, 11)" label="Demand p50" filled />
          <LegendDot color="rgb(255, 255, 255)" label="Fleet capacity" filled />
          <LegendDot color="rgb(16, 185, 129)" label="Buffered capacity" filled />
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={timeline} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
          <defs>
            <linearGradient id="demandBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(245, 158, 11)" stopOpacity={0.25} />
              <stop offset="100%" stopColor="rgb(245, 158, 11)" stopOpacity={0.05} />
            </linearGradient>
          </defs>

          <XAxis
            dataKey="week"
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
          />
          <YAxis
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
            label={{ value: "Units", angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.5)" }}
          />

          {/* Probabilistic band */}
          <Area
            type="monotone"
            dataKey="demand_p90"
            stackId="band"
            stroke="none"
            fill="url(#demandBand)"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="demand_p10"
            stackId="band"
            stroke="none"
            fill="rgb(10, 14, 26)"
            isAnimationActive={false}
          />

          {/* Median demand line */}
          <Line
            type="monotone"
            dataKey="demand_p50"
            stroke="rgb(245, 158, 11)"
            strokeWidth={3}
            dot={false}
            isAnimationActive={false}
          />

          {/* Fleet capacity baseline */}
          <Line
            type="monotone"
            dataKey="fleet_capacity"
            stroke="rgb(255, 255, 255)"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            isAnimationActive={false}
          />

          {/* Buffered capacity overlay — animates as slider moves */}
          {bufferedCapacity && (
            <Line
              type="monotone"
              dataKey="buffered_capacity"
              stroke="rgb(16, 185, 129)"
              strokeWidth={3}
              dot={false}
              isAnimationActive={true}
              animationDuration={500}
            />
          )}

          {highlightWeek && <ReferenceLine x={highlightWeek} stroke="white" strokeOpacity={0.4} />}

          <Tooltip
            contentStyle={{
              backgroundColor: "rgb(17, 23, 42)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "rgba(255,255,255,0.8)" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function LegendDot({ color, label, filled }: { color: string; label: string; filled?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {filled ? (
        <div className="h-1 w-3" style={{ backgroundColor: color }} />
      ) : (
        <div className="h-2 w-3 rounded-sm opacity-30" style={{ backgroundColor: color }} />
      )}
      <span className="text-white/60">{label}</span>
    </div>
  );
}
```

### Step 4 — Build the risk-tolerance slider

`canvas/components/canvas/RiskToleranceSlider.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { useState } from "react";

import type { BufferOption } from "@/data/fleetUtilizationData";

interface RiskToleranceSliderProps {
  options: BufferOption[];
  value: BufferOption["risk_tolerance"];
  onChange: (v: BufferOption["risk_tolerance"]) => void;
}

const TOLERANCE_LABELS = ["conservative", "balanced", "aggressive"] as const;

// DEMO NARRATION (Beat 4): "Watch what happens when Tomas drags this
// slider from Conservative — his default — to Balanced. The buffer drops
// from 18% to 12%. The buffered capacity line on the chart slides down.
// The tradeoff panel updates: idle cost drops by 400K but late-start
// exposure rises. The agent is helping him visualize a tradeoff that
// previously lived in a spreadsheet only one person fully understood."
export function RiskToleranceSlider({ options, value, onChange }: RiskToleranceSliderProps) {
  const currentIndex = TOLERANCE_LABELS.indexOf(value);

  return (
    <div className="rounded-2xl bg-white/5 p-6">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-white/70">Risk tolerance</h3>
        <span className="text-xs text-white/40">drag or click a label</span>
      </div>

      {/* Track */}
      <div className="relative mb-4 h-2 rounded-full bg-white/10">
        <motion.div
          className="absolute h-2 rounded-full"
          style={{ background: "linear-gradient(90deg, #10b981, #f59e0b)" }}
          animate={{ width: `${(currentIndex / 2) * 100}%` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
        <motion.div
          className="absolute top-1/2 h-6 w-6 -translate-y-1/2 rounded-full bg-white shadow-lg cursor-grab"
          animate={{ left: `calc(${(currentIndex / 2) * 100}% - 12px)` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between text-sm">
        {TOLERANCE_LABELS.map((label, i) => (
          <button
            key={label}
            onClick={() => onChange(label)}
            className={`capitalize transition-colors ${
              value === label
                ? "text-white font-medium"
                : "text-white/40 hover:text-white/60"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
```

### Step 5 — Build the cost reconciliation panel

This panel shows the dollar tradeoff between over-buffering and under-buffering at the current slider position. Lives in the side drawer.

`canvas/components/canvas/BufferCostReconciliation.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Target } from "lucide-react";

import type { BufferOption } from "@/data/fleetUtilizationData";

interface BufferCostReconciliationProps {
  option: BufferOption;
}

// DEMO NARRATION (Beat 5): "Here's the dollar tradeoff. At Balanced —
// 12% buffer — Tomas is paying 820K in expected idle cost. His late-start
// exposure is 410K. The agent's model says 88% on-time probability. The
// agent isn't telling him what to do — it's showing him the shape of the
// tradeoff in terms he can act on."
export function BufferCostReconciliation({ option }: BufferCostReconciliationProps) {
  return (
    <motion.div
      key={option.risk_tolerance}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-4 p-6"
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-medium capitalize">{option.risk_tolerance} buffer</h3>
        <span className="text-3xl font-bold tabular-nums">{option.buffer_pct}%</span>
      </div>
      <p className="text-sm text-white/60">{option.description}</p>

      <div className="space-y-3 border-t border-white/10 pt-4">
        <Row
          label="Expected idle cost"
          value={option.expected_idle_cost_usd}
          icon={<TrendingUp className="h-4 w-4 text-amber-400" />}
          help="Cost of fleet sitting idle when demand comes in below buffered capacity"
        />
        <Row
          label="Expected late-start cost"
          value={option.expected_late_start_cost_usd}
          icon={<TrendingDown className="h-4 w-4 text-red-400" />}
          help="Customer penalties + opportunity cost when capacity falls short"
        />
        <Row
          label="On-time probability"
          value={option.on_time_probability}
          format="percent"
          icon={<Target className="h-4 w-4 text-emerald-400" />}
          help="Model estimate of meeting 100% of customer commitments this quarter"
        />
      </div>

      <div className="rounded-lg bg-white/5 p-3 text-sm">
        <div className="text-white/60 mb-1">Net expected cost</div>
        <div className="text-2xl font-semibold tabular-nums">
          ${(option.expected_idle_cost_usd + option.expected_late_start_cost_usd).toLocaleString()}
        </div>
      </div>
    </motion.div>
  );
}

function Row({
  label,
  value,
  icon,
  help,
  format = "currency",
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  help?: string;
  format?: "currency" | "percent";
}) {
  const formatted =
    format === "percent" ? `${(value * 100).toFixed(0)}%` : `$${value.toLocaleString()}`;

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <div>
          <div className="text-sm text-white/80">{label}</div>
          {help && <div className="text-xs text-white/40">{help}</div>}
        </div>
      </div>
      <div className="text-lg font-medium tabular-nums">{formatted}</div>
    </div>
  );
}
```

### Step 6 — Define Tomas's 5-6 beats

`canvas/data/bufferPlanningBeats.ts`:

```typescript
import { fracPumpScenario, BufferOption } from "./fleetUtilizationData";

export interface BufferBeat {
  beatNumber: number;
  durationMs: number;
  description: string;
  state: {
    showTimeline: boolean;
    bufferOption: BufferOption["risk_tolerance"];
    drawerOpen: boolean;
    highlightWeek?: string;
    chatNarration: string;
  };
}

export const bufferPlanningBeats: BufferBeat[] = [
  {
    beatNumber: 0,
    durationMs: 0,
    description: "Initial state — Tomas's view loads, no timeline yet",
    state: {
      showTimeline: false,
      bufferOption: "conservative",
      drawerOpen: false,
      chatNarration: "Tomas: \"Frac pump Q3 buffer plan for ExxonMobil-Permian.\"",
    },
  },
  {
    beatNumber: 1,
    durationMs: 2500,
    description: "Capacity Planning Agent loads, fetches 12-week forecast — timeline appears",
    state: {
      showTimeline: true,
      bufferOption: "conservative",
      drawerOpen: false,
      chatNarration: "Capacity Planning Agent loaded forecast from BigQuery. 12 weeks. p10/p50/p90 bands visible.",
    },
  },
  {
    beatNumber: 2,
    durationMs: 3000,
    description: "Agent highlights Week 27 demand spike",
    state: {
      showTimeline: true,
      bufferOption: "conservative",
      drawerOpen: false,
      highlightWeek: "W27",
      chatNarration: "Demand spike forecast in W27 — p90 reaches 56 units against 40-unit fleet capacity. Buffer planning needed.",
    },
  },
  {
    beatNumber: 3,
    durationMs: 3500,
    description: "Agent applies Tomas's Memory Profile default — Conservative buffer",
    state: {
      showTimeline: true,
      bufferOption: "conservative",
      drawerOpen: true,
      chatNarration: "Using your default risk tolerance from your profile: Conservative. 18% buffer recommended. Buffered capacity line shown in green.",
    },
  },
  {
    beatNumber: 4,
    durationMs: 4000,
    description: "Tomas drags slider to Balanced — chart and reconciliation panel update reactively",
    state: {
      showTimeline: true,
      bufferOption: "balanced",
      drawerOpen: true,
      chatNarration: "At Balanced (12% buffer), idle cost drops 420K but late-start exposure rises 230K. On-time probability: 88%.",
    },
  },
  {
    beatNumber: 5,
    durationMs: 3000,
    description: "Tomas approves the Balanced plan — Agent writes recommendation to record",
    state: {
      showTimeline: true,
      bufferOption: "balanced",
      drawerOpen: true,
      chatNarration: "Approved 12% buffer for Q3. Capacity Planning Agent will sync to Maximo and notify the basin team. Decision logged to Memory Profile.",
    },
  },
];
```

### Step 7 — Assemble the page

`canvas/app/scenarios/buffer-planning/page.tsx`:

```tsx
"use client";

import { useState, useMemo } from "react";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { FleetTimelineChart } from "@/components/canvas/FleetTimelineChart";
import { RiskToleranceSlider } from "@/components/canvas/RiskToleranceSlider";
import { BufferCostReconciliation } from "@/components/canvas/BufferCostReconciliation";
import { useScenario } from "@/hooks/useScenario";
import { bufferPlanningBeats } from "@/data/bufferPlanningBeats";
import { fracPumpScenario, BufferOption } from "@/data/fleetUtilizationData";

export default function BufferPlanningScenarioPage() {
  const { state: beatState, currentBeat, totalBeats } = useScenario({ beats: bufferPlanningBeats });

  // Allow manual slider override (overrides the beat's preset) during free exploration
  const [manualOverride, setManualOverride] = useState<BufferOption["risk_tolerance"] | null>(null);
  const activeBufferTolerance = manualOverride ?? beatState.bufferOption;

  const currentOption = useMemo(
    () => fracPumpScenario.buffer_options.find((o) => o.risk_tolerance === activeBufferTolerance)!,
    [activeBufferTolerance],
  );

  // Apply the current buffer to the timeline
  const timelineWithBuffer = useMemo(() => {
    const multiplier = 1 + currentOption.buffer_pct / 100;
    return fracPumpScenario.timeline.map((pt) => ({
      ...pt,
      buffered_capacity: pt.fleet_capacity * multiplier,
    }));
  }, [currentOption.buffer_pct]);

  return (
    <CanvasShell
      chat={<ChatPanel beat={currentBeat} totalBeats={totalBeats} message={beatState.chatNarration} />}
      drawer={<BufferCostReconciliation option={currentOption} />}
      drawerOpen={beatState.drawerOpen}
      canvas={
        <div className="flex h-full flex-col gap-6 p-8">
          <div>
            <div className="text-xs uppercase tracking-wider text-white/40">
              {fracPumpScenario.customer} • {fracPumpScenario.equipment_class}
            </div>
            <h1 className="mt-1 text-2xl font-semibold">Q3 buffer planning</h1>
          </div>

          {beatState.showTimeline && (
            <FleetTimelineChart
              timeline={timelineWithBuffer}
              bufferedCapacity={currentOption.buffer_pct}
              highlightWeek={beatState.highlightWeek}
            />
          )}

          <RiskToleranceSlider
            options={fracPumpScenario.buffer_options}
            value={activeBufferTolerance}
            onChange={setManualOverride}
          />

          <BeatIndicator current={currentBeat} total={totalBeats} />
        </div>
      }
    />
  );
}

function ChatPanel({ beat, totalBeats, message }: { beat: number; totalBeats: number; message: string }) {
  return (
    <div className="p-4 text-sm">
      <div className="text-xs uppercase tracking-wider text-white/40 mb-2">
        Tomas @ Fleet Scheduler • Permian
      </div>
      <div className="rounded-lg bg-white/5 p-3 text-white/90">{message}</div>
    </div>
  );
}

function BeatIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="mt-auto flex gap-1">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1 w-8 rounded-full transition-colors ${i <= current ? "bg-white/80" : "bg-white/20"}`}
        />
      ))}
    </div>
  );
}
```

### Step 8 — Smoke test

```bash
cd canvas
npm run dev
# Open http://localhost:3000/scenarios/buffer-planning
```

Walk through:
- Beat 0: chat narration appears, no chart yet
- Beat 1: timeline renders, p10/p90 band visible, p50 line in amber, fleet capacity dashed white
- Beat 2: Week 27 highlighted with reference line
- Beat 3: drawer opens, buffered capacity green line appears at 18% above fleet capacity, reconciliation panel shows Conservative numbers
- Beat 4: when slider moves to Balanced, buffered line drops to 12% above, reconciliation panel re-renders with Balanced numbers, animations smooth
- Beat 5: chat shows approval confirmation

Manual exploration: after running through beats, drag the slider freely between Conservative / Balanced / Aggressive. Verify reactive updates.

### Step 9 — Add to the canvas navigation

`canvas/app/page.tsx` (the canvas root) should now show both scenarios as available entry points (for rehearsal mode):

```tsx
import Link from "next/link";

export default function CanvasHomePage() {
  return (
    <main className="min-h-screen p-12">
      <h1 className="text-3xl font-bold mb-8">Operations Canvas — Demo Scenarios</h1>
      <div className="grid gap-4 max-w-2xl">
        <Link
          href="/scenarios/cargo-plane"
          className="rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10"
        >
          <div className="text-xs uppercase tracking-wider text-white/40 mb-1">Persona 3 — Maria</div>
          <div className="text-xl font-medium">Cargo plane pivot</div>
          <div className="mt-2 text-sm text-white/60">
            West Africa supply response. $380K avoided cost. Global asset view with Knowledge Catalog drawer.
          </div>
        </Link>

        <Link
          href="/scenarios/buffer-planning"
          className="rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10"
        >
          <div className="text-xs uppercase tracking-wider text-white/40 mb-1">Persona 2 — Tomas</div>
          <div className="text-xl font-medium">Q3 buffer planning</div>
          <div className="mt-2 text-sm text-white/60">
            Permian fleet utilization with probabilistic forecast and risk-tolerance-aware buffer recommendation.
          </div>
        </Link>
      </div>
    </main>
  );
}
```

### Step 10 — Commit

```bash
git add canvas/
git commit -m "feat: Operations Canvas Fleet Utilization View for Persona 2 (TASK-09)"
git push
```

---

## Acceptance criteria

- [ ] Recharts integrated
- [ ] Fleet Utilization View renders at `/scenarios/buffer-planning`
- [ ] Multi-week timeline shows demand band (p10–p90), median line, fleet capacity, buffered capacity
- [ ] Risk-tolerance slider has three discrete stops with smooth transitions
- [ ] Slider movement updates the buffered capacity line and reconciliation panel reactively
- [ ] BufferCostReconciliation panel shows idle cost, late-start cost, on-time probability with help text
- [ ] All 5-6 beats render cleanly with the static demo data
- [ ] Manual slider override works after beats complete
- [ ] Canvas home page links to both scenarios
- [ ] Animations run smoothly when slider moves
- [ ] Every component with demo significance has a `// DEMO NARRATION:` comment
- [ ] Commit pushed

---

## Common pitfalls

**Recharts area rendering bug.** Stacking an area band requires the band layers to be `<Area>` components with matching `stackId`, with the lower bound rendered first using the background color (to "subtract" it). Test the visual outcome carefully — it's easy to end up with the wrong band shape.

**Slider drag UX feels wrong.** A click-to-stop slider with smooth animation is more demo-friendly than a continuously-draggable slider, because demoers can show specific stops and the animation telegraphs the change clearly. If continuous dragging is wanted, debounce the chart re-renders to avoid jank.

**Reconciliation panel content overflow.** The drawer is 420px wide. If the help text or large dollar values overflow, the layout breaks. Test with realistic values; truncate help text if needed.

**Buffer percentage math wrong.** `buffered_capacity = fleet_capacity * (1 + buffer_pct / 100)` is the right formula. Don't confuse with `fleet_capacity * buffer_pct` (which would compute buffer-only). Add a unit test for this.

**Chart re-rendering on every slider tick.** Recharts re-renders the full chart on every prop change. For three-stop sliders this is fine. For continuous dragging it can stutter. Use `useDeferredValue` on the buffer percentage if going continuous.

**Color contrast in dark mode.** Amber (`#f59e0b`) on the dark background reads well; muted amber (`opacity: 0.3`) for the band can disappear. Test contrast at projection brightness — a screen that looks fine on a laptop may look washed out on a low-lumen projector.

**Memory Profile preference not being honored.** Beat 3's narration explicitly says "your default risk tolerance from your profile: Conservative." This implies Tomas's profile preference (`risk_tolerance: "conservative"` from TASK-07) is being read. Confirm the integration is real, not faked — the beat data should derive the default from the Memory Profile lookup.

**Beat 5 approval is just narration, not a real action.** This is fine for v1 but flag it. In a fuller demo, "approve" would trigger an Agent Inbox action and an actual write to Memory Bank. For v1 the narration suggests this without doing it. Don't pretend it's wired when it isn't.

---

## References

- Recharts: `https://recharts.org/en-US/api`
- Recharts ComposedChart: `https://recharts.org/en-US/examples/ComposedChart`
- Framer Motion `<motion.div>`: `https://www.framer.com/motion/component/`
- Tailwind 4 utilities: `https://tailwindcss.com/docs`
- Previous task: `claude_code_specs/tasks/TASK-08-canvas-global-asset-view.md`

---

*When TASK-09 is complete, the canvas serves both Persona 2 (Tomas, buffer planning) and Persona 3 (Maria, cargo-plane) scenarios in static demo mode. Both scenarios are choreographed beat-by-beat with the same keyboard controls and beat indicator. The next task wires WebSocket-driven live agent events so the canvas reacts to the actual backend Orchestrator output instead of hardcoded beat data.*
