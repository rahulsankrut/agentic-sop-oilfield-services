"use client";

/**
 * Persona 3 (Maria, OCC Planner) — cargo-plane scenario page.
 *
 * Tri-state mode (TASK-10):
 *  - "static"  — beat-by-beat scenario state from `cargoPlaneBeats` (default).
 *                Space advances, B / Shift+Space steps back, R resets.
 *  - "live"    — SSE-driven from the deployed Capacity Orchestrator's A2A
 *                `message:stream` endpoint. Auto-falls back to replay on
 *                connection error (TASK-12 generalization of the prior
 *                live→static fallback).
 *  - "replay"  — pre-recorded event sequence played at original timing
 *                (`/recorded_events/cargo_plane_v1.json`). Demo safety net.
 *
 * Press `L` to cycle Static → Live → Replay → Static.
 *
 * TASK-12 additions on top of the TASK-10 implementation:
 *  - Publishes into the global demo context (Backstage / Help / 1..6 hotkeys).
 *  - Demo timer in the bottom-right corner.
 *  - Auto-fallback now lands on Replay (not Static) and surfaces a small
 *    audience-safe banner so the demoer doesn't have to narrate the
 *    failure manually.
 *  - WebSocket disconnect surfaces a `ReconnectBanner` with one-click
 *    reconnect.
 *  - `useRehearsalControls` replaces `useKeyboardControls`, picking up
 *    Shift+Space, L, P out of the box.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { GlobalMap } from "@/components/canvas/GlobalMap";
import { AssetMarker } from "@/components/canvas/AssetMarker";
import { LogisticsArc } from "@/components/canvas/LogisticsArc";
import { KnowledgeCatalogDrawer } from "@/components/canvas/KnowledgeCatalogDrawer";
import { CostRollupBanner } from "@/components/canvas/CostRollupBanner";
import { A2UIPanel } from "@/components/a2ui/A2UIPanel";
import { COST_ROLLUP_CARGO_PLANE, KC_DRAWER_TX007 } from "@/data/a2uiSamples";
import { DemoTimer } from "@/components/demo/DemoTimer";
import { ReconnectBanner } from "@/components/demo/ReconnectBanner";
import { personaForPathname } from "@/data/personas";
import { cargoPlaneBeats } from "@/data/demoScenarios";
import { useScenario } from "@/hooks/useScenario";
import { useRehearsalControls } from "@/hooks/useRehearsalControls";
import { useLiveScenario } from "@/hooks/useLiveScenario";
import { useReplayScenario } from "@/hooks/useReplayScenario";
import { publishDemoState } from "@/hooks/useDemoContext";
import type { ConnectionState } from "@/lib/agent-stream";
import { preWarmSession } from "@/lib/preWarmSession";
import { getPersona, getScenario } from "@/lib/skin";

type Mode = "static" | "live" | "replay";

// Persona 3 (the OCC planner) + cargo-plane scenario data come from the
// active customer skin (TASK-13). Identifiers (memoryProfileUserId,
// sessionId) stay STABLE across skins — only display strings change.
// MARIA_SESSION_ID is deliberately empty: see the TASK-10 implementation
// note in the prior revision. The runtime auto-creates a session per Live
// trigger; ``preload_memory`` still hits the persona's seeded memories
// via ``user_id``.
const MARIA_PERSONA = getPersona("maria");
const CARGO_PLANE_SCENARIO = getScenario("cargo-plane");
const MARIA_SESSION_ID = "";
const MARIA_USER_ID = MARIA_PERSONA.memory_profile_user_id;
const MARIA_PROMPT =
  CARGO_PLANE_SCENARIO?.opening_prompt ??
  "I need an equivalent variant on site — what are my options?";

const REPLAY_PATH = "/recorded_events/cargo_plane_v1.json";

export default function CargoPlaneScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(
    () => personaForPathname(pathname),
    [pathname],
  );

  const [mode, setMode] = useState<Mode>("static");
  const [paused, setPaused] = useState(false);
  // Generation counter — bumped on R to force the live stream to redial.
  const [liveGeneration, setLiveGeneration] = useState(0);
  // True once the demoer has taken a meaningful action (first Space, live trigger).
  const [startedAt, setStartedAt] = useState<number | null>(null);
  // Banner state when the live mode falls back automatically.
  const [autoFellBack, setAutoFellBack] = useState(false);
  // TASK-45: agent-driven UI toggle. `A` cycles between bespoke and
  // A2UI-rendered non-spatial panels (KC drawer + cost rollup).
  const [a2uiMode, setA2uiMode] = useState(false);

  const staticScenario = useScenario({ beats: cargoPlaneBeats });
  const liveScenario = useLiveScenario({
    scenarioName: "cargo-plane",
    sessionId: MARIA_SESSION_ID || `cargo-plane-${liveGeneration}`,
    userId: MARIA_USER_ID,
    userMessage: MARIA_PROMPT,
    enabled: mode === "live" && !paused,
    initialState: cargoPlaneBeats[0].state,
  });
  const replayScenario = useReplayScenario({
    recordingPath: REPLAY_PATH,
    enabled: mode === "replay" && !paused,
    initialState: cargoPlaneBeats[0].state,
  });

  // First Space / first live trigger seeds startedAt.
  const markStarted = useCallback(() => {
    setStartedAt((prev) => prev ?? Date.now());
  }, []);

  // Pre-warm on mount + on persona-jump back.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  // Hard reset wraps the scenario reset plus mode/paused/timer flags.
  const hardReset = useCallback(() => {
    setMode("static");
    setPaused(false);
    setAutoFellBack(false);
    setLiveGeneration((g) => g + 1);
    setStartedAt(null);
    staticScenario.reset();
    if (persona) void preWarmSession(persona);
  }, [persona, staticScenario]);

  const toggleMode = useCallback(() => {
    setAutoFellBack(false);
    setPaused(false);
    setMode((m) =>
      m === "static" ? "live" : m === "live" ? "replay" : "static",
    );
    // Switching into live counts as a meaningful trigger.
    if (mode === "static") markStarted();
  }, [mode, markStarted]);

  const togglePause = useCallback(() => {
    setPaused((p) => !p);
  }, []);

  // Skip-to-end jumps the static beat cursor; live/replay don't have a
  // meaningful "end" we can fast-forward to without skipping the canvas
  // transitions, so we just snap the static state to the final beat.
  // Each `advance()` is a state setter that batches inside React 18+, so
  // running the loop N times during one event tick produces N queued
  // updates that all collapse to the final beat index.
  const skipToEnd = useCallback(() => {
    const stepsLeft =
      staticScenario.totalBeats - 1 - staticScenario.currentBeatIndex;
    for (let i = 0; i < stepsLeft; i++) staticScenario.advance();
  }, [staticScenario]);

  // Per-scenario hotkeys: Space / Shift+Space / B / R / L / P
  useRehearsalControls({
    onAdvance: () => {
      markStarted();
      staticScenario.advance();
    },
    onStepBack: () => staticScenario.stepBack(),
    onReset: hardReset,
    onToggleMode: toggleMode,
    onPause: togglePause,
  });

  // Auto-fallback: Live → Replay on connection error. Differs from the
  // TASK-10 implementation which fell back to Static — Replay preserves
  // the visual storytelling while abandoning the broken stream.
  //
  // The setState-in-effect lint rule fires here, but this is the canonical
  // "external state changed; synchronize my mode" pattern: the connection
  // state is owned by `useLiveScenario` (an external system from this
  // component's perspective) and we need to react to its transitions.
  useEffect(() => {
    if (mode !== "live") return;
    if (liveScenario.connectionState === "error") {
      console.warn("Live SSE failed — falling back to Replay mode");
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMode("replay");
      setAutoFellBack(true);
    }
  }, [mode, liveScenario.connectionState]);

  // Workflow-timeout fallback: if Live mode connects but no canvas events
  // arrive within 30s, switch to Replay. The reducer pre-seeds initialState
  // from beat 0, so we can detect "still on beat 0" by checking that the
  // live state has not produced any non-empty assets/arcs.
  const liveHadActivity = useMemo(() => {
    const s = liveScenario.state;
    return s.assets.length > 0 || s.arcs.length > 0 || s.costBanner.visible;
  }, [liveScenario.state]);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (mode !== "live") {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      return;
    }
    if (liveHadActivity) return;
    timeoutRef.current = setTimeout(() => {
      console.warn(
        "Live mode produced no activity in 30s — falling back to Replay",
      );
      setMode("replay");
      setAutoFellBack(true);
    }, 30_000);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [mode, liveHadActivity]);

  // Publish demo context for Backstage / hotkeys.
  useEffect(() => {
    if (!persona) return;
    const beat = staticScenario.currentBeat;
    const nextBeat =
      staticScenario.currentBeatIndex < cargoPlaneBeats.length - 1
        ? cargoPlaneBeats[staticScenario.currentBeatIndex + 1]
        : null;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex: staticScenario.currentBeatIndex,
      totalBeats: staticScenario.totalBeats,
      currentBeatId: beat.id,
      narrationCue: beat.narration,
      nextBeatId: nextBeat?.id ?? null,
      nextNarrationCue: nextBeat?.narration ?? null,
      mode,
      connectionState: mode === "live" ? liveScenario.connectionState : "idle",
      lastError:
        mode === "live" && liveScenario.connectionState === "error"
          ? "Live SSE stream failed — falling back to Replay."
          : null,
      startedAt,
      onReset: hardReset,
      onToggleMode: toggleMode,
      onPause: togglePause,
      onSkipToEnd: skipToEnd,
    });
    return cleanup;
  }, [
    persona,
    staticScenario.currentBeatIndex,
    staticScenario.currentBeat,
    staticScenario.totalBeats,
    mode,
    liveScenario.connectionState,
    startedAt,
    hardReset,
    toggleMode,
    togglePause,
    skipToEnd,
  ]);

  const state =
    mode === "live"
      ? liveScenario.state
      : mode === "replay"
        ? replayScenario.state
        : staticScenario.state;

  const reconnect = useCallback(() => {
    setAutoFellBack(false);
    setMode("live");
    setLiveGeneration((g) => g + 1);
  }, []);

  // TASK-45: `A` toggles A2UI-rendered non-spatial panels.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (e.key === "a" || e.key === "A") setA2uiMode((m) => !m);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const showReconnectBanner =
    (mode === "live" &&
      (liveScenario.connectionState === "closed" ||
        liveScenario.connectionState === "error")) ||
    autoFellBack;

  return (
    <CanvasShell
      drawerOpen={state.drawer.open}
      chat={
        <ChatPanel
          mode={mode}
          paused={paused}
          connectionState={liveScenario.connectionState}
          beat={staticScenario.currentBeat}
          index={staticScenario.currentBeatIndex}
          total={staticScenario.totalBeats}
          replayProgress={replayScenario.progress}
        />
      }
      drawer={
        state.drawer.entity ? (
          a2uiMode ? (
            <A2UIPanel
              messages={KC_DRAWER_TX007}
              surfaceId="kc-drawer"
              className="p-4"
            />
          ) : (
            <KnowledgeCatalogDrawer
              canonicalId={state.drawer.entity.canonicalId}
              canonicalLabel={state.drawer.entity.canonicalLabel}
              aspects={state.drawer.entity.aspects}
            />
          )
        ) : null
      }
      canvas={
        <>
          <GlobalMap center={state.mapCenter} zoom={state.mapZoom}>
            {state.assets.map((asset) => (
              <AssetMarker
                key={asset.id}
                id={asset.id}
                location={asset.location}
                state={asset.state}
                label={asset.label}
                pulse={asset.pulse}
                size={asset.size}
              />
            ))}

            {state.arcs.map((arc) => (
              <LogisticsArc
                key={arc.id}
                id={arc.id}
                from={arc.from}
                to={arc.to}
                color={arc.color}
                dashed={arc.dashed}
                animateDraw={arc.animateDraw}
                opacity={arc.opacity}
              />
            ))}
          </GlobalMap>

          {a2uiMode ? (
            state.costBanner.visible ? (
              <div className="absolute bottom-6 right-6 max-w-md">
                <A2UIPanel
                  messages={COST_ROLLUP_CARGO_PLANE}
                  surfaceId="cost-rollup"
                />
              </div>
            ) : null
          ) : (
            <CostRollupBanner
              visible={state.costBanner.visible}
              doomed={state.costBanner.doomed}
              recommended={state.costBanner.recommended}
              avoided={state.costBanner.avoided}
            />
          )}

          <ModeIndicator
            mode={mode}
            paused={paused}
            connectionState={liveScenario.connectionState}
          />

          {a2uiMode && (
            <div className="absolute top-6 right-6 flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-400/10 px-3 py-1.5 backdrop-blur-md">
              <div className="h-2 w-2 rounded-full bg-emerald-400" />
              <div className="text-[10px] uppercase tracking-[0.18em] text-emerald-200">
                A2UI · agent-driven UI
              </div>
            </div>
          )}

          {mode === "static" && (
            <BeatIndicator
              index={staticScenario.currentBeatIndex}
              total={staticScenario.totalBeats}
            />
          )}

          <ReconnectBanner
            visible={showReconnectBanner}
            variant={autoFellBack ? "fellback" : "reconnect"}
            onReconnect={reconnect}
          />

          {persona && (
            <DemoTimer
              targetMinutes={persona.targetDurationMin}
              startedAt={startedAt}
            />
          )}
        </>
      }
    />
  );
}

interface ChatPanelProps {
  mode: Mode;
  paused: boolean;
  connectionState: ConnectionState;
  beat: { id: string; narration: string };
  index: number;
  total: number;
  replayProgress: number;
}

/**
 * Placeholder for the embedded Gemini Enterprise chat surface. The real
 * version (TASK-13) renders the GE chat iframe; this static stand-in
 * surfaces the current beat's narration so the demoer can see what
 * Maria's chat would be showing at this moment.
 */
function ChatPanel({
  mode,
  paused,
  connectionState,
  beat,
  index,
  total,
  replayProgress,
}: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        {MARIA_PERSONA.name.split(" ")[0]} · {MARIA_PERSONA.role}
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>
      <div className="flex-1 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.03] p-4">
        {mode === "static" ? (
          <>
            <div className="mb-2 text-[10px] uppercase tracking-wider text-white/40">
              Beat {index + 1} / {total}
            </div>
            <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
              {beat.id}
            </div>
            <div className="text-sm leading-relaxed text-white/90">
              {beat.narration}
            </div>
          </>
        ) : mode === "live" ? (
          <>
            <div className="mb-2 text-[10px] uppercase tracking-wider text-white/40">
              Live · SSE {paused ? "· paused" : ""}
            </div>
            <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
              connection: {connectionState}
            </div>
            <div className="text-sm leading-relaxed text-white/90">
              Streaming events from the Capacity Orchestrator. Canvas is
              reacting to live Workflow execution.
            </div>
          </>
        ) : (
          <>
            <div className="mb-2 text-[10px] uppercase tracking-wider text-white/40">
              Replay · pre-recorded {paused ? "· paused" : ""}
            </div>
            <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
              events played: {replayProgress}
            </div>
            <div className="text-sm leading-relaxed text-white/90">
              Playing back a canonical cargo-plane run from disk.
            </div>
          </>
        )}
      </div>
      <div className="mt-4 text-[10px] uppercase tracking-wider text-white/40">
        Space advance · Shift+Space back · R reset · L mode · P pause · \ backstage
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

interface ModeIndicatorProps {
  mode: Mode;
  paused: boolean;
  connectionState: ConnectionState;
}

function ModeIndicator({ mode, paused, connectionState }: ModeIndicatorProps) {
  const dotColor =
    mode === "live"
      ? connectionState === "open"
        ? "bg-emerald-400"
        : connectionState === "connecting"
          ? "bg-amber-400"
          : connectionState === "error"
            ? "bg-rose-400"
            : "bg-white/40"
      : mode === "replay"
        ? "bg-sky-400"
        : "bg-white/40";

  return (
    <div className="absolute top-6 left-6 flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 backdrop-blur-md">
      <div className={`h-2 w-2 rounded-full ${dotColor}`} />
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/70">
        {mode}
      </div>
      {mode === "live" && (
        <div className="text-[10px] tracking-wider text-white/40">
          · {connectionState}
        </div>
      )}
      {paused && (
        <div className="text-[10px] uppercase tracking-[0.18em] text-amber-300/90">
          · paused
        </div>
      )}
    </div>
  );
}
