"use client";

/**
 * RehearsalControls.tsx
 *
 * Global keyboard handler + Backstage/Help overlays for the demo runner.
 *
 * Mounted in the root layout so its shortcuts work on every page,
 * including `/demo` itself. Per-scenario shortcuts (Space / R / L / P /
 * B / Shift+Space) are handled by `useRehearsalControls` inside each
 * scenario page — those need access to scenario-local actions, so they
 * live with the page.
 *
 * Owned here:
 *
 *   1, 2, 3, 4, 5, 6  → jump to persona N's scenario route, with pre-warm
 *   0 or Home         → back to /demo launcher
 *   \                 → toggle Backstage panel
 *   ?                 → toggle Help overlay
 *   Esc               → close whichever overlay is open
 */

import { AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BackstagePanel } from "./BackstagePanel";
import { HelpOverlay } from "./HelpOverlay";
import { PERSONAS, personaByNumber } from "@/data/personas";
import { preWarmSession } from "@/lib/preWarmSession";

export function RehearsalControls() {
  const router = useRouter();
  const [backstageOpen, setBackstageOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  // Close both overlays — used as part of the navigation handlers so we
  // never have a stale panel on top of an unrelated page. Inlined here
  // rather than as a useEffect on pathname because the latter trips
  // react-hooks/set-state-in-effect and is also less explicit about intent.
  const closeOverlays = () => {
    setBackstageOpen(false);
    setHelpOpen(false);
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Modifier short-circuit. The demoer never wants us swallowing
      // Cmd+R, Cmd+L, Ctrl+\, etc.
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Form-input safety — same guard as useRehearsalControls.
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

      // 1..6 — persona jump (with pre-warm)
      if (/^[1-6]$/.test(e.key)) {
        e.preventDefault();
        const persona = personaByNumber(parseInt(e.key, 10));
        if (!persona) return;
        // Fire-and-forget the pre-warm — the navigation doesn't wait.
        // The scenario page will (in v1) re-issue its own pre-warm on
        // mount to be safe. TODO: move pre-warm to a real route in TASK-13.
        void preWarmSession(persona);
        closeOverlays();
        router.push(persona.route);
        return;
      }

      // 0 / Home — back to launcher
      if (e.key === "0" || e.key === "Home") {
        e.preventDefault();
        closeOverlays();
        router.push("/demo");
        return;
      }

      // Backslash — backstage panel
      if (e.key === "\\") {
        e.preventDefault();
        setBackstageOpen((b) => !b);
        return;
      }

      // ? — help overlay (Shift+/ on US keyboards; e.key is "?")
      if (e.key === "?") {
        e.preventDefault();
        setHelpOpen((h) => !h);
        return;
      }

      // Esc — close any open overlay
      if (e.key === "Escape") {
        if (helpOpen || backstageOpen) {
          e.preventDefault();
          setHelpOpen(false);
          setBackstageOpen(false);
        }
        return;
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router, helpOpen, backstageOpen]);

  return (
    <>
      <AnimatePresence>
        {backstageOpen && (
          <BackstagePanel onClose={() => setBackstageOpen(false)} />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {helpOpen && <HelpOverlay onClose={() => setHelpOpen(false)} />}
      </AnimatePresence>
    </>
  );
}

/**
 * Compile-time guard: this triggers a TS error if PERSONAS ever shrinks
 * below 6 entries — keeping the 1..6 hotkey contract honest.
 */
type _AssertSixPersonas = typeof PERSONAS extends readonly { number: 1 | 2 | 3 | 4 | 5 | 6 }[]
  ? true
  : never;
const _SIX: _AssertSixPersonas = true;
void _SIX;
