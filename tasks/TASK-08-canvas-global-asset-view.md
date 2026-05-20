# TASK-08: Operations Canvas scaffold and Global Asset View

**Prerequisites:** TASK-07 complete. Memory Bank profiles wired; demo sessions seeded; backend produces deterministic cargo-plane output. The Cloud Trace from a cargo-plane run shows the Workflow graph executing, MCP calls happening, Knowledge Catalog being queried.

**Estimated effort:** 5-7 days for one engineer.

**Stream:** Frontend

---

> **Spec-history note (2026-05-20):** This spec originally specified
> Mapbox GL JS 3.x for the cartographic base. The actual implementation
> uses **Google Maps Platform via `@vis.gl/react-google-maps@^1.8`**
> instead, to keep the canvas aligned with the rest of the Google stack
> (single GCP billing surface, Cloud-managed Map IDs, geodesic Polylines
> built-in). The shipped components in `canvas/src/components/canvas/`
> are the source of truth; the Mapbox code snippets in Steps 4-7 below
> are kept for historical context but should be read as the *previous*
> design — the shipped code is functionally equivalent.
>
> Env var renamed: `NEXT_PUBLIC_MAPBOX_TOKEN` → `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`
> (plus optional `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` for cloud-managed
> styling). The trade-off: no true 3D globe (Google Maps is 2D Mercator);
> the cargo-plane story works fine on 2D because the drama is the arc +
> cost banner, not the curvature.

---

## Context

The Operations Canvas is a Next.js companion view that opens **inside** the Gemini Enterprise app for Personas 2 and 3. It is not a separate application; it is a Custom View embedded in the GE app shell. The customer sees one interface — GE — with the canvas appearing as a side panel when Maria or Tomas activates their scenario.

For Persona 3 (Maria, the cargo-plane centerpiece), the canvas renders the **Global Asset View**: a Mapbox dark cartographic globe with asset markers, logistics arcs, a Knowledge Catalog entity drawer, and a cost roll-up banner. The narrative is choreographed in `persona3_canvas_storyboard.md` — eight beats that play out over roughly two minutes within Maria's five-minute segment.

This task builds the **structural foundation** plus the **Global Asset View specifically**. The Fleet Utilization View for Persona 2 comes in TASK-09. WebSocket integration that makes the canvas react to live agent events comes in TASK-10. For TASK-08, the canvas runs in **static demo mode** with hardcoded scenario data — enough to verify the visual storytelling works before wiring it to live agent output.

The design principle: every visual element on the canvas must be readable from the back row of a conference room at 1920×1080. Markers are large, arcs are bold, type is set in clear weights, contrast is high. Subtle is for product UI; demos need legibility.

---

## Inputs

- TASK-07 complete (backend producing deterministic cargo-plane output via session `demo-maria-cargo-plane-v1`)
- Storyboard: `persona3_canvas_storyboard.md` — beat-by-beat choreography
- Brief: `agentic_sop_oilfield_services_brief.md` — Operations Canvas section, technical stack
- Reference repo: `/tmp/next-26-keynotes/devkey/demo-2` — has Next.js + Tailwind patterns to follow
- Mapbox account with access token (provision in TASK-01 if not done)

---

## Deliverables

When this task is complete:

1. **Next.js 15 app** scaffolded at `canvas/` with:
   - TypeScript 5 strict mode
   - Tailwind 4 with the design tokens from the brief
   - shadcn/ui components installed
   - Mapbox GL 3
   - Framer Motion for choreographed animations
   - lucide-react for icons
2. **Three-panel layout shell**: embedded chat (left, narrow) | canvas (center, wide) | side drawer (right, collapsible)
3. **Global Asset View** rendering for Persona 3 with:
   - Mapbox dark cartographic base
   - Asset marker layer (color-coded: green=available, amber=in-transit, red=blocked, blue=in-repair)
   - Logistics arc layer (animated drawing with directional arrowhead)
   - Knowledge Catalog entity drawer (expandable, side-right)
   - Cost roll-up banner (top-right)
   - Capacity gap origin highlighted (pulsing red ring around Luanda)
4. **Beat-by-beat animation choreography** matching the storyboard's 8 beats, driven by a `useScenario` hook
5. **Static demo mode** with hardcoded scenario data in `canvas/data/demoScenarios.ts` (WebSocket events arrive in TASK-10)
6. **Demo runner controls** for manual beat advancement during rehearsal: keyboard shortcuts (Space to advance, R to reset, B to step back)
7. **Tested in Chrome at 1920×1080** with no layout breaks; runs at smooth 60fps for animations
8. **Deployment config** for Cloud Run hosting (Dockerfile, cloudbuild.yaml)

---

## Step-by-step instructions

### Step 1 — Scaffold the Next.js project

```bash
cd /path/to/agentic-sop-oilfield-services
npx create-next-app@15 canvas \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*"

cd canvas
```

Add dependencies:

```bash
npm install \
  mapbox-gl@^3.0.0 \
  framer-motion@^11.0.0 \
  lucide-react \
  @radix-ui/react-dialog \
  @radix-ui/react-slot \
  @radix-ui/react-tabs \
  class-variance-authority \
  clsx \
  tailwind-merge

npm install -D \
  @types/mapbox-gl

# shadcn/ui setup
npx shadcn@latest init -d
npx shadcn@latest add button card badge dialog tabs separator
```

### Step 2 — Configure design tokens

The brief and storyboard specify the color palette and typography. Codify them as CSS variables in `canvas/app/globals.css`:

```css
@import "tailwindcss";

@theme {
  /* Background scale — dark cartographic context */
  --color-bg-base: #0a0e1a;
  --color-bg-elevated: #11172a;
  --color-bg-overlay: #1a2238;

  /* Asset state colors — high contrast for back-of-room readability */
  --color-asset-available: #10b981;    /* green */
  --color-asset-in-transit: #f59e0b;   /* amber */
  --color-asset-blocked: #ef4444;      /* red */
  --color-asset-in-repair: #3b82f6;    /* blue */

  /* Accent colors */
  --color-knowledge-catalog: #3b82f6;  /* blue — KC accent */
  --color-cost-saved: #10b981;         /* green — money rolling up */
  --color-cost-avoided: #6b7280;       /* gray — strikethrough doomed costs */

  /* Type scale */
  --font-display: ui-sans-serif, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

body {
  background: var(--color-bg-base);
  color: white;
  font-family: var(--font-display);
}

/* Mapbox dark style overrides for our context */
.mapboxgl-ctrl-attrib {
  background: rgba(0, 0, 0, 0.6);
  color: rgba(255, 255, 255, 0.5);
}
```

### Step 3 — Build the three-panel layout shell

`canvas/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Operations Canvas — Agentic S&OP",
  description: "Companion view for the Capacity Orchestrator Agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}
```

`canvas/components/layout/CanvasShell.tsx`:

```tsx
"use client";

import { ReactNode, useState } from "react";

interface CanvasShellProps {
  chat: ReactNode;        // embedded GE chat (or placeholder in static mode)
  canvas: ReactNode;      // the main visualization
  drawer?: ReactNode;     // optional side drawer (Knowledge Catalog entity, etc.)
  drawerOpen?: boolean;
}

export function CanvasShell({ chat, canvas, drawer, drawerOpen = false }: CanvasShellProps) {
  return (
    <div className="grid h-screen" style={{
      gridTemplateColumns: `360px 1fr ${drawerOpen ? "420px" : "0"}`,
      transition: "grid-template-columns 400ms cubic-bezier(0.4, 0, 0.2, 1)",
    }}>
      {/* Left: embedded chat */}
      <aside className="border-r border-white/10 bg-bg-elevated overflow-y-auto">
        {chat}
      </aside>

      {/* Center: canvas */}
      <main className="relative overflow-hidden">
        {canvas}
      </main>

      {/* Right: drawer (collapsible) */}
      <aside className={`border-l border-white/10 bg-bg-elevated overflow-y-auto ${drawerOpen ? "" : "pointer-events-none"}`}>
        {drawerOpen && drawer}
      </aside>
    </div>
  );
}
```

### Step 4 — Build the Mapbox map component

`canvas/components/canvas/GlobalMap.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN!;

interface GlobalMapProps {
  center?: [number, number];   // [lng, lat]
  zoom?: number;
  onMapReady?: (map: mapboxgl.Map) => void;
}

export function GlobalMap({
  center = [15, 5],   // Africa-centered for the cargo-plane scenario
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
      projection: "globe" as any,   // 3D globe for the cargo-plane drama
      attributionControl: false,
    });

    map.on("load", () => {
      // Add fog for the globe effect
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

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className="absolute inset-0" />;
}
```

### Step 5 — Build the AssetMarker component

Asset markers are the most visible thing on the canvas. They need to be big enough to read from the back row and color-coded by state.

`canvas/components/canvas/AssetMarker.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";

export type AssetState = "available" | "in-transit" | "blocked" | "in-repair";

const stateColors: Record<AssetState, string> = {
  "available": "var(--color-asset-available)",
  "in-transit": "var(--color-asset-in-transit)",
  "blocked": "var(--color-asset-blocked)",
  "in-repair": "var(--color-asset-in-repair)",
};

interface AssetMarkerProps {
  state: AssetState;
  label?: string;
  pulse?: boolean;     // for emphasis: capacity gap, hero asset
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "h-3 w-3",
  md: "h-4 w-4",
  lg: "h-6 w-6",
};

export function AssetMarker({ state, label, pulse, size = "md" }: AssetMarkerProps) {
  const color = stateColors[state];

  return (
    <div className="relative flex items-center justify-center">
      {pulse && (
        <motion.div
          className={`absolute rounded-full ${sizeClasses[size]}`}
          style={{ backgroundColor: color, opacity: 0.4 }}
          animate={{ scale: [1, 2.5], opacity: [0.6, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <div
        className={`rounded-full ring-2 ring-white/30 shadow-lg ${sizeClasses[size]}`}
        style={{ backgroundColor: color }}
      />
      {label && (
        <span className="absolute left-full ml-2 whitespace-nowrap text-xs font-medium text-white/90">
          {label}
        </span>
      )}
    </div>
  );
}
```

To attach a React marker to a Mapbox map, use the marker pattern:

```tsx
// In a parent component that owns the map ref
useEffect(() => {
  if (!map) return;

  const container = document.createElement("div");
  ReactDOM.createRoot(container).render(
    <AssetMarker state="blocked" label="Tool X gap" pulse size="lg" />
  );

  const marker = new mapboxgl.Marker(container)
    .setLngLat([13.2894, -8.8390])   // Luanda
    .addTo(map);

  return () => marker.remove();
}, [map]);
```

### Step 6 — Build the LogisticsArc component

Arcs draw between assets to show transport. The "doomed" Australia → Luanda route renders in faint grey. The recommended Lagos → Luanda route renders in pulsing green with directional arrowhead.

`canvas/components/canvas/LogisticsArc.ts`:

```typescript
import mapboxgl from "mapbox-gl";

interface ArcOptions {
  from: [number, number];
  to: [number, number];
  color: string;
  width?: number;
  dashed?: boolean;
  animateDraw?: boolean;
  id: string;
}

/**
 * Add a logistics arc to a Mapbox map.
 * Uses a great-circle GeoJSON line with custom styling.
 */
export function addLogisticsArc(map: mapboxgl.Map, opts: ArcOptions) {
  const greatCircle = generateGreatCircle(opts.from, opts.to, 64);

  map.addSource(opts.id, {
    type: "geojson",
    data: {
      type: "Feature",
      properties: {},
      geometry: { type: "LineString", coordinates: greatCircle },
    },
  });

  map.addLayer({
    id: opts.id,
    type: "line",
    source: opts.id,
    paint: {
      "line-color": opts.color,
      "line-width": opts.width ?? 3,
      "line-dasharray": opts.dashed ? [2, 2] : [1],
      "line-opacity": 0.9,
    },
  });

  if (opts.animateDraw) {
    // Animate from 0 to full length
    animateArcDraw(map, opts.id, 800);
  }
}

export function removeLogisticsArc(map: mapboxgl.Map, id: string) {
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);
}

function generateGreatCircle(
  from: [number, number],
  to: [number, number],
  steps: number,
): [number, number][] {
  // Spherical linear interpolation between two lng/lat points
  // Implementation: convert to 3D cartesian, slerp, convert back
  // ... (use turf.js or implement directly)
  return [];
}

function animateArcDraw(map: mapboxgl.Map, layerId: string, durationMs: number) {
  // Animate the line-dasharray to reveal the arc progressively
  // ... (use Framer Motion's animate function on a synthetic ref)
}
```

This is non-trivial geometry. Two options for the great-circle math:
1. Use `@turf/great-circle` from the Turf.js library
2. Implement spherical lerp directly

For simplicity, use Turf: `npm install @turf/turf`.

### Step 7 — Build the Knowledge Catalog entity drawer

`canvas/components/canvas/KnowledgeCatalogDrawer.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { Database, ArrowRight } from "lucide-react";

interface KCEntityProps {
  canonicalId: string;
  canonicalLabel: string;
  aspects: {
    asset_specification?: Record<string, any>;
    cross_system_aliases?: {
      sap_material_number?: string;
      maximo_equipment_id?: string;
      fdp_config_id?: string;
      intouch_spec_refs?: string[];
    };
    functional_equivalence?: {
      equivalents: Array<{
        equivalent_canonical_id: string;
        confidence: number;
        rationale_source: string;
      }>;
    };
  };
}

// DEMO NARRATION (Beat 5/8 of cargo-plane storyboard):
// "Here's why the agent never got confused. Knowledge Catalog's managed
// remote MCP server returned this canonical entity. SAP calls it MAT-67890,
// Maximo calls it EQ-12345, FDP has its own ID. The agent never sees that
// chaos. One canonical entity, all aliases, equivalence relationships
// with spec citations. This is your Issue 4 — dissolved."
export function KnowledgeCatalogDrawer({ canonicalId, canonicalLabel, aspects }: KCEntityProps) {
  return (
    <motion.div
      initial={{ x: 50, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 50, opacity: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="h-full overflow-y-auto p-6"
    >
      {/* Header */}
      <div className="mb-4 flex items-center gap-2">
        <Database className="h-5 w-5 text-knowledge-catalog" />
        <span className="text-xs uppercase tracking-wider text-knowledge-catalog font-medium">
          Knowledge Catalog
        </span>
      </div>
      <h2 className="text-2xl font-semibold mb-1">{canonicalLabel}</h2>
      <code className="text-xs text-white/50">{canonicalId}</code>

      {/* Cross-system aliases — the Issue 4 dissolve moment */}
      {aspects.cross_system_aliases && (
        <section className="mt-6">
          <h3 className="text-sm font-medium text-white/70 mb-3">Cross-system aliases</h3>
          <dl className="space-y-2">
            {aspects.cross_system_aliases.sap_material_number && (
              <div className="flex justify-between text-sm">
                <dt className="text-white/60">SAP material #</dt>
                <dd className="font-mono">{aspects.cross_system_aliases.sap_material_number}</dd>
              </div>
            )}
            {aspects.cross_system_aliases.maximo_equipment_id && (
              <div className="flex justify-between text-sm">
                <dt className="text-white/60">Maximo equipment</dt>
                <dd className="font-mono">{aspects.cross_system_aliases.maximo_equipment_id}</dd>
              </div>
            )}
            {aspects.cross_system_aliases.fdp_config_id && (
              <div className="flex justify-between text-sm">
                <dt className="text-white/60">FDP config</dt>
                <dd className="font-mono">{aspects.cross_system_aliases.fdp_config_id}</dd>
              </div>
            )}
            {aspects.cross_system_aliases.intouch_spec_refs && aspects.cross_system_aliases.intouch_spec_refs.length > 0 && (
              <div className="text-sm">
                <dt className="text-white/60 mb-1">InTouch specs</dt>
                <dd className="space-y-1">
                  {aspects.cross_system_aliases.intouch_spec_refs.map((ref) => (
                    <div key={ref} className="font-mono text-xs">{ref}</div>
                  ))}
                </dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {/* Functional equivalence */}
      {aspects.functional_equivalence?.equivalents && (
        <section className="mt-6">
          <h3 className="text-sm font-medium text-white/70 mb-3">Functional equivalents</h3>
          {aspects.functional_equivalence.equivalents.map((eq) => (
            <div key={eq.equivalent_canonical_id} className="rounded-lg bg-white/5 p-3 mb-2">
              <div className="flex items-center justify-between">
                <span className="font-medium">{eq.equivalent_canonical_id}</span>
                <span className="text-xs text-white/60">
                  {(eq.confidence * 100).toFixed(0)}% confidence
                </span>
              </div>
              <div className="mt-1 text-xs text-white/50 flex items-center gap-1">
                <ArrowRight className="h-3 w-3" />
                Source: {eq.rationale_source}
              </div>
            </div>
          ))}
        </section>
      )}
    </motion.div>
  );
}
```

### Step 8 — Build the cost roll-up banner

`canvas/components/canvas/CostRollupBanner.tsx`:

```tsx
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { TrendingDown } from "lucide-react";

interface CostRollupProps {
  avoidedCostUsd?: number;
  doomedCostUsd?: number;
  recommendedCostUsd?: number;
  visible: boolean;
}

// DEMO NARRATION (Beat 7/8): "The cost roll-up animates in. $420K cargo plane
// charter avoided. $40K ground transit from Lagos. Net $380K savings on
// this single decision. The customer's CFO can read this from across the
// room."
export function CostRollupBanner({ avoidedCostUsd, doomedCostUsd, recommendedCostUsd, visible }: CostRollupProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -40, opacity: 0 }}
          className="absolute top-6 right-6 rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-6 min-w-[320px]"
        >
          {doomedCostUsd && (
            <div className="text-sm text-cost-avoided mb-2">
              <span className="line-through">
                ${doomedCostUsd.toLocaleString()} cargo charter
              </span>
            </div>
          )}
          {recommendedCostUsd && (
            <div className="text-sm text-white/70 mb-3">
              ${recommendedCostUsd.toLocaleString()} ground transit (Lagos → Luanda)
            </div>
          )}
          {avoidedCostUsd && (
            <div className="flex items-baseline gap-2 mt-2 border-t border-white/10 pt-3">
              <TrendingDown className="h-6 w-6 text-cost-saved" />
              <span className="text-3xl font-bold text-cost-saved tabular-nums">
                ${avoidedCostUsd.toLocaleString()}
              </span>
              <span className="text-sm text-white/60">avoided</span>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

### Step 9 — Build the demo scenario data

For TASK-08, all data is static. WebSocket-driven updates come in TASK-10.

`canvas/data/demoScenarios.ts`:

```typescript
export interface DemoBeat {
  beatNumber: number;
  durationMs: number;
  description: string;
  state: ScenarioState;
}

export interface ScenarioState {
  mapCenter: [number, number];
  mapZoom: number;
  assets: AssetMarkerData[];
  arcs: ArcData[];
  drawer: { open: boolean; entity?: KCEntityData };
  costBanner: { visible: boolean; doomed?: number; recommended?: number; avoided?: number };
  bottomChat?: string;   // optional chat overlay narration
}

// The eight beats of the cargo-plane scenario, as defined in persona3_canvas_storyboard.md
export const cargoPlaneBeats: DemoBeat[] = [
  {
    beatNumber: 0,
    durationMs: 0,
    description: "Initial state — globe with all assets, no arcs",
    state: {
      mapCenter: [15, 5],
      mapZoom: 3,
      assets: ALL_BASELINE_ASSETS,
      arcs: [],
      drawer: { open: false },
      costBanner: { visible: false },
    },
  },
  {
    beatNumber: 1,
    durationMs: 2000,
    description: "Capacity gap appears — Luanda highlighted, pulse animation",
    state: {
      // ... Luanda pulse asset added
    },
  },
  {
    beatNumber: 2,
    durationMs: 3000,
    description: "Parallel system queries — 4 pills appear in chat panel",
    state: {
      // ... bottomChat shows the four queries
    },
  },
  {
    beatNumber: 3,
    durationMs: 2500,
    description: "Doomed arc draws — Australia → Luanda in faint grey, dashed",
    state: {
      arcs: [
        { id: "doomed", from: [149.1, -35.3], to: [13.29, -8.84], color: "#6b7280", dashed: true, animateDraw: true },
      ],
      // cost banner shows the doomed $420K
    },
  },
  {
    beatNumber: 4,
    durationMs: 3000,
    description: "Equivalence pivot — Lagos asset pulses, KC drawer opens",
    state: {
      drawer: { open: true, entity: TOOL_X_KC_ENTITY },
      // Lagos asset now pulses green
    },
  },
  {
    beatNumber: 5,
    durationMs: 4000,
    description: "Knowledge Catalog drawer fully expanded — aliases visible",
    state: {
      drawer: { open: true, entity: TOOL_X_KC_ENTITY },
    },
  },
  {
    beatNumber: 6,
    durationMs: 2500,
    description: "Recommended arc draws — Lagos → Luanda green, animated",
    state: {
      arcs: [
        { id: "doomed", from: [149.1, -35.3], to: [13.29, -8.84], color: "#6b7280", dashed: true, opacity: 0.3 },
        { id: "recommended", from: [3.38, 6.46], to: [13.29, -8.84], color: "#10b981", animateDraw: true },
      ],
    },
  },
  {
    beatNumber: 7,
    durationMs: 2000,
    description: "Cost roll-up — $380K avoided cost animates in",
    state: {
      costBanner: { visible: true, doomed: 420000, recommended: 40000, avoided: 380000 },
    },
  },
  {
    beatNumber: 8,
    durationMs: 2000,
    description: "Approve in Agent Inbox — visible confirmation",
    state: {
      // confirmation overlay
    },
  },
];

const ALL_BASELINE_ASSETS = [/* ... */];
const TOOL_X_KC_ENTITY = {
  canonicalId: "TX-001",
  canonicalLabel: "Tool X",
  aspects: {
    cross_system_aliases: {
      sap_material_number: "MAT-67890",
      maximo_equipment_id: "EQ-12345",
      fdp_config_id: "TX-CONFIG-A",
      intouch_spec_refs: ["spec-3.2-2024", "compatibility-cc-204"],
    },
    functional_equivalence: {
      equivalents: [
        { equivalent_canonical_id: "TX-007", confidence: 0.92, rationale_source: "InTouch Spec §3.2" },
      ],
    },
  },
};
```

### Step 10 — Build the scenario player hook

`canvas/hooks/useScenario.ts`:

```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { DemoBeat, ScenarioState } from "@/data/demoScenarios";

interface UseScenarioOptions {
  beats: DemoBeat[];
  autoPlay?: boolean;
}

export function useScenario({ beats, autoPlay = false }: UseScenarioOptions) {
  const [currentBeat, setCurrentBeat] = useState(0);
  const [isPlaying, setIsPlaying] = useState(autoPlay);

  const advance = useCallback(() => {
    setCurrentBeat((b) => Math.min(b + 1, beats.length - 1));
  }, [beats.length]);

  const back = useCallback(() => {
    setCurrentBeat((b) => Math.max(b - 1, 0));
  }, []);

  const reset = useCallback(() => {
    setCurrentBeat(0);
    setIsPlaying(autoPlay);
  }, [autoPlay]);

  // Keyboard controls for rehearsal mode
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === " ") { e.preventDefault(); advance(); }
      if (e.key === "ArrowLeft" || e.key === "b") back();
      if (e.key === "r") reset();
      if (e.key === "p") setIsPlaying((p) => !p);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [advance, back, reset]);

  // Auto-advance based on beat duration
  useEffect(() => {
    if (!isPlaying || currentBeat >= beats.length - 1) return;
    const t = setTimeout(advance, beats[currentBeat].durationMs);
    return () => clearTimeout(t);
  }, [isPlaying, currentBeat, beats, advance]);

  return {
    state: beats[currentBeat].state,
    currentBeat,
    totalBeats: beats.length,
    isPlaying,
    advance,
    back,
    reset,
    setIsPlaying,
  };
}
```

### Step 11 — Assemble the Global Asset View page

`canvas/app/scenarios/cargo-plane/page.tsx`:

```tsx
"use client";

import { useRef, useState } from "react";
import mapboxgl from "mapbox-gl";

import { CanvasShell } from "@/components/layout/CanvasShell";
import { GlobalMap } from "@/components/canvas/GlobalMap";
import { KnowledgeCatalogDrawer } from "@/components/canvas/KnowledgeCatalogDrawer";
import { CostRollupBanner } from "@/components/canvas/CostRollupBanner";
import { useScenario } from "@/hooks/useScenario";
import { cargoPlaneBeats } from "@/data/demoScenarios";
import { useMapMarkers } from "@/hooks/useMapMarkers";
import { useMapArcs } from "@/hooks/useMapArcs";

// DEMO NARRATION (Beat 0): "This is Maria's Operations Canvas. The map shows
// every Tool X and Tool X variant across her West Africa portfolio.
// Color-coded by status — green available, amber in transit, red blocked,
// blue in repair. The pulsing red ring on Luanda is the active capacity gap."
export default function CargoPlaneScenarioPage() {
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const { state, currentBeat, totalBeats } = useScenario({ beats: cargoPlaneBeats });

  useMapMarkers(mapRef.current, state.assets, mapReady);
  useMapArcs(mapRef.current, state.arcs, mapReady);

  return (
    <CanvasShell
      chat={<ChatPanel beat={currentBeat} totalBeats={totalBeats} />}
      drawer={state.drawer.entity ? <KnowledgeCatalogDrawer {...state.drawer.entity} /> : null}
      drawerOpen={state.drawer.open}
      canvas={
        <>
          <GlobalMap
            center={state.mapCenter}
            zoom={state.mapZoom}
            onMapReady={(m) => { mapRef.current = m; setMapReady(true); }}
          />
          <CostRollupBanner {...state.costBanner} />
          <BeatIndicator current={currentBeat} total={totalBeats} />
        </>
      }
    />
  );
}

function ChatPanel({ beat, totalBeats }: { beat: number; totalBeats: number }) {
  // Static beat-by-beat chat messages for the static demo
  return (
    <div className="p-4">
      <div className="text-xs uppercase tracking-wider text-white/40 mb-2">Maria @ OCC</div>
      <div className="text-sm">
        {/* render the chat narration matching the current beat */}
      </div>
    </div>
  );
}

function BeatIndicator({ current, total }: { current: number; total: number }) {
  return (
    <div className="absolute bottom-6 left-6 flex gap-1">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-1 w-8 rounded-full transition-colors ${i <= current ? "bg-white/80" : "bg-white/20"}`}
        />
      ))}
    </div>
  );
}
```

The `useMapMarkers` and `useMapArcs` hooks manage the lifecycle of markers/arcs on the Mapbox map, syncing with the scenario state.

### Step 12 — Smoke test the full scenario

```bash
cd canvas
npm run dev
# Open http://localhost:3000/scenarios/cargo-plane
```

In Chrome at 1920×1080:
- Press Space to advance through beats
- Verify each beat renders cleanly: assets appear/pulse/change color, arcs draw smoothly, drawer expands/collapses, cost banner animates in
- Verify animations are 60fps (no jank); check DevTools Performance tab
- Verify back row legibility: stand 10 feet from a 27" monitor displaying the canvas. Can you read the cost banner? The marker labels?

### Step 13 — Dockerfile and Cloud Run config

`canvas/Dockerfile`:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

Update `canvas/next.config.ts` for standalone output:

```ts
const nextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_MAPBOX_TOKEN: process.env.NEXT_PUBLIC_MAPBOX_TOKEN,
  },
};
export default nextConfig;
```

Cloud Build:

```yaml
# canvas/cloudbuild.yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "gcr.io/$PROJECT_ID/operations-canvas", "."]
  - name: gcr.io/cloud-builders/docker
    args: ["push", "gcr.io/$PROJECT_ID/operations-canvas"]
  - name: gcr.io/cloud-builders/gcloud
    args:
      - run
      - deploy
      - operations-canvas
      - --image=gcr.io/$PROJECT_ID/operations-canvas
      - --region=us-central1
      - --allow-unauthenticated
      - --set-env-vars=NEXT_PUBLIC_MAPBOX_TOKEN=$_MAPBOX_TOKEN
```

### Step 14 — Commit

```bash
git add canvas/
git commit -m "feat: Operations Canvas scaffold and Global Asset View (TASK-08)"
git push
```

---

## Acceptance criteria

- [ ] Next.js 15 app at `canvas/` with TypeScript 5 strict mode
- [ ] Tailwind 4 configured with the design tokens from the brief
- [ ] shadcn/ui components available (button, card, badge, dialog, tabs)
- [ ] Mapbox GL 3 integrated with dark cartographic style and globe projection
- [ ] Framer Motion handling animations
- [ ] Three-panel layout (chat | canvas | drawer) with smooth drawer expand/collapse
- [ ] Global Asset View at `/scenarios/cargo-plane` rendering all eight beats
- [ ] Asset markers color-coded with pulse animation for the capacity gap
- [ ] Logistics arcs drawing with animated reveal, dashed for doomed routes
- [ ] Knowledge Catalog entity drawer renders Tool X with all aliases visible
- [ ] Cost roll-up banner animates in showing $380K avoided
- [ ] Keyboard controls (Space, ArrowLeft, R, P) work for rehearsal mode
- [ ] All eight beats render cleanly with no layout breaks at 1920×1080
- [ ] Animations run at 60fps in Chrome
- [ ] Dockerfile builds and Cloud Run deployment works
- [ ] Every component with demo significance has a `// DEMO NARRATION:` comment
- [ ] Commit pushed

---

## Common pitfalls

**Mapbox token leaking.** `NEXT_PUBLIC_MAPBOX_TOKEN` is bundled into the client JS. Use a URL-restricted token in Mapbox settings to lock it to your domains. Don't use an unrestricted token in production.

**Globe projection performance.** The 3D globe is more GPU-intensive than the standard mercator projection. On older laptops the animations may stutter. Test on the actual demo machine. If performance is iffy, fall back to mercator (still looks great).

**Marker syncing with React.** Mapbox markers live outside React's render tree. The `useMapMarkers` hook must imperatively add/remove markers when state changes, and clean up old markers on unmount. Forgetting cleanup leads to ghost markers.

**Arc draw animation timing.** The arc draw animation duration must match the beat duration in `cargoPlaneBeats`. If beat 6 is `durationMs: 2500` but the arc draw takes 800ms, the audience watches a static map for 1.7 seconds. Tune both together.

**Knowledge Catalog drawer breaking the layout.** The grid layout uses `420px` for the drawer when open. If the drawer content overflows that width, the canvas compresses. Use `overflow-x: hidden` on the drawer content and ensure all aliases fit.

**Tailwind 4 class generation.** Tailwind 4 uses a different content scanning approach than v3. If markers appear without their colors, check that `tailwind.config.ts` includes `canvas/**/*.{ts,tsx}` in content paths.

**Static export vs. server-side rendering.** Don't use `next export` — Mapbox requires runtime client JS, which static export breaks for SSR pages. Standalone output (`output: "standalone"`) is what we want for Cloud Run.

**Framer Motion + Mapbox conflict.** Mapbox handles its own animation frame loop. If Framer Motion animations stutter when the map is interacting, check that animations don't compete for the main thread. Use `will-change: transform` on Framer-animated elements.

**Beat 5 (KC drawer) lingering too long.** The storyboard gives Beat 5 four seconds. Watch the demo recording: is the drawer content visible long enough to read? If not, extend the beat or split into two beats.

**Demo on a different aspect ratio.** Conference rooms have varied projector aspect ratios. Test at 1920×1080, 1366×768, and 2560×1440. The three-panel grid may need adjustment for very wide ultrawide displays.

---

## References

- Next.js 15 docs: `https://nextjs.org/docs`
- Mapbox GL JS 3: `https://docs.mapbox.com/mapbox-gl-js/api/`
- Mapbox dark style: `mapbox://styles/mapbox/dark-v11`
- Framer Motion: `https://www.framer.com/motion/`
- Tailwind 4: `https://tailwindcss.com/docs`
- shadcn/ui: `https://ui.shadcn.com`
- Turf.js (for great-circle math): `https://turfjs.org`
- Reference Next.js code: `/tmp/next-26-keynotes/devkey/demo-2/frontend/`

---

*When TASK-08 is complete, Maria's cargo-plane scenario renders as a static-but-choreographed visual. The demoer can advance beat by beat with the spacebar and see the full storyboard play out. Next: build the Fleet Utilization View for Tomas (TASK-09), then wire WebSocket-driven live agent events to replace static beats (TASK-10).*
