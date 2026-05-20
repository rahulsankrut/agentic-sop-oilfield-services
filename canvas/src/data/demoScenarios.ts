/**
 * demoScenarios.ts
 *
 * Static, typed beat data for the Operations Canvas demo scenarios.
 *
 * For TASK-08 / TASK-10 we ship a single hard-coded scenario — the
 * cargo-plane / capacity-gap story for Maria (Persona 3, West Africa OCC).
 * Every beat is the COMPLETE intended canvas state (not a delta); the
 * `useScenario` hook simply hands the current beat's `state` to the
 * downstream renderers.
 *
 * Source of truth for the beat-by-beat choreography:
 *   docs/planning/persona3_canvas_storyboard.md
 *
 * WebSocket-driven live state lands in TASK-10; until then this file is
 * the demo's spine.
 */

// ---------------------------------------------------------------------------
// Map / geographic constants (locked at storyboard authoring time)
// ---------------------------------------------------------------------------

// Mapbox uses [lng, lat]. Keep that convention everywhere in this file.
const LUANDA: [number, number] = [13.2343, -8.8383];
const LAGOS: [number, number] = [3.3792, 6.5244];
const DARWIN: [number, number] = [130.8456, -12.4634];

// Africa-centered camera for the at-rest opening and the Lagos-Luanda close.
const AFRICA_CENTER: [number, number] = [15, 5];
const AFRICA_WIDE: [number, number] = [40, -5]; // pulled back to include Australia
const WEST_AFRICA_CLOSE: [number, number] = [8, -1];

// ---------------------------------------------------------------------------
// Public types (exported for consumers: useScenario, page, components)
// ---------------------------------------------------------------------------

export interface AssetMarkerData {
  id: string;
  location: [number, number]; // [lng, lat]
  state: "available" | "in-transit" | "blocked" | "in-repair";
  label: string;
  pulse?: boolean;
  size?: "sm" | "md" | "lg";
}

export interface LogisticsArcData {
  id: string;
  from: [number, number];
  to: [number, number];
  color: string;
  dashed?: boolean;
  animateDraw?: boolean;
  opacity?: number;
}

export interface DrawerState {
  open: boolean;
  entity?: {
    canonicalId: string;
    canonicalLabel: string;
    aspects: Record<string, unknown>;
  };
}

export interface CostBannerState {
  visible: boolean;
  doomed?: number;
  recommended?: number;
  avoided?: number;
}

export interface ScenarioState {
  mapCenter: [number, number];
  mapZoom: number;
  assets: AssetMarkerData[];
  arcs: LogisticsArcData[];
  drawer: DrawerState;
  costBanner: CostBannerState;
  activeMcpCalls?: Array<{ server: string; tool: string; startedAt: string }>;
  showTimeline?: boolean;
  timeline?: unknown[];
  bufferOption?: "conservative" | "balanced" | "aggressive";
  drawerOpen?: boolean;
}

export interface Beat {
  id: string;
  narration: string;
  state: ScenarioState;
}

// ---------------------------------------------------------------------------
// Knowledge Catalog entity for the Tool X canonical lookup (Beats 3-7)
// ---------------------------------------------------------------------------

// DEMO NARRATION (Beats 3-5): "Same Tool X has different identifiers in SAP,
// Maximo, FDP, and InTouch, all unified under one canonical entity. The
// agent reasons against this — not against any individual system's naming
// convention. That's Issue 4, dissolved structurally."
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
        {
          equivalent_canonical_id: "TX-007",
          equivalent_canonical_label: "Tool X-V7",
          confidence: 0.92,
          rationale_source: "InTouch Spec §3.2",
        },
      ],
    },
  },
} as const;

// ---------------------------------------------------------------------------
// Marker presets — each beat composes a subset of these
// ---------------------------------------------------------------------------

// Luanda — the capacity gap. Red pulsing from Beat 1 onward.
const LUANDA_GAP: AssetMarkerData = {
  id: "luanda-gap",
  location: LUANDA,
  state: "blocked",
  label: "Luanda — Tool X needed by Friday",
  pulse: true,
  size: "lg",
};

// Darwin — the naive source. Yellow in-use, fades to dimmed once Lagos wins.
const DARWIN_NAIVE: AssetMarkerData = {
  id: "darwin-naive",
  location: DARWIN,
  state: "in-transit", // yellow / in-use (closest semantic in our enum)
  label: "Darwin — Tool X (in-use)",
  pulse: false,
  size: "md",
};

// Lagos — the equivalent Tool X-V7 sitting in a repair shop, ready.
const LAGOS_EQUIVALENT: AssetMarkerData = {
  id: "lagos-equivalent",
  location: LAGOS,
  state: "available",
  label: "Lagos — Tool X-V7 (ready)",
  pulse: true,
  size: "lg",
};

const LAGOS_EQUIVALENT_SETTLED: AssetMarkerData = {
  ...LAGOS_EQUIVALENT,
  pulse: false,
};

// ---------------------------------------------------------------------------
// Arc presets
// ---------------------------------------------------------------------------

// Darwin → Luanda — the naive $420K cargo charter the agent rejects.
const DOOMED_ARC: LogisticsArcData = {
  id: "doomed-darwin-luanda",
  from: DARWIN,
  to: LUANDA,
  color: "#6b7280", // slate-500, dimmed
  dashed: true,
  animateDraw: true,
  opacity: 0.7,
};

const DOOMED_ARC_FADED: LogisticsArcData = {
  ...DOOMED_ARC,
  animateDraw: false,
  opacity: 0.2,
};

// Lagos → Luanda — the $40K local ground transit the agent recommends.
const RECOMMENDED_ARC: LogisticsArcData = {
  id: "recommended-lagos-luanda",
  from: LAGOS,
  to: LUANDA,
  color: "#10b981", // emerald-500
  dashed: false,
  animateDraw: true,
  opacity: 1,
};

const RECOMMENDED_ARC_SETTLED: LogisticsArcData = {
  ...RECOMMENDED_ARC,
  animateDraw: false,
};

// ---------------------------------------------------------------------------
// The eight beats
// ---------------------------------------------------------------------------

// DEMO NARRATION lines are pulled verbatim (or near-verbatim) from
// persona3_canvas_storyboard.md so the demoer can read straight off them.
export const cargoPlaneBeats: Beat[] = [
  // ---- Beat 0: pre-demo at rest ----
  {
    id: "beat-0-pre-demo",
    narration:
      "This is Maria's Operations Canvas. She's our OCC planner for West Africa. The canvas is just a visualization layer — the platform's intelligence is running in Gemini Enterprise Agent Platform in the background.",
    state: {
      mapCenter: AFRICA_CENTER,
      mapZoom: 3,
      assets: [],
      arcs: [],
      drawer: { open: false },
      costBanner: { visible: false },
    },
  },

  // ---- Beat 1: capacity gap detected at Luanda ----
  {
    id: "beat-1-gap-detected",
    narration:
      "Maria's typed her question. The agent's started reasoning — you can see the chain streaming on the left. On the canvas, the gap is now visualized: Luanda, with a Friday deadline.",
    state: {
      mapCenter: LUANDA,
      mapZoom: 4,
      assets: [LUANDA_GAP],
      arcs: [],
      drawer: { open: false },
      costBanner: { visible: false },
    },
  },

  // ---- Beat 2: naive plan surfaces — Darwin → Luanda dashed grey ----
  {
    id: "beat-2-naive-plan",
    narration:
      "Here's the naive option — chartering a cargo plane from Darwin to Luanda. That's a 420 thousand dollar decision the agent could've stopped at. A lot of planning tools would have. But this agent has more to check.",
    state: {
      mapCenter: AFRICA_WIDE,
      mapZoom: 2.5,
      assets: [LUANDA_GAP, DARWIN_NAIVE],
      arcs: [DOOMED_ARC],
      drawer: { open: false },
      costBanner: {
        visible: true,
        doomed: 420000,
      },
    },
  },

  // ---- Beat 3: Knowledge Catalog lookup begins, drawer opens with Tool X ----
  {
    id: "beat-3-kc-lookup",
    narration:
      "This is the pivot. The agent reaches into Knowledge Catalog — your unified context graph — and pulls up the canonical Tool X entity. Same tool, different identifiers in SAP, Maximo, FDP, and InTouch, all unified.",
    state: {
      mapCenter: AFRICA_WIDE,
      mapZoom: 2.5,
      assets: [LUANDA_GAP, DARWIN_NAIVE],
      arcs: [DOOMED_ARC],
      drawer: { open: true, entity: { ...TOOL_X_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: 420000,
      },
    },
  },

  // ---- Beat 4: equivalent asset found — Lagos pulses green ----
  {
    id: "beat-4-equivalent-found",
    narration:
      "And the agent finds a functionally equivalent sub-variant — Tool X-V7 — in a Lagos repair shop, 50 kilometers from the Luanda site. Per a spec from your own InTouch repository.",
    state: {
      mapCenter: WEST_AFRICA_CLOSE,
      mapZoom: 4.5,
      assets: [LUANDA_GAP, DARWIN_NAIVE, LAGOS_EQUIVALENT],
      arcs: [DOOMED_ARC_FADED],
      drawer: { open: true, entity: { ...TOOL_X_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: 420000,
      },
    },
  },

  // ---- Beat 5: sourcing logistics decision — Lagos → Luanda green arc ----
  {
    id: "beat-5-sourcing-decision",
    narration:
      "FDP confirms Gulf Petroleum's config accepts V7. SAP confirms workforce is available for Lagos dispatch. Ground transit — four hours plus four hours of certification.",
    state: {
      mapCenter: WEST_AFRICA_CLOSE,
      mapZoom: 4.5,
      assets: [LUANDA_GAP, DARWIN_NAIVE, LAGOS_EQUIVALENT],
      arcs: [DOOMED_ARC_FADED, RECOMMENDED_ARC],
      drawer: { open: true, entity: { ...TOOL_X_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: 420000,
        recommended: 40000,
      },
    },
  },

  // ---- Beat 6: cost rollup completes — $380K avoided ----
  // NOTE: storyboard locks the savings at $380K ($420K doomed - $40K recommended),
  // not $474K. We follow the storyboard's number.
  {
    id: "beat-6-cost-rollup",
    narration:
      "Three hundred and eighty thousand dollars. That's the difference between the naive option and what the agent surfaced. And it surfaced the reasoning, the customer compatibility, the workforce confirmation, the risk score, and a procurement approval — all in under two minutes.",
    state: {
      mapCenter: WEST_AFRICA_CLOSE,
      mapZoom: 4.5,
      assets: [LUANDA_GAP, DARWIN_NAIVE, LAGOS_EQUIVALENT],
      arcs: [DOOMED_ARC_FADED, RECOMMENDED_ARC],
      drawer: { open: true, entity: { ...TOOL_X_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: 420000,
        recommended: 40000,
        avoided: 380000,
      },
    },
  },

  // ---- Beat 7: final SourcingPlan — assets/arcs settle, drawer collapses ----
  {
    id: "beat-7-final-plan",
    narration:
      "Maria approves it from her Agent Inbox and it's done. Lagos to Luanda, ground transit, $380K avoided, full audit trail attached.",
    state: {
      mapCenter: WEST_AFRICA_CLOSE,
      mapZoom: 4.5,
      assets: [LUANDA_GAP, LAGOS_EQUIVALENT_SETTLED],
      arcs: [RECOMMENDED_ARC_SETTLED],
      drawer: { open: false },
      drawerOpen: false,
      costBanner: {
        visible: true,
        doomed: 420000,
        recommended: 40000,
        avoided: 380000,
      },
    },
  },
];
