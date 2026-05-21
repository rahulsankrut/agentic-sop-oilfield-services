"use client";

/**
 * Persona 5 (Rafael, Citizen Developer) — Agent Studio scenario page.
 *
 * Five beats over ~2 minutes:
 *   0. Rafael's prompt (empty studio)
 *   1. four-block scaffold appears (input, query, filter, output)
 *   2. input bound to ZHR_WORKFORCE.BASIN (default Permian)
 *   3. test run shows three Permian crews over the 21-day threshold
 *   4. publish to team — Monday 9am schedule confirmed
 *
 * Same shell pattern as the deep-research page — local beat cursor,
 * static-only mode (no live A2A wiring yet for Agent Studio in v1),
 * publishes into the global demo context so the demo timer / Backstage /
 * persona hotkeys behave consistently.
 *
 * Keyboard:
 *   Space        → next beat
 *   Shift+Space  → previous beat (B works too)
 *   R            → hard reset
 *   P            → pause / resume (no-op for static, kept for muscle memory)
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { DemoTimer } from "@/components/demo/DemoTimer";
import { SkillBuilder } from "@/components/studio/SkillBuilder";
import { personaForPathname } from "@/data/personas";
import { agentStudioBeats } from "@/data/scenarios/agentStudio";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { getPersona } from "@/lib/skin";
import { preWarmSession } from "@/lib/preWarmSession";

const RAFAEL = getPersona("rafael");
const RAFAEL_PROMPT =
  "I want to add a quick custom check: alert me when any Permian crew has been deployed > 21 days continuously.";

export default function AgentStudioScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(
    () => personaForPathname(pathname),
    [pathname],
  );

  const [beatIndex, setBeatIndex] = useState(0);
  const totalBeats = agentStudioBeats.length;
  const currentBeat = agentStudioBeats[beatIndex];

  const [paused, setPaused] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  const advance = useCallback(() => {
    setBeatIndex((i) => Math.min(i + 1, totalBeats - 1));
  }, [totalBeats]);

  const stepBack = useCallback(() => {
    setBeatIndex((i) => Math.max(i - 1, 0));
  }, []);

  const hardReset = useCallback(() => {
    setBeatIndex(0);
    setPaused(false);
    setStartedAt(null);
    if (persona) void preWarmSession(persona);
  }, [persona]);

  const skipToEnd = useCallback(() => {
    setBeatIndex(totalBeats - 1);
  }, [totalBeats]);

  // Pre-warm on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      advance();
    },
    onStepBack: stepBack,
    onReset: hardReset,
    onToggleMode: undefined,
    onPause: () => setPaused((p) => !p),
  });

  // Publish demo context.
  useEffect(() => {
    if (!persona) return;
    const nextBeat =
      beatIndex < totalBeats - 1 ? agentStudioBeats[beatIndex + 1] : null;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex: beatIndex,
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
    beatIndex,
    totalBeats,
    currentBeat,
    startedAt,
    hardReset,
    skipToEnd,
  ]);

  const state = currentBeat.state;

  return (
    <CanvasShell
      drawerOpen={false}
      chat={
        <ChatPanel
          prompt={RAFAEL_PROMPT}
          beatId={currentBeat.id}
          narration={currentBeat.narration}
          index={beatIndex}
          total={totalBeats}
          paused={paused}
        />
      }
      canvas={
        <div
          className="relative h-full"
          style={{ background: "var(--color-bg-base)" }}
        >
          <SkillBuilder
            skillName={state.skillName}
            blocks={state.blocks}
            testResults={state.testResults}
            publishStatus={state.publishStatus}
            codePreview={state.codePreview}
          />

          <BeatIndicator index={beatIndex} total={totalBeats} />

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
// Chat panel
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  prompt: string;
  beatId: string;
  narration: string;
  index: number;
  total: number;
  paused: boolean;
}

function ChatPanel({
  prompt,
  beatId,
  narration,
  index,
  total,
  paused,
}: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        {RAFAEL.name.split(" ")[0]} · {RAFAEL.role}
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>

      <div className="mb-3 rounded-lg bg-white/[0.06] p-3">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-white/40">
          {RAFAEL.name.split(" ")[0]}
        </div>
        <div className="text-sm leading-relaxed text-white/90">{prompt}</div>
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
// Beat indicator
// ---------------------------------------------------------------------------

interface BeatIndicatorProps {
  index: number;
  total: number;
}

function BeatIndicator({ index, total }: BeatIndicatorProps) {
  return (
    <div className="absolute bottom-6 left-6 flex items-center gap-3 rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
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
