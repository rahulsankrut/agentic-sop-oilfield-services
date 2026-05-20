"use client";

/**
 * Persona 3 (Maria, OCC Planner) — cargo-plane scenario page.
 *
 * Tri-state mode (TASK-10):
 *  - "static"  — beat-by-beat scenario state from `cargoPlaneBeats` (default).
 *                Space advances, B steps back, R resets.
 *  - "live"    — SSE-driven from the deployed Capacity Orchestrator's A2A
 *                `message:stream` endpoint. Auto-falls back to static on
 *                connection error.
 *  - "replay"  — pre-recorded event sequence played at original timing
 *                (`/recorded_events/cargo_plane_v1.json`). Demo safety net.
 *
 * Press `L` to cycle Static → Live → Replay → Static.
 */

import { useEffect, useState } from "react";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { GlobalMap } from "@/components/canvas/GlobalMap";
import { AssetMarker } from "@/components/canvas/AssetMarker";
import { LogisticsArc } from "@/components/canvas/LogisticsArc";
import { KnowledgeCatalogDrawer } from "@/components/canvas/KnowledgeCatalogDrawer";
import { CostRollupBanner } from "@/components/canvas/CostRollupBanner";
import { useScenario } from "@/hooks/useScenario";
import { useKeyboardControls } from "@/hooks/useKeyboardControls";
import { useLiveScenario } from "@/hooks/useLiveScenario";
import { useReplayScenario } from "@/hooks/useReplayScenario";
import type { ConnectionState } from "@/lib/agent-stream";
import { cargoPlaneBeats } from "@/data/demoScenarios";

type Mode = "static" | "live" | "replay";

const MARIA_SESSION_ID = "demo-maria-cargo-plane-v1";
const MARIA_USER_ID = "maria-occ-planner-west-africa";
const MARIA_PROMPT =
  "I need a Tool X variant in Luanda by Friday — what are my options?";

const REPLAY_PATH = "/recorded_events/cargo_plane_v1.json";

export default function CargoPlaneScenarioPage() {
  const [mode, setMode] = useState<Mode>("static");

  const staticScenario = useScenario({ beats: cargoPlaneBeats });
  const liveScenario = useLiveScenario({
    scenarioName: "cargo-plane",
    sessionId: MARIA_SESSION_ID,
    userId: MARIA_USER_ID,
    userMessage: MARIA_PROMPT,
    enabled: mode === "live",
    initialState: cargoPlaneBeats[0].state,
  });
  const replayScenario = useReplayScenario({
    recordingPath: REPLAY_PATH,
    enabled: mode === "replay",
    initialState: cargoPlaneBeats[0].state,
  });

  // DEMO NARRATION (rehearsal controls): preserved verbatim from static mode.
  // In live/replay mode the keys still work — they only mutate the static
  // scenario's beat index, which is harmless when the active mode is
  // live/replay (we don't read static state in those modes).
  useKeyboardControls({
    onAdvance: staticScenario.advance,
    onStepBack: staticScenario.stepBack,
    onReset: staticScenario.reset,
  });

  // L key cycles Static → Live → Replay → Static.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "l" && e.key !== "L") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      setMode((m) =>
        m === "static" ? "live" : m === "live" ? "replay" : "static",
      );
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Auto-fallback if Live errors.
  useEffect(() => {
    if (mode === "live" && liveScenario.connectionState === "error") {
      // eslint-disable-next-line no-console
      console.warn("Live SSE failed, falling back to Static");
      setMode("static");
    }
  }, [mode, liveScenario.connectionState]);

  const state =
    mode === "live"
      ? liveScenario.state
      : mode === "replay"
        ? replayScenario.state
        : staticScenario.state;

  return (
    <CanvasShell
      drawerOpen={state.drawer.open}
      chat={
        <ChatPanel
          mode={mode}
          connectionState={liveScenario.connectionState}
          beat={staticScenario.currentBeat}
          index={staticScenario.currentBeatIndex}
          total={staticScenario.totalBeats}
          replayProgress={replayScenario.progress}
        />
      }
      drawer={
        state.drawer.entity ? (
          <KnowledgeCatalogDrawer
            canonicalId={state.drawer.entity.canonicalId}
            canonicalLabel={state.drawer.entity.canonicalLabel}
            aspects={state.drawer.entity.aspects}
          />
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

          <CostRollupBanner
            visible={state.costBanner.visible}
            doomed={state.costBanner.doomed}
            recommended={state.costBanner.recommended}
            avoided={state.costBanner.avoided}
          />

          <ModeIndicator
            mode={mode}
            connectionState={liveScenario.connectionState}
          />

          {mode === "static" && (
            <BeatIndicator
              index={staticScenario.currentBeatIndex}
              total={staticScenario.totalBeats}
            />
          )}
        </>
      }
    />
  );
}

interface ChatPanelProps {
  mode: Mode;
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
  connectionState,
  beat,
  index,
  total,
  replayProgress,
}: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        Maria · OCC West Africa
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
              Live · SSE
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
              Replay · pre-recorded
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
        Space advance · B back · R reset · L mode
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
  connectionState: ConnectionState;
}

function ModeIndicator({ mode, connectionState }: ModeIndicatorProps) {
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
    </div>
  );
}
