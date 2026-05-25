"use client";

/**
 * Persona 2 (Tomas, West Texas Fleet Scheduler) — buffer-planning scenario.
 *
 * Tri-state mode (P2 wiring, 2026-05-22):
 *  - "static" — beat-by-beat scenario state from `bufferPlanningBeats`.
 *  - "live"   — same scripted beats, but two real calls to the deployed
 *               Capacity Planning Agent replace the static stat-tile and
 *               timeline numbers at the moments the agent is genuinely
 *               doing optimization work:
 *                 Beat 2 (initial 14→8 drop, risk_tolerance=0.5)
 *                 Beat 3 (counter-proposal, risk_tolerance=0.7)
 *               Press `L` to toggle Static ↔ Live.
 *
 * Choreography (6 beats, ~3 min):
 *   Space → Beat 0..5. Shift+Space steps back, R resets, P pauses,
 *   \ opens the global backstage panel.
 *
 *   Beat 0  chat panel posts Tomas's opening prompt; canvas opens to the
 *           30-day Permian fleet timeline at the status-quo 14-day buffer.
 *   Beat 1  stat tiles surface: 14d buffer, 92% on-time, 68% utilization.
 *   Beat 2  agent models the 14→8 buffer drop. Stats reflow; timeline
 *           tightens; risk-tolerance slider stays at 0.5.
 *   Beat 3  risk-tolerance slider animates 0.5 → 0.7; agent counter-
 *           proposes a 10-day buffer. Stats land at 78% / 76% / $3.2M.
 *   Beat 4  Tomas accepts; the BufferCommitBanner appears at the bottom
 *           of the canvas.
 *   Beat 5  saved-as confirmation; persona timer rolls.
 *
 * Wiring identical to the cargo-plane page: rehearsal controls, demo
 * context publication, pre-warm on mount.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { FleetDailyTimelineChart } from "@/components/canvas/FleetTimelineChart";
import { RiskToleranceSliderContinuous } from "@/components/canvas/RiskToleranceSlider";
import { BufferCommitBanner } from "@/components/canvas/BufferCostReconciliation";
import { DemoTimer } from "@/components/demo/DemoTimer";
import {
  bufferPlanningBeats,
  buildTimeline,
} from "@/data/scenarios/bufferPlanning";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useScenario } from "@/hooks/useScenario";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { useAgentCall } from "@/hooks/useAgentCall";
import { preWarmSession } from "@/lib/preWarmSession";
import { getPersona } from "@/lib/skin";

// Mirror of `agents.schemas.BufferOptimization`. Inlined rather than added
// to a shared types module — it's the only TS consumer today.
interface BufferOptimization {
  request_id: string;
  basin: string;
  risk_tolerance: number;
  current_buffer_days: number;
  recommended_buffer_days: number;
  projected_on_time_rate: number; // 0.0..1.0
  fleet_utilization_uplift_pct: number;
  deferred_capex_usd: number;
}

type Mode = "static" | "live";

const TOMAS_PERSONA = getPersona("tomas");
const TOMAS_USER_ID = TOMAS_PERSONA.memory_profile_user_id;
const TOMAS_OPENING_PROMPT =
  'Show me Permian fleet utilization and the buffer trade-off — I want to drop the buffer from 14 to 8 days and see what the on-time rate does.';

// Two prompts — one per live-call moment. Match the eval-tested format in
// agents/capacity_planning_agent/evals/capacity_planning_agent.evalset.json
// (`persona2_tomas_west_texas_q3`), parameterized on risk_tolerance for the
// initial drop (0.5) vs. the counter-proposal (0.7). The agent's instruction
// in agents/capacity_planning_agent/prompts.py parses basin + risk_tolerance
// from this single-sentence form.
const BUFFER_DROP_PROMPT =
  "What's my buffer exposure on the permian basin (West Texas fleet) for Q3, " +
  "given the rig count signals we're seeing? Risk tolerance: 0.5.";

const BUFFER_COUNTER_PROMPT =
  "What's my buffer exposure on the permian basin (West Texas fleet) for Q3, " +
  "given the rig count signals we're seeing? Risk tolerance: 0.7.";

const CAPACITY_STREAM_URL =
  process.env.NEXT_PUBLIC_CAPACITY_PLANNING_STREAM_URL ?? "";

// Per-beat auto-advance durations in live mode (ms). Beats 2 and 3 are 0
// because their advance is gated on their live-call resolutions.
const LIVE_BEAT_DURATIONS_MS = [1500, 2200, 0, 0, 2200, 2500];

export default function BufferPlanningScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(
    () => personaForPathname(pathname),
    [pathname],
  );

  const scenario = useScenario({ beats: bufferPlanningBeats });
  const { state, currentBeat, currentBeatIndex, totalBeats } = scenario;

  const [paused, setPaused] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>(
    CAPACITY_STREAM_URL ? "live" : "static",
  );
  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  // Manual risk-tolerance override — when the demoer drags the slider
  // between beats, this wins over the beat-driven value until the next
  // Space press (which clears it).
  const [manualRisk, setManualRisk] = useState<number | null>(null);
  const activeRisk = manualRisk ?? state.riskTolerance ?? 0.5;

  // Two live calls — one per "agent doing optimization work" beat. Each is
  // its own hook instance so the call results don't trample each other.
  const dropCall = useAgentCall<BufferOptimization>({
    streamUrl: CAPACITY_STREAM_URL,
    userId: TOMAS_USER_ID,
  });
  const counterCall = useAgentCall<BufferOptimization>({
    streamUrl: CAPACITY_STREAM_URL,
    userId: TOMAS_USER_ID,
  });

  // Pre-warm on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  const hardReset = useCallback(() => {
    setManualRisk(null);
    setPaused(false);
    setStartedAt(null);
    dropCall.reset();
    counterCall.reset();
    scenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, scenario, dropCall, counterCall]);

  const skipToEnd = useCallback(() => {
    setManualRisk(null);
    const stepsLeft = scenario.totalBeats - 1 - scenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) scenario.advance();
  }, [scenario]);

  const toggleMode = useCallback(() => {
    setMode((m) => (m === "live" ? "static" : "live"));
  }, []);

  // DEMO NARRATION: "Same keyboard wiring as the cargo-plane view — Space
  // advances Tomas's beats. Between beats he can nudge the risk slider
  // and the chart still reacts; Space then jumps to the next scripted
  // beat regardless."
  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      setManualRisk(null);
      scenario.advance();
    },
    onStepBack: () => {
      setManualRisk(null);
      scenario.stepBack();
    },
    onReset: hardReset,
    onToggleMode: toggleMode,
    onPause: () => setPaused((p) => !p),
  });

  // Fire live calls as the beats land — one per moment-of-optimization.
  useEffect(() => {
    if (mode !== "live") return;
    if (!CAPACITY_STREAM_URL) return;
    if (currentBeatIndex >= 2 && dropCall.status === "idle") {
      dropCall.run(BUFFER_DROP_PROMPT);
    }
    if (currentBeatIndex >= 3 && counterCall.status === "idle") {
      counterCall.run(BUFFER_COUNTER_PROMPT);
    }
  }, [mode, currentBeatIndex, dropCall, counterCall]);

  // In live mode the page auto-advances so the experience mirrors the real
  // product — Tomas opens the chat, the agent answers, he nudges the
  // slider, the agent re-runs. Beats fire on per-beat timers EXCEPT beats
  // 2 and 3 which gate on their live calls resolving (so stat tiles update
  // before the next beat reads them).
  useEffect(() => {
    if (mode !== "live") return;
    if (paused) return;
    if (currentBeatIndex >= totalBeats - 1) return;
    if (currentBeatIndex === 2 && dropCall.status === "loading") return;
    if (currentBeatIndex === 3 && counterCall.status === "loading") return;
    const dur = LIVE_BEAT_DURATIONS_MS[currentBeatIndex] ?? 2000;
    const delay =
      currentBeatIndex === 2 || currentBeatIndex === 3
        ? Math.max(dur, 1800)
        : dur;
    const timer = setTimeout(() => {
      setManualRisk(null);
      scenario.advance();
    }, delay);
    return () => clearTimeout(timer);
  }, [
    mode,
    paused,
    currentBeatIndex,
    totalBeats,
    dropCall.status,
    counterCall.status,
    scenario,
  ]);

  // Live mode is auto-play — mark started on mount so the demo timer rolls.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (mode === "live") markStarted();
  }, [mode, markStarted]);

  // Pick the most-relevant live result for the current beat. Beats 3+ prefer
  // the counter-proposal call; beats 2..2 use the initial drop call. If the
  // preferred call hasn't landed yet (or errored), we fall back to the other
  // / to static state, in that order.
  const activeLiveResult = useMemo<BufferOptimization | null>(() => {
    if (mode !== "live") return null;
    if (currentBeatIndex >= 3) {
      if (counterCall.status === "ok" && counterCall.data) return counterCall.data;
      if (dropCall.status === "ok" && dropCall.data) return dropCall.data;
      return null;
    }
    if (currentBeatIndex >= 2) {
      if (dropCall.status === "ok" && dropCall.data) return dropCall.data;
      return null;
    }
    return null;
  }, [mode, currentBeatIndex, dropCall.status, dropCall.data, counterCall.status, counterCall.data]);

  // Combined load/error indicator for the LiveStatusPill + chat surface.
  const liveStatus = useMemo<"idle" | "loading" | "ok" | "error">(() => {
    if (mode !== "live") return "idle";
    const relevant = currentBeatIndex >= 3 ? counterCall : currentBeatIndex >= 2 ? dropCall : null;
    if (!relevant) return "idle";
    return relevant.status;
  }, [mode, currentBeatIndex, dropCall, counterCall]);

  const liveError = useMemo<string | null>(() => {
    if (mode !== "live") return null;
    if (currentBeatIndex >= 3 && counterCall.error) return counterCall.error;
    if (currentBeatIndex >= 2 && dropCall.error) return dropCall.error;
    return null;
  }, [mode, currentBeatIndex, dropCall.error, counterCall.error]);

  // Publish into the global demo context (Backstage / 1..6 hotkeys / timer).
  useEffect(() => {
    if (!persona) return;
    const beat = currentBeat;
    const nextBeat =
      currentBeatIndex < bufferPlanningBeats.length - 1
        ? bufferPlanningBeats[currentBeatIndex + 1]
        : null;
    const connectionState =
      liveStatus === "loading"
        ? "connecting"
        : liveStatus === "ok"
          ? "open"
          : liveStatus === "error"
            ? "error"
            : "idle";
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex,
      totalBeats,
      currentBeatId: beat.id,
      narrationCue: beat.narration,
      nextBeatId: nextBeat?.id ?? null,
      nextNarrationCue: nextBeat?.narration ?? null,
      mode,
      connectionState: mode === "live" ? connectionState : "idle",
      lastError: liveError,
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
    liveStatus,
    liveError,
    toggleMode,
  ]);

  // Static beat values come from the scenario file. Live values, when
  // present, override them with the deployed agent's recommendation.
  // `fleet_utilization_uplift_pct` is added to the basin's 68% baseline.
  const PERMIAN_BASELINE_UTIL_PCT = 68;
  const staticBufferDays = state.bufferDays ?? 14;
  const staticOnTime = state.onTimeRatePct ?? 0;
  const staticUtil = state.utilizationPct ?? 0;
  const staticCapex = state.capexDeferredUsd ?? 0;
  const staticTimeline = state.fleetTimelineData ?? [];

  const bufferDays = activeLiveResult
    ? Math.round(activeLiveResult.recommended_buffer_days)
    : staticBufferDays;
  const onTimeRatePct = activeLiveResult
    ? Math.round(activeLiveResult.projected_on_time_rate * 100)
    : staticOnTime;
  const utilizationPct = activeLiveResult
    ? PERMIAN_BASELINE_UTIL_PCT + Math.round(activeLiveResult.fleet_utilization_uplift_pct)
    : staticUtil;
  const capexDeferredUsd = activeLiveResult
    ? activeLiveResult.deferred_capex_usd
    : staticCapex;
  const fleetTimelineData = activeLiveResult
    ? buildTimeline(activeLiveResult.recommended_buffer_days)
    : staticTimeline;

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
          showOpeningPrompt={currentBeatIndex === 0}
          mode={mode}
          liveStatus={liveStatus}
          liveError={liveError}
          liveResult={activeLiveResult}
        />
      }
      canvas={
        <div
          className="relative flex h-full flex-col gap-5 p-8"
          style={{ background: "var(--color-bg-base)" }}
        >
          <header className="flex items-end justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
                Permian basin · Midland · ExxonMobil · {TOMAS_PERSONA.sop_stage}
              </div>
              <h1 className="mt-1 text-2xl font-semibold">
                Q4 fleet buffer planning
              </h1>
            </div>
            <BeatIndicator
              index={currentBeatIndex}
              total={totalBeats}
              mode={mode}
            />
          </header>

          <StatTiles
            bufferDays={bufferDays}
            onTimeRatePct={onTimeRatePct}
            utilizationPct={utilizationPct}
            capexDeferredUsd={capexDeferredUsd}
          />

          <div className="flex-1 min-h-0">
            {state.showTimeline ? (
              <FleetDailyTimelineChart
                data={fleetTimelineData}
                bufferDays={bufferDays}
              />
            ) : (
              <ChartPlaceholder />
            )}
          </div>

          <RiskToleranceSliderContinuous
            value={activeRisk}
            onChange={setManualRisk}
          />

          <BufferCommitBanner
            visible={!!state.commitBannerVisible}
            headline={state.commitBannerHeadline}
            subline={
              currentBeatIndex >= 5
                ? "Synced to Maximo · Memory Bank: buffer_outcomes"
                : "Saved as Q4 fleet schedule v3"
            }
            bufferDays={bufferDays}
            onTimeRatePct={onTimeRatePct}
            capexDeferredUsd={capexDeferredUsd}
          />

          <LiveStatusPill
            mode={mode}
            status={liveStatus}
            buffer={activeLiveResult?.recommended_buffer_days}
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

function ChartPlaceholder() {
  return (
    <div className="flex h-full min-h-[380px] w-full items-center justify-center rounded-2xl border border-white/5 bg-white/[0.03]">
      <div className="text-sm text-white/40">
        Capacity Planning Agent loading — press Space to advance.
      </div>
    </div>
  );
}

interface StatTilesProps {
  bufferDays: number;
  onTimeRatePct: number;
  utilizationPct: number;
  capexDeferredUsd: number;
}

function StatTiles({
  bufferDays,
  onTimeRatePct,
  utilizationPct,
  capexDeferredUsd,
}: StatTilesProps) {
  return (
    <div className="grid grid-cols-4 gap-3">
      <StatTile
        label="Buffer"
        value={`${bufferDays}d`}
        sub={
          bufferDays >= 14
            ? "status quo"
            : `${14 - bufferDays}d below baseline`
        }
        accent="amber"
      />
      <StatTile
        label="On-time start rate"
        value={`${onTimeRatePct}%`}
        sub={
          onTimeRatePct >= 90
            ? "comfortable margin"
            : onTimeRatePct >= 75
              ? "acceptable"
              : "below SLO"
        }
        accent={onTimeRatePct >= 75 ? "emerald" : "rose"}
      />
      <StatTile
        label="Fleet utilization"
        value={`${utilizationPct}%`}
        sub={
          utilizationPct >= 80
            ? "tight"
            : utilizationPct >= 70
              ? "balanced"
              : "loose"
        }
        accent="emerald"
      />
      <StatTile
        label="CapEx deferred"
        value={
          capexDeferredUsd === 0
            ? "$0"
            : `$${(capexDeferredUsd / 1_000_000).toFixed(1)}M`
        }
        sub={
          capexDeferredUsd === 0
            ? "baseline plan"
            : "vs replacement-tool spend"
        }
        accent="emerald"
      />
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: "amber" | "emerald" | "rose";
}) {
  const accentClass =
    accent === "amber"
      ? "text-amber-300"
      : accent === "rose"
        ? "text-rose-300"
        : "text-emerald-300";
  return (
    <div className="rounded-xl border border-white/5 bg-white/[0.03] p-4">
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
        {label}
      </div>
      <div
        className={`mt-1 text-3xl font-semibold tabular-nums ${accentClass}`}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-0.5 text-[11px] text-white/40">{sub}</div>
      )}
    </div>
  );
}

interface ChatPanelProps {
  beatId: string;
  narration: string;
  index: number;
  total: number;
  paused: boolean;
  showOpeningPrompt: boolean;
  mode: Mode;
  liveStatus: "idle" | "loading" | "ok" | "error";
  liveError: string | null;
  liveResult: BufferOptimization | null;
}

function ChatPanel({
  beatId,
  narration,
  index,
  total,
  paused,
  showOpeningPrompt,
  mode,
  liveStatus,
  liveError,
  liveResult,
}: ChatPanelProps) {
  const firstName = TOMAS_PERSONA.name.split(" ")[0];
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        {firstName} · {TOMAS_PERSONA.role} — {TOMAS_PERSONA.region}
      </div>
      <div className="mb-4 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>

      {showOpeningPrompt && (
        <div className="mb-3 rounded-lg border border-amber-400/20 bg-amber-400/5 p-3">
          <div className="mb-1 text-[10px] uppercase tracking-wider text-amber-300/80">
            {firstName} → Capacity Planning Agent
          </div>
          <div className="text-sm leading-relaxed text-white/90">
            {TOMAS_OPENING_PROMPT}
          </div>
        </div>
      )}

      {mode === "live" && index >= 2 && (
        <LiveAgentBubble
          status={liveStatus}
          error={liveError}
          result={liveResult}
          beatIndex={index}
        />
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

// Chat-side surface for the live Capacity Planning Agent calls. Only renders
// at beat 2+ when mode is "live" — that's where the agent is actually running
// the BQ ML buffer optimization (vs. earlier beats which are just showing
// status-quo fleet data).
function LiveAgentBubble({
  status,
  error,
  result,
  beatIndex,
}: {
  status: "idle" | "loading" | "ok" | "error";
  error: string | null;
  result: BufferOptimization | null;
  beatIndex: number;
}) {
  const dot =
    status === "loading"
      ? "bg-amber-400 animate-pulse"
      : status === "ok"
        ? "bg-emerald-400"
        : status === "error"
          ? "bg-rose-400"
          : "bg-white/40";
  const label =
    beatIndex >= 3
      ? "Capacity Planning Agent · counter-proposal @ risk 0.7"
      : "Capacity Planning Agent · 14→8 day model @ risk 0.5";
  return (
    <div className="mb-4 rounded-xl border border-sky-400/20 bg-sky-400/[0.04] p-3">
      <div className="mb-1 flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${dot}`} />
        <div className="text-[10px] uppercase tracking-wider text-sky-300/80">
          {label}
        </div>
      </div>
      {status === "loading" && (
        <div className="text-sm text-white/80">
          Running BQ ML start-date distribution + optimal-buffer compute…
        </div>
      )}
      {status === "ok" && result && (
        <div className="text-sm text-white/90">
          <span className="text-white/60">Buffer:</span>{" "}
          <span className="font-mono">
            {Math.round(result.recommended_buffer_days)}d
          </span>
          <span className="ml-2 text-white/60">on-time:</span>{" "}
          <span className="font-mono">
            {Math.round(result.projected_on_time_rate * 100)}%
          </span>
          <span className="ml-2 text-white/60">CapEx deferred:</span>{" "}
          <span className="font-mono">
            ${(result.deferred_capex_usd / 1_000_000).toFixed(1)}M
          </span>
        </div>
      )}
      {status === "error" && (
        <div className="text-sm text-rose-200">
          Live call failed — falling back to scripted numbers. ({error ?? "unknown"})
        </div>
      )}
      {status === "idle" && (
        <div className="text-sm text-white/60">
          Awaiting trigger — advance to fire the agent call.
        </div>
      )}
    </div>
  );
}

interface BeatIndicatorProps {
  index: number;
  total: number;
  mode: Mode;
}

function BeatIndicator({ index, total, mode }: BeatIndicatorProps) {
  return (
    <div className="flex items-center gap-3 self-end rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
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

// Top-left mode pill — mirrors the cargo-plane and forecast-review treatments.
function LiveStatusPill({
  mode,
  status,
  buffer,
}: {
  mode: Mode;
  status: "idle" | "loading" | "ok" | "error";
  buffer?: number;
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
        ? "optimizing…"
        : status === "ok"
          ? buffer != null
            ? `ok · ${Math.round(buffer)}d buffer`
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
