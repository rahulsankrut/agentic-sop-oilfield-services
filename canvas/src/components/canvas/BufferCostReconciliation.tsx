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
