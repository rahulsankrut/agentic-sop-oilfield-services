/**
 * demoScenarios.ts
 *
 * Static, typed beat data for the Operations Canvas demo scenarios.
 *
 * For TASK-08 / TASK-10 we ship a single hard-coded scenario — the
 * cargo-plane / capacity-gap story for the OCC planner persona (Persona 3).
 * Every beat is the COMPLETE intended canvas state (not a delta); the
 * `useScenario` hook simply hands the current beat's `state` to the
 * downstream renderers.
 *
 * TASK-13: customer-specific strings (location names, asset labels, costs)
 * are now pulled from the active customer skin
 * (`canvas/src/data/skin.generated.ts`). Beat *structure* and choreography
 * stay fixed; only the display content varies per skin.
 *
 * Source of truth for the beat-by-beat choreography:
 *   docs/planning/persona3_canvas_storyboard.md
 *
 * WebSocket-driven live state lands in TASK-10; until then this file is
 * the demo's spine.
 */

import { getActiveSkin, getScenario } from "@/lib/skin";

// ---------------------------------------------------------------------------
// Skin-derived constants. Resolved at module load — the skin is build-time
// bundled so there's no async path here.
// ---------------------------------------------------------------------------

const SKIN = getActiveSkin();
const CARGO_PLANE = getScenario("cargo-plane");
if (!CARGO_PLANE) {
  // Should never fire — the JSON Schema requires every skin to ship a
  // `cargo-plane` scenario block. This guard is just belt-and-suspenders.
  throw new Error(
    `Active skin '${SKIN.meta.customer_slug}' is missing a 'cargo-plane' scenario block`,
  );
}

// Mapbox uses [lng, lat]. Keep that convention everywhere in this file.
// All three points come from the skin's cargo-plane scenario block.
const GAP_LOCATION: [number, number] = [
  CARGO_PLANE.location_focus_lng ?? 0,
  CARGO_PLANE.location_focus_lat ?? 0,
];
const RECOMMENDED_ORIGIN: [number, number] = [
  CARGO_PLANE.recommended_origin_lng ?? 0,
  CARGO_PLANE.recommended_origin_lat ?? 0,
];
const NAIVE_ORIGIN: [number, number] = [
  CARGO_PLANE.naive_origin_lng ?? 0,
  CARGO_PLANE.naive_origin_lat ?? 0,
];

// Short labels for the marker chips — strip the country suffix so e.g.
// "Luanda, Angola" → "Luanda" for the marker title.
function shortLabel(label: string): string {
  return label.split(",")[0].trim();
}

const GAP_SHORT = shortLabel(CARGO_PLANE.location_focus_label);
const RECOMMENDED_SHORT = shortLabel(
  CARGO_PLANE.recommended_origin_label ?? "",
);
const NAIVE_SHORT = shortLabel(CARGO_PLANE.naive_origin_label ?? "");

const ASSET_LABEL = CARGO_PLANE.asset_focus_label;
const EQUIVALENT_LABEL =
  SKIN.taxonomy.hero_asset.equivalent_canonical_label ?? `${ASSET_LABEL}-V7`;
const DEADLINE_PHRASE = CARGO_PLANE.deadline_phrase ?? "by Friday";
const CUSTOMER_ACCOUNT_NAME =
  CARGO_PLANE.customer_account_short ?? CARGO_PLANE.customer_account_name;
const REGULATORY_REPO = SKIN.terminology.regulatory_repository;
const REGULATORY_REF =
  CARGO_PLANE.regulatory_reference ?? `${REGULATORY_REPO} Spec §3.2`;

const NAIVE_COST = CARGO_PLANE.naive_cost_usd ?? 0;
const RECOMMENDED_COST = CARGO_PLANE.recommended_cost_usd ?? 0;
const AVOIDED_COST =
  CARGO_PLANE.avoided_cost_usd ?? NAIVE_COST - RECOMMENDED_COST;

const PERSONA_3 = SKIN.personas.find((p) => p.id === "maria");
const PERSONA_3_NAME = PERSONA_3?.name.split(" ")[0] ?? "Maria";
const OCC_LABEL = SKIN.terminology.occ_short ?? SKIN.terminology.occ_label;

// Camera presets — derived from the gap location with offsets that keep the
// storyboard composition stable across skins (gap at center, secondary
// origins visible at the wide camera).
const GAP_CENTER: [number, number] = GAP_LOCATION;
const WIDE_VIEW: [number, number] = [
  (NAIVE_ORIGIN[0] + GAP_LOCATION[0]) / 2,
  (NAIVE_ORIGIN[1] + GAP_LOCATION[1]) / 2,
];
const CLOSE_VIEW: [number, number] = [
  (RECOMMENDED_ORIGIN[0] + GAP_LOCATION[0]) / 2,
  (RECOMMENDED_ORIGIN[1] + GAP_LOCATION[1]) / 2,
];

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
  /** Buffer-planning view (Persona 2, TASK-09): which buffer option is active. */
  bufferOption?: "conservative" | "balanced" | "aggressive";
  /** Buffer-planning view: optional week label to highlight with a reference line. */
  highlightWeek?: string;
  drawerOpen?: boolean;
}

export interface Beat {
  id: string;
  narration: string;
  state: ScenarioState;
}

// ---------------------------------------------------------------------------
// Knowledge Catalog entity for the hero-asset canonical lookup (Beats 3-7).
// Canonical ID and labels come from the skin's taxonomy block.
// ---------------------------------------------------------------------------

// DEMO NARRATION (Beats 3-5): the hero asset's identifiers are unified across
// SAP, Maximo, FDP, and the regulatory repository (InTouch / WellSite Hub /
// etc.) under one canonical entity. The cross-system alias numbers stay
// fixed across skins — they're synthetic IDs and changing them per skin
// doesn't add demo value.
const HERO_ASSET_KC_ENTITY = {
  canonicalId: SKIN.taxonomy.hero_asset.canonical_id,
  canonicalLabel: SKIN.taxonomy.hero_asset.canonical_label,
  aspects: {
    cross_system_aliases: {
      sap_material_number: "MAT-67890",
      maximo_equipment_id: "EQ-12345",
      fdp_config_id: `${SKIN.taxonomy.hero_asset.canonical_id}-CONFIG-A`,
      intouch_spec_refs: ["spec-3.2-2024", "compatibility-cc-204"],
    },
    functional_equivalence: {
      equivalents: [
        {
          equivalent_canonical_id:
            SKIN.taxonomy.hero_asset.equivalent_canonical_id ?? "EQ-V7",
          equivalent_canonical_label: EQUIVALENT_LABEL,
          confidence: 0.92,
          rationale_source: REGULATORY_REF,
        },
      ],
    },
  },
} as const;

// ---------------------------------------------------------------------------
// Marker presets — each beat composes a subset of these
// ---------------------------------------------------------------------------

// Gap location — the capacity gap. Red pulsing from Beat 1 onward.
const GAP_MARKER: AssetMarkerData = {
  id: "gap-location",
  location: GAP_LOCATION,
  state: "blocked",
  label: `${GAP_SHORT} — ${ASSET_LABEL} needed ${DEADLINE_PHRASE}`,
  pulse: true,
  size: "lg",
};

// Naive origin — yellow in-use, fades to dimmed once the recommended path wins.
const NAIVE_MARKER: AssetMarkerData = {
  id: "naive-origin",
  location: NAIVE_ORIGIN,
  state: "in-transit", // yellow / in-use (closest semantic in our enum)
  label: `${NAIVE_SHORT} — ${ASSET_LABEL} (in-use)`,
  pulse: false,
  size: "md",
};

// Recommended origin — the equivalent variant sitting ready.
const RECOMMENDED_MARKER: AssetMarkerData = {
  id: "recommended-origin",
  location: RECOMMENDED_ORIGIN,
  state: "available",
  label: `${RECOMMENDED_SHORT} — ${EQUIVALENT_LABEL} (ready)`,
  pulse: true,
  size: "lg",
};

const RECOMMENDED_MARKER_SETTLED: AssetMarkerData = {
  ...RECOMMENDED_MARKER,
  pulse: false,
};

// ---------------------------------------------------------------------------
// Arc presets
// ---------------------------------------------------------------------------

// Naive → gap — the doomed cargo charter the agent rejects.
const DOOMED_ARC: LogisticsArcData = {
  id: "doomed-arc",
  from: NAIVE_ORIGIN,
  to: GAP_LOCATION,
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

// Recommended → gap — the local ground transit the agent recommends.
const RECOMMENDED_ARC: LogisticsArcData = {
  id: "recommended-arc",
  from: RECOMMENDED_ORIGIN,
  to: GAP_LOCATION,
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
// Narration helpers — keep the prose stable across skins by templating in
// the customer-specific bits. The text intentionally mirrors the original
// storyboard wording for the default skin.
// ---------------------------------------------------------------------------

function fmtUsd(n: number): string {
  if (n >= 1000) {
    return `$${Math.round(n / 1000)}K`;
  }
  return `$${n}`;
}

function spellOutDollars(n: number): string {
  // The original Beat 6 narration spells out the avoided cost ("Three hundred
  // and eighty thousand dollars"). Keep the same cadence but parameterize the
  // number — fall back to digits when the number doesn't divide cleanly.
  const thousands = Math.round(n / 1000);
  return `${thousands.toLocaleString()} thousand dollars`;
}

// ---------------------------------------------------------------------------
// The eight beats
// ---------------------------------------------------------------------------

// DEMO NARRATION lines are templated from the active skin — for the default
// skin the wording matches persona3_canvas_storyboard.md verbatim. Other
// skins substitute persona name, locations, asset names, customer account,
// regulatory repository, and cost figures while keeping the cadence stable.
export const cargoPlaneBeats: Beat[] = [
  // ---- Beat 0: pre-demo at rest ----
  {
    id: "beat-0-pre-demo",
    narration:
      `This is ${PERSONA_3_NAME}'s Operations Canvas. ${PERSONA_3_NAME}'s our ${OCC_LABEL} planner for ${PERSONA_3?.region ?? "the region"}. The canvas is just a visualization layer — the platform's intelligence is running in Gemini Enterprise Agent Platform in the background.`,
    state: {
      mapCenter: WIDE_VIEW,
      mapZoom: 3,
      assets: [],
      arcs: [],
      drawer: { open: false },
      costBanner: { visible: false },
    },
  },

  // ---- Beat 1: capacity gap detected ----
  {
    id: "beat-1-gap-detected",
    narration:
      `${PERSONA_3_NAME}'s typed the question. The agent's started reasoning — you can see the chain streaming on the left. On the canvas, the gap is now visualized: ${GAP_SHORT}, ${DEADLINE_PHRASE}.`,
    state: {
      mapCenter: GAP_CENTER,
      mapZoom: 4,
      assets: [GAP_MARKER],
      arcs: [],
      drawer: { open: false },
      costBanner: { visible: false },
    },
  },

  // ---- Beat 2: naive plan surfaces — dashed grey ----
  {
    id: "beat-2-naive-plan",
    narration:
      `Here's the naive option — chartering a cargo plane from ${NAIVE_SHORT} to ${GAP_SHORT}. That's a ${spellOutDollars(NAIVE_COST)} decision the agent could've stopped at. A lot of planning tools would have. But this agent has more to check.`,
    state: {
      mapCenter: WIDE_VIEW,
      mapZoom: 2.5,
      assets: [GAP_MARKER, NAIVE_MARKER],
      arcs: [DOOMED_ARC],
      drawer: { open: false },
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
      },
    },
  },

  // ---- Beat 3: Knowledge Catalog lookup begins, drawer opens ----
  {
    id: "beat-3-kc-lookup",
    narration:
      `This is the pivot. The agent reaches into Knowledge Catalog — your unified context graph — and pulls up the canonical ${ASSET_LABEL} entity. Same ${SKIN.terminology.fleet_unit_singular}, different identifiers in SAP, Maximo, FDP, and ${REGULATORY_REPO}, all unified.`,
    state: {
      mapCenter: WIDE_VIEW,
      mapZoom: 2.5,
      assets: [GAP_MARKER, NAIVE_MARKER],
      arcs: [DOOMED_ARC],
      drawer: { open: true, entity: { ...HERO_ASSET_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
      },
    },
  },

  // ---- Beat 4: equivalent asset found — recommended origin pulses green ----
  {
    id: "beat-4-equivalent-found",
    narration:
      `And the agent finds a functionally equivalent sub-variant — ${EQUIVALENT_LABEL} — in a ${RECOMMENDED_SHORT} repair shop, close to the ${GAP_SHORT} site. Per a spec from your own ${REGULATORY_REPO} repository.`,
    state: {
      mapCenter: CLOSE_VIEW,
      mapZoom: 4.5,
      assets: [GAP_MARKER, NAIVE_MARKER, RECOMMENDED_MARKER],
      arcs: [DOOMED_ARC_FADED],
      drawer: { open: true, entity: { ...HERO_ASSET_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
      },
    },
  },

  // ---- Beat 5: sourcing logistics decision — recommended green arc ----
  {
    id: "beat-5-sourcing-decision",
    narration:
      `FDP confirms ${CUSTOMER_ACCOUNT_NAME}'s config accepts the variant. SAP confirms workforce is available for ${RECOMMENDED_SHORT} dispatch. Ground transit — four hours plus four hours of certification.`,
    state: {
      mapCenter: CLOSE_VIEW,
      mapZoom: 4.5,
      assets: [GAP_MARKER, NAIVE_MARKER, RECOMMENDED_MARKER],
      arcs: [DOOMED_ARC_FADED, RECOMMENDED_ARC],
      drawer: { open: true, entity: { ...HERO_ASSET_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
        recommended: RECOMMENDED_COST,
      },
    },
  },

  // ---- Beat 6: cost rollup completes — avoided cost surfaces ----
  // Avoided is supplied by the skin (NAIVE - RECOMMENDED for default).
  {
    id: "beat-6-cost-rollup",
    narration:
      `${spellOutDollars(AVOIDED_COST).charAt(0).toUpperCase()}${spellOutDollars(AVOIDED_COST).slice(1)}. That's the difference between the naive option and what the agent surfaced. And it surfaced the reasoning, the customer compatibility, the workforce confirmation, the risk score, and a procurement approval — all in under two minutes.`,
    state: {
      mapCenter: CLOSE_VIEW,
      mapZoom: 4.5,
      assets: [GAP_MARKER, NAIVE_MARKER, RECOMMENDED_MARKER],
      arcs: [DOOMED_ARC_FADED, RECOMMENDED_ARC],
      drawer: { open: true, entity: { ...HERO_ASSET_KC_ENTITY } },
      drawerOpen: true,
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
        recommended: RECOMMENDED_COST,
        avoided: AVOIDED_COST,
      },
    },
  },

  // ---- Beat 7: final SourcingPlan — assets/arcs settle, drawer collapses ----
  {
    id: "beat-7-final-plan",
    narration:
      `${PERSONA_3_NAME} approves it from the Agent Inbox and it's done. ${RECOMMENDED_SHORT} to ${GAP_SHORT}, ground transit, ${fmtUsd(AVOIDED_COST)} avoided, full audit trail attached.`,
    state: {
      mapCenter: CLOSE_VIEW,
      mapZoom: 4.5,
      assets: [GAP_MARKER, RECOMMENDED_MARKER_SETTLED],
      arcs: [RECOMMENDED_ARC_SETTLED],
      drawer: { open: false },
      drawerOpen: false,
      costBanner: {
        visible: true,
        doomed: NAIVE_COST,
        recommended: RECOMMENDED_COST,
        avoided: AVOIDED_COST,
      },
    },
  },
];
