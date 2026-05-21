"use client";

/**
 * Persona 4 (Priya, EVP / Operations VP) — deep-research scenario page.
 *
 * Five beats over ~2 minutes:
 *   0. question posed (notebook empty)
 *   1. citations gathered (3 chips, public + internal)
 *   2. synthesis populates (markdown body)
 *   3. recommendation card surfaces
 *   4. save confirmation toast
 *
 * Unlike the cargo-plane / buffer-planning pages, this scenario doesn't
 * share ``ScenarioState`` from ``demoScenarios.ts`` — Priya's canvas is a
 * research notebook (no map, no arcs, no asset markers). The local
 * beat-driver below is the cargo-plane page's choreography pattern,
 * minus the live/replay tri-mode (Priya's scenario is static-only for
 * v1 because the deep-research agent hasn't been wired to A2A yet).
 *
 * Keyboard parity with the other scenarios:
 *   Space        → next beat
 *   Shift+Space  → previous beat (B works too)
 *   R            → hard reset
 *   P            → pause / resume (no-op in static, kept for muscle memory)
 *
 * Publishes into the global demo context so Backstage / the demo timer /
 * the persona hotkeys all behave the same as on Maria's page.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { DemoTimer } from "@/components/demo/DemoTimer";
import { ResearchNotebook } from "@/components/research/ResearchNotebook";
import { personaForPathname } from "@/data/personas";
import { deepResearchBeats } from "@/data/scenarios/deepResearch";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { getPersona } from "@/lib/skin";
import { preWarmSession } from "@/lib/preWarmSession";

const PRIYA = getPersona("priya");
const PRIYA_PROMPT =
  "Why did our Permian utilization underperform last quarter? Compare to public Baker Hughes data.";

export default function DeepResearchScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(
    () => personaForPathname(pathname),
    [pathname],
  );

  // Local beat cursor — the standard ``useScenario`` hook is hard-typed to
  // the cargo-plane ScenarioState shape, and Priya's beats carry a
  // different state schema (DeepResearchState). A 4-line setState
  // pattern is cheaper than threading a generic through the shared hook.
  const [beatIndex, setBeatIndex] = useState(0);
  const totalBeats = deepResearchBeats.length;
  const currentBeat = deepResearchBeats[beatIndex];

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
    // Static-only for v1 — live mode would require an A2A endpoint for the
    // Deep Research Agent. Leave L unwired so it doesn't surface a button
    // in Backstage we can't honor.
    onToggleMode: undefined,
    onPause: () => setPaused((p) => !p),
  });

  // Publish demo context.
  useEffect(() => {
    if (!persona) return;
    const nextBeat =
      beatIndex < totalBeats - 1 ? deepResearchBeats[beatIndex + 1] : null;
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
          prompt={PRIYA_PROMPT}
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
          <ResearchNotebook
            question={state.question}
            citations={state.citations}
            synthesisMarkdown={state.synthesisMarkdown}
            recommendation={state.recommendation}
            saveToast={state.saveToast}
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
// Chat panel — Priya's prompt and the beat narration cue
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
        {PRIYA.name.split(" ")[0]} · {PRIYA.role}
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>

      {/* Priya's outgoing message — always visible from Beat 0 onward. */}
      <div className="mb-3 rounded-lg bg-white/[0.06] p-3">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-white/40">
          {PRIYA.name.split(" ")[0]}
        </div>
        <div className="text-sm leading-relaxed text-white/90">{prompt}</div>
      </div>

      {/* Beat narration cue — what the demoer is saying right now. */}
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
// Beat indicator — bottom-left dots that match the other scenario pages
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
