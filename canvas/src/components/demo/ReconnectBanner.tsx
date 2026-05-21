"use client";

/**
 * ReconnectBanner.tsx
 *
 * Small top-center banner that surfaces when the live SSE/WebSocket
 * stream disconnects unexpectedly, with a one-click reconnect button.
 *
 * Positioning (per spec pitfall): top-center, NOT over the map area.
 * Width is bounded so the cargo-plane GlobalMap behind it stays visible.
 *
 * Auto-fallback behavior is handled separately by useScenarioWithFallback —
 * this banner is the audience-visible affordance for the *manual* path.
 * If the auto-fallback already kicked in, the banner narrates that
 * gracefully ("Switched to replay so we can finish telling the story.").
 */

interface ReconnectBannerProps {
  /** True when we should show the banner. */
  visible: boolean;
  /**
   * Variant — `reconnect` shows the call to action, `fellback` narrates
   * the automatic fallback that already happened.
   */
  variant?: "reconnect" | "fellback";
  /** Click handler for the reconnect button. */
  onReconnect?: () => void;
}

export function ReconnectBanner({
  visible,
  variant = "reconnect",
  onReconnect,
}: ReconnectBannerProps) {
  if (!visible) return null;

  const isReconnect = variant === "reconnect";

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none absolute left-1/2 top-6 z-30 -translate-x-1/2"
    >
      <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-amber-300/30 bg-amber-300/[0.08] px-4 py-2 text-[11px] tracking-wide text-amber-100/95 shadow-lg backdrop-blur-md">
        <span className="relative inline-flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-300/70" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-300" />
        </span>
        {isReconnect ? (
          <>
            <span>Live connection lost.</span>
            <button
              type="button"
              onClick={onReconnect}
              className="rounded-full bg-amber-300/20 px-2.5 py-0.5 text-[10px] uppercase tracking-[0.18em] text-amber-100 hover:bg-amber-300/30"
            >
              Reconnect
            </button>
          </>
        ) : (
          <span>Switched to replay so the demo continues.</span>
        )}
      </div>
    </div>
  );
}
