/**
 * deepResearch.ts
 *
 * Beat-by-beat storyboard for Persona 4 (Priya, EVP) — the deep-research
 * notebook scenario. Priya asks a strategic, cross-domain question about
 * Permian utilization and the Deep Research Agent grounds the answer in a
 * mix of public (BLS, Baker Hughes, EIA) and internal (SAP MARC, ZHR
 * workforce) sources.
 *
 * Why a brand-new state shape (instead of reusing ``ScenarioState`` from
 * ``demoScenarios.ts``)? Priya's canvas is a research notebook, not a map
 * — there are no asset markers, arcs, or cost banners to template. The
 * cargo-plane shape was tuned for spatial planning. A purpose-built
 * ``DeepResearchState`` keeps the page free of unused fields and avoids
 * forcing the shared scenario type to grow new optional columns for every
 * persona.
 *
 * Target wall-clock: 2 minutes (4 beats × ~30s each).
 */

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/**
 * A single grounded citation chip. ``href`` is informational only — the
 * v1 chips are no-op (no click handler). Including the URL keeps the
 * data file honest about provenance for the demoer.
 */
export interface Citation {
  /** Stable id for React keys + future click handlers. */
  id: string;
  /** Short label on the chip itself, e.g. "BLS QCEW 2024". */
  label: string;
  /** Subtitle / context line, e.g. "NAICS 211 · Permian employment". */
  source: string;
  /** Whether this is a public or internal source — controls chip color. */
  kind: "public" | "internal";
  /** Optional URL (not wired in v1). */
  href?: string;
}

export interface Recommendation {
  title: string;
  body: string;
}

export interface DeepResearchState {
  /** Priya's question (always present, but only rendered from Beat 0). */
  question: string;
  /** Citations gathered so far (empty in Beat 0, three in Beats 1+). */
  citations: Citation[];
  /** Markdown-style synthesis body. Empty string in Beats 0/1. */
  synthesisMarkdown: string;
  /** Blue "Recommended action" card. Null until Beat 3. */
  recommendation: Recommendation | null;
  /** Toast that fires after Beat 4. Null until then. */
  saveToast: string | null;
}

export interface Beat {
  id: string;
  /** Demoer narration cue (mirrored from the chat panel). */
  narration: string;
  state: DeepResearchState;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const QUESTION =
  "Why did our Permian utilization underperform last quarter? Compare to public Baker Hughes data.";

const CITATIONS: Citation[] = [
  {
    id: "bls-qcew",
    label: "BLS QCEW 2024",
    source: "NAICS 211 · Permian employment",
    kind: "public",
    href: "https://www.bls.gov/cew/",
  },
  {
    id: "baker-hughes",
    label: "Baker Hughes weekly rig count",
    source: "Permian basin · Q3 2026",
    kind: "public",
    href: "https://rigcount.bakerhughes.com/",
  },
  {
    id: "sap-marc",
    label: "SAP MARC + ZHR_WORKFORCE",
    source: "Our Permian fleet · internal",
    kind: "internal",
  },
];

const SYNTHESIS = `**Permian utilization underperformed by ~9 pts vs. the Q3 baseline.** Three contributing factors stand out:

1. **Demand softened.** Baker Hughes Permian rig count fell from 311 to 290 (-7%) over the quarter, reducing service demand across the basin.
2. **Crew availability stayed flat.** BLS QCEW data shows industry-wide oilfield-services employment up 2% year-over-year, but our own basin headcount held at 42 crews — we did not flex with the market.
3. **Leading indicator missed.** The EIA STEO completion-lag indicator shows oil productivity per rig declining 3% — we had this signal in the data but did not act on it.`;

const RECOMMENDATION: Recommendation = {
  title: "Recommended action",
  body: "Cut Permian crew rotation cadence by 1 week to absorb the demand drop. Reallocate 2 crews to Eagle Ford, where rig count is up 5% quarter-over-quarter.",
};

const SAVE_TOAST =
  "Insight saved to Priya's research notebook. Follow-up scheduled in 2 weeks: re-evaluate vs. Q1 actuals.";

// ---------------------------------------------------------------------------
// The five beats (0 through 4)
// ---------------------------------------------------------------------------

function emptyState(): DeepResearchState {
  return {
    question: QUESTION,
    citations: [],
    synthesisMarkdown: "",
    recommendation: null,
    saveToast: null,
  };
}

export const deepResearchBeats: Beat[] = [
  // ---- Beat 0: question posed, notebook empty ----
  {
    id: "beat-0-question",
    narration:
      "Priya is the EVP. She asks the kind of cross-domain question that used to take a research analyst two weeks. The notebook is empty — the agent is starting to reason.",
    state: emptyState(),
  },

  // ---- Beat 1: citations gathered ----
  {
    id: "beat-1-sources-gathered",
    narration:
      "The Deep Research Agent pulls three sources in parallel — two public (BLS QCEW, Baker Hughes), one internal (SAP MARC plus our ZHR workforce table). Every chip is groundable; nothing here is hallucinated.",
    state: {
      ...emptyState(),
      citations: CITATIONS,
    },
  },

  // ---- Beat 2: synthesis populates ----
  {
    id: "beat-2-synthesis",
    narration:
      "Synthesis populates inline. Three contributing factors — demand softened, crew availability stayed flat, and a leading indicator from EIA STEO we had but did not act on. Each claim is anchored to a citation above.",
    state: {
      ...emptyState(),
      citations: CITATIONS,
      synthesisMarkdown: SYNTHESIS,
    },
  },

  // ---- Beat 3: recommendation card ----
  {
    id: "beat-3-recommendation",
    narration:
      "And the recommended action — cut Permian crew rotation cadence by one week and reallocate two crews to Eagle Ford. That is the strategic next move, surfaced with the reasoning intact.",
    state: {
      ...emptyState(),
      citations: CITATIONS,
      synthesisMarkdown: SYNTHESIS,
      recommendation: RECOMMENDATION,
    },
  },

  // ---- Beat 4: insight saved + follow-up scheduled ----
  {
    id: "beat-4-saved",
    narration:
      "Priya saves it to her research notebook. The follow-up — re-evaluate in two weeks against Q1 actuals — is scheduled automatically. The whole investigation took two minutes.",
    state: {
      ...emptyState(),
      citations: CITATIONS,
      synthesisMarkdown: SYNTHESIS,
      recommendation: RECOMMENDATION,
      saveToast: SAVE_TOAST,
    },
  },
];
