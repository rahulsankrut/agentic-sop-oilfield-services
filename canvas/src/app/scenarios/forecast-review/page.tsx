"use client";

/**
 * Persona 1 (David, Basin Leader) — forecast review scenario page.
 *
 * Tri-state mode (P1 wiring, 2026-05-22):
 *  - "static" — beat-by-beat scenario state from `forecastReviewBeats`.
 *               Space advances, B / Shift+Space steps back, R resets.
 *  - "live"   — same scripted beats, but on advance into beat 3 the page
 *               makes ONE real call to the deployed Forecast Review Agent
 *               with David's Permian override + freeform note. The returned
 *               `ForecastRationale.rationale_tags` REPLACE the static
 *               `PERMIAN_TAGS` chip set on the Permian tile. Everything
 *               else (Gulf override, save toast, delta banner) stays
 *               scripted — only the one beat where the agent is genuinely
 *               doing LLM work is wired to the live agent. Press `L` to
 *               toggle Static ↔ Live.
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
import { useAgentCall } from "@/hooks/useAgentCall";
import { preWarmSession } from "@/lib/preWarmSession";
import { getPersona } from "@/lib/skin";

// Mirror of `agents.schemas.ForecastRationale`. Inlined rather than added to
// a shared types module — it's the only TS consumer today.
interface ForecastRationale {
  override_id: string;
  rationale_tags: string[];
  freeform_text: string;
  confidence: number;
}

type Mode = "static" | "live";

// Persona 1 — David, Permian Basin Director. Pulled from the active skin
// so every customer skin re-skins his name and role for free.
const DAVID_PERSONA = getPersona("david");
const DAVID_FIRST_NAME = DAVID_PERSONA.name.split(" ")[0];
const DAVID_USER_ID = DAVID_PERSONA.memory_profile_user_id;
const DAVID_OPENING_PROMPT =
  "Show me Q4 by basin — I want to override two basins where the model is missing the rig-count slowdown.";

// The live call the page fires on entry to beat 3. Matches the eval-tested
// format in agents/forecast_review_agent/evals/forecast_review_agent.evalset.json
// (`persona1_david_permian_q4_completions`), with the $ amounts tuned to the
// canvas's Permian baseline ($215M → $186M, a 13% override). The Forecast
// Review Agent's instruction in agents/forecast_review_agent/prompts.py
// extracts override_id, original_value, override_value, freeform_text from
// this natural-language form.
const DAVID_LIVE_PROMPT =
  "Q4 forecast review for the permian basin. " +
  "override_id: ovr-pm-q4-david-001. " +
  "The ML model projected Q4 completions revenue of $215M; I'm overriding " +
  "to $186M (down 13%). Reason: rig count declined 8% MoM, not captured in " +
  "the Q3 cut. Two operators paused programs in the Permian. " +
  "Permian-specific signal, not basin-wide weakness.";

const FORECAST_STREAM_URL =
  process.env.NEXT_PUBLIC_FORECAST_REVIEW_STREAM_URL ?? "";

// Per-beat auto-advance durations in live mode (ms). Beat 3 uses 0 because
// its advance is gated on the live LLM call resolving — the duration kicks
// in only after the response lands.
const LIVE_BEAT_DURATIONS_MS = [1200, 2200, 1800, 0, 2200, 2500];

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
  // Default to "live" — if the env var is missing or the call fails, we
  // gracefully render the static tags. Press `L` to force static.
  const [mode, setMode] = useState<Mode>(
    FORECAST_STREAM_URL ? "live" : "static",
  );
  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  const forecastCall = useAgentCall<ForecastRationale>({
    streamUrl: FORECAST_STREAM_URL,
    userId: DAVID_USER_ID,
  });

  // Pre-warm Memory Bank on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  // In live mode, mark started as soon as the page mounts so the demo
  // timer rolls — the experience is auto-play, no Space press required.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (mode === "live") markStarted();
  }, [mode, markStarted]);

  const hardReset = useCallback(() => {
    setPaused(false);
    setStartedAt(null);
    forecastCall.reset();
    scenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, scenario, forecastCall]);

  const skipToEnd = useCallback(() => {
    const stepsLeft = scenario.totalBeats - 1 - scenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) scenario.advance();
  }, [scenario]);

  const toggleMode = useCallback(() => {
    setMode((m) => (m === "live" ? "static" : "live"));
  }, []);

  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      scenario.advance();
    },
    onStepBack: () => scenario.stepBack(),
    onReset: hardReset,
    onToggleMode: toggleMode,
    onPause: () => setPaused((p) => !p),
  });

  // Fire the live call on entry to beat 3 (rationale-extracted). One call
  // per scenario run; reset by `R` (hardReset clears forecastCall) or by
  // returning to an earlier beat and re-advancing only if status is idle.
  useEffect(() => {
    if (mode !== "live") return;
    if (currentBeatIndex < 3) return;
    if (forecastCall.status !== "idle") return;
    if (!FORECAST_STREAM_URL) return;
    forecastCall.run(DAVID_LIVE_PROMPT);
  }, [mode, currentBeatIndex, forecastCall]);

  // In live mode the page auto-advances so the experience mirrors the real
  // product — David doesn't press Space; he opens the override form, types,
  // submits, and the tile updates on its own. Beats fire on per-beat timers
  // EXCEPT beat 3 which waits for the live LLM response before progressing
  // (otherwise we'd be advancing past empty data). Space + Backspace still
  // work as manual overrides; P pauses the auto-advance.
  //
  // Static mode keeps the original Space-only flow for rehearsal.
  useEffect(() => {
    if (mode !== "live") return;
    if (paused) return;
    if (currentBeatIndex >= totalBeats - 1) return;
    // Beat 3 advance is gated on the live call resolving so the tag chips
    // are visible before the overrides-applied beat lands.
    if (currentBeatIndex === 3 && forecastCall.status === "loading") return;
    const dur = LIVE_BEAT_DURATIONS_MS[currentBeatIndex] ?? 2000;
    const delay = currentBeatIndex === 3 ? Math.max(dur, 1200) : dur;
    const timer = setTimeout(() => {
      scenario.advance();
    }, delay);
    return () => clearTimeout(timer);
  }, [
    mode,
    paused,
    currentBeatIndex,
    totalBeats,
    forecastCall.status,
    scenario,
  ]);

  // Publish into the global demo context (Backstage / 1..6 hotkeys read this).
  useEffect(() => {
    if (!persona) return;
    const nextBeat =
      currentBeatIndex < forecastReviewBeats.length - 1
        ? forecastReviewBeats[currentBeatIndex + 1]
        : null;
    const liveConnState =
      forecastCall.status === "loading"
        ? "connecting"
        : forecastCall.status === "ok"
          ? "open"
          : forecastCall.status === "error"
            ? "error"
            : "idle";
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex,
      totalBeats,
      currentBeatId: currentBeat.id,
      narrationCue: currentBeat.narration,
      nextBeatId: nextBeat?.id ?? null,
      nextNarrationCue: nextBeat?.narration ?? null,
      mode,
      connectionState: mode === "live" ? liveConnState : "idle",
      lastError: mode === "live" ? forecastCall.error : null,
      startedAt,
      onReset: hardReset,
      onToggleMode: toggleMode,
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
    mode,
    forecastCall.status,
    forecastCall.error,
    toggleMode,
  ]);

  // Patch the Permian tile's rationaleTags with the live agent response when
  // available. In live+loading state we clear the static tags so the chip
  // area surfaces the "classifying…" indicator below the tile instead.
  const tiles = useMemo<BasinTileData[]>(() => {
    const base = state.basinTiles ?? [];
    if (mode !== "live") return base;
    if (currentBeatIndex < 3) return base;
    return base.map((t) => {
      if (t.id !== "permian") return t;
      if (forecastCall.status === "ok" && forecastCall.data) {
        return { ...t, rationaleTags: forecastCall.data.rationale_tags };
      }
      if (forecastCall.status === "loading") {
        return { ...t, rationaleTags: [] };
      }
      // status === "idle" | "error" → fall back to the static tags shipped
      // in the beat's state. Error gets surfaced via the LiveStatusPill.
      return t;
    });
  }, [
    state.basinTiles,
    mode,
    currentBeatIndex,
    forecastCall.status,
    forecastCall.data,
  ]);
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
          mode={mode}
          liveStatus={forecastCall.status}
          liveError={forecastCall.error}
          liveData={forecastCall.data}
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
              mode={mode}
            />
          </div>

          <ForecastDeltaBanner state={forecastDelta} />

          <ForecastToast
            visible={!!forecastToast.visible}
            message={forecastToast.message}
          />

          <LiveStatusPill
            mode={mode}
            status={forecastCall.status}
            confidence={forecastCall.data?.confidence}
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
  mode: Mode;
  liveStatus: "idle" | "loading" | "ok" | "error";
  liveError: string | null;
  liveData: ForecastRationale | null;
}

function ChatPanel({
  beatId,
  narration,
  index,
  total,
  paused,
  mode,
  liveStatus,
  liveError,
  liveData,
}: ChatPanelProps) {
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

      {mode === "live" && index >= 3 && (
        <LiveAgentBubble status={liveStatus} error={liveError} data={liveData} />
      )}

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
        Space advance · Shift+Space back · R reset · L mode · P pause · \
        backstage
      </div>
    </div>
  );
}

// Chat-side surface for the live Forecast Review Agent call. Only renders
// at beat 3+ when mode is "live" — that's the one beat where the agent is
// actually doing work (classifying David's freeform rationale).
function LiveAgentBubble({
  status,
  error,
  data,
}: {
  status: "idle" | "loading" | "ok" | "error";
  error: string | null;
  data: ForecastRationale | null;
}) {
  const dot =
    status === "loading"
      ? "bg-amber-400 animate-pulse"
      : status === "ok"
        ? "bg-emerald-400"
        : status === "error"
          ? "bg-rose-400"
          : "bg-white/40";
  return (
    <div className="mb-4 rounded-xl border border-sky-400/20 bg-sky-400/[0.04] p-3">
      <div className="mb-1 flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${dot}`} />
        <div className="text-[10px] uppercase tracking-wider text-sky-300/80">
          Forecast Review Agent · live
        </div>
      </div>
      {status === "loading" && (
        <div className="text-sm text-white/80">
          Classifying David&apos;s freeform note into structured rationale tags…
        </div>
      )}
      {status === "ok" && data && (
        <div className="text-sm text-white/90">
          <span className="text-white/60">Tags:</span>{" "}
          <span className="font-mono">[{data.rationale_tags.join(", ")}]</span>
          <span className="ml-2 text-white/50">
            · confidence {data.confidence.toFixed(2)}
          </span>
        </div>
      )}
      {status === "error" && (
        <div className="text-sm text-rose-200">
          Live call failed — falling back to scripted tags. ({error ?? "unknown"})
        </div>
      )}
      {status === "idle" && (
        <div className="text-sm text-white/60">
          Awaiting trigger — advance to beat 3 to call the agent.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bottom beat indicator (matches cargo-plane treatment).
// ---------------------------------------------------------------------------

interface BeatIndicatorProps {
  index: number;
  total: number;
  mode: Mode;
}

function BeatIndicator({ index, total, mode }: BeatIndicatorProps) {
  return (
    <div className="flex items-center gap-3 self-start rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/50">
        {mode === "live" ? "Live demo" : "Static demo"}
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

// Small top-left pill — same vibe as cargo-plane's ModeIndicator. Shows the
// active mode and, when live, the connection state to the Forecast Review
// Agent. Helps the demoer (and the audience) see at a glance whether the
// rationale tags they're about to see came from a real LLM call or static.
function LiveStatusPill({
  mode,
  status,
  confidence,
}: {
  mode: Mode;
  status: "idle" | "loading" | "ok" | "error";
  confidence?: number;
}) {
  const dot =
    mode !== "live"
      ? "bg-white/40"
      : status === "loading"
        ? "bg-amber-400 animate-pulse"
        : status === "ok"
          ? "bg-emerald-400"
          : status === "error"
            ? "bg-rose-400"
            : "bg-white/40";
  const sub =
    mode !== "live"
      ? null
      : status === "loading"
        ? "classifying…"
        : status === "ok"
          ? confidence != null
            ? `ok · conf ${confidence.toFixed(2)}`
            : "ok"
          : status === "error"
            ? "fallback → static"
            : "idle";
  return (
    <div className="absolute top-6 left-6 z-10 flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 backdrop-blur-md">
      <div className={`h-2 w-2 rounded-full ${dot}`} />
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/70">
        {mode}
      </div>
      {sub && (
        <div className="text-[10px] tracking-wider text-white/40">· {sub}</div>
      )}
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
