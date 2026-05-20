"use client";

/**
 * Persona 3 (Maria, OCC Planner) — cargo-plane scenario page.
 *
 * Static demo mode: beat-by-beat scenario state from
 * ``cargoPlaneBeats``. Press Space to advance, R to reset, B to step
 * back. Live mode (SSE-driven) lands in TASK-10.
 */

import { CanvasShell } from "@/components/layout/CanvasShell";
import { GlobalMap } from "@/components/canvas/GlobalMap";
import { AssetMarker } from "@/components/canvas/AssetMarker";
import { LogisticsArc } from "@/components/canvas/LogisticsArc";
import { KnowledgeCatalogDrawer } from "@/components/canvas/KnowledgeCatalogDrawer";
import { CostRollupBanner } from "@/components/canvas/CostRollupBanner";
import { useScenario } from "@/hooks/useScenario";
import { useKeyboardControls } from "@/hooks/useKeyboardControls";
import { cargoPlaneBeats } from "@/data/demoScenarios";

export default function CargoPlaneScenarioPage() {
  const scenario = useScenario({ beats: cargoPlaneBeats });
  const { state, currentBeat, currentBeatIndex, totalBeats } = scenario;

  // DEMO NARRATION (rehearsal controls): "Demoer drives the scenario manually
  // — Space advances a beat, B steps back, R resets. Keyboard-only so we never
  // touch the mouse during the keynote."
  useKeyboardControls({
    onAdvance: scenario.advance,
    onStepBack: scenario.stepBack,
    onReset: scenario.reset,
  });

  return (
    <CanvasShell
      drawerOpen={state.drawer.open}
      chat={<ChatPanel beat={currentBeat} index={currentBeatIndex} total={totalBeats} />}
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

          <BeatIndicator index={currentBeatIndex} total={totalBeats} />
        </>
      }
    />
  );
}

interface ChatPanelProps {
  beat: { id: string; narration: string };
  index: number;
  total: number;
}

/**
 * Placeholder for the embedded Gemini Enterprise chat surface. The real
 * version (TASK-13) renders the GE chat iframe; this static stand-in
 * surfaces the current beat's narration so the demoer can see what
 * Maria's chat would be showing at this moment.
 */
function ChatPanel({ beat, index, total }: ChatPanelProps) {
  return (
    <div className="flex h-full flex-col p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.18em] text-white/40">
        Maria · OCC West Africa
      </div>
      <div className="mb-6 text-sm text-white/70">
        Gemini Enterprise chat (stand-in)
      </div>
      <div className="flex-1 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.03] p-4">
        <div className="mb-2 text-[10px] uppercase tracking-wider text-white/40">
          Beat {index + 1} / {total}
        </div>
        <div className="mb-3 text-[10px] uppercase tracking-wider text-white/30">
          {beat.id}
        </div>
        <div className="text-sm leading-relaxed text-white/90">
          {beat.narration}
        </div>
      </div>
      <div className="mt-4 text-[10px] uppercase tracking-wider text-white/40">
        Space advance · B back · R reset
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
