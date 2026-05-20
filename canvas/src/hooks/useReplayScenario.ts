"use client";

/**
 * useReplayScenario.ts
 *
 * Plays a pre-recorded sequence of canvas events at their original timing
 * so the demo has a "guaranteed-good" mode if the live SSE path fails on a
 * customer network. Uses the same `eventReducer` as `useLiveScenario` — so
 * Live and Replay produce identical canvas behavior; only the source of the
 * events differs (live SSE vs. JSON file under `/canvas/data/recorded_events/`).
 *
 * The actual recording lives at, e.g., `public/recorded_events/cargo_plane_v1.json`
 * (a thin static-asset mirror of `canvas/data/recorded_events/...`). Recording
 * tooling lands later in TASK-10 (see spec Step 8); for now this hook simply
 * fetches whatever JSON the operator drops at `recordingPath`.
 */

import { useEffect, useReducer, useState } from "react";

import type { CanvasEvent } from "@/lib/canvas-events";
import type { ScenarioState } from "@/data/demoScenarios";

import { eventReducer } from "./useLiveScenario";

interface RecordedEntry {
  delayMsFromStart: number;
  event: CanvasEvent;
}

export interface Recording {
  events: RecordedEntry[];
}

export interface UseReplayScenarioOptions {
  /**
   * Public path served by Next.js, e.g. `/recorded_events/cargo_plane_v1.json`.
   * Files dropped in `canvas/public/recorded_events/` are served from there;
   * `canvas/data/recorded_events/` is the source-of-truth folder for
   * recordings that are checked into the repo.
   */
  recordingPath: string;
  enabled: boolean;
  initialState: ScenarioState;
}

export interface UseReplayScenarioResult {
  state: ScenarioState;
  /** Number of events dispatched so far. */
  progress: number;
}

export function useReplayScenario(
  opts: UseReplayScenarioOptions,
): UseReplayScenarioResult {
  const [state, dispatch] = useReducer(eventReducer, opts.initialState);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!opts.enabled) return;

    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];

    fetch(opts.recordingPath)
      .then((r) => {
        if (!r.ok) {
          throw new Error(
            `useReplayScenario: failed to load ${opts.recordingPath} (HTTP ${r.status})`,
          );
        }
        return r.json();
      })
      .then((rec: Recording) => {
        if (cancelled) return;
        for (const { delayMsFromStart, event } of rec.events) {
          const t = setTimeout(() => {
            if (cancelled) return;
            dispatch(event);
            setProgress((p) => p + 1);
          }, delayMsFromStart);
          timers.push(t);
        }
      })
      .catch((err: unknown) => {
        // eslint-disable-next-line no-console
        console.error("useReplayScenario: load/parse failed", err);
      });

    return () => {
      cancelled = true;
      for (const t of timers) clearTimeout(t);
    };
  }, [opts.enabled, opts.recordingPath]);

  return { state, progress };
}
