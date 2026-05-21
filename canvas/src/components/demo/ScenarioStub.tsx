"use client";

/**
 * ScenarioStub.tsx
 *
 * Shared placeholder for personas whose scenario pages haven't shipped
 * yet (Personas 1, 4, 5 as of TASK-12). Mirrors the dark-canvas
 * typography of the launcher so the demoer / reviewer immediately
 * recognizes it as part of the same surface.
 *
 * Each stub still publishes into the demo context — that way the
 * Backstage panel surfaces the persona name + the "Coming in TASK-XX"
 * narration cue, and the persona-jump hotkeys (1..6) still feel
 * coherent when the demoer is rehearsing.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { DemoTimer } from "@/components/demo/DemoTimer";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { preWarmSession } from "@/lib/preWarmSession";

interface ScenarioStubProps {
  pathname: string;
  /** Short label for the TASK that will replace this stub (e.g. "TASK-14"). */
  comingInTask?: string;
  /** One-sentence summary of what this scenario will show. */
  scenarioSummary: string;
}

export function ScenarioStub({
  pathname,
  comingInTask = "a follow-up task",
  scenarioSummary,
}: ScenarioStubProps) {
  const persona = personaForPathname(pathname);
  // Stable `startedAt` so the timer doesn't bounce between renders.
  const [startedAt] = useState<number>(() => Date.now());

  // Publish into the demo context so Backstage shows the persona's name
  // and the placeholder narration cue.
  useEffect(() => {
    if (!persona) return;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex: 0,
      totalBeats: 1,
      currentBeatId: "stub",
      narrationCue: scenarioSummary,
      nextBeatId: null,
      nextNarrationCue: `Full scenario lands in ${comingInTask}. For now, narrate the persona briefly and move on.`,
      mode: "static",
      connectionState: "idle",
      lastError: null,
      startedAt,
      onReset: null,
      onToggleMode: null,
      onPause: null,
      onSkipToEnd: null,
    });
    return cleanup;
  }, [persona, scenarioSummary, comingInTask, startedAt]);

  // Echo the pre-warm so rehearsal flow matches a ready scenario.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  if (!persona) {
    return (
      <main
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--color-bg-base)" }}
      >
        <div className="text-sm text-white/55">Unknown persona route.</div>
      </main>
    );
  }

  return (
    <main
      className="relative min-h-screen overflow-hidden"
      style={{ background: "var(--color-bg-base)" }}
    >
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-8 py-16">
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">
          Persona {persona.number} · {persona.sopStage}
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-white">
          {persona.displayName}
        </h1>
        <div className="mt-1 text-sm text-white/55">{persona.role}</div>

        <div className="mt-8 max-w-xl rounded-2xl border border-white/10 bg-white/[0.04] p-6">
          <div className="text-[10px] uppercase tracking-[0.18em] text-amber-200/80">
            Scenario coming in {comingInTask}
          </div>
          <p className="mt-3 text-sm leading-relaxed text-white/85">
            {scenarioSummary}
          </p>
          <p className="mt-4 text-xs leading-relaxed text-white/50">
            This stub keeps the rehearsal hotkeys honest. The Backstage panel
            still shows the persona, the target time, and the narration cue
            you would deliver here. Press <Kbd>0</Kbd> to return to the
            launcher, or <Kbd>{persona.number === 6 ? 1 : persona.number + 1}</Kbd>{" "}
            to advance to the next persona.
          </p>
        </div>

        <div className="mt-8 flex items-center gap-4">
          <Link
            href="/demo"
            className="text-[10px] uppercase tracking-[0.18em] text-white/55 hover:text-white/85"
          >
            ← Back to launcher
          </Link>
          <span className="text-[10px] uppercase tracking-[0.18em] text-white/30">
            target {persona.targetDurationMin}:00
          </span>
        </div>
      </div>

      <DemoTimer
        targetMinutes={persona.targetDurationMin}
        startedAt={startedAt}
      />
    </main>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white/80">
      {children}
    </kbd>
  );
}
