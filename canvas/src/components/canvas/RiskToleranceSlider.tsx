"use client";

import { motion, useMotionValue, type PanInfo } from "framer-motion";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import type { BufferOption } from "@/data/fleetUtilizationData";

interface RiskToleranceSliderProps {
  options: BufferOption[];
  value: BufferOption["risk_tolerance"];
  onChange: (v: BufferOption["risk_tolerance"]) => void;
}

const TOLERANCE_LABELS = ["conservative", "balanced", "aggressive"] as const;
const THUMB_SIZE = 24; // px — matches h-6 w-6

// DEMO NARRATION (Beat 4): "Watch what happens when Tomas drags this
// slider from Conservative — his default — to Balanced. The buffer drops
// from 18% to 12%. The buffered capacity line on the chart slides down.
// The tradeoff panel updates: idle cost drops by 400K but late-start
// exposure rises. The agent is helping him visualize a tradeoff that
// previously lived in a spreadsheet only one person fully understood."
export function RiskToleranceSlider({
  options: _options,
  value,
  onChange,
}: RiskToleranceSliderProps) {
  const currentIndex = Math.max(0, TOLERANCE_LABELS.indexOf(value));

  const trackRef = useRef<HTMLDivElement | null>(null);
  const [trackWidth, setTrackWidth] = useState(0);
  const thumbX = useMotionValue(0);

  // Measure the track so drag constraints + position math use pixels, not %.
  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return;

    const measure = () => setTrackWidth(el.getBoundingClientRect().width);
    measure();

    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Keep the motion value in sync with the controlled `value` prop (and on resize).
  useEffect(() => {
    if (trackWidth === 0) return;
    const target = (currentIndex / 2) * trackWidth - THUMB_SIZE / 2;
    thumbX.set(target);
  }, [currentIndex, trackWidth, thumbX]);

  const snapToNearest = useCallback(
    (centerPx: number) => {
      if (trackWidth === 0) return;
      const ratio = Math.min(1, Math.max(0, centerPx / trackWidth));
      const idx = Math.round(ratio * 2) as 0 | 1 | 2;
      const next = TOLERANCE_LABELS[idx];
      if (next !== value) onChange(next);
    },
    [trackWidth, value, onChange],
  );

  const handleDragEnd = useCallback(
    (_e: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      if (trackWidth === 0) return;
      // info.point.x is viewport-relative; convert to track-relative center.
      const rect = trackRef.current?.getBoundingClientRect();
      if (!rect) return;
      const centerPx = info.point.x - rect.left;
      snapToNearest(centerPx);
    },
    [snapToNearest, trackWidth],
  );

  const handleKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowRight" || e.key === "ArrowUp") {
        e.preventDefault();
        const next = TOLERANCE_LABELS[Math.min(2, currentIndex + 1)];
        if (next !== value) onChange(next);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
        e.preventDefault();
        const next = TOLERANCE_LABELS[Math.max(0, currentIndex - 1)];
        if (next !== value) onChange(next);
      } else if (e.key === "Home") {
        e.preventDefault();
        if (TOLERANCE_LABELS[0] !== value) onChange(TOLERANCE_LABELS[0]);
      } else if (e.key === "End") {
        e.preventDefault();
        if (TOLERANCE_LABELS[2] !== value) onChange(TOLERANCE_LABELS[2]);
      }
    },
    [currentIndex, value, onChange],
  );

  // Filled portion uses the controlled index so it animates whether the
  // user dragged, clicked a label, or pressed an arrow key.
  const fillWidthPct = (currentIndex / 2) * 100;

  return (
    <div className="rounded-2xl bg-white/5 p-6">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-white/70">Risk tolerance</h3>
        <span className="text-xs text-white/40">drag or click a label</span>
      </div>

      {/* Track */}
      <div ref={trackRef} className="relative mb-4 h-2 rounded-full bg-white/10">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ background: "linear-gradient(90deg, #10b981, #f59e0b)" }}
          animate={{ width: `${fillWidthPct}%` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
        <motion.div
          role="slider"
          tabIndex={0}
          aria-label="Risk tolerance"
          aria-valuemin={0}
          aria-valuemax={2}
          aria-valuenow={currentIndex}
          aria-valuetext={TOLERANCE_LABELS[currentIndex]}
          onKeyDown={handleKeyDown}
          className="absolute top-1/2 h-6 w-6 -translate-y-1/2 rounded-full bg-white shadow-lg cursor-grab outline-none focus-visible:ring-2 focus-visible:ring-white/60 active:cursor-grabbing"
          style={{ x: thumbX, left: 0 }}
          drag="x"
          dragConstraints={{
            left: -THUMB_SIZE / 2,
            right: Math.max(0, trackWidth - THUMB_SIZE / 2),
          }}
          dragElastic={0}
          dragMomentum={false}
          onDragEnd={handleDragEnd}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between text-sm">
        {TOLERANCE_LABELS.map((label) => (
          <button
            key={label}
            type="button"
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
