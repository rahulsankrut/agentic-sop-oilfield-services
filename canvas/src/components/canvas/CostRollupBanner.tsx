"use client";

import { useEffect, useState } from "react";
import {
  AnimatePresence,
  animate,
  motion,
  useMotionValue,
  useTransform,
} from "framer-motion";
import { TrendingDown } from "lucide-react";

interface CostRollupBannerProps {
  visible: boolean;
  /** The naive plan cost — e.g. $700K cargo charter. Rendered with strikethrough. */
  doomed?: number;
  /** The smart plan cost — e.g. $216K ground transit. Rendered in white. */
  recommended?: number;
  /** Savings — usually `doomed - recommended`. Rolls up from 0 with animation. */
  avoided?: number;
}

const USD = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function formatUSD(value: number): string {
  return USD.format(Math.round(value));
}

// DEMO NARRATION (Beat 7/8): "The cost roll-up animates in. The doomed
// $700K cargo charter strikes through. The recommended $216K ground transit
// from Lagos replaces it. And the savings — $484K — rolls up in green.
// The customer's CFO can read this from across the room."
export function CostRollupBanner({
  visible,
  doomed,
  recommended,
  avoided,
}: CostRollupBannerProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="cost-rollup-banner"
          initial={{ y: -32, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -32, opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="absolute top-6 right-6 z-10 min-w-[320px] rounded-2xl border border-white/10 p-5 backdrop-blur-md"
          style={{
            background:
              "color-mix(in srgb, var(--color-bg-overlay) 70%, transparent)",
            boxShadow: "0 12px 40px -8px rgba(0, 0, 0, 0.6)",
          }}
        >
          {/* Doomed (strikethrough) */}
          {typeof doomed === "number" && (
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="text-[11px] uppercase tracking-wider text-white/40">
                Doomed plan
              </span>
              <span
                className="font-mono text-sm tabular-nums line-through"
                style={{ color: "var(--color-cost-avoided)" }}
              >
                {formatUSD(doomed)}
              </span>
            </div>
          )}

          {/* Recommended */}
          {typeof recommended === "number" && (
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <span className="text-[11px] uppercase tracking-wider text-white/40">
                Recommended
              </span>
              <span className="font-mono text-base tabular-nums text-white">
                {formatUSD(recommended)}
              </span>
            </div>
          )}

          {/* Avoided — animated roll-up */}
          {typeof avoided === "number" && (
            <div
              className="flex items-baseline justify-between gap-3 border-t pt-3"
              style={{ borderColor: "rgba(255,255,255,0.08)" }}
            >
              <div className="flex items-center gap-1.5">
                <TrendingDown
                  className="h-4 w-4"
                  style={{ color: "var(--color-cost-saved)" }}
                />
                <span className="text-[11px] uppercase tracking-wider text-white/60">
                  Avoided
                </span>
              </div>
              <RollUpNumber
                value={avoided}
                className="font-mono text-3xl font-bold tabular-nums"
                style={{ color: "var(--color-cost-saved)" }}
              />
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---------------------------------------------------------------------------
// Animated numeric counter
// ---------------------------------------------------------------------------

interface RollUpNumberProps {
  value: number;
  className?: string;
  style?: React.CSSProperties;
  /** Animation duration in seconds. */
  durationSec?: number;
}

/**
 * Counts from 0 to `value` over `durationSec`, formatted as USD.
 * Re-runs whenever `value` changes so the roll-up re-plays on prop change.
 */
function RollUpNumber({
  value,
  className,
  style,
  durationSec = 1.1,
}: RollUpNumberProps) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) => formatUSD(v));
  // useTransform yields a MotionValue<string>; mirror it into local state so
  // the value is rendered through React (motion.span renders MotionValues too,
  // but using local state keeps the JSX explicit and avoids Server Components
  // serialization quirks under Next 16).
  const [rendered, setRendered] = useState(() => formatUSD(0));

  useEffect(() => {
    const unsubscribe = display.on("change", setRendered);
    return unsubscribe;
  }, [display]);

  useEffect(() => {
    mv.set(0);
    const controls = animate(mv, value, {
      duration: durationSec,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [value, durationSec, mv]);

  return (
    <span className={className} style={style}>
      {rendered}
    </span>
  );
}
