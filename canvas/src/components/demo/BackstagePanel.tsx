"use client";

/**
 * BackstagePanel.tsx
 *
 * The demoer's coach — a slide-in overlay (toggle: `\`) that surfaces
 * everything they need to land each beat without referring to a script.
 *
 * Layout (top → bottom):
 *   1. Now playing — persona name + role.
 *   2. Beat progress — segmented bar + N of M counter.
 *   3. Say next — the narration cue for the *next* moment, highlighted.
 *   4. Currently — the narration for the *current* beat (smaller).
 *   5. Technical — mode, connection state, last error.
 *   6. Quick actions — restart, switch mode, pause, skip to end.
 *
 * The "say next" panel is intentionally the most prominent — when the
 * demoer glances at this surface mid-sentence, that's the line they
 * want to be looking at, not a recap of what they just said.
 *
 * Recovery banner (per pitfalls): error messaging stays muted and
 * coachable here. The audience-facing canvas never surfaces these
 * strings in red text on the projector — the WebSocket reconnect
 * banner lives in the chat column at top-center, not on the map.
 */

import { motion } from "framer-motion";
import {
  FastForward,
  Pause,
  RotateCcw,
  Shuffle,
  X,
} from "lucide-react";

import { useDemoContext } from "@/hooks/useDemoContext";

interface BackstagePanelProps {
  onClose: () => void;
}

// DEMO NARRATION (off-screen — for the demoer): "This is the backstage
// panel. The audience doesn't see it. Current beat, the next narration
// cue, technical state, quick actions. Recovery is one click away."
export function BackstagePanel({ onClose }: BackstagePanelProps) {
  const ctx = useDemoContext();
  const {
    persona,
    currentBeatIndex,
    totalBeats,
    currentBeatId,
    narrationCue,
    nextBeatId,
    nextNarrationCue,
    mode,
    connectionState,
    lastError,
    onReset,
    onToggleMode,
    onPause,
    onSkipToEnd,
  } = ctx;

  const inBeatScenario = totalBeats > 0 && currentBeatIndex >= 0;

  return (
    <motion.aside
      initial={{ x: 420, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 420, opacity: 0 }}
      transition={{ type: "tween", duration: 0.24, ease: [0.4, 0, 0.2, 1] }}
      role="complementary"
      aria-label="Backstage demo controls"
      className="fixed top-0 right-0 z-50 flex h-screen w-[400px] flex-col border-l border-white/10 shadow-2xl"
      style={{ background: "var(--color-bg-elevated)" }}
    >
      <header className="sticky top-0 flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-white/40">
            Backstage
          </div>
          <div className="mt-0.5 text-sm font-medium text-white">
            Rehearsal coach
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close backstage panel"
          className="rounded-full p-1 text-white/50 hover:bg-white/5 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
        {/* Now playing */}
        <section>
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
            Now playing
          </div>
          <div className="mt-1 text-lg font-medium text-white">
            {persona ? persona.displayName : "—"}
          </div>
          <div className="text-sm text-white/60">
            {persona ? persona.role : "Launcher / no scenario active"}
          </div>
        </section>

        {/* Beat indicator */}
        {inBeatScenario && (
          <section>
            <div className="mb-2 flex items-baseline justify-between text-[10px] uppercase tracking-[0.18em] text-white/40">
              <span>
                Beat {currentBeatIndex + 1} of {totalBeats}
              </span>
              {currentBeatId && (
                <span className="font-mono normal-case tracking-wider text-white/35">
                  {currentBeatId}
                </span>
              )}
            </div>
            <div className="flex gap-1">
              {Array.from({ length: totalBeats }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full ${
                    i < currentBeatIndex
                      ? "bg-white/60"
                      : i === currentBeatIndex
                        ? "bg-amber-300"
                        : "bg-white/15"
                  }`}
                />
              ))}
            </div>
          </section>
        )}

        {/* Say next — most important panel on this surface */}
        <section className="rounded-xl border border-amber-300/30 bg-amber-300/[0.06] p-4">
          <div className="text-[10px] uppercase tracking-[0.18em] text-amber-200/80">
            Say next
          </div>
          <div className="mt-2 text-sm leading-relaxed text-white/95">
            {nextNarrationCue ??
              (narrationCue
                ? "(final beat — close with the wrap line on the handbook)"
                : "Pick a persona to load the first narration cue.")}
          </div>
          {nextBeatId && (
            <div className="mt-3 text-[10px] uppercase tracking-wider text-amber-200/40">
              cue id · {nextBeatId}
            </div>
          )}
        </section>

        {/* Currently — small, for context only */}
        {narrationCue && (
          <section>
            <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
              Currently saying
            </div>
            <div className="mt-1.5 text-xs leading-relaxed text-white/55">
              {narrationCue}
            </div>
          </section>
        )}

        {/* Technical state */}
        <section>
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
            Technical
          </div>
          <dl className="mt-2 space-y-1.5 text-xs">
            <div className="flex justify-between">
              <dt className="text-white/55">Mode</dt>
              <dd className="font-mono uppercase tracking-wider text-white/85">
                {mode}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-white/55">Connection</dt>
              <dd
                className={`font-mono uppercase tracking-wider ${
                  connectionState === "open"
                    ? "text-emerald-300"
                    : connectionState === "error"
                      ? "text-rose-300"
                      : connectionState === "connecting"
                        ? "text-amber-300"
                        : "text-white/55"
                }`}
              >
                {connectionState}
              </dd>
            </div>
            {persona && (
              <div className="flex justify-between">
                <dt className="text-white/55">Target</dt>
                <dd className="font-mono text-white/70">
                  {persona.targetDurationMin}:00
                </dd>
              </div>
            )}
          </dl>
          {lastError && (
            <div className="mt-3 rounded-lg border border-rose-400/30 bg-rose-400/[0.06] px-3 py-2 text-[11px] leading-relaxed text-rose-200/90">
              {lastError}
            </div>
          )}
        </section>

        {/* Quick actions */}
        <section>
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
            Quick actions
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <ActionButton
              icon={<RotateCcw className="h-3.5 w-3.5" />}
              label="Restart"
              shortcut="R"
              onClick={onReset}
              disabled={!onReset}
            />
            <ActionButton
              icon={<Shuffle className="h-3.5 w-3.5" />}
              label="Switch mode"
              shortcut="L"
              onClick={onToggleMode}
              disabled={!onToggleMode}
            />
            <ActionButton
              icon={<Pause className="h-3.5 w-3.5" />}
              label="Pause"
              shortcut="P"
              onClick={onPause}
              disabled={!onPause}
            />
            <ActionButton
              icon={<FastForward className="h-3.5 w-3.5" />}
              label="Skip to end"
              onClick={onSkipToEnd}
              disabled={!onSkipToEnd}
            />
          </div>
        </section>
      </div>

      <footer className="border-t border-white/10 px-5 py-3 text-[10px] uppercase tracking-wider text-white/35">
        <kbd className="rounded bg-white/10 px-1">\</kbd> close ·
        <kbd className="ml-2 rounded bg-white/10 px-1">?</kbd> all shortcuts
      </footer>
    </motion.aside>
  );
}

interface ActionButtonProps {
  icon?: React.ReactNode;
  label: string;
  shortcut?: string;
  onClick: (() => void) | null;
  disabled?: boolean;
}

function ActionButton({
  icon,
  label,
  shortcut,
  onClick,
  disabled,
}: ActionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick ?? undefined}
      disabled={disabled}
      className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-2 text-xs text-white/85 transition-colors hover:bg-white/[0.07] disabled:cursor-not-allowed disabled:text-white/30 disabled:hover:bg-white/[0.03]"
    >
      <span className="flex items-center gap-2">
        {icon}
        {label}
      </span>
      {shortcut && (
        <kbd className="rounded bg-white/10 px-1 text-[10px] uppercase tracking-wider text-white/60">
          {shortcut}
        </kbd>
      )}
    </button>
  );
}
