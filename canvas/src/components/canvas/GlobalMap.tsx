"use client";

/**
 * GlobalMap — Mapbox dark globe canvas for the Persona 3 Operations Canvas.
 *
 * Renders a full-bleed 3D globe centered on West Africa for the cargo-plane
 * scenario. The map instance is published back to the parent via
 * `onMapReady` so sibling components can imperatively add markers and arcs
 * (Mapbox markers live outside React's render tree).
 *
 * Operator setup: set `NEXT_PUBLIC_MAPBOX_TOKEN` in `canvas/.env.local` (or
 * the deploy env). Without it, Mapbox returns 401 on tile requests and the
 * canvas renders blank. The token is bundled into the client JS, so it must
 * be a URL-restricted token in production (see TASK-08 Common pitfalls).
 *
 * The bang assertion below is intentional: the demo deploy always provides
 * the env var; for syntax-only checks the value is not consulted.
 */

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

// DEMO NARRATION (Beat 0/8): "This is Maria's Operations Canvas. The map shows
// every Tool X and Tool X variant across her West Africa portfolio."
mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN!;

export interface GlobalMapProps {
  /** Map center as [lng, lat]. Defaults to Africa-centered for the cargo-plane scenario. */
  center?: [number, number];
  /** Initial zoom level. */
  zoom?: number;
  /** Callback fired once the Mapbox style finishes loading; parent uses this to attach markers/arcs. */
  onMapReady?: (map: mapboxgl.Map) => void;
}

export function GlobalMap({
  center = [15, 5], // Africa-centered for the cargo-plane scenario
  zoom = 3,
  onMapReady,
}: GlobalMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center,
      zoom,
      // 3D globe projection — gives the cargo-plane drama its visual scale.
      // Mapbox GL 3.x accepts either a string shorthand or a
      // ProjectionSpecification object for `projection`.
      projection: "globe",
      attributionControl: false,
    });

    map.on("load", () => {
      // Fog/atmosphere for the globe effect — matches the dark-v11 palette.
      map.setFog({
        color: "rgb(20, 27, 53)",
        "high-color": "rgb(36, 92, 223)",
        "horizon-blend": 0.02,
        "space-color": "rgb(11, 11, 25)",
        "star-intensity": 0.6,
      });
      mapRef.current = map;
      onMapReady?.(map);
    });

    // React Strict Mode in dev double-mounts effects; without this cleanup
    // Mapbox throws "Map container is already initialized".
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Full-bleed inside the CanvasShell's relative <main> column.
  return <div ref={containerRef} className="absolute inset-0" />;
}
