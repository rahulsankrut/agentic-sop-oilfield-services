# TASK-16: Persona 4 (Priya) — Deep Research Agent scenario

**Prerequisites:** TASK-06 complete (Knowledge Catalog populated), TASK-07 complete (Memory Profiles incl. Priya), TASK-12 complete (demo runner with Priya's launcher tile). Ideally TASK-10 (WebSocket) for live event rendering, though this scenario can run without it.

**Estimated effort:** 2-3 days for one engineer.

**Stream:** Both (light backend configuration + a briefing render view)

---

## Context

Priya Krishnan is the Operations VP, Global. Her scenario is different in kind from Maria's and Tomas's. They're operators acting on specific decisions; Priya is an executive asking a synthesis question that spans the entire portfolio. She doesn't want to drive a workflow — she wants a grounded answer to *"what's my West African deepwater exposure right now, and what should I be worried about?"*

This is the **Deep Research Agent** scenario. Deep Research Agent is a real Gemini Enterprise feature, used as-is — we do not build it. It autonomously plans a multi-step research process, queries multiple sources (Knowledge Catalog, the synthetic fleet/customer data, BigQuery forecasts), and produces a citation-grounded briefing. Our job is to wire the data sources, frame the scenario, and render the briefing in a way that reads like an executive document rather than a chat log.

The platform-narration win: this persona shows that the same data foundation powering the operational agents (Knowledge Catalog, the canonical asset model, the enterprise system connections) also powers executive synthesis — without anyone building a custom "executive dashboard." Priya asks a question in natural language; the Deep Research Agent does the rest; every claim in the answer cites its source. The demoer's line: *"We didn't build Priya a dashboard. We pointed the platform's Deep Research Agent at the same grounded data the operational agents use. She asks; it researches; every number is traceable."*

This is a **lighter build than Maria's** because the heavy lifting is a platform feature. The task is configuration plus a presentation layer, not a custom multi-agent workflow.

---

## Inputs

- TASK-06 complete (Knowledge Catalog with canonical assets, cross-system aliases, functional equivalence)
- TASK-07 complete (Priya's Memory Profile: Operations VP, Global region, executive KPIs)
- Synthetic data: fleet status, customer commitments, forecasts (from TASK-03)
- Deep Research Agent docs: `https://docs.cloud.google.com/gemini-enterprise/docs/deep-research` (verify exact URL)
- Canvas scaffold from TASK-08 (design tokens, shell, demo runner integration)

---

## Deliverables

When this task is complete:

1. **Deep Research Agent configured** with access to the right grounded sources: Knowledge Catalog (via managed MCP), the synthetic fleet/customer data, BigQuery forecasts
2. **Scenario framing** — Priya's question and the expected research plan, with deterministic seeding so the demo reproduces
3. **Briefing render view** at `/scenarios/deep-research` — an executive-document presentation of the Deep Research output, with inline citations that link back to sources
4. **Citation drill-down** — clicking a citation opens the underlying source (a Knowledge Catalog entry, a data record, a forecast)
5. **Beat-by-beat choreography** for Priya's ~2-minute segment (4-5 beats: question posed → research plan shown → sources queried → briefing assembled → citations explored)
6. **Demo runner integration** — Priya's launcher tile (already exists in TASK-12) routes here and pre-warms her session
7. **Static + replay modes** consistent with the other scenarios

---

## Step-by-step instructions

### Step 1 — Understand Deep Research Agent as a platform feature

Deep Research Agent is part of Gemini Enterprise. It is not something we build. It:
- Takes a natural-language research question
- Autonomously plans a multi-step research process
- Queries available grounded sources (data stores, connectors, web if enabled)
- Synthesizes a structured, citation-grounded report

Our integration is: make the right sources available to it, frame the scenario, and present its output well. Read the Deep Research Agent docs before proceeding to understand the configuration surface — specifically how to scope its sources to our Knowledge Catalog + synthetic data, and how to disable web grounding (we want it grounded only in the customer's own data for this scenario).

### Step 2 — Configure the grounded sources

Deep Research Agent should research against:
1. **Knowledge Catalog** — the canonical asset model (via the managed MCP, already available from TASK-06)
2. **Synthetic operational data** — fleet status, customer commitments, on-time-start history. Expose this as a data store or via the existing MCP servers
3. **BigQuery forecasts** — the probabilistic demand forecasts (the same data Tomas's Capacity Planning Agent uses)

`src/deep_research/sources_config.py`:

```python
"""Configure the grounded sources for Priya's Deep Research scenario.

Deep Research Agent is a platform feature; this module declares which
data sources it should research against for the executive-exposure question.
"""

from src.skin.skin_loader import get_active_skin


def get_deep_research_sources() -> dict:
    """Return the source configuration for the Deep Research Agent.

    Scoped to the customer's own grounded data. Web grounding disabled —
    this is an internal exposure analysis, not a market research task.
    """
    skin = get_active_skin()
    return {
        "grounding_sources": [
            {
                "type": "knowledge_catalog",
                "scope": "oilfield-canonical-assets",
                "description": "Canonical asset model with cross-system aliases and functional equivalence",
            },
            {
                "type": "data_store",
                "name": "operational-status",
                "description": "Fleet status, customer commitments, on-time-start history",
            },
            {
                "type": "bigquery",
                "dataset": "demand_forecasts",
                "description": "12-week probabilistic demand forecasts per equipment class and region",
            },
        ],
        "web_grounding": False,   # internal exposure analysis only
        "citation_required": True,
        "region_focus": skin.personas_by_id["priya"].region,
    }
```

### Step 3 — Frame the scenario and seed deterministically

Priya's question is fixed for the demo so the research plan and output reproduce.

`src/deep_research/scenario.py`:

```python
"""Priya's Deep Research scenario — executive exposure analysis."""

from src.skin.skin_loader import get_active_skin


def get_priya_research_question() -> str:
    """The executive question Priya poses. Customer-skin-aware."""
    skin = get_active_skin()
    region = "West African deepwater"   # default skin; skin can override
    return (
        f"What is our {region} exposure across the portfolio right now? "
        f"Summarize active customer commitments, the assets committed to them, "
        f"forecast demand over the next 12 weeks, and flag the top three operational "
        f"risks to those commitments. Cite sources for every figure."
    )


# DEMO NARRATION (Beat 1): "Priya doesn't drive a workflow. She asks a question
# the way she'd ask a chief of staff. Watch the Deep Research Agent plan its
# research — it's going to decompose this into sub-questions, query Knowledge
# Catalog, the operational data, and the forecasts, then synthesize. Every
# number it returns will cite where it came from."
EXPECTED_RESEARCH_PLAN = [
    "Identify active customer commitments in the target region",
    "Map committed assets via Knowledge Catalog canonical model",
    "Pull 12-week demand forecast for those asset classes",
    "Cross-reference fleet availability against commitments",
    "Identify gaps, late-start risks, and single-points-of-failure",
    "Synthesize into executive briefing with citations",
]
```

### Step 4 — Build the briefing render view

The output should read like an executive briefing, not a chat transcript. Structured sections, clear figures, inline citations.

`canvas/components/canvas/ExecutiveBriefing.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { FileText, AlertTriangle, TrendingUp } from "lucide-react";

interface Citation {
  id: string;
  source_type: "knowledge_catalog" | "operational_data" | "forecast";
  source_label: string;
  source_ref: string;   // link/id to drill into
}

interface BriefingSection {
  heading: string;
  body: string;
  figures?: Array<{ label: string; value: string; citationId: string }>;
  citations: Citation[];
}

interface ExecutiveBriefingProps {
  title: string;
  generatedAt: string;
  sections: BriefingSection[];
  risks: Array<{ severity: "high" | "medium" | "low"; description: string; citationId: string }>;
  onCitationClick: (citation: Citation) => void;
}

// DEMO NARRATION (Beat 4): "Here's the briefing. Notice it's not a wall of
// text — it's structured the way an exec would want it. Active commitments,
// committed assets, forecast, risks. And every figure is a citation. Priya
// clicks the $42M number — it drills straight into the source records.
// This is grounded synthesis, not a chatbot guessing."
export function ExecutiveBriefing({ title, generatedAt, sections, risks, onCitationClick }: ExecutiveBriefingProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-3xl p-8 space-y-8 overflow-y-auto"
    >
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-white/10 pb-4">
        <FileText className="h-6 w-6 text-knowledge-catalog" />
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <div className="text-xs text-white/40">
            Generated {generatedAt} by Deep Research Agent · grounded in your data
          </div>
        </div>
      </div>

      {/* Sections */}
      {sections.map((section, i) => (
        <section key={i}>
          <h2 className="text-lg font-medium mb-2">{section.heading}</h2>
          <p className="text-sm text-white/80 leading-relaxed">{section.body}</p>
          {section.figures && (
            <div className="mt-4 grid grid-cols-3 gap-3">
              {section.figures.map((fig) => (
                <button
                  key={fig.label}
                  onClick={() => {
                    const c = section.citations.find((c) => c.id === fig.citationId);
                    if (c) onCitationClick(c);
                  }}
                  className="rounded-lg bg-white/5 p-3 text-left hover:bg-white/10 transition-colors"
                >
                  <div className="text-xs text-white/50">{fig.label}</div>
                  <div className="text-xl font-semibold tabular-nums">{fig.value}</div>
                  <div className="text-[10px] text-knowledge-catalog mt-1">cited ↗</div>
                </button>
              ))}
            </div>
          )}
        </section>
      ))}

      {/* Risks */}
      <section>
        <h2 className="text-lg font-medium mb-3 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-amber-400" />
          Top operational risks
        </h2>
        <div className="space-y-2">
          {risks.map((risk, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg bg-white/5 p-3">
              <span className={`mt-0.5 h-2 w-2 rounded-full ${
                risk.severity === "high" ? "bg-red-400" :
                risk.severity === "medium" ? "bg-amber-400" : "bg-white/40"
              }`} />
              <span className="text-sm text-white/80 flex-1">{risk.description}</span>
            </div>
          ))}
        </div>
      </section>
    </motion.div>
  );
}
```

### Step 5 — Build the citation drill-down

Clicking a citation opens the underlying source in the side drawer (reuse the drawer from the canvas shell).

`canvas/components/canvas/CitationDrawer.tsx`:

```tsx
"use client";

// DEMO NARRATION (Beat 5): "Priya clicks into the West Africa commitment
// figure. It drills into the actual records — the Chevron-Lagos commitment,
// the committed Tool X assets via Knowledge Catalog, the forecast that
// underpins the number. No hand-waving. The exec can audit her own briefing."
export function CitationDrawer({ citation }: { citation: Citation }) {
  // Render the underlying source based on citation.source_type:
  // - knowledge_catalog: show the canonical entry (reuse KnowledgeCatalogDrawer)
  // - operational_data: show the records (commitments, fleet status)
  // - forecast: show the forecast chart excerpt
  return (
    <div className="p-6">
      <div className="text-xs uppercase tracking-wider text-knowledge-catalog mb-2">
        Source: {citation.source_type.replace("_", " ")}
      </div>
      <h3 className="text-lg font-medium">{citation.source_label}</h3>
      {/* render source-specific content */}
    </div>
  );
}
```

### Step 6 — Define the scenario beats

`canvas/data/deepResearchBeats.ts`:

```typescript
export const deepResearchBeats = [
  {
    beatNumber: 0,
    durationMs: 0,
    description: "Priya's view loads — chat ready, no briefing yet",
    state: { showBriefing: false, drawerOpen: false, chatNarration: "Priya @ Operations VP, Global" },
  },
  {
    beatNumber: 1,
    durationMs: 3000,
    description: "Priya poses her exposure question; Deep Research Agent shows its research plan",
    state: {
      showBriefing: false,
      showResearchPlan: true,
      chatNarration: "Posing the West African deepwater exposure question. Deep Research Agent is planning its research steps.",
    },
  },
  {
    beatNumber: 2,
    durationMs: 3500,
    description: "Research executes — sources queried (KC, operational data, forecasts) shown as progress",
    state: {
      showBriefing: false,
      showResearchProgress: true,
      chatNarration: "Querying Knowledge Catalog, operational data, and demand forecasts. Six research steps, all grounded in your data.",
    },
  },
  {
    beatNumber: 3,
    durationMs: 3000,
    description: "Briefing assembles — sections appear",
    state: {
      showBriefing: true,
      chatNarration: "Briefing assembled. Active commitments, committed assets, 12-week forecast, top three risks.",
    },
  },
  {
    beatNumber: 4,
    durationMs: 4000,
    description: "Priya drills into a citation — source records open in drawer",
    state: {
      showBriefing: true,
      drawerOpen: true,
      chatNarration: "Every figure cites its source. Clicking the West Africa exposure number drills into the underlying records.",
    },
  },
];
```

### Step 7 — Assemble the page and integrate with the demo runner

`canvas/app/scenarios/deep-research/page.tsx` — follow the same pattern as the other scenario pages: `CanvasShell` with chat + briefing canvas + citation drawer, `useScenario` for static mode, `useLiveScenario` for live mode (if TASK-10 is wired), keyboard controls inherited from the root `RehearsalControls`.

Pre-warm Priya's session on mount (TASK-12 pattern). The launcher tile already routes here.

### Step 8 — Commit

```bash
git add src/deep_research/ canvas/app/scenarios/deep-research/ \
        canvas/components/canvas/ExecutiveBriefing.tsx canvas/components/canvas/CitationDrawer.tsx \
        canvas/data/deepResearchBeats.ts
git commit -m "feat: Persona 4 (Priya) Deep Research Agent scenario (TASK-16)"
git push
```

---

## Acceptance criteria

- [ ] Deep Research Agent configured with Knowledge Catalog + operational data + forecast sources, web grounding disabled
- [ ] Priya's research question framed and deterministically seeded
- [ ] Briefing render view at `/scenarios/deep-research` reads like an executive document
- [ ] Every figure in the briefing has a working citation
- [ ] Citation drill-down opens the underlying source in the drawer
- [ ] 4-5 beats render cleanly in static mode
- [ ] Demo runner launcher tile routes here and pre-warms Priya's session
- [ ] Scenario fits in ~2 minutes at demo pace
- [ ] Every demo-significant component has a `// DEMO NARRATION:` comment
- [ ] Commit pushed

---

## Common pitfalls

**Deep Research Agent latency.** Autonomous multi-step research can take 30-90 seconds for real. That's too long for a live 2-minute demo beat. Use the deterministic seeded run (pre-computed briefing) for the demo; keep a live run available for the "show me it's real" moment if a customer pushes. Note this honestly in the demo handbook.

**Citations that don't actually resolve.** The drill-down must open the *real* underlying source. If a citation points to a Knowledge Catalog entry that doesn't exist, the exec audit fails visibly. Verify every citation in the seeded briefing resolves before the demo.

**Briefing reading like a chatbot.** Resist the markdown-chat-bubble look. This is an executive document. Structured sections, clear typography, scannable figures. If it looks like a chat transcript, the "this isn't a chatbot" narration falls flat.

**Web grounding accidentally enabled.** If Deep Research Agent grounds against the web, it may pull in real public data about real oil companies, polluting the synthetic scenario. Confirm web grounding is OFF for this scenario.

**Over-claiming what we built.** The narration must be honest: Deep Research Agent is the platform; we configured sources and built a render view. Don't let the demo imply we built the research capability.

---

## References

- Deep Research Agent: `https://docs.cloud.google.com/gemini-enterprise/docs/deep-research`
- Knowledge Catalog MCP: `https://docs.cloud.google.com/dataplex/docs/use-remote-mcp`
- Canvas scaffold: `claude_code_specs/tasks/TASK-08-canvas-global-asset-view.md`

---

*When TASK-16 is complete, Persona 4 shows executive synthesis grounded in the same data foundation as the operational agents — without a custom dashboard. Next: Rafael's Agent Studio live build.*
