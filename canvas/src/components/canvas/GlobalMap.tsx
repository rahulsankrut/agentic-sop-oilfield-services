"use client";

import { ReactNode, useCallback, useEffect } from "react";
import { APIProvider, Map, useMap } from "@vis.gl/react-google-maps";

/**
 * GlobalMap — Google Maps Platform canvas base.
 *
 * Wrapper around ``@vis.gl/react-google-maps``'s `<Map>` with a dark
 * cartographic style approximating the demo aesthetic. Children render
 * inside the map provider so they can call `useMap()` and attach
 * markers / polylines via the Maps JS API.
 *
 * Required env: ``NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`` (baked into client
 * JS at build time; restrict to the canvas domain in the GCP Console).
 * Optional: ``NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID`` for cloud-managed
 * styling (preferred over the inline ``styles`` array in production).
 */

const API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";
// Map ID is required for AdvancedMarkerElement (modern markers). Falls back
// to Google's "DEMO_MAP_ID" string literal — works for development with the
// default Google style. For production, create a Map ID in Cloud Console
// (Maps Platform → Map Management) with a dark cloud-managed style and set
// NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID. With a real Map ID, the inline DARK_STYLES
// below is ignored (cloud style wins).
const MAP_ID = process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? "DEMO_MAP_ID";
const USE_INLINE_STYLES =
  !process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID; // only when no real Map ID

// Inline dark cartographic style. Mirrors the visual feel of Mapbox's
// dark-v11 — muted blues for water, dark slate for land, dimmed labels.
// Used when NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID is unset (dev fallback).
const DARK_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: "geometry", stylers: [{ color: "#11172a" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#11172a" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#6b7280" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0a0e1a" }] },
  { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#3b4253" }] },
  { featureType: "administrative.country", elementType: "geometry.stroke", stylers: [{ color: "#1f2937" }] },
  { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#1a2238" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ visibility: "off" }] },
  { featureType: "poi", elementType: "all", stylers: [{ visibility: "off" }] },
  { featureType: "transit", elementType: "all", stylers: [{ visibility: "off" }] },
];

interface GlobalMapProps {
  center?: [number, number]; // [lng, lat] — kept lng-first to match the rest of the codebase
  zoom?: number;
  onMapReady?: (map: google.maps.Map) => void;
  children?: ReactNode;
}

// DEMO NARRATION: "The canvas is a Google Maps Platform map — same
// engine the operator sees in Google Earth, same Cloud-managed Map ID
// the customer's own GIS team can edit. Markers and arcs are React
// components that attach via the Maps JS API."
export function GlobalMap({
  center = [15, 5], // Africa-centered for the cargo-plane scenario
  zoom = 3,
  onMapReady,
  children,
}: GlobalMapProps) {
  if (!API_KEY) {
    return <MapMissingKeyOverlay />;
  }

  return (
    <APIProvider apiKey={API_KEY}>
      <div className="absolute inset-0">
        <Map
          mapId={MAP_ID}
          styles={USE_INLINE_STYLES ? DARK_STYLES : undefined}
          defaultCenter={{ lat: center[1], lng: center[0] }}
          defaultZoom={zoom}
          disableDefaultUI
          gestureHandling="greedy"
          backgroundColor="#0a0e1a"
        >
          <MapHandoff onMapReady={onMapReady} center={center} zoom={zoom} />
          {children}
        </Map>
      </div>
    </APIProvider>
  );
}

/**
 * Forwards the Maps JS API map instance up to the parent and animates
 * the camera when center / zoom change between scenario beats. Rendered
 * INSIDE <Map> so ``useMap()`` resolves to the right instance.
 */
function MapHandoff({
  onMapReady,
  center,
  zoom,
}: {
  onMapReady?: (m: google.maps.Map) => void;
  center: [number, number];
  zoom: number;
}) {
  const map = useMap();

  const ready = useCallback(() => {
    if (map && onMapReady) onMapReady(map);
  }, [map, onMapReady]);

  useEffect(() => {
    ready();
  }, [ready]);

  // Pan / zoom when the active beat changes. Google Maps ``panTo`` is the
  // smooth move; ``setZoom`` is instant — for the demo's pace that's fine.
  useEffect(() => {
    if (!map) return;
    map.panTo({ lat: center[1], lng: center[0] });
    map.setZoom(zoom);
  }, [map, center, zoom]);

  return null;
}

function MapMissingKeyOverlay() {
  return (
    <div
      className="absolute inset-0 flex items-center justify-center"
      style={{ background: "var(--color-bg-base)" }}
    >
      <div className="max-w-md rounded-lg border border-amber-400/30 bg-amber-500/5 p-6 text-amber-100">
        <div className="mb-2 text-xs uppercase tracking-[0.18em] text-amber-300/70">
          Map disabled
        </div>
        <div className="text-sm leading-relaxed">
          Set{" "}
          <code className="rounded bg-black/40 px-1">
            NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
          </code>{" "}
          in <code className="rounded bg-black/40 px-1">canvas/.env.local</code>{" "}
          to render the canvas. Markers and arcs will still render on top once
          the key is present.
        </div>
      </div>
    </div>
  );
}
