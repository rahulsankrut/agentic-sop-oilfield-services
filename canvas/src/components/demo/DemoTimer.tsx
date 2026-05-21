"use client";

/**
 * DemoTimer.tsx
 *
 * Unobtrusive elapsed-time chip for every scenario page (TASK-12 Step 5).
 *
 * Reads `startedAt` from the global demo context (set by the scenario
 * page on first user action, e.g. first Space press or live trigger).
 * Renders `M:SS / TARGET:00` in the bottom-right corner of the canvas.
 *
 * Color rules:
 *   - White-on-transparent while under target.
 *   - Amber once elapsed > target.
 *   - Rose once elapsed > target * 1.2 (warning glow).
 *
 * Spec footnote (per pitfalls): "Demo timer showing red on first run.
 * If the timer goes amber/red the moment you hit the persona, it's
 * because `startedAt` defaults to scenario load time instead of trigger
 * time." We address this by:
 *   - Defaulting `startedAt` to null (no tick at all until set).
 *   - Showing `--:-- / TARGET:00` until the scenario publishes startedAt.
 *
 * The display does NOT bind to the persona's `targetDurationMin` directly
 * — scenario pages pass it explicitly so the chip can render even when the
 * page is wrapped in a different persona context (replay-of-a-different-scenario,
 * dev preview, etc.).
 */

import { useEffect, useState } from "react";

export interface DemoTimerProps {
  /** Target wall-clock minutes for the scenario. */
  targetMinutes: number;
  /**
   * Unix timestamp (ms) the scenario started, or null while not started.
   * Pass `Date.now()` on first user action, then keep stable until reset.
   */
  startedAt: number | null;
  /** Optional position override; defaults to bottom-right. */
  className?: string;
}

export function DemoTimer({
  targetMinutes,
  startedAt,
  className,
}: DemoTimerProps) {
  const [now, setNow] = useState<number>(() => Date.now());

  // Tick once per second only while started — saves a Hot setInterval on
  // the launcher and idle pages.
  useEffect(() => {
    if (startedAt == null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const targetSeconds = Math.max(0, targetMinutes * 60);

  if (startedAt == null) {
    return (
      <div
        className={
          className ??
          "absolute bottom-6 right-6 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 font-mono text-[11px] tracking-wider text-white/40 backdrop-blur-md"
        }
        aria-label="Demo timer, not yet started"
      >
        --:-- / {formatMmSs(targetSeconds)}
      </div>
    );
  }

  const elapsedSec = Math.max(0, Math.floor((now - startedAt) / 1000));
  const overshoot = elapsedSec - targetSeconds;
  const colorClass =
    overshoot > targetSeconds * 0.2
      ? "border-rose-400/40 text-rose-300"
      : overshoot > 0
        ? "border-amber-400/40 text-amber-300"
        : "border-white/10 text-white/70";

  return (
    <div
      className={
        className ??
        `absolute bottom-6 right-6 rounded-full border bg-black/40 px-3 py-1.5 font-mono text-[11px] tracking-wider backdrop-blur-md ${colorClass}`
      }
      aria-label={`Demo timer ${formatMmSs(elapsedSec)} of ${formatMmSs(targetSeconds)}`}
    >
      {formatMmSs(elapsedSec)} / {formatMmSs(targetSeconds)}
    </div>
  );
}

function formatMmSs(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
