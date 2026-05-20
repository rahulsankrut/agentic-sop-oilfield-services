"use client";

/**
 * LogisticsArc — animated great-circle arc between two assets on the globe.
 *
 * Two roles in the cargo-plane storyboard:
 *   - "Doomed" arc (Australia → Luanda) renders in faint grey, dashed,
 *     conveying the rejected cargo charter route.
 *   - "Recommended" arc (Lagos → Luanda) renders in vivid green with an
 *     animated draw, conveying the agent's equivalence-based pivot.
 *
 * Implementation notes:
 *   - We add a Mapbox `geojson` source + `line` layer per arc. The line
 *     coordinates are sampled along a great circle via spherical lerp so the
 *     arc curves naturally over the globe instead of cutting through it.
 *   - The "animate draw" effect is achieved by progressively pushing more
 *     interpolated coordinates into the source's GeoJSON over ~800ms — a
 *     reliable approach across mapbox-gl 3.x (the line-trim/line-progress
 *     paints are style-version dependent).
 *   - We deliberately avoid `@turf/great-circle` to keep the canvas
 *     dependency surface small; the math here is ~25 lines.
 */

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";

export interface LogisticsArcProps {
  /** Unique id; used as the Mapbox source + layer id. */
  id: string;
  /** Origin [lng, lat]. */
  from: [number, number];
  /** Destination [lng, lat]. */
  to: [number, number];
  /** Mapbox map instance. Layer is a no-op until the map is ready. */
  map: mapboxgl.Map | null;
  /** Stroke color — accepts any CSS color or `var(--color-...)` for tokens. */
  color: string;
  /** Stroke width in pixels. Defaults to 3 for back-of-room readability. */
  width?: number;
  /** Dashed stroke for "doomed" / rejected routes. */
  dashed?: boolean;
  /** Animate the arc drawing from origin to destination. */
  animateDraw?: boolean;
  /** Stroke opacity. Defaults to 0.9. */
  opacity?: number;
}

// Number of interpolation steps along the great circle. 96 keeps the curve
// smooth at globe zoom levels without bloating the GeoJSON payload.
const ARC_STEPS = 96;

// Total draw animation duration. Tuned in concert with beat durations in
// `demoScenarios.ts` (TASK-08 Step 9).
const DRAW_DURATION_MS = 800;

/**
 * Great-circle interpolation between two lng/lat points via spherical lerp.
 * Both inputs are degrees; returns a polyline of [lng, lat] in degrees.
 */
function greatCircle(
  from: [number, number],
  to: [number, number],
  steps: number,
): [number, number][] {
  const [lng1, lat1] = from;
  const [lng2, lat2] = to;

  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;

  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const lam1 = toRad(lng1);
  const lam2 = toRad(lng2);

  // Cartesian unit vectors on the unit sphere.
  const p1 = {
    x: Math.cos(phi1) * Math.cos(lam1),
    y: Math.cos(phi1) * Math.sin(lam1),
    z: Math.sin(phi1),
  };
  const p2 = {
    x: Math.cos(phi2) * Math.cos(lam2),
    y: Math.cos(phi2) * Math.sin(lam2),
    z: Math.sin(phi2),
  };

  // Angle between the two vectors.
  const dot = Math.max(-1, Math.min(1, p1.x * p2.x + p1.y * p2.y + p1.z * p2.z));
  const omega = Math.acos(dot);
  const sinOmega = Math.sin(omega);

  const out: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    let x: number, y: number, z: number;
    if (sinOmega < 1e-9) {
      // Endpoints coincide (or are antipodal — degenerate); fall back to linear.
      x = p1.x + (p2.x - p1.x) * t;
      y = p1.y + (p2.y - p1.y) * t;
      z = p1.z + (p2.z - p1.z) * t;
    } else {
      const a = Math.sin((1 - t) * omega) / sinOmega;
      const b = Math.sin(t * omega) / sinOmega;
      x = a * p1.x + b * p2.x;
      y = a * p1.y + b * p2.y;
      z = a * p1.z + b * p2.z;
    }
    const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
    const lng = toDeg(Math.atan2(y, x));
    out.push([lng, lat]);
  }
  return out;
}

/**
 * Build a GeoJSON LineString feature from an array of [lng, lat] coords.
 */
function lineStringFeature(coords: [number, number][]): GeoJSON.Feature<GeoJSON.LineString> {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: coords },
  };
}

export function LogisticsArc({
  id,
  from,
  to,
  map,
  color,
  width = 3,
  dashed = false,
  animateDraw = false,
  opacity = 0.9,
}: LogisticsArcProps) {
  // Track the rAF id so we can cancel mid-animation on unmount / prop change.
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!map) return;

    // Defensive cleanup: if a previous instance with this id leaked, drop it
    // before adding a fresh source+layer.
    const safeRemove = () => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    };
    safeRemove();

    const fullArc = greatCircle(from, to, ARC_STEPS);

    map.addSource(id, {
      type: "geojson",
      // Start with just the origin if animating, otherwise the full arc.
      data: lineStringFeature(animateDraw ? [fullArc[0]] : fullArc),
    });

    map.addLayer({
      id,
      type: "line",
      source: id,
      layout: {
        "line-cap": "round",
        "line-join": "round",
      },
      paint: {
        "line-color": color,
        "line-width": width,
        "line-opacity": opacity,
        // Dashed pattern for "doomed" routes. Mapbox spec: array of dash/gap
        // lengths in line widths. `[1]` means a solid line (single segment).
        "line-dasharray": dashed ? [2, 2] : [1],
      },
    });

    if (animateDraw) {
      const startTs = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - startTs) / DRAW_DURATION_MS);
        // Ease out cubic for a snappier feel at the head of the arc.
        const eased = 1 - Math.pow(1 - t, 3);
        const count = Math.max(2, Math.floor(eased * fullArc.length));
        const partial = fullArc.slice(0, count);
        const source = map.getSource<mapboxgl.GeoJSONSource>(id);
        if (source) {
          source.setData(lineStringFeature(partial));
        }
        if (t < 1) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          rafRef.current = null;
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    }

    return () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      // The map may already be torn down (Strict Mode double-mount); guard
      // accordingly.
      try {
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      } catch {
        // map.remove() may have already cleared the style; safe to ignore.
      }
    };
    // Re-create the arc when any visual prop changes. Beats are static, so
    // this fires only on beat transitions.
  }, [
    map,
    id,
    from[0],
    from[1],
    to[0],
    to[1],
    color,
    width,
    dashed,
    animateDraw,
    opacity,
  ]);

  // The arc lives on the Mapbox style, not in the React DOM tree.
  return null;
}
