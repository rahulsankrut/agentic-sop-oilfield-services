"use client";

/**
 * useKeyboardControls.ts
 *
 * Wires global keyboard shortcuts for the demo rehearsal flow.
 *
 *   Space  → onAdvance   (move to the next beat)
 *   B      → onStepBack  (move back one beat)
 *   R      → onReset     (jump to beat 0)
 *
 * The hook attaches a single `keydown` listener on `window` and ignores
 * events that arrive with a meta/ctrl/alt modifier — so Cmd+R still
 * reloads the page and Ctrl+Space still does whatever the browser/OS
 * decided it should do. Repeated keydowns (key-held auto-repeat) are
 * also ignored to keep the demo from skating through beats.
 *
 * Pass `enabled: false` to suppress the listener (e.g. when an input
 * field is focused and we don't want Space to advance the demo).
 */

import { useEffect } from "react";

export interface UseKeyboardControlsOptions {
  onAdvance?: () => void;
  onReset?: () => void;
  onStepBack?: () => void;
  /** Default true. Set false to no-op (used when input fields have focus). */
  enabled?: boolean;
}

export function useKeyboardControls(opts: UseKeyboardControlsOptions): void {
  const { onAdvance, onReset, onStepBack, enabled = true } = opts;

  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      // Bail out on any modifier so we don't intercept Cmd+R / Ctrl+R /
      // Alt+Space / etc. Shift is fine — the demoer may have shift on
      // unintentionally and we don't want to swallow Space silently.
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Ignore OS-level key repeat: holding Space shouldn't fly through
      // every beat in 200ms.
      if (e.repeat) return;

      // Don't hijack typing in form inputs / textareas / contenteditable.
      // We could expose this via `enabled`, but it's cheap insurance.
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return;
        }
      }

      // Normalize for case so Shift+R / capslock-R still work.
      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;

      switch (key) {
        case " ":
        case "Spacebar": // older IE/Edge alias; harmless to keep
          if (onAdvance) {
            e.preventDefault();
            onAdvance();
          }
          break;
        case "r":
          if (onReset) {
            e.preventDefault();
            onReset();
          }
          break;
        case "b":
          if (onStepBack) {
            e.preventDefault();
            onStepBack();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled, onAdvance, onReset, onStepBack]);
}
