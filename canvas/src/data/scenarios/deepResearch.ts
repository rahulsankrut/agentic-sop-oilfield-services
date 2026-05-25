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
 * A single grounded citation chip. Clicking a chip opens
 * ``CitationDrawer`` with the source's detail panel — so an exec can drill
 * from the synthesis back into the underlying record.
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
  /** Optional URL — opened in a new tab from the drawer's "View source" link. */
  href?: string;
  /**
   * Structured source detail rendered inside the drawer when the chip is
   * clicked. The shape is intentionally loose (free-form key/value pairs
   * plus an optional summary paragraph) so each source can surface what's
   * specific to it — BLS shows NAICS code + employment numbers, Baker
   * Hughes shows the rig-count series, SAP MARC shows the per-plant fields
   * the synthesis actually pulled.
   */
  detail?: CitationDetail;
}

export interface CitationDetail {
  /** 1-2 sentence framing of what this source is and why it matters here. */
  summary: string;
  /** Key/value pairs the drawer renders as a definition list. */
  facts: Array<{ key: string; value: string }>;
  /** Optional raw excerpt (e.g. a row from a BQ extract). Rendered as preformatted text. */
  excerpt?: string;
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
    detail: {
      summary:
        "Quarterly Census of Employment and Wages — the authoritative US oil-and-gas-extraction employment series. The synthesis pulls the Permian-county-FIPS-aggregated workforce trend.",
      facts: [
        { key: "NAICS code", value: "211 (Oil and Gas Extraction)" },
        { key: "Geography", value: "Permian counties (TX + NM)" },
        { key: "Series", value: "Total employees, all establishments" },
        { key: "Q3 2026 vs Q3 2025", value: "+2.1% YoY" },
        { key: "Latest update", value: "Q3 2026 release" },
      ],
      excerpt:
        "naics_211_state_employment: 9,840 (TX Permian counties, Q3 2026 avg)\nyoy_change_pct: +2.1",
    },
  },
  {
    id: "baker-hughes",
    label: "Baker Hughes weekly rig count",
    source: "Permian basin · Q3 2026",
    kind: "public",
    href: "https://rigcount.bakerhughes.com/",
    detail: {
      summary:
        "Weekly North America rig count by basin. The single most-followed leading indicator for US shale activity. We pull the Permian sub-series for the quarter.",
      facts: [
        { key: "Series", value: "US oil rigs · Permian basin · weekly" },
        { key: "Q3 start", value: "311 active rigs (week of 2026-07-04)" },
        { key: "Q3 end", value: "290 active rigs (week of 2026-09-26)" },
        { key: "Quarter delta", value: "−21 rigs (−6.8%)" },
        { key: "Trailing 4 weeks", value: "Flat at ~290" },
      ],
      excerpt:
        "permian_active_rigs:\n  w27=311  w28=310  w29=307  w30=302\n  w35=298  w36=295  w37=293\n  w40=290  w41=290  w42=290",
    },
  },
  {
    id: "sap-marc",
    label: "SAP MARC + ZHR_WORKFORCE",
    source: "Our Permian fleet · internal",
    kind: "internal",
    detail: {
      summary:
        "Internal SAP material-and-plant-master plus the ZHR_WORKFORCE Z-table snapshot. Combined to answer 'how many crews did we have available, and against what fleet?' for the Permian.",
      facts: [
        { key: "MARC plant", value: "WERKS=PER1 (Midland)" },
        { key: "Fleet size", value: "42 crew slots (Q3 stable)" },
        { key: "ZHR snapshot date", value: "2026-09-30" },
        { key: "Specialists available", value: "11" },
        { key: "On-call pool", value: "6" },
        { key: "Utilization (Q3)", value: "68% (vs 77% Q2)" },
      ],
      excerpt:
        "ZHR_WORKFORCE row:\n  basin=permian\n  crew_count_available=42\n  specialist_count_available=11\n  on_call_count=6\n  snapshot_date=2026-09-30",
    },
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
