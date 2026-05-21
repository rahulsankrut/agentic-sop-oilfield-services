"use client";

/**
 * useDemoContext.ts
 *
 * Lightweight global store for the rehearsal control surface (TASK-12).
 *
 * Scenario pages publish their current beat, narration cue, mode, and
 * connection state into a module-scoped store via `publishDemoState`.
 * The Backstage panel (overlay toggled by `\`) and any other rehearsal
 * surface subscribe via `useDemoContext()`.
 *
 * Why a module-scoped store instead of React context?
 *
 *   The RehearsalControls component mounts in the root layout — above
 *   every page. Scenario pages mount below it. We need the panel to
 *   read state *published by* its descendants, which is the opposite
 *   direction context naturally flows. Two clean options: (a) lift a
 *   provider into the layout and have every scenario page imperatively
 *   call into it, (b) keep a small module-scoped store with a
 *   useSyncExternalStore subscription. We pick (b) because it sidesteps
 *   provider mount-order foot-guns and the surface is intentionally
 *   tiny.
 *
 * The store is reset on each `publishDemoState` call — there's no merge,
 * scenario pages publish the full snapshot each beat. Mounts publish
 * defaults; unmounts clear via the returned cleanup.
 */

import { useSyncExternalStore } from "react";

import type { Persona } from "@/data/personas";

export type DemoMode = "static" | "live" | "replay";

export type DemoConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export interface DemoState {
  /** Persona currently on screen, or null on the launcher / unknown route. */
  persona: Persona | null;
  /** 0-based beat index; -1 when not in a beat-driven scenario. */
  currentBeatIndex: number;
  /** Total beats in the active scenario; 0 when not applicable. */
  totalBeats: number;
  /** Beat id (slug) — useful for debug; rendered in Backstage as small caps. */
  currentBeatId: string | null;
  /** Human-readable narration cue for the current beat. */
  narrationCue: string | null;
  /** Preview of the next beat's id, when available. */
  nextBeatId: string | null;
  /** Preview of the next beat's narration cue, when available. */
  nextNarrationCue: string | null;
  /** Active mode — static / live / replay. */
  mode: DemoMode;
  /** Live-mode connection state; for static/replay this is "idle". */
  connectionState: DemoConnectionState;
  /** Most recent error string, if any — surfaces in the Backstage. */
  lastError: string | null;
  /**
   * Timestamp the user first triggered an advance / live connect.
   * Drives the demo timer's elapsed counter. Null until the first
   * meaningful action, so timers don't tick during mount.
   */
  startedAt: number | null;
  /** Reset handler — bound to the scenario's reset action. */
  onReset: (() => void) | null;
  /** Mode-toggle handler — bound to the scenario's L-key handler. */
  onToggleMode: (() => void) | null;
  /** Pause handler — bound to the scenario's P-key handler. */
  onPause: (() => void) | null;
  /** Skip-to-end handler — bound to the scenario's quick-jump action. */
  onSkipToEnd: (() => void) | null;
}

const DEFAULT_STATE: DemoState = {
  persona: null,
  currentBeatIndex: -1,
  totalBeats: 0,
  currentBeatId: null,
  narrationCue: null,
  nextBeatId: null,
  nextNarrationCue: null,
  mode: "static",
  connectionState: "idle",
  lastError: null,
  startedAt: null,
  onReset: null,
  onToggleMode: null,
  onPause: null,
  onSkipToEnd: null,
};

// Module-scoped store. Subscribers are notified on every publish.
let currentState: DemoState = DEFAULT_STATE;
const subscribers = new Set<() => void>();

function notify(): void {
  for (const sub of subscribers) sub();
}

function subscribe(fn: () => void): () => void {
  subscribers.add(fn);
  return () => {
    subscribers.delete(fn);
  };
}

function getSnapshot(): DemoState {
  return currentState;
}

// useSyncExternalStore demands a stable server snapshot — return defaults
// during SSR. Scenario pages are "use client" so this only matters for the
// initial hydration tick, where DEFAULT_STATE is a safe placeholder.
function getServerSnapshot(): DemoState {
  return DEFAULT_STATE;
}

/**
 * Publish a (partial) update to the demo state. Scenario pages call this
 * from useEffect after each beat change / mode toggle / connection change.
 * Returns a cleanup that resets the store to defaults — wire it into the
 * effect's cleanup to keep the Backstage panel honest when the page unmounts.
 */
export function publishDemoState(partial: Partial<DemoState>): () => void {
  currentState = { ...currentState, ...partial };
  notify();
  return () => {
    // Only clear the slots we set, so concurrent publishers don't trample
    // each other. In practice only one scenario page is mounted at a time.
    currentState = { ...currentState, ...invertPartial(partial) };
    notify();
  };
}

function invertPartial(partial: Partial<DemoState>): Partial<DemoState> {
  const out: Partial<DemoState> = {};
  for (const key of Object.keys(partial) as Array<keyof DemoState>) {
    // Reset each touched key to its DEFAULT_STATE value.
    (out as Record<string, unknown>)[key] = DEFAULT_STATE[key];
  }
  return out;
}

/** Subscribe to the demo state. Returns a fresh snapshot on each change. */
export function useDemoContext(): DemoState {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Imperative read — for callbacks outside of React render. */
export function readDemoState(): DemoState {
  return currentState;
}
