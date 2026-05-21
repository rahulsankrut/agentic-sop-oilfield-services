"use client";

/**
 * Persona 2 (Tomas, Fleet Scheduler — Permian) — buffer planning scenario.
 *
 * Static demo mode: beat-by-beat scenario state from
 * ``bufferPlanningBeats``. Space advances, R resets, B / Shift+Space
 * steps back. Between beats (or after the final beat), the slider is
 * manually overridable — moving it triggers a reactive chart +
 * reconciliation panel update without changing the active beat.
 *
 * TASK-12 wires this page into the demo runner: publishes into the
 * global demo context, mounts the DemoTimer, and uses
 * `useRehearsalControls` so the same Space / R / Shift+Space / L / P
 * shortcuts feel identical to the cargo-plane page.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { FleetTimelineChart } from "@/components/canvas/FleetTimelineChart";
import { RiskToleranceSlider } from "@/components/canvas/RiskToleranceSlider";
import { BufferCostReconciliation } from "@/components/canvas/BufferCostReconciliation";
import { DemoTimer } from "@/components/demo/DemoTimer";
import { bufferPlanningBeats } from "@/data/bufferPlanningBeats";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useScenario } from "@/hooks/useScenario";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { preWarmSession } from "@/lib/preWarmSession";
import {
  bufferOptionFor,
  fracPumpScenario,
  withBuffer,
  type BufferOption,
} from "@/data/fleetUtilizationData";

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

  // Manual slider override — when the user drags the slider between beats,
  // this wins over `state.bufferOption`. Cleared when the beat advances so
  // the storyboard reasserts control.
  const [manualOverride, setManualOverride] = useState<
    BufferOption["risk_tolerance"] | null
  >(null);
  const activeTolerance =
    manualOverride ?? state.bufferOption ?? "conservative";
  const currentOption = bufferOptionFor(activeTolerance);

  // Pre-warm on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  const hardReset = useCallback(() => {
    setManualOverride(null);
    setPaused(false);
    setStartedAt(null);
    scenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, scenario]);

  const skipToEnd = useCallback(() => {
    setManualOverride(null);
    const stepsLeft = scenario.totalBeats - 1 - scenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) scenario.advance();
  }, [scenario]);

  // DEMO NARRATION (rehearsal controls): "Same keyboard wiring as the
  // cargo-plane view — Space advances Tomas's beats. Between beats he
  // can drag the slider freely; the chart and the cost panel update
  // live without touching the storyboard cursor."
  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      setManualOverride(null);
      scenario.advance();
    },
    onStepBack: () => {
      setManualOverride(null);
      scenario.stepBack();
    },
    onReset: hardReset,
    // Buffer planning is static-only for now — L is a no-op until live
    // mode lands. Wiring the handler so the Backstage button still
    // surfaces, but it intentionally does nothing.
    onToggleMode: undefined,
    onPause: () => setPaused((p) => !p),
  });

  // Publish into the global demo context.
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
      onToggleMode: null, // no live mode yet for buffer planning
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

  const timelineWithBuffer = useMemo(
    () => withBuffer(fracPumpScenario.timeline, currentOption.buffer_pct),
    [currentOption.buffer_pct],
  );

  return (
    <CanvasShell
      drawerOpen={!!state.drawerOpen}
      chat={
        <ChatPanel
          beatId={currentBeat.id}
          narration={currentBeat.narration}
          index={currentBeatIndex}
          total={totalBeats}
          paused={paused}
        />
      }
      drawer={<BufferCostReconciliation option={currentOption} />}
      canvas={
        <div
          className="relative flex h-full flex-col gap-6 p-8"
          style={{ background: "var(--color-bg-base)" }}
        >
          <header>
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
              {fracPumpScenario.customer} · {fracPumpScenario.equipment_class}
            </div>
            <h1 className="mt-1 text-2xl font-semibold">Q3 buffer planning</h1>
          </header>

          {state.showTimeline ? (
            <FleetTimelineChart
              timeline={timelineWithBuffer}
              bufferedCapacity={currentOption.buffer_pct}
              highlightWeek={state.highlightWeek}
            />
          ) : (
            <ChartPlaceholder />
          )}

          <RiskToleranceSlider
            options={fracPumpScenario.buffer_options}
            value={activeTolerance}
            onChange={setManualOverride}
          />

          <BeatIndicator index={currentBeatIndex} total={totalBeats} />

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
    <div className="flex h-[480px] w-full items-center justify-center rounded-2xl border border-white/5 bg-white/[0.03]">
      <div className="text-sm text-white/40">
        Forecast loading — press Space to advance.
      </div>
    </div>
  );
}

interface ChatPanelProps {
  beatId: string;
  narration: string;
  index: number;
  total: number;
  paused: boolean;
}

function ChatPanel({
  beatId,
  narration,
  index,
  total,
  paused,
}: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        Tomas · Fleet Scheduler Permian
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
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

interface BeatIndicatorProps {
  index: number;
  total: number;
}

function BeatIndicator({ index, total }: BeatIndicatorProps) {
  return (
    <div className="mt-auto flex items-center gap-3 self-start rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
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
