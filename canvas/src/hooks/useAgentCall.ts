"use client";

/**
 * useAgentCall.ts
 *
 * React hook wrapping `runAgentCall` (lib/agent-call.ts) with status state,
 * cancellation, and reset. Used by the P1 (forecast-review) and P2
 * (buffer-planning) scenario pages to make ONE live call to a deployed
 * agent at the moment of agent intelligence in the scenario — replacing
 * static beat data with the live structured output.
 *
 * The hook intentionally has no auto-fire semantics: the page calls
 * `run(message)` imperatively when its scenario advances past the trigger
 * beat. This keeps the contract tight ("the live call happens HERE in the
 * narrative") and avoids surprise calls on mount / re-render.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { runAgentCall } from "@/lib/agent-call";

export type AgentCallStatus = "idle" | "loading" | "ok" | "error";

export interface UseAgentCallOptions {
  /** Vertex AI streamQuery URL for the target agent. Empty disables. */
  streamUrl: string;
  /** Persona's memory-profile user id (drives Memory Bank preload). */
  userId: string;
  /** Pre-seeded session id, or empty to auto-create per call. */
  sessionId?: string;
}

export interface UseAgentCallResult<T> {
  status: AgentCallStatus;
  data: T | null;
  rawText: string;
  error: string | null;
  /** Fire one live call. No-op if streamUrl is empty or a call is in-flight. */
  run: (userMessage: string) => void;
  /** Reset to idle + abort any in-flight call. */
  reset: () => void;
}

export function useAgentCall<T>(
  opts: UseAgentCallOptions,
): UseAgentCallResult<T> {
  const [status, setStatus] = useState<AgentCallStatus>("idle");
  const [data, setData] = useState<T | null>(null);
  const [rawText, setRawText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  // Mount flag so we don't setState after unmount (the run is async).
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setData(null);
    setRawText("");
    setError(null);
  }, []);

  const run = useCallback(
    (userMessage: string) => {
      if (!opts.streamUrl) {
        setStatus("error");
        setError("streamUrl is not configured");
        return;
      }
      if (abortRef.current) {
        // A call is already in-flight; ignore re-trigger.
        return;
      }
      const controller = new AbortController();
      abortRef.current = controller;
      setStatus("loading");
      setError(null);
      setData(null);
      setRawText("");

      runAgentCall<T>({
        streamUrl: opts.streamUrl,
        sessionId: opts.sessionId ?? "",
        userId: opts.userId,
        userMessage,
        signal: controller.signal,
      })
        .then((result) => {
          if (!mountedRef.current) return;
          if (controller.signal.aborted) return;
          setRawText(result.rawText);
          if (result.parsed) {
            setData(result.parsed);
            setStatus("ok");
          } else {
            setStatus("error");
            setError("Agent response could not be parsed as JSON");
          }
        })
        .catch((err: unknown) => {
          if (!mountedRef.current) return;
          if (controller.signal.aborted) return;
          setStatus("error");
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (abortRef.current === controller) abortRef.current = null;
        });
    },
    [opts.streamUrl, opts.userId, opts.sessionId],
  );

  return { status, data, rawText, error, run, reset };
}
