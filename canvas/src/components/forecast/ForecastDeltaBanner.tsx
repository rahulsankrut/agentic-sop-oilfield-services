"use client";

/**
 * ForecastDeltaBanner.tsx
 *
 * Bottom-of-canvas "Δ vs baseline" stat for Persona 1 (David). Mirrors the
 * visual treatment of `CostRollupBanner` — same blurred dark card, same
 * motion roll-up — but positioned at the bottom center and surfacing the
 * forecast revision rather than a cost savings number.
 *
 * Shows after Beat 4 (overrides applied). The delta_usd is signed: negative
 * means David revised the Q4 plan downward (the dominant case in the demo),
 * positive would mean upward.
 */

import { useEffect, useState } from "react";
import {
  AnimatePresence,
  animate,
  motion,
  useMotionValue,
  useTransform,
} from "framer-motion";
import { TrendingDown, TrendingUp } from "lucide-react";

import type { ForecastDeltaBannerState } from "@/data/demoScenarios";

interface ForecastDeltaBannerProps {
  state: ForecastDeltaBannerState;
}

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const USD_COMPACT = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
  style: "currency",
  currency: "USD",
});

function formatUSDCompact(n: number): string {
  return USD_COMPACT.format(n);
}

function formatUSD(n: number): string {
  return USD.format(Math.round(n));
}

// DEMO NARRATION (Beat 4): "$44M off the Q4 plan. That's two basins worth
// of regional knowledge that the model didn't have on its own. And the
// override rationale is being re-ingested — next quarter that gap closes
// on its own."
export function ForecastDeltaBanner({ state }: ForecastDeltaBannerProps) {
  const { visible, delta_usd, baseline_total_usd, revised_total_usd, overrides_count } =
    state;
  return (
    <AnimatePresence>
      {visible && typeof delta_usd === "number" && (
        <motion.div
          key="forecast-delta-banner"
          initial={{ y: 24, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 24, opacity: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="absolute bottom-6 left-1/2 z-10 -translate-x-1/2 min-w-[440px] rounded-2xl border border-white/10 p-5 backdrop-blur-md"
          style={{
            background:
              "color-mix(in srgb, var(--color-bg-overlay) 70%, transparent)",
            boxShadow: "0 12px 40px -8px rgba(0, 0, 0, 0.6)",
          }}
        >
          <div className="flex items-center gap-6">
            {/* Headline delta */}
            <div className="flex items-center gap-3 border-r border-white/10 pr-6">
              {delta_usd < 0 ? (
                <TrendingDown className="h-7 w-7 text-rose-300" />
              ) : (
                <TrendingUp className="h-7 w-7 text-emerald-300" />
              )}
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">
                  Δ vs baseline
                </div>
                <RollUpNumber
                  value={delta_usd}
                  className={`font-mono text-3xl font-bold tabular-nums ${
                    delta_usd < 0 ? "text-rose-200" : "text-emerald-200"
                  }`}
                  signed
                />
              </div>
            </div>

            {/* Baseline → revised */}
            {typeof baseline_total_usd === "number" &&
              typeof revised_total_usd === "number" && (
                <div className="flex flex-col gap-1">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">
                    Q4 total
                  </div>
                  <div className="flex items-baseline gap-2 font-mono text-sm tabular-nums">
                    <span className="text-white/40 line-through">
                      {formatUSDCompact(baseline_total_usd)}
                    </span>
                    <span className="text-white/30">→</span>
                    <span className="text-white">
                      {formatUSDCompact(revised_total_usd)}
                    </span>
                  </div>
                </div>
              )}

            {/* Override count */}
            {typeof overrides_count === "number" && (
              <div className="flex flex-col gap-1 border-l border-white/10 pl-6">
                <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">
                  Overrides
                </div>
                <div className="font-mono text-sm tabular-nums text-white">
                  {overrides_count} basin
                  {overrides_count === 1 ? "" : "s"} · re-ingested
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// Animated numeric counter (signed). Mirrors RollUpNumber in
// `CostRollupBanner.tsx` but renders with sign for the delta case.
// ---------------------------------------------------------------------------

interface RollUpNumberProps {
  value: number;
  className?: string;
  durationSec?: number;
  signed?: boolean;
}

function RollUpNumber({
  value,
  className,
  durationSec = 1.1,
  signed = false,
}: RollUpNumberProps) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) => {
    const formatted = formatUSD(Math.abs(v));
    if (!signed) return formatted;
    return v < 0 ? `-${formatted}` : v > 0 ? `+${formatted}` : formatted;
  });
  const [rendered, setRendered] = useState(() =>
    signed ? `${value < 0 ? "-" : value > 0 ? "+" : ""}${formatUSD(0)}` : formatUSD(0),
  );

  useEffect(() => {
    const unsub = display.on("change", setRendered);
    return unsub;
  }, [display]);

  useEffect(() => {
    mv.set(0);
    const controls = animate(mv, value, {
      duration: durationSec,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [value, durationSec, mv]);

  return <span className={className}>{rendered}</span>;
}
