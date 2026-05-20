"use client";

/**
 * Persona 2 (Tomas, Fleet Scheduler — Permian) — buffer planning scenario.
 *
 * Static demo mode: beat-by-beat scenario state from
 * ``bufferPlanningBeats``. Space advances, R resets, B steps back.
 * Between beats (or after the final beat), the slider is manually
 * overridable — moving it triggers a reactive chart + reconciliation
 * panel update without changing the active beat.
 */

import { useMemo, useState } from "react";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { FleetTimelineChart } from "@/components/canvas/FleetTimelineChart";
import { RiskToleranceSlider } from "@/components/canvas/RiskToleranceSlider";
import { BufferCostReconciliation } from "@/components/canvas/BufferCostReconciliation";
import { useScenario } from "@/hooks/useScenario";
import { useKeyboardControls } from "@/hooks/useKeyboardControls";
import { bufferPlanningBeats } from "@/data/bufferPlanningBeats";
import {
  bufferOptionFor,
  fracPumpScenario,
  withBuffer,
  type BufferOption,
} from "@/data/fleetUtilizationData";

export default function BufferPlanningScenarioPage() {
  const scenario = useScenario({ beats: bufferPlanningBeats });
  const { state, currentBeat, currentBeatIndex, totalBeats } = scenario;

  // Manual slider override — when the user drags the slider between beats,
  // this wins over `state.bufferOption`. Cleared when the beat advances so
  // the storyboard reasserts control.
  const [manualOverride, setManualOverride] = useState<
    BufferOption["risk_tolerance"] | null
  >(null);
  const activeTolerance =
    manualOverride ?? state.bufferOption ?? "conservative";
  const currentOption = bufferOptionFor(activeTolerance);

  // DEMO NARRATION (rehearsal controls): "Same keyboard wiring as the
  // cargo-plane view — Space advances Tomas's beats. Between beats he
  // can drag the slider freely; the chart and the cost panel update
  // live without touching the storyboard cursor."
  useKeyboardControls({
    onAdvance: () => {
      setManualOverride(null);
      scenario.advance();
    },
    onStepBack: () => {
      setManualOverride(null);
      scenario.stepBack();
    },
    onReset: () => {
      setManualOverride(null);
      scenario.reset();
    },
  });

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
        />
      }
      drawer={<BufferCostReconciliation option={currentOption} />}
      canvas={
        <div
          className="flex h-full flex-col gap-6 p-8"
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
}

function ChatPanel({ beatId, narration, index, total }: ChatPanelProps) {
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
          Beat {index + 1} / {total}
        </div>
        <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
          {beatId}
        </div>
        <div className="text-sm leading-relaxed text-white/90">{narration}</div>
      </div>
      <div className="mt-4 text-[10px] uppercase tracking-wider text-white/40">
        Space advance · B back · R reset · drag slider any time
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
