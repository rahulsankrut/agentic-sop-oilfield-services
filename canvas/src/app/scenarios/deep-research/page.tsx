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
 * Bi-state mode (TASK-18, 2026-05-22):
 *  - "static" — beat-by-beat seeded briefing grounded in real source data
 *               (BLS QCEW, Baker Hughes rig count, SAP MARC + ZHR_WORKFORCE
 *               internal extracts). The numbers in the synthesis are not
 *               fabricated; they're pulled from the same datasets the other
 *               personas reach for.
 *  - "live"   — POSTs to `/api/deep-research/run` which is a stub today
 *               (returns 501 with a structured "not provisioned" reason).
 *               The page surfaces that honestly via the LiveStatusPill and
 *               keeps the seeded briefing visible. When Deep Research Agent
 *               is wired in the tenant, the gap-fix is one file: the route.
 *
 * Press `L` to toggle live ↔ static.
 *
 * Citation drill-down: clicking a chip opens `CitationDrawer` in the right
 * panel — the auditor's "show me where this number came from" path. Works
 * in both modes.
 *
 * Keyboard parity with the other scenarios:
 *   Space        → next beat
 *   Shift+Space  → previous beat (B works too)
 *   R            → hard reset
 *   L            → toggle live ↔ static (live shows the stub state)
 *   P            → pause / resume (no-op in static, kept for muscle memory)
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { DemoTimer } from "@/components/demo/DemoTimer";
import { ResearchNotebook } from "@/components/research/ResearchNotebook";
import { CitationDrawer } from "@/components/research/CitationDrawer";
import { personaForPathname } from "@/data/personas";
import {
  deepResearchBeats,
  type Citation,
} from "@/data/scenarios/deepResearch";
import { publishDemoState } from "@/hooks/useDemoContext";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { getPersona } from "@/lib/skin";
import { preWarmSession } from "@/lib/preWarmSession";

type Mode = "static" | "live";
type LiveStatus = "idle" | "loading" | "ok" | "not_provisioned" | "error";

const PRIYA = getPersona("priya");
const PRIYA_PROMPT =
  "Why did our Permian utilization underperform last quarter? Compare to public Baker Hughes data.";

// Per-beat auto-advance durations in live mode (ms). Beat 1 is 0 because
// its advance is gated on the live call (stub or real) resolving.
const LIVE_BEAT_DURATIONS_MS = [1500, 0, 3000, 2200, 2500];

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
  // Default to "live" so the demoer can show DRA's availability without
  // having to remember a hotkey. The "live" path is honest about the stub.
  const [mode, setMode] = useState<Mode>("live");
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("idle");
  const [liveDetail, setLiveDetail] = useState<string | null>(null);
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);

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
    setLiveStatus("idle");
    setLiveDetail(null);
    setOpenCitation(null);
    if (persona) void preWarmSession(persona);
  }, [persona]);

  const skipToEnd = useCallback(() => {
    setBeatIndex(totalBeats - 1);
  }, [totalBeats]);

  const toggleMode = useCallback(() => {
    setMode((m) => (m === "live" ? "static" : "live"));
  }, []);

  // Pre-warm on mount.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  // In live mode the page auto-advances so the experience mirrors the real
  // product — Priya types her question once and the briefing assembles on
  // its own (citations → synthesis → recommendation → save). Beats fire on
  // per-beat timers; beat 1 (where the live call kicks off) waits for the
  // call to resolve before progressing to keep the surfaces aligned.
  useEffect(() => {
    if (mode !== "live") return;
    if (paused) return;
    if (beatIndex >= totalBeats - 1) return;
    // Beat 1 advance is gated on the live call resolving — the briefing
    // shape can be the seeded fallback or the live response either way.
    if (beatIndex === 1 && liveStatus === "loading") return;
    const dur = LIVE_BEAT_DURATIONS_MS[beatIndex] ?? 2000;
    const delay = beatIndex === 1 ? Math.max(dur, 1500) : dur;
    const timer = setTimeout(() => {
      advance();
    }, delay);
    return () => clearTimeout(timer);
  }, [mode, paused, beatIndex, totalBeats, liveStatus, advance]);

  // Live mode is auto-play — mark started on mount so the demo timer rolls.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (mode === "live") markStarted();
  }, [mode, markStarted]);

  // Fire the live call on entry to beat 1 in live mode. One call per
  // scenario run; reset by R. The stub returns 501 with a structured
  // "not provisioned" reason; the page surfaces that honestly and keeps
  // the seeded briefing visible.
  //
  // The setState-in-effect lint rule fires here — this is the canonical
  // "kick off async work on a transition + reflect its progress" pattern.
  // The same shape lives in the cargo-plane page's auto-fallback effect.
  useEffect(() => {
    if (mode !== "live") return;
    if (beatIndex < 1) return;
    if (liveStatus !== "idle") return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLiveStatus("loading");
    setLiveDetail(null);
    (async () => {
      try {
        const res = await fetch("/api/deep-research/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: PRIYA_PROMPT }),
          signal: controller.signal,
        });
        const body = (await res.json().catch(() => null)) as
          | { provisioned?: boolean; reason?: string }
          | null;
        if (res.status === 501 || body?.provisioned === false) {
          setLiveStatus("not_provisioned");
          setLiveDetail(
            body?.reason ?? "Deep Research Agent not provisioned in tenant.",
          );
        } else if (res.ok) {
          setLiveStatus("ok");
          setLiveDetail(null);
        } else {
          setLiveStatus("error");
          setLiveDetail(`HTTP ${res.status}`);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setLiveStatus("error");
        setLiveDetail(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => controller.abort();
  }, [mode, beatIndex, liveStatus]);

  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      advance();
    },
    onStepBack: stepBack,
    onReset: hardReset,
    onToggleMode: toggleMode,
    onPause: () => setPaused((p) => !p),
  });

  // Publish demo context.
  useEffect(() => {
    if (!persona) return;
    const nextBeat =
      beatIndex < totalBeats - 1 ? deepResearchBeats[beatIndex + 1] : null;
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
      currentBeatIndex: beatIndex,
      totalBeats,
      currentBeatId: currentBeat.id,
      narrationCue: currentBeat.narration,
      nextBeatId: nextBeat?.id ?? null,
      nextNarrationCue: nextBeat?.narration ?? null,
      mode,
      connectionState: mode === "live" ? connectionState : "idle",
      lastError: liveDetail,
      startedAt,
      onReset: hardReset,
      onToggleMode: toggleMode,
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
    mode,
    liveStatus,
    liveDetail,
    toggleMode,
  ]);

  const state = currentBeat.state;

  return (
    <CanvasShell
      drawerOpen={openCitation !== null}
      drawer={
        openCitation ? (
          <CitationDrawer
            citation={openCitation}
            onClose={() => setOpenCitation(null)}
          />
        ) : null
      }
      chat={
        <ChatPanel
          prompt={PRIYA_PROMPT}
          beatId={currentBeat.id}
          narration={currentBeat.narration}
          index={beatIndex}
          total={totalBeats}
          paused={paused}
          mode={mode}
          liveStatus={liveStatus}
          liveDetail={liveDetail}
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
            onCitationOpen={setOpenCitation}
          />

          <LiveStatusPill mode={mode} status={liveStatus} />

          <BeatIndicator index={beatIndex} total={totalBeats} mode={mode} />

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
  mode: Mode;
  liveStatus: LiveStatus;
  liveDetail: string | null;
}

function ChatPanel({
  prompt,
  beatId,
  narration,
  index,
  total,
  paused,
  mode,
  liveStatus,
  liveDetail,
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

      {mode === "live" && index >= 1 && (
        <LiveAgentBubble status={liveStatus} detail={liveDetail} />
      )}

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
        Space advance · Shift+Space back · R reset · L mode · P pause · \
        backstage
      </div>
    </div>
  );
}

// Surfaces the live-call state honestly: when the stub returns 501
// (Deep Research Agent not provisioned in tenant), the demoer can frame
// the briefing as "this is the seeded version; live wiring is one route
// away" without simulating a fake research run.
function LiveAgentBubble({
  status,
  detail,
}: {
  status: LiveStatus;
  detail: string | null;
}) {
  const dot =
    status === "loading"
      ? "bg-amber-400 animate-pulse"
      : status === "ok"
        ? "bg-emerald-400"
        : status === "not_provisioned"
          ? "bg-amber-400"
          : status === "error"
            ? "bg-rose-400"
            : "bg-white/40";
  return (
    <div className="mb-4 rounded-xl border border-sky-400/20 bg-sky-400/[0.04] p-3">
      <div className="mb-1 flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${dot}`} />
        <div className="text-[10px] uppercase tracking-wider text-sky-300/80">
          Deep Research Agent · live
        </div>
      </div>
      {status === "loading" && (
        <div className="text-sm text-white/80">
          Asking Gemini Enterprise to run the research plan against the
          configured sources…
        </div>
      )}
      {status === "ok" && (
        <div className="text-sm text-white/90">
          Live research returned a briefing. The seeded version matches the
          shape — comparing for divergence is left as an exercise.
        </div>
      )}
      {status === "not_provisioned" && (
        <div className="text-sm text-white/90">
          <strong className="text-amber-200">
            Deep Research Agent is not wired in this tenant.
          </strong>{" "}
          Showing the seeded briefing instead — every number is grounded in
          real source data the agent would have queried.
          {detail && (
            <div className="mt-1 text-xs text-white/55">{detail}</div>
          )}
        </div>
      )}
      {status === "error" && (
        <div className="text-sm text-rose-200">
          Live call errored — keeping the seeded briefing visible.
          {detail && (
            <div className="mt-1 text-xs text-white/55">{detail}</div>
          )}
        </div>
      )}
      {status === "idle" && (
        <div className="text-sm text-white/60">
          Awaiting trigger — advance past beat 0 to fire the live call.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Beat indicator — bottom-left dots that match the other scenario pages
// ---------------------------------------------------------------------------

interface BeatIndicatorProps {
  index: number;
  total: number;
  mode: Mode;
}

function BeatIndicator({ index, total, mode }: BeatIndicatorProps) {
  return (
    <div className="absolute bottom-6 left-6 flex items-center gap-3 rounded-full border border-white/10 bg-black/40 px-4 py-2 backdrop-blur-md">
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

// Top-left mode pill — same treatment as cargo-plane / forecast-review /
// buffer-planning so the demoer's eye lands on the same place across
// scenarios.
function LiveStatusPill({
  mode,
  status,
}: {
  mode: Mode;
  status: LiveStatus;
}) {
  const dot =
    mode !== "live"
      ? "bg-white/40"
      : status === "loading"
        ? "bg-amber-400 animate-pulse"
        : status === "ok"
          ? "bg-emerald-400"
          : status === "not_provisioned"
            ? "bg-amber-400"
            : status === "error"
              ? "bg-rose-400"
              : "bg-white/40";
  const sub =
    mode !== "live"
      ? null
      : status === "loading"
        ? "researching…"
        : status === "ok"
          ? "ok"
          : status === "not_provisioned"
            ? "stub · using seeded briefing"
            : status === "error"
              ? "error · using seeded briefing"
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
