"use client";

/**
 * useScenario.ts
 *
 * Drives beat-by-beat advancement of the Operations Canvas demo.
 *
 * The hook owns the current beat index and exposes a small imperative
 * surface (`advance` / `stepBack` / `reset`) that the page wires to
 * keyboard shortcuts (see useKeyboardControls) and any future on-screen
 * controls. The downstream renderers (GlobalMap, KnowledgeCatalogDrawer,
 * CostRollupBanner) consume `state` — which is just the current beat's
 * fully-formed ScenarioState.
 *
 * For TASK-08 / TASK-10 the data source is the static `cargoPlaneBeats`
 * array in `demoScenarios.ts`. TASK-11 will wire live WebSocket events
 * into this same surface so the rest of the canvas doesn't have to change.
 */

import { useCallback, useEffect, useState } from "react";

import type { Beat, ScenarioState } from "@/data/demoScenarios";

export interface UseScenarioOptions {
  beats: Beat[];
  /**
   * If set, auto-advance to the next beat after this many ms have elapsed
   * since the last beat change. Omit (or set 0) for manual / keyboard-driven
   * pacing — which is the rehearsal default.
   */
  autoAdvanceMs?: number;
}

export interface UseScenarioResult {
  state: ScenarioState;
  currentBeat: Beat;
  currentBeatIndex: number;
  totalBeats: number;
  advance: () => void;
  stepBack: () => void;
  reset: () => void;
}

export function useScenario(opts: UseScenarioOptions): UseScenarioResult {
  const { beats, autoAdvanceMs } = opts;

  if (beats.length === 0) {
    // Throwing here is the right call — a zero-beat scenario is a config bug,
    // not a runtime condition. Better to fail loudly at mount than silently
    // render an empty canvas during a customer demo.
    throw new Error("useScenario: beats must contain at least one beat.");
  }

  const [currentBeatIndex, setCurrentBeatIndex] = useState(0);

  const advance = useCallback(() => {
    setCurrentBeatIndex((i) => Math.min(i + 1, beats.length - 1));
  }, [beats.length]);

  const stepBack = useCallback(() => {
    setCurrentBeatIndex((i) => Math.max(i - 1, 0));
  }, []);

  const reset = useCallback(() => {
    setCurrentBeatIndex(0);
  }, []);

  // Optional auto-advance. Only runs while we're not already on the final
  // beat — we never wrap, because the storyboard's final state is the
  // intended hold for closing narration.
  useEffect(() => {
    if (!autoAdvanceMs || autoAdvanceMs <= 0) return;
    if (currentBeatIndex >= beats.length - 1) return;

    const timer = setTimeout(() => {
      setCurrentBeatIndex((i) => Math.min(i + 1, beats.length - 1));
    }, autoAdvanceMs);

    return () => clearTimeout(timer);
  }, [autoAdvanceMs, currentBeatIndex, beats.length]);

  const currentBeat = beats[currentBeatIndex];

  return {
    state: currentBeat.state,
    currentBeat,
    currentBeatIndex,
    totalBeats: beats.length,
    advance,
    stepBack,
    reset,
  };
}
