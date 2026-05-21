"use client";

/**
 * BasinTile.tsx
 *
 * Single basin card for the Persona 1 forecast-review canvas (TASK-14).
 *
 * Visual structure:
 *   ┌──────────────────────────────────────┐
 *   │ BASIN NAME             [confidence]  │  ← eyebrow + confidence pill
 *   │                                      │
 *   │ $215M                                │  ← baseline (or override) value
 *   │ +4% YoY                              │  ← delta line
 *   │                                      │
 *   │ [chip] [chip] [chip]                 │  ← rationale tags (when set)
 *   │                                      │
 *   │ ╭ Why is the model wrong here? ╮     │  ← prompt overlay (when promptOpen)
 *   └──────────────────────────────────────┘
 *
 * Three render states:
 *   1. Baseline-only  — model forecast, confidence pill, YoY delta.
 *   2. Active+prompt  — the "Why is the model wrong here?" prompt is open
 *                       next to the tile. Used in Beat 2.
 *   3. Overridden     — baseline strikes through; override value shows
 *                       in white with a red Δ line; rationale chips render.
 *
 * `pulse` is implicit: an `active` tile gets an emerald ring + subtle
 * glow so the demoer's eye lands on it.
 */

import { motion } from "framer-motion";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

import type { BasinTileData } from "@/data/demoScenarios";

interface BasinTileProps {
  tile: BasinTileData;
}

const USD_M = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
  style: "currency",
  currency: "USD",
});

function formatUsdCompact(n: number): string {
  // Intl compact gives "$215M" naturally — exactly the shape the brief asks for.
  return USD_M.format(n);
}

function formatYoy(pct: number): string {
  if (pct === 0) return "flat YoY";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct}% YoY`;
}

function confidencePillClasses(c: BasinTileData["confidence"]): string {
  switch (c) {
    case "high":
      return "border-emerald-400/40 bg-emerald-400/10 text-emerald-200";
    case "medium":
      return "border-amber-400/40 bg-amber-400/10 text-amber-200";
    case "low":
      return "border-rose-400/40 bg-rose-400/10 text-rose-200";
  }
}

// DEMO NARRATION (Beat 1): "Each tile is a basin. The pill on the right
// is the model's own confidence — Permian and Gulf are 'high', the long
// tail is hedging. That's where David's domain knowledge has leverage."
export function BasinTile({ tile }: BasinTileProps) {
  const overridden = typeof tile.override_usd === "number";
  const displayValue = overridden ? tile.override_usd! : tile.baseline_usd;
  const deltaUsd = overridden ? tile.override_usd! - tile.baseline_usd : 0;
  const deltaPct = overridden
    ? Math.round((deltaUsd / tile.baseline_usd) * 100)
    : 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className={`relative rounded-2xl border p-5 backdrop-blur-sm ${
        tile.active
          ? "border-emerald-400/50 shadow-[0_0_0_1px_rgba(16,185,129,0.25),0_8px_30px_-8px_rgba(16,185,129,0.45)]"
          : "border-white/10"
      }`}
      style={{
        background:
          "color-mix(in srgb, var(--color-bg-overlay) 60%, transparent)",
      }}
    >
      {/* Eyebrow row */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-white/50">
          {tile.label}
        </div>
        <ConfidencePill confidence={tile.confidence} />
      </div>

      {/* Value */}
      <div className="space-y-1">
        {overridden && (
          <div className="font-mono text-xs tabular-nums text-white/35 line-through">
            {formatUsdCompact(tile.baseline_usd)}
          </div>
        )}
        <div className="font-mono text-3xl font-semibold tabular-nums text-white">
          {formatUsdCompact(displayValue)}
        </div>

        {overridden ? (
          <div className="flex items-center gap-1.5 text-xs">
            <TrendingDown className="h-3.5 w-3.5 text-rose-300" />
            <span className="font-mono tabular-nums text-rose-300">
              {formatUsdCompact(Math.abs(deltaUsd))} ({deltaPct}%)
            </span>
            <span className="text-white/40">vs baseline</span>
          </div>
        ) : (
          <YoyLine pct={tile.yoy_pct} />
        )}
      </div>

      {/* Rationale chips */}
      {tile.rationaleTags && tile.rationaleTags.length > 0 && (
        <motion.div
          layout
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.3 }}
          className="mt-4 flex flex-wrap gap-1.5"
        >
          {tile.rationaleTags.map((tag) => (
            <span
              key={tag}
              className="rounded-md border border-emerald-400/30 bg-emerald-400/[0.06] px-2 py-1 font-mono text-[10px] tracking-wider text-emerald-200/90"
            >
              {tag}
            </span>
          ))}
        </motion.div>
      )}

      {/* "Why is the model wrong here?" prompt overlay */}
      {tile.promptOpen && <OverridePrompt basinLabel={tile.label} />}
    </motion.div>
  );
}

function ConfidencePill({
  confidence,
}: {
  confidence: BasinTileData["confidence"];
}) {
  return (
    <div
      className={`rounded-full border px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider ${confidencePillClasses(
        confidence,
      )}`}
    >
      {confidence} confidence
    </div>
  );
}

function YoyLine({ pct }: { pct: number }) {
  const Icon = pct > 0 ? TrendingUp : pct < 0 ? TrendingDown : Minus;
  const color =
    pct > 0
      ? "text-emerald-300"
      : pct < 0
        ? "text-rose-300"
        : "text-white/50";
  return (
    <div className={`flex items-center gap-1.5 text-xs ${color}`}>
      <Icon className="h-3.5 w-3.5" />
      <span className="font-mono tabular-nums">{formatYoy(pct)}</span>
    </div>
  );
}

// DEMO NARRATION (Beat 2): "Agent Inbox surfaces the prompt — 'Why is the
// model wrong here?'. David picks the structured option. Gemini extracts
// the rationale tags as he types."
function OverridePrompt({ basinLabel }: { basinLabel: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className="absolute left-full top-4 z-20 ml-3 w-72 rounded-xl border border-emerald-400/30 bg-black/80 p-4 shadow-2xl backdrop-blur-md"
    >
      <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-emerald-300/80">
        Forecast Review Agent
      </div>
      <div className="mb-3 text-sm font-medium text-white">
        Why is the model wrong here?
      </div>
      <div className="space-y-1.5">
        <PromptOption
          label={
            basinLabel === "Permian"
              ? "Rig count declined 8% MoM, not captured in the Q3 cut"
              : "Operator delays — three programs pushed to 2026 Q1"
          }
          selected
        />
        <PromptOption label="Customer mix shift" />
        <PromptOption label="Pricing pressure" />
      </div>
      <div className="mt-3 text-[10px] tracking-wider text-white/40">
        + freeform note · rationale tags extracted by Gemini
      </div>
    </motion.div>
  );
}

function PromptOption({
  label,
  selected = false,
}: {
  label: string;
  selected?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs ${
        selected
          ? "border-emerald-400/40 bg-emerald-400/10 text-white"
          : "border-white/5 text-white/50"
      }`}
    >
      <div
        className={`h-1.5 w-1.5 rounded-full ${
          selected ? "bg-emerald-400" : "bg-white/20"
        }`}
      />
      {label}
    </div>
  );
}
