"use client";

/**
 * Persona 1 (David, Basin Leader) — forecast review scenario page.
 *
 * Static demo mode: beat-by-beat scenario state from `forecastReviewBeats`.
 * Space advances, Shift+Space / B steps back, R resets, P pauses, L is a
 * no-op for now (no live mode wired for this scenario yet).
 *
 * Layout differs from the cargo-plane and buffer-planning pages — there's
 * no map and no chart. The canvas is a grid of `BasinTile` cards (the Q4
 * forecast) with a `ForecastDeltaBanner` rolling up at the bottom once
 * David's overrides land. The structural pattern (chat panel left, canvas
 * center, BeatIndicator, DemoTimer, demo-context publish) is preserved
 * verbatim from `/scenarios/cargo-plane`.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { BasinTile } from "@/components/forecast/BasinTile";
import { ForecastDeltaBanner } from "@/components/forecast/ForecastDeltaBanner";
import { DemoTimer } from "@/components/demo/DemoTimer";
import type { BasinTileData } from "@/data/demoScenarios";
import { forecastReviewBeats } from "@/data/scenarios/forecastReview";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useScenario } from "@/hooks/useScenario";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { preWarmSession } from "@/lib/preWarmSession";
import { getPersona } from "@/lib/skin";

// Persona 1 — David, Permian Basin Director. Pulled from the active skin
// so every customer skin re-skins his name and role for free.
const DAVID_PERSONA = getPersona("david");
const DAVID_FIRST_NAME = DAVID_PERSONA.name.split(" ")[0];
const DAVID_OPENING_PROMPT =
  "Show me Q4 by basin — I want to override two basins where the model is missing the rig-count slowdown.";

export default function ForecastReviewScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(
    () => personaForPathname(pathname),
    [pathname],
  );

  const scenario = useScenario({ beats: forecastReviewBeats });
  const { state, currentBeat, currentBeatIndex, totalBeats } = scenario;

  const [paused, setPaused] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  // Pre-warm Memory Bank on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  const hardReset = useCallback(() => {
    setPaused(false);
    setStartedAt(null);
    scenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, scenario]);

  const skipToEnd = useCallback(() => {
    const stepsLeft = scenario.totalBeats - 1 - scenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) scenario.advance();
  }, [scenario]);

  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      scenario.advance();
    },
    onStepBack: () => scenario.stepBack(),
    onReset: hardReset,
    // Live mode for forecast-review lands later; L is intentionally a no-op.
    onToggleMode: undefined,
    onPause: () => setPaused((p) => !p),
  });

  // Publish into the global demo context (Backstage / 1..6 hotkeys read this).
  useEffect(() => {
    if (!persona) return;
    const nextBeat =
      currentBeatIndex < forecastReviewBeats.length - 1
        ? forecastReviewBeats[currentBeatIndex + 1]
        : null;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex,
      totalBeats,
      currentBeatId: currentBeat.id,
      narrationCue: currentBeat.narration,
      nextBeatId: nextBeat?.id ?? null,
      nextNarrationCue: nextBeat?.narration ?? null,
      mode: "static",
      connectionState: "idle",
      lastError: null,
      startedAt,
      onReset: hardReset,
      onToggleMode: null,
      onPause: () => setPaused((p) => !p),
      onSkipToEnd: skipToEnd,
    });
    return cleanup;
  }, [
    persona,
    currentBeat,
    currentBeatIndex,
    totalBeats,
    startedAt,
    hardReset,
    skipToEnd,
  ]);

  const tiles = state.basinTiles ?? [];
  const forecastDelta = state.forecastDelta ?? { visible: false };
  const forecastToast = state.forecastToast ?? { visible: false };

  return (
    <CanvasShell
      drawerOpen={false}
      chat={
        <ChatPanel
          beatId={currentBeat.id}
          narration={currentBeat.narration}
          index={currentBeatIndex}
          total={totalBeats}
          paused={paused}
        />
      }
      canvas={
        <div
          className="relative h-full overflow-y-auto"
          style={{ background: "var(--color-bg-base)" }}
        >
          <div className="flex h-full flex-col gap-6 p-8">
            <header className="flex items-start justify-between gap-6">
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
                  {DAVID_PERSONA.region} · Q4 demand sensing
                </div>
                <h1 className="mt-1 text-2xl font-semibold">
                  Q4 completions revenue · by basin
                </h1>
                <p className="mt-1 text-sm text-white/50">
                  ML baseline from BigQuery measures · {DAVID_FIRST_NAME}{" "}
                  reviewing
                </p>
              </div>

              <MlForecastTile
                visible={tiles.length > 0}
                baselineTotal={tiles.reduce(
                  (acc, t) => acc + t.baseline_usd,
                  0,
                )}
              />
            </header>

            {tiles.length === 0 ? (
              <ForecastLoadingPlaceholder />
            ) : (
              <BasinGrid tiles={tiles} />
            )}

            <div className="flex-1" />

            <BeatIndicator
              index={currentBeatIndex}
              total={totalBeats}
            />
          </div>

          <ForecastDeltaBanner state={forecastDelta} />

          <ForecastToast
            visible={!!forecastToast.visible}
            message={forecastToast.message}
          />

          {persona && (
            <DemoTimer
              targetMinutes={persona.targetDurationMin}
              startedAt={startedAt}
            />
          )}
        </div>
      }
    />
  );
}

// ---------------------------------------------------------------------------
// Basin grid — three columns on large screens, two on medium, one on small.
// `BasinTile` handles its own layout animation so reordering / overriding
// stays smooth.
// ---------------------------------------------------------------------------

function BasinGrid({ tiles }: { tiles: BasinTileData[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {tiles.map((t) => (
        <BasinTile key={t.id} tile={t} />
      ))}
    </div>
  );
}

function ForecastLoadingPlaceholder() {
  return (
    <div className="flex h-[360px] w-full items-center justify-center rounded-2xl border border-white/5 bg-white/[0.03]">
      <div className="text-sm text-white/40">
        Forecast Review Agent spinning up — press Space to advance.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ML forecast tile in the top-right (the "model says X" reference). Mirrors
// the storyboard's Beat 0 description: "ML forecast tile in top-right
// showing Q4 completions revenue baseline."
// ---------------------------------------------------------------------------

interface MlForecastTileProps {
  visible: boolean;
  baselineTotal: number;
}

const USD_COMPACT = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
  style: "currency",
  currency: "USD",
});

function MlForecastTile({ visible, baselineTotal }: MlForecastTileProps) {
  if (!visible) return null;
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-xl border border-white/10 px-4 py-3 backdrop-blur-md"
      style={{
        background:
          "color-mix(in srgb, var(--color-bg-overlay) 60%, transparent)",
      }}
    >
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
        BigQuery ML · Q4 baseline
      </div>
      <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-white">
        {USD_COMPACT.format(baselineTotal)}
      </div>
      <div className="mt-0.5 text-[10px] text-white/40">
        completions revenue · model v1.2
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Chat panel — same shape as cargo-plane / buffer-planning, skin-aware.
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  beatId: string;
  narration: string;
  index: number;
  total: number;
  paused: boolean;
}

function ChatPanel({ beatId, narration, index, total, paused }: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        {DAVID_FIRST_NAME} · {DAVID_PERSONA.role} — {DAVID_PERSONA.region}
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>

      {/* David's opening question — shown as a chat bubble */}
      <div className="mb-4 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.04] p-3">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-emerald-300/70">
          {DAVID_FIRST_NAME}
        </div>
        <div className="text-sm text-white/90">{DAVID_OPENING_PROMPT}</div>
      </div>

      <div className="flex-1 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.03] p-4">
        <div className="mb-2 text-[10px] uppercase tracking-wider text-white/40">
          Beat {index + 1} / {total} {paused ? "· paused" : ""}
        </div>
        <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
          {beatId}
        </div>
        <div className="text-sm leading-relaxed text-white/90">{narration}</div>
      </div>
      <div className="mt-4 text-[10px] uppercase tracking-wider text-white/40">
        Space advance · Shift+Space back · R reset · P pause · \ backstage
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bottom beat indicator (matches cargo-plane treatment).
// ---------------------------------------------------------------------------

interface BeatIndicatorProps {
  index: number;
  total: number;
}

function BeatIndicator({ index, total }: BeatIndicatorProps) {
  return (
    <div className="flex items-center gap-3 self-start rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">
        Static demo
      </div>
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 w-6 rounded-full transition-colors ${
              i === index
                ? "bg-white"
                : i < index
                  ? "bg-white/40"
                  : "bg-white/10"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Beat 5 confirmation toast — "saved as v2".
// ---------------------------------------------------------------------------

function ForecastToast({
  visible,
  message,
}: {
  visible: boolean;
  message?: string;
}) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="forecast-toast"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="absolute left-1/2 top-6 z-20 -translate-x-1/2 rounded-full border border-emerald-400/40 bg-black/70 px-4 py-2 backdrop-blur-md"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            <div className="text-[12px] text-white/90">
              {message ?? "Forecast saved."}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
