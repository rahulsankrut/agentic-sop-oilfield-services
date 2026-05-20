"use client";

/**
 * AssetMarker — color-coded asset dot for the Global Asset View.
 *
 * Markers must be readable from the back of a conference room at 1920×1080,
 * so they are large, high-contrast, and color-coded by state. The capacity
 * gap (e.g. Luanda) sets `pulse` to draw the eye.
 *
 * Attaches to a Mapbox map via `mapboxgl.Marker` and renders its visual
 * content through a React portal into the marker's DOM element. This keeps
 * the marker imperative (Mapbox owns the on-map positioning) while the
 * visual stays declarative (Framer Motion animations, design tokens, etc.).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import mapboxgl from "mapbox-gl";
import { motion } from "framer-motion";

export type AssetState = "available" | "in-transit" | "blocked" | "in-repair";

/**
 * Inline-style CSS var references for each asset state.
 * Using `var(--color-...)` directly is safest in Tailwind 4: arbitrary token
 * names don't always autogenerate utility classes, and inline styles are
 * unambiguous for the demo render path.
 */
const STATE_COLOR_VAR: Record<AssetState, string> = {
  available: "var(--color-asset-available)",
  "in-transit": "var(--color-asset-in-transit)",
  blocked: "var(--color-asset-blocked)",
  "in-repair": "var(--color-asset-in-repair)",
};

const SIZE_PX: Record<NonNullable<AssetMarkerProps["size"]>, number> = {
  sm: 12,
  md: 16,
  lg: 24,
};

export interface AssetMarkerProps {
  /** Stable identifier — used for React key + Mapbox cleanup. */
  id: string;
  /** [lng, lat] of the asset on the globe. */
  location: [number, number];
  /** Operational state, drives marker color. */
  state: AssetState;
  /** Label rendered to the right of the dot. */
  label: string;
  /** Mapbox map instance. Marker is a no-op until the map is ready. */
  map: mapboxgl.Map | null;
  /** When true, an outward radial pulse animates behind the marker (capacity gap, hero asset). */
  pulse?: boolean;
  /** Marker dot size. Defaults to `md`. */
  size?: "sm" | "md" | "lg";
}

// DEMO NARRATION (Beat 0/8): "Color-coded by status — green available, amber
// in transit, red blocked, blue in repair. The pulsing red ring on Luanda is
// the active capacity gap."
export function AssetMarker({
  id,
  location,
  state,
  label,
  map,
  pulse = false,
  size = "md",
}: AssetMarkerProps) {
  // Mount a single DOM node per marker; the portal renders our React tree
  // into it, while Mapbox positions it on the globe.
  const container = useMemo(() => {
    if (typeof document === "undefined") return null;
    const el = document.createElement("div");
    el.setAttribute("data-asset-marker", id);
    // Allow the radial pulse and label to overflow the marker's dot.
    el.style.overflow = "visible";
    el.style.pointerEvents = "none";
    return el;
  }, [id]);

  const [mounted, setMounted] = useState(false);
  const markerRef = useRef<mapboxgl.Marker | null>(null);

  // Attach/detach the Mapbox marker. Stable across location updates so we
  // don't churn the DOM node every beat.
  useEffect(() => {
    if (!map || !container) return;
    const marker = new mapboxgl.Marker({ element: container, anchor: "center" })
      .setLngLat(location)
      .addTo(map);
    markerRef.current = marker;
    setMounted(true);
    return () => {
      marker.remove();
      markerRef.current = null;
      setMounted(false);
    };
    // Intentionally exclude `location` — location updates flow through the
    // next effect via setLngLat so we keep the same marker instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, container]);

  // Update marker position if the asset moves (in-transit beats in TASK-10).
  // Depend on scalar lng/lat so a new array literal from the parent doesn't
  // trigger a redundant Mapbox call every render.
  useEffect(() => {
    if (!markerRef.current) return;
    markerRef.current.setLngLat(location);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location[0], location[1]]);

  const dotSize = SIZE_PX[size];
  const color = STATE_COLOR_VAR[state];

  if (!container || !mounted) return null;

  return createPortal(
    <div
      className="relative flex items-center justify-center"
      style={{ width: dotSize, height: dotSize }}
    >
      {pulse && (
        <motion.div
          aria-hidden
          className="absolute rounded-full"
          style={{
            width: dotSize,
            height: dotSize,
            backgroundColor: color,
            opacity: 0.4,
          }}
          animate={{ scale: [1, 2.5], opacity: [0.6, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <div
        className="rounded-full shadow-lg ring-2 ring-white/30"
        style={{
          width: dotSize,
          height: dotSize,
          backgroundColor: color,
        }}
      />
      {label && (
        <span
          className="absolute left-full ml-2 whitespace-nowrap text-xs font-medium text-white/90"
          // Subtle shadow lifts the label off the dark cartographic base.
          style={{ textShadow: "0 1px 2px rgba(0,0,0,0.8)" }}
        >
          {label}
        </span>
      )}
    </div>,
    container,
  );
}
