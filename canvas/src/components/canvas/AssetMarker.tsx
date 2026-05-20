"use client";

/**
 * AssetMarker — color-coded asset dot rendered on Google Maps via
 * ``AdvancedMarkerElement``.
 *
 * Markers must be readable from the back of a conference room at
 * 1920×1080, so they are large, high-contrast, and color-coded by
 * state. The capacity gap (e.g. Luanda) sets ``pulse`` to draw the eye.
 *
 * The ``map`` prop is no longer required by callers — the component
 * grabs the map via ``useMap()`` from ``@vis.gl/react-google-maps``,
 * which the surrounding ``<Map>`` provides. The optional ``map`` prop
 * is preserved as a legacy passthrough so the page wire-up doesn't have
 * to change.
 */

import { AdvancedMarker, useMap } from "@vis.gl/react-google-maps";

export type AssetState = "available" | "in-transit" | "blocked" | "in-repair";
export type MarkerSize = "sm" | "md" | "lg";

interface AssetMarkerProps {
  id: string;
  location: [number, number]; // [lng, lat]
  state: AssetState;
  label: string;
  pulse?: boolean;
  size?: MarkerSize;
  /** Optional — kept for API compatibility with the page wire-up. */
  map?: google.maps.Map | null;
}

const STATE_COLOR: Record<AssetState, string> = {
  available: "var(--color-asset-available)",
  "in-transit": "var(--color-asset-in-transit)",
  blocked: "var(--color-asset-blocked)",
  "in-repair": "var(--color-asset-in-repair)",
};

const SIZE_PX: Record<MarkerSize, number> = {
  sm: 14,
  md: 20,
  lg: 28,
};

// DEMO NARRATION: "Color-coded by status — green available, amber in
// transit, red blocked, blue in repair. The pulsing red ring on Luanda
// is the capacity gap; the pulsing green ring on Lagos is the local
// substitute. Visual hierarchy carries the eye through the beat."
export function AssetMarker({
  id,
  location,
  state,
  label,
  pulse = false,
  size = "md",
}: AssetMarkerProps) {
  const map = useMap();
  if (!map) return null;

  const color = STATE_COLOR[state];
  const sizePx = SIZE_PX[size];

  return (
    <AdvancedMarker
      position={{ lat: location[1], lng: location[0] }}
      title={label}
    >
      <div
        data-asset-id={id}
        className="relative flex items-center justify-center"
        style={{ width: sizePx * 2, height: sizePx * 2 }}
      >
        {/* Pulsing halo for capacity-gap / hero markers */}
        {pulse && (
          <span
            className="absolute inline-block rounded-full opacity-50"
            style={{
              width: sizePx * 1.8,
              height: sizePx * 1.8,
              background: color,
              animation: "asset-marker-pulse 1.6s ease-out infinite",
            }}
          />
        )}
        {/* Solid dot */}
        <span
          className="relative rounded-full ring-2 ring-white/70"
          style={{
            width: sizePx,
            height: sizePx,
            background: color,
            boxShadow: `0 0 0 4px rgba(0,0,0,0.55), 0 0 18px ${color}`,
          }}
        />
        {/* Label badge */}
        <span
          className="absolute whitespace-nowrap rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white"
          style={{
            top: sizePx * 1.5,
            background: "rgba(10,14,26,0.78)",
            border: "1px solid rgba(255,255,255,0.10)",
          }}
        >
          {label}
        </span>
        <style jsx>{`
          @keyframes asset-marker-pulse {
            0% {
              transform: scale(0.7);
              opacity: 0.55;
            }
            70% {
              transform: scale(1.6);
              opacity: 0;
            }
            100% {
              transform: scale(1.6);
              opacity: 0;
            }
          }
        `}</style>
      </div>
    </AdvancedMarker>
  );
}
