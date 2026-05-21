"use client";

import {
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from "recharts";

import type { FleetUtilizationPoint } from "@/data/fleetUtilizationData";
import type { FleetTimelineDayPoint } from "@/data/demoScenarios";

interface FleetTimelineChartProps {
  timeline: FleetUtilizationPoint[];
  /** Buffer percentage in effect — drives the green overlay line. If
   *  not provided, the buffered_capacity column from the timeline data
   *  is used as-is. */
  bufferedCapacity?: number;
  /** Optional week label (e.g. "W27") to draw a vertical reference
   *  line — used when the agent's narration points at a specific week. */
  highlightWeek?: string;
}

interface FleetDailyTimelineChartProps {
  data: FleetTimelineDayPoint[];
  /** Numeric buffer in days — drives the vertical reference line. */
  bufferDays?: number;
  /** Optional chart title; defaults to "30-day Permian fleet deployment". */
  title?: string;
}

// DEMO NARRATION (Beat 2): "Here's the 12-week forecast. The shaded band
// is the demand probability — p10 to p90. The solid orange line is the
// median forecast. The white line is fleet capacity. Notice in Week 27,
// demand is forecast to spike. Tomas's job: decide how much buffer to
// add. Too much, he's paying for idle fleet. Too little, he's missing
// on-time starts. The agent is going to help him reason about it."
export function FleetTimelineChart({
  timeline,
  bufferedCapacity,
  highlightWeek,
}: FleetTimelineChartProps) {
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
            label={{
              value: "Units",
              angle: -90,
              position: "insideLeft",
              fill: "rgba(255,255,255,0.5)",
            }}
          />

          {/* Probabilistic band — stacked-Area trick: render p90 with the
              amber gradient, then mask the lower half with a p10 area painted
              in the canvas background color. */}
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
          {bufferedCapacity !== undefined && (
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

          {highlightWeek && (
            <ReferenceLine x={highlightWeek} stroke="white" strokeOpacity={0.4} />
          )}

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

function LegendDot({
  color,
  label,
  filled,
}: {
  color: string;
  label: string;
  filled?: boolean;
}) {
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

// DEMO NARRATION (Persona 2 v2): "Thirty days of Permian deployment. The
// white line is the basin's active rig count — Baker Hughes data. The
// emerald line is what this fleet's actually committed to. Tighter
// the gap, higher the utilization but also higher the late-start risk.
// The vertical marker is the current buffer-day cutoff."
export function FleetDailyTimelineChart({
  data,
  bufferDays,
  title = "30-day Permian fleet deployment",
}: FleetDailyTimelineChartProps) {
  // Place the buffer line at (30 - bufferDays) → the buffer extends
  // FROM that day to the right edge of the timeline.
  const bufferLineDay =
    typeof bufferDays === "number" ? Math.max(1, 30 - bufferDays) : null;

  return (
    <div className="h-full w-full rounded-2xl bg-white/5 p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-lg font-medium">{title}</h3>
        <div className="flex gap-4 text-xs">
          <LegendDot color="rgb(255, 255, 255)" label="Basin active rigs" filled />
          <LegendDot color="rgb(16, 185, 129)" label="Fleet deployed" filled />
          {bufferLineDay !== null && (
            <LegendDot
              color="rgb(245, 158, 11)"
              label={`${bufferDays}-day buffer`}
              filled
            />
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart
          data={data}
          margin={{ top: 20, right: 30, bottom: 20, left: 30 }}
        >
          <defs>
            <linearGradient id="activeRigsBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(255, 255, 255)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="rgb(255, 255, 255)" stopOpacity={0.03} />
            </linearGradient>
            <linearGradient id="deployedBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity={0.35} />
              <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity={0.05} />
            </linearGradient>
          </defs>

          <XAxis
            dataKey="day"
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
            label={{
              value: "Day",
              position: "insideBottom",
              offset: -10,
              fill: "rgba(255,255,255,0.5)",
            }}
          />
          <YAxis
            stroke="rgba(255,255,255,0.5)"
            tick={{ fill: "rgba(255,255,255,0.7)", fontSize: 12 }}
            domain={[200, 360]}
            label={{
              value: "Rigs",
              angle: -90,
              position: "insideLeft",
              fill: "rgba(255,255,255,0.5)",
            }}
          />

          <Area
            type="monotone"
            dataKey="active_rigs"
            stroke="rgb(255, 255, 255)"
            strokeWidth={2}
            strokeDasharray="6 3"
            fill="url(#activeRigsBand)"
            isAnimationActive={false}
          />

          <Area
            type="monotone"
            dataKey="deployed"
            stroke="rgb(16, 185, 129)"
            strokeWidth={3}
            fill="url(#deployedBand)"
            isAnimationActive={true}
            animationDuration={500}
          />

          {bufferLineDay !== null && (
            <ReferenceLine
              x={bufferLineDay}
              stroke="rgb(245, 158, 11)"
              strokeDasharray="4 2"
              strokeWidth={2}
              label={{
                value: `${bufferDays}d`,
                fill: "rgb(245, 158, 11)",
                fontSize: 11,
                position: "top",
              }}
            />
          )}

          <Tooltip
            contentStyle={{
              backgroundColor: "rgb(17, 23, 42)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "rgba(255,255,255,0.8)" }}
            labelFormatter={(d) => `Day ${d}`}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
