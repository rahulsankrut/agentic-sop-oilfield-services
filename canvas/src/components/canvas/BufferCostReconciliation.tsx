"use client";

import { motion } from "framer-motion";
import { CheckCircle2, TrendingUp, TrendingDown, Target } from "lucide-react";

import type { BufferOption } from "@/data/fleetUtilizationData";

interface BufferCommitBannerProps {
  visible: boolean;
  /** e.g. "Recommendation accepted. Buffer 14d → 10d. CapEx deferred $3.2M." */
  headline?: string;
  /** Optional second line — saved-as / version string. */
  subline?: string;
  /** Capex deferred (USD), rendered as the big stat. */
  capexDeferredUsd?: number;
  /** Buffer-days landed on (e.g. 10). */
  bufferDays?: number;
  /** On-time rate % (e.g. 78). */
  onTimeRatePct?: number;
}

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
        <div className="mb-1 text-white/60">Net expected cost</div>
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

// DEMO NARRATION (Persona 2 v2, Beat 4): "Banner lands at the bottom of
// the canvas. Buffer 14 down to 10, three-point-two million in CapEx
// deferred, saved as Q4 fleet schedule v3. Capacity Planning Agent wrote
// the outcome back to Memory Bank — next quarter's recommendation will
// remember Tomas accepted a 10-day buffer at 0.7 risk tolerance."
export function BufferCommitBanner({
  visible,
  headline,
  subline,
  capexDeferredUsd,
  bufferDays,
  onTimeRatePct,
}: BufferCommitBannerProps) {
  if (!visible) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="pointer-events-none absolute inset-x-6 bottom-6 z-10"
    >
      <div className="pointer-events-auto rounded-2xl border border-emerald-400/30 bg-gradient-to-r from-emerald-500/15 via-emerald-500/10 to-emerald-400/5 p-5 backdrop-blur-md">
        <div className="flex items-start gap-4">
          <CheckCircle2 className="mt-0.5 h-6 w-6 flex-none text-emerald-400" />
          <div className="flex-1">
            <div className="text-sm font-medium text-emerald-100">
              {headline ?? "Recommendation accepted."}
            </div>
            {subline && (
              <div className="mt-0.5 text-xs text-emerald-200/70">{subline}</div>
            )}
          </div>
          <div className="flex items-baseline gap-5">
            {typeof bufferDays === "number" && (
              <Stat label="Buffer" value={`${bufferDays}d`} />
            )}
            {typeof onTimeRatePct === "number" && (
              <Stat label="On-time" value={`${onTimeRatePct}%`} />
            )}
            {typeof capexDeferredUsd === "number" && (
              <Stat
                label="CapEx deferred"
                value={`$${(capexDeferredUsd / 1_000_000).toFixed(1)}M`}
                accent
              />
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-[0.18em] text-emerald-200/60">
        {label}
      </div>
      <div
        className={`text-xl font-semibold tabular-nums ${
          accent ? "text-emerald-200" : "text-white"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
