"use client";

/**
 * LogisticsArc — animated great-circle arc between two assets on Google Maps.
 *
 * Roles in the cargo-plane storyboard:
 *   - "Doomed" arc (Darwin → Luanda) renders in faint grey, dashed,
 *     conveying the rejected cargo charter route.
 *   - "Recommended" arc (Lagos → Luanda) renders in vivid green with an
 *     animated draw, conveying the agent's equivalence-based pivot.
 *
 * Renders nothing in the React tree — uses ``useMap()`` to grab the
 * Google Maps instance and creates a Polyline with ``geodesic: true``
 * so the curvature follows the great circle automatically (no spherical
 * lerp needed; the Maps JS API does it).
 *
 * Animation: ``animateDraw`` reveals the polyline progressively via a
 * single ``requestAnimationFrame`` loop that updates the path from
 * 0% to 100% over 800ms.
 */

import { useEffect, useRef } from "react";
import { useMap } from "@vis.gl/react-google-maps";

interface LogisticsArcProps {
  id: string;
  from: [number, number]; // [lng, lat]
  to: [number, number];
  color: string;          // CSS color (hex or rgba)
  dashed?: boolean;
  animateDraw?: boolean;
  opacity?: number;
  /** Optional — kept for API compatibility with the page wire-up. */
  map?: google.maps.Map | null;
}

const ARC_WIDTH_PX = 4;

// DEMO NARRATION: "The doomed arc — Darwin to Luanda, 13,200km, dashed
// grey — is what the agent could have stopped at. The recommended arc
// — Lagos to Luanda, ~2700km, solid green — is what equivalence lookup
// in Knowledge Catalog made possible. Same map, same eye, the savings
// are visible without anyone saying a word."
export function LogisticsArc({
  id,
  from,
  to,
  color,
  dashed = false,
  animateDraw = false,
  opacity = 1,
}: LogisticsArcProps) {
  const map = useMap();
  const lineRef = useRef<google.maps.Polyline | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!map) return;

    // Resolve the iconography for dashed lines: Google Maps emulates
    // dashes by drawing a "dot" icon repeatedly along the line with a
    // gap. The base polyline opacity is set to 0 in that case so only
    // the icons show; this matches the Mapbox dashed look.
    const polylineOptions: google.maps.PolylineOptions = {
      path: animateDraw ? [{ lat: from[1], lng: from[0] }] : geodesicPath(from, to),
      geodesic: true,
      strokeColor: color,
      strokeOpacity: dashed ? 0 : opacity,
      strokeWeight: ARC_WIDTH_PX,
      icons: dashed
        ? [
            {
              icon: {
                path: "M 0,-1 0,1",
                strokeOpacity: opacity,
                strokeColor: color,
                strokeWeight: ARC_WIDTH_PX,
                scale: 3,
              },
              offset: "0",
              repeat: "12px",
            },
          ]
        : undefined,
      map,
    };

    const polyline = new google.maps.Polyline(polylineOptions);
    lineRef.current = polyline;

    if (animateDraw) {
      const startTs = performance.now();
      const DURATION_MS = 800;
      const step = (now: number) => {
        const t = Math.min(1, (now - startTs) / DURATION_MS);
        const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
        const path = geodesicPath(from, to, eased);
        polyline.setPath(path);
        if (t < 1) {
          rafRef.current = requestAnimationFrame(step);
        }
      };
      rafRef.current = requestAnimationFrame(step);
    }

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      polyline.setMap(null);
      lineRef.current = null;
    };
  }, [map, id, from, to, color, dashed, animateDraw, opacity]);

  return null;
}

/**
 * Sample N points along the great circle between two ``[lng, lat]``
 * coordinates and return them as a Google Maps ``LatLngLiteral[]`` path.
 * Google Maps ``geodesic: true`` handles the rendering curvature
 * automatically, but we still sample so the animation can grow the line
 * progressively and so the curvature is honored on long arcs.
 *
 * ``progress`` (default 1) lets callers reveal only the first
 * ``progress * 100%`` of the arc — used by the draw animation.
 */
function geodesicPath(
  from: [number, number],
  to: [number, number],
  progress = 1,
  steps = 64,
): google.maps.LatLngLiteral[] {
  const path: google.maps.LatLngLiteral[] = [];
  const total = Math.max(1, Math.floor(steps * progress));
  const φ1 = (from[1] * Math.PI) / 180;
  const λ1 = (from[0] * Math.PI) / 180;
  const φ2 = (to[1] * Math.PI) / 180;
  const λ2 = (to[0] * Math.PI) / 180;

  const Δσ = Math.acos(
    Math.min(
      1,
      Math.max(
        -1,
        Math.sin(φ1) * Math.sin(φ2) +
          Math.cos(φ1) * Math.cos(φ2) * Math.cos(λ2 - λ1),
      ),
    ),
  );

  for (let i = 0; i <= total; i++) {
    const f = (i / steps) * progress;
    if (Δσ === 0) {
      path.push({ lat: from[1], lng: from[0] });
      continue;
    }
    const A = Math.sin((1 - f) * Δσ) / Math.sin(Δσ);
    const B = Math.sin(f * Δσ) / Math.sin(Δσ);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1) + B * Math.sin(φ2);
    const φ = Math.atan2(z, Math.sqrt(x * x + y * y));
    const λ = Math.atan2(y, x);
    path.push({ lat: (φ * 180) / Math.PI, lng: (λ * 180) / Math.PI });
  }
  return path;
}
