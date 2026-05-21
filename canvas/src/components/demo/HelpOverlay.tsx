"use client";

/**
 * HelpOverlay.tsx
 *
 * Lightweight keyboard reference overlay (toggle: `?`).
 *
 * Renders centered on top of any scenario page so the demoer can confirm
 * a shortcut without leaving the demo. The grid is hand-ordered by
 * demo-flow importance, not alphabetically.
 */

import { motion } from "framer-motion";
import { X } from "lucide-react";

interface HelpOverlayProps {
  onClose: () => void;
}

interface Shortcut {
  keys: string[];
  description: string;
}

const NAVIGATION: Shortcut[] = [
  { keys: ["1", "…", "6"], description: "Jump to persona N" },
  { keys: ["0"], description: "Back to demo launcher" },
  { keys: ["Home"], description: "Back to demo launcher" },
];

const REHEARSAL: Shortcut[] = [
  { keys: ["Space"], description: "Advance beat" },
  { keys: ["Shift", "Space"], description: "Previous beat" },
  { keys: ["B"], description: "Previous beat (legacy)" },
  { keys: ["R"], description: "Reset current scenario" },
  { keys: ["L"], description: "Toggle Static / Live / Replay" },
  { keys: ["P"], description: "Pause / resume" },
];

const OVERLAY: Shortcut[] = [
  { keys: ["\\"], description: "Toggle Backstage panel" },
  { keys: ["?"], description: "Toggle this help" },
  { keys: ["Esc"], description: "Close any open overlay" },
];

export function HelpOverlay({ onClose }: HelpOverlayProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.15 }}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcut reference"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 8, opacity: 0 }}
        transition={{ duration: 0.18 }}
        className="relative w-[640px] max-w-[92vw] rounded-2xl border border-white/10 shadow-2xl"
        style={{ background: "var(--color-bg-elevated)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between border-b border-white/10 px-6 py-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-white/40">
              Rehearsal controls
            </div>
            <h2 className="mt-1 text-lg font-medium text-white">
              Keyboard reference
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close help overlay"
            className="rounded-full p-1 text-white/50 hover:bg-white/5 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid grid-cols-3 gap-x-8 gap-y-6 px-6 py-5">
          <ShortcutGroup title="Navigate" items={NAVIGATION} />
          <ShortcutGroup title="Rehearse" items={REHEARSAL} />
          <ShortcutGroup title="Overlay" items={OVERLAY} />
        </div>

        <footer className="border-t border-white/10 px-6 py-3 text-[10px] uppercase tracking-wider text-white/35">
          Shortcuts are disabled while typing in form inputs.
        </footer>
      </motion.div>
    </motion.div>
  );
}

interface ShortcutGroupProps {
  title: string;
  items: Shortcut[];
}

function ShortcutGroup({ title, items }: ShortcutGroupProps) {
  return (
    <div>
      <div className="mb-3 text-[10px] uppercase tracking-[0.18em] text-white/40">
        {title}
      </div>
      <ul className="space-y-2.5">
        {items.map((s, i) => (
          <li key={i} className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1">
              {s.keys.map((k, j) => (
                <kbd
                  key={j}
                  className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white/80"
                >
                  {k}
                </kbd>
              ))}
            </div>
            <div className="text-[11px] text-white/55">{s.description}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
