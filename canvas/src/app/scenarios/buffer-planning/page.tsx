"use client";

/**
 * Persona 2 (Tomas, West Texas Fleet Scheduler) — buffer-planning scenario.
 *
 * Static demo mode: beat-by-beat scenario state from
 * ``bufferPlanningBeats`` (src/data/scenarios/bufferPlanning.ts).
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
import { bufferPlanningBeats } from "@/data/scenarios/bufferPlanning";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useScenario } from "@/hooks/useScenario";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { preWarmSession } from "@/lib/preWarmSession";
import { getPersona } from "@/lib/skin";

const TOMAS_PERSONA = getPersona("tomas");
const TOMAS_OPENING_PROMPT =
  'Show me Permian fleet utilization and the buffer trade-off — I want to drop the buffer from 14 to 8 days and see what the on-time rate does.';

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
  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  // Manual risk-tolerance override — when the demoer drags the slider
  // between beats, this wins over the beat-driven value until the next
  // Space press (which clears it).
  const [manualRisk, setManualRisk] = useState<number | null>(null);
  const activeRisk = manualRisk ?? state.riskTolerance ?? 0.5;

  // Pre-warm on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  const hardReset = useCallback(() => {
    setManualRisk(null);
    setPaused(false);
    setStartedAt(null);
    scenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, scenario]);

  const skipToEnd = useCallback(() => {
    setManualRisk(null);
    const stepsLeft = scenario.totalBeats - 1 - scenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) scenario.advance();
  }, [scenario]);

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
    // Buffer planning is static-only for v1 — L is a no-op.
    onToggleMode: undefined,
    onPause: () => setPaused((p) => !p),
  });

  // Publish into the global demo context (Backstage / 1..6 hotkeys / timer).
  useEffect(() => {
    if (!persona) return;
    const beat = currentBeat;
    const nextBeat =
      currentBeatIndex < bufferPlanningBeats.length - 1
        ? bufferPlanningBeats[currentBeatIndex + 1]
        : null;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex,
      totalBeats,
      currentBeatId: beat.id,
      narrationCue: beat.narration,
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

  const bufferDays = state.bufferDays ?? 14;
  const onTimeRatePct = state.onTimeRatePct ?? 0;
  const utilizationPct = state.utilizationPct ?? 0;
  const capexDeferredUsd = state.capexDeferredUsd ?? 0;
  const fleetTimelineData = state.fleetTimelineData ?? [];

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
            <BeatIndicator index={currentBeatIndex} total={totalBeats} />
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
}

function ChatPanel({
  beatId,
  narration,
  index,
  total,
  paused,
  showOpeningPrompt,
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

interface BeatIndicatorProps {
  index: number;
  total: number;
}

function BeatIndicator({ index, total }: BeatIndicatorProps) {
  return (
    <div className="flex items-center gap-3 self-end rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
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
