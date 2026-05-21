"use client";

/**
 * useRehearsalControls.ts
 *
 * Per-scenario keyboard wiring for the demo runner (TASK-12).
 *
 * Extends `useKeyboardControls` (Space / B / R) with the rehearsal-mode
 * additions:
 *
 *   Space         → onAdvance      (next beat)
 *   Shift+Space   → onStepBack     (previous beat — spec's preferred binding)
 *   B             → onStepBack     (legacy binding, kept for muscle memory)
 *   R             → onReset        (jump to beat 0, full reset)
 *   L             → onToggleMode   (cycle Static → Live → Replay → Static)
 *   P             → onPause        (pause / resume auto-advance or live stream)
 *
 * The global hotkeys `1`..`6` (persona jump), `\` (backstage), `?` (help),
 * and `0`/`Home` (back to launcher) are owned by the
 * RehearsalControls component in the root layout — those need to work
 * even when no scenario page is mounted, so they live higher.
 *
 * Modifier rules:
 *   - Cmd / Ctrl / Alt + any: passed through to the browser. The demoer
 *     does not need (or want) us hijacking Cmd+R.
 *   - Shift is significant for Space only (Shift+Space === step back).
 *     Shift+R / Shift+L are treated identically to plain R / L so that
 *     capslock-on or accidental-shift don't break the rehearsal.
 *   - Repeats (key-held) are dropped — holding Space should not skate
 *     through beats in 200ms.
 *
 * Form-input safety:
 *   - Events from <input>, <textarea>, <select>, or contenteditable
 *     targets are ignored so a focused search box doesn't eat Space.
 */

import { useEffect } from "react";

export interface UseRehearsalControlsOptions {
  onAdvance?: () => void;
  onStepBack?: () => void;
  onReset?: () => void;
  onToggleMode?: () => void;
  onPause?: () => void;
  /** Default true. Set false to disable all per-scenario shortcuts. */
  enabled?: boolean;
}

export function useRehearsalControls(opts: UseRehearsalControlsOptions): void {
  const {
    onAdvance,
    onStepBack,
    onReset,
    onToggleMode,
    onPause,
    enabled = true,
  } = opts;

  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      // Modifier short-circuits — Shift is handled below per key.
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Drop key-held repeats.
      if (e.repeat) return;

      // Form input guard.
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

      // Space + Shift+Space — beat navigation.
      // Treat `" "`, `Spacebar` (older browsers) and `e.code === "Space"`
      // as the spacebar to be robust across keyboard layouts.
      const isSpace = e.key === " " || e.key === "Spacebar" || e.code === "Space";
      if (isSpace) {
        if (e.shiftKey) {
          if (onStepBack) {
            e.preventDefault();
            onStepBack();
          }
        } else if (onAdvance) {
          e.preventDefault();
          onAdvance();
        }
        return;
      }

      // Letter keys — case-insensitive. Use e.code where available so
      // `l` and `L` route the same regardless of Shift state.
      const letter = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      switch (letter) {
        case "b":
          if (onStepBack) {
            e.preventDefault();
            onStepBack();
          }
          break;
        case "r":
          if (onReset) {
            e.preventDefault();
            onReset();
          }
          break;
        case "l":
          if (onToggleMode) {
            e.preventDefault();
            onToggleMode();
          }
          break;
        case "p":
          if (onPause) {
            e.preventDefault();
            onPause();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled, onAdvance, onStepBack, onReset, onToggleMode, onPause]);
}
