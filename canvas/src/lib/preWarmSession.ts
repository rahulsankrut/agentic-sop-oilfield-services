/**
 * preWarmSession.ts
 *
 * Stub for the persona session pre-warm flow (TASK-12 Step 4).
 *
 * When the demoer launches a persona, this is the call that *should*:
 *   1. Load the persona's Memory Profile from Memory Bank (user_id).
 *   2. Activate the deterministic session in Sessions (session_id).
 *   3. Reset any in-flight A2A workflow state for that session.
 *
 * For TASK-12 v1, that wiring is deferred. We do three things:
 *   - Log to the console so the demoer can verify the pre-warm fired
 *     when rehearsing in dev mode.
 *   - Resolve immediately (no network round-trip), so the scenario page
 *     can `await` it without slowing the demo.
 *   - Leave a clear TODO marker for the wiring work that belongs in
 *     TASK-13 / the deploy stream.
 *
 * Once the `/api/demo/pre-warm` route exists, swap the body of
 * `preWarmSession` for the real `fetch` call — the call sites do not
 * need to change.
 */

import type { Persona } from "@/data/personas";

export interface PreWarmResult {
  ok: boolean;
  /** True if a real backend call was made; false for the v1 stub. */
  backendCalled: boolean;
  /** Persona we tried to warm — echoed back for the caller's diagnostics. */
  persona: Persona;
  /** Diagnostic message, surfaced in dev console. */
  message: string;
}

// TODO: wire Memory Bank pre-warm — this is the v1 stub. Real impl in TASK-13.
export async function preWarmSession(persona: Persona): Promise<PreWarmResult> {
  const message =
    `[demo-runner] pre-warm STUB for persona=${persona.id} ` +
    `(user_id=${persona.memoryProfileUserId}, session_id=${persona.sessionId}). ` +
    `Memory Bank load + Sessions seed wired in TASK-13.`;

  if (typeof console !== "undefined") {
    console.info(message);
  }

  // Yield a microtask so callers awaiting this can rely on async semantics
  // matching the eventual real implementation.
  await Promise.resolve();

  return {
    ok: true,
    backendCalled: false,
    persona,
    message,
  };
}
