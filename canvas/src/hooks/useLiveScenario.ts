"use client";

/**
 * useLiveScenario.ts
 *
 * Subscribes to the Capacity Orchestrator's A2A SSE stream and reduces the
 * incoming `CanvasEvent`s into the same `ScenarioState` shape the static
 * beats produce — so the existing canvas components render unchanged.
 *
 * The reducer is exported (`eventReducer`) so the replay hook
 * (`useReplayScenario`) can share it: same events, same output, only the
 * source of the events differs (live SSE vs. pre-recorded JSON).
 */

import { useEffect, useReducer, useRef, useState } from "react";

import { AgentStream } from "@/lib/agent-stream";
import type { ConnectionState } from "@/lib/agent-stream";
import type { CanvasEvent } from "@/lib/canvas-events";
import type { ScenarioState } from "@/data/demoScenarios";

// ---------------------------------------------------------------------------
// Event → ScenarioState reducer (shared with useReplayScenario)
// ---------------------------------------------------------------------------

/**
 * Replace the entry in `list` with the same `id` as `item`, or append
 * `item` if no match. Used so the same canvas event firing more than
 * once (re-emit from a different node, replay loop, Live→Static→Live
 * toggle) doesn't produce React duplicate-key warnings.
 */
function upsertById<T extends { id: string }>(list: readonly T[], item: T): T[] {
  const idx = list.findIndex((x) => x.id === item.id);
  if (idx < 0) return [...list, item];
  const next = list.slice();
  next[idx] = item;
  return next;
}

/**
 * Apply one canvas event to the current `ScenarioState`. Unknown event
 * types pass through unchanged — the canvas tolerates unknown events so
 * that backend additions don't break already-deployed canvases.
 */
export function eventReducer(
  state: ScenarioState,
  event: CanvasEvent,
): ScenarioState {
  switch (event.type) {
    case "workflow.started":
      // DEMO NARRATION: "And we're live — the workflow just started.
      // Canvas is now driven by the Orchestrator's SSE stream."
      return {
        ...state,
        drawer: { open: false },
        costBanner: { visible: false },
      };

    case "capacity.gap_detected":
      return {
        ...state,
        mapCenter: [event.location.longitude, event.location.latitude],
        mapZoom: 4,
        assets: upsertById(state.assets, {
          id: "capacity-gap",
          location: [event.location.longitude, event.location.latitude],
          state: "blocked",
          label: event.location.label ?? `Gap: ${event.canonical_asset_id}`,
          pulse: true,
          size: "lg",
        }),
      };

    case "mcp.call.started":
      return {
        ...state,
        activeMcpCalls: [
          ...(state.activeMcpCalls ?? []),
          {
            server: event.server,
            tool: event.tool,
            startedAt: event.timestamp,
          },
        ],
      };

    case "mcp.call.completed":
      return {
        ...state,
        activeMcpCalls: (state.activeMcpCalls ?? []).filter(
          (c) => !(c.server === event.server && c.tool === event.tool),
        ),
      };

    case "route.doomed_proposed":
      return {
        ...state,
        arcs: upsertById(state.arcs, {
          id: "doomed",
          from: [event.from_location.longitude, event.from_location.latitude],
          to: [event.to_location.longitude, event.to_location.latitude],
          color: "#6b7280",
          dashed: true,
          animateDraw: true,
          opacity: 0.7,
        }),
        costBanner: {
          ...state.costBanner,
          visible: true,
          doomed: event.estimated_cost_usd,
        },
      };

    case "knowledge_catalog.lookup":
      return {
        ...state,
        drawer: {
          open: true,
          entity: {
            canonicalId: event.canonical_id,
            canonicalLabel: event.canonical_label,
            aspects: event.aspects,
          },
        },
        drawerOpen: true,
      };

    case "equivalence.found":
      return {
        ...state,
        assets: upsertById(state.assets, {
          id: `equivalent-${event.equivalent_asset.canonical_id}`,
          location: [event.location.longitude, event.location.latitude],
          state: "available",
          label: event.equivalent_asset.label,
          pulse: true,
          size: "lg",
        }),
      };

    case "route.recommended": {
      // Fade the doomed arc (if present) first, then upsert the recommended arc.
      const fadedArcs = state.arcs.map((a) =>
        a.id === "doomed" ? { ...a, opacity: 0.2, animateDraw: false } : a,
      );
      return {
        ...state,
        arcs: upsertById(fadedArcs, {
          id: "recommended",
          from: [event.from_location.longitude, event.from_location.latitude],
          to: [event.to_location.longitude, event.to_location.latitude],
          color: "#10b981",
          dashed: false,
          animateDraw: true,
          opacity: 1,
        }),
        costBanner: {
          visible: true,
          doomed: state.costBanner.doomed,
          recommended: event.estimated_cost_usd,
          avoided: event.avoided_cost_usd,
        },
      };
    }

    case "forecast.loaded":
      return {
        ...state,
        showTimeline: true,
        timeline: event.timeline,
      };

    case "buffer.recommendation":
      return {
        ...state,
        bufferOption: event.risk_tolerance,
        drawerOpen: true,
      };

    // Pass-through events (no canvas mutation needed today).
    case "workflow.completed":
    case "workflow.failed":
    case "node.started":
    case "node.completed":
    case "router.decision":
      return state;

    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseLiveScenarioOptions {
  scenarioName: "cargo-plane" | "buffer-planning";
  sessionId: string;
  userId: string;
  /** The prompt that kicks off the workflow on the Orchestrator. */
  userMessage: string;
  /** When false, the hook holds `initialState` and does not open a stream. */
  enabled: boolean;
  initialState: ScenarioState;
}

export interface UseLiveScenarioResult {
  state: ScenarioState;
  connectionState: ConnectionState;
}

export function useLiveScenario(
  opts: UseLiveScenarioOptions,
): UseLiveScenarioResult {
  const [state, dispatch] = useReducer(eventReducer, opts.initialState);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("idle");
  const streamRef = useRef<AgentStream | null>(null);

  useEffect(() => {
    if (!opts.enabled) return;

    const url = process.env.NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL;
    if (!url) {
      // eslint-disable-next-line no-console
      console.error(
        "useLiveScenario: NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL is not set",
      );
      setConnectionState("error");
      return;
    }

    const stream = new AgentStream({
      streamUrl: url,
      sessionId: opts.sessionId,
      userId: opts.userId,
      userMessage: opts.userMessage,
      onEvent: (evt) => dispatch(evt),
      onStateChange: setConnectionState,
    });
    streamRef.current = stream;
    void stream.connect();

    return () => {
      stream.close();
      streamRef.current = null;
    };
  }, [
    opts.enabled,
    opts.sessionId,
    opts.userId,
    opts.userMessage,
  ]);

  return { state, connectionState };
}
