# Persona 3 Canvas Storyboard
## The Cargo-Plane Spatial Choreography

*Beat-by-beat specification for the Operations Canvas during Maria's capacity-gap scenario.*

This is both an engineering specification and a demo rehearsal script. The canvas engineer builds to this; the demoer rehearses to this. Every beat is anchored to a structured agent event from the Capacity Orchestrator Agent, consumed via WebSocket by the canvas frontend.

Total canvas-active runtime: ~2 minutes within the 5-minute Persona 3 segment. The chat-only opening and the closing "approve in Agent Inbox" moments bracket the canvas choreography.

---

## Pre-demo state (the canvas at rest)

Before Maria types her question, the canvas is open alongside the Gemini Enterprise chat surface but visually quiet. Establishes context without competing for attention.

**Visual state:**
- Dark cartographic globe (Mapbox dark vector style or equivalent custom corporate style)
- Camera centered on West Africa with Atlantic context, gentle 15° tilt
- Ambient activity layer: small dim pulses at major operational sites worldwide (Permian, North Sea, Gulf of Mexico, Bohai, North West Shelf, West Africa) — subtle, evokes "live ops"
- Top-left: customer logo + "Operations Canvas" label
- Top-right: Maria's identity badge (small avatar, "Maria Chen — OCC, West Africa region")
- Bottom-left: small clock showing local time at her ops center
- No markers, no arcs, no banners. Quiet.

**Narration cue at this state (delivered while introducing the persona, before Maria types):**

> "This is Maria's Operations Canvas. She's our OCC planner for West Africa — same region she'd cover in your actual operations control center. Notice the canvas is just a visualization layer; the platform's intelligence isn't here, it's in Gemini Enterprise Agent Platform running in the background. The canvas just renders what the platform decides."

---

## Beat-by-beat sequence

Timings are approximate; the demoer's pacing dictates flow. Each beat is triggered by a specific structured event from the Capacity Orchestrator. Engineering builds the event handlers; rehearsal locks the demoer's narration to the event timing.

### Beat 1 — The question lands (0:00–0:10)

**In Gemini Enterprise chat:**
Maria types (live or via pre-staged input — choose at rehearsal):
> *"I need a Tool X variant on site in Luanda by Friday. What are my options?"*

The Capacity Orchestrator Agent acknowledges and visibly begins task decomposition. ADK reasoning chain starts streaming in the chat.

**On canvas:**
- Red pulsing marker emerges at Luanda (-8.8390, 13.2894), 2-second fade-in with subtle ripple
- Camera glides over 1.5 seconds to center Luanda, slight zoom-in (Mapbox flyTo)
- Side panel slides in from right with header "Active capacity gap" and a deadline counter showing days-to-Friday
- The ambient global pulses dim slightly to put visual weight on Luanda

**Triggering event:** `CapacityGapDetected`
```python
class CapacityGapDetected(BaseModel):
    target_location: GeoPoint   # (-8.8390, 13.2894)
    target_label: str           # "Luanda, Angola"
    requested_asset_class: str  # "Tool X variant"
    deadline_iso: str           # "2026-05-22T00:00:00Z"
    request_id: UUID
```

**Narration:**
> "Maria's typed her question. The agent's started reasoning in Gemini Enterprise — you can see the reasoning chain streaming on the left. On the canvas, the gap is now visualized: Luanda, with a Friday deadline."

---

### Beat 2 — Multi-system decomposition (0:10–0:20)

**In Gemini Enterprise chat:**
Capacity Orchestrator decomposes the task into parallel sub-queries. Visible in the trace: "Querying Maximo for Tool X availability... Querying SAP for workforce and materials... Querying FDP for customer configuration... Retrieving InTouch technical specs..."

**On canvas:**
- A small "Systems being queried" badge cluster appears bottom-right
- Four pill-shaped badges (Maximo, SAP, FDP, InTouch) appear and start pulsing in parallel
- Each badge has a small spinning indicator showing active query
- Narration ties this to A2A / MCP

**Triggering event:** `MultiSystemQueryStarted`
```python
class MultiSystemQueryStarted(BaseModel):
    systems: list[str]   # ["maximo", "sap", "fdp", "intouch"]
    parallel: bool       # True
    request_id: UUID
```

**Narration:**
> "Notice that the agent doesn't go through these one at a time. It decomposes the task and hits four systems in parallel — Maximo via MCP, SAP via Apigee-managed MCP, FDP, and InTouch retrieval through Knowledge Catalog. These four pills are the agent's actual queries running concurrently."

---

### Beat 3 — Maximo returns empty (0:20–0:30)

**In Gemini Enterprise chat:**
> "Maximo result: 0 Tool X variants currently available in West Africa region"

**On canvas:**
- Maximo badge resolves with a small red ❌ icon
- A brief "scan sweep" effect ripples across the West Africa region (subtle radial gradient, 1.5s duration)
- No markers light up in the region — confirming the scarcity
- Side panel updates: "No direct matches in West Africa"

**Triggering event:** `SystemQueryResult`
```python
class SystemQueryResult(BaseModel):
    system: str          # "maximo"
    status: str          # "empty"
    count: int           # 0
    region_filter: str   # "west_africa"
    request_id: UUID
```

**Narration:**
> "Maximo confirms what Maria probably already suspected — there's no Tool X available in West Africa. This is the moment in the old workflow where the panicked logistics conversation starts."

---

### Beat 4 — Global scan and the naive option (0:30–0:50)

**In Gemini Enterprise chat:**
Agent expands search globally and surfaces the naive baseline.
> "Tool X availability worldwide: Darwin Australia (in-use), Houston (in-use), Aberdeen UK (committed), Singapore (in-use). Closest deployable: Darwin, 13,200km, cargo charter ~$420K."

**On canvas:**
- Camera pulls back to show a wider geographic view (Africa + Indian Ocean + Australia)
- Markers populate at each Tool X location, color-coded:
  - Yellow for in-use (Darwin, Houston, Singapore)
  - Orange for committed (Aberdeen)
- Darwin marker grows slightly more prominent
- A faded grey-blue arc draws itself from Darwin to Luanda over 2 seconds (Mapbox arc-line with animated path)
- A cost banner emerges next to the arc: **"Naive option: ~$420K cargo charter, 32hr transit"**
- The banner is styled in dimmed/grey tones — visually de-emphasized but readable

**Triggering event:** `NaiveOptionIdentified`
```python
class NaiveOptionIdentified(BaseModel):
    origin: GeoPoint          # Darwin
    origin_label: str         # "Darwin, Australia"
    destination: GeoPoint     # Luanda
    transit_mode: str         # "cargo_charter"
    estimated_cost_usd: int   # 420000
    transit_hours: float      # 32
    request_id: UUID
```

**Narration:**
> "Here's the naive option — chartering a cargo plane from Darwin to Luanda. That's the $420K decision the agent could've stopped at. A lot of planning tools would have. But this agent has more to check."

---

### Beat 5 — The pivot to equivalence (0:50–1:05)

**In Gemini Enterprise chat:**
> "Loading `asset-equivalence` skill... Querying Knowledge Catalog for functionally equivalent variants of Tool X..."

**On canvas:**
- A new side panel slides in from the right (replacing or expanding the current side panel)
- Header: **"Knowledge Catalog: Tool X canonical entity"**
- The panel shows the canonical entity with its cross-system aliases listed cleanly:
  - SAP Material Master: `MAT-67890`
  - Maximo Equipment ID: `EQ-12345`
  - FDP Configuration: `TX-CONFIG-A`
  - InTouch References: `Spec §3.2, Cust Config CC-204`
- Below: a "Functionally equivalent variants" expansion appears
  - Tool X-V7 — *equivalent per InTouch spec §3.2*
  - With a small confidence indicator: "High confidence — same operating envelope"

**Triggering event:** `EquivalenceLookupStarted` followed by `EquivalentAssetIdentified`
```python
class EquivalentAssetIdentified(BaseModel):
    canonical_entity: KnowledgeCatalogEntity
    equivalent_variants: list[EquivalentVariant]
    request_id: UUID

class EquivalentVariant(BaseModel):
    variant_id: str            # "tool_x_v7"
    variant_label: str         # "Tool X-V7"
    confidence: float          # 0.92
    rationale_source: str      # "InTouch Spec §3.2"
```

**Narration:**
> "This is the pivot. The agent reaches into Knowledge Catalog — your unified context graph — and finds a functionally equivalent sub-variant per a spec from your own InTouch repository. Notice the canonical entity panel: same Tool X has different identifiers in SAP, Maximo, FDP, and InTouch, all unified. The agent reasons against this canonical entity, not against any individual system's naming convention. That's Issue 4 — dissolved."

---

### Beat 6 — The local solution emerges (1:05–1:20)

**In Gemini Enterprise chat:**
> "Maximo result (filtered for Tool X-V7): 1 unit available, Lagos repair shop, status: ready-for-deployment after 4hr certification."
> "FDP: Customer Gulf Petroleum config CC-204 accepts Tool X-V7 — confirmed compatible."
> "SAP: Workforce available for Lagos dispatch."

**On canvas:**
- A new bright green marker appears in Lagos (6.5244, 3.3792), pulsing rhythmically (1 Hz pulse, 1.3x scale at peak)
- A green arc draws itself from Lagos to Luanda over 1 second — short, direct, visually triumphant
- Cost banner under the green arc: **"Local sourcing: ~$40K, 4hr ground transit + 4hr certification"**
- The original grey Darwin arc fades further to ~20% opacity
- Camera slightly zooms in to frame the Lagos-Luanda corridor prominently

**Triggering event:** `RecommendedSourceIdentified`
```python
class RecommendedSourceIdentified(BaseModel):
    source_location: GeoPoint       # Lagos
    source_label: str               # "Lagos, Nigeria"
    asset_variant_id: str           # "tool_x_v7"
    distance_km: float              # 50
    transit_mode: str               # "ground_transit"
    estimated_cost_usd: int         # 40000
    transit_hours: float            # 4
    certification_hours: float      # 4
    customer_compatibility: bool    # True
    workforce_available: bool       # True
    request_id: UUID
```

**Narration:**
> "And there's the answer. The same canonical Tool X — different sub-variant, in a Lagos repair shop, 50 kilometers from the Luanda site. FDP confirms the customer accepts V7. SAP confirms workforce is available. The agent's basically done — it just has to tell Maria."

---

### Beat 7 — The savings reveal (1:20–1:35)

**In Gemini Enterprise chat:**
> "Plan Evaluator assessment: 0.91 (high confidence). Procurement Approval Agent: APPROVED — all prerequisites met, well under threshold for human review."
> Final recommendation surfaced to Maria's Agent Inbox.

**On canvas:**
- A prominent banner emerges from the top of the canvas with a smooth roll-up animation (Framer Motion `useMotionValue` for the number):
  - **"$380,000 avoided cost"** — number rolls up from $0 to $380K over 1.2s
- A secondary stat panel populates below the banner:
  - Original option: $420K, 32hr transit
  - Recommended: $40K, 8hr total (transit + certification)
  - Savings: $380K
  - Risk score: 0.91
  - Approval: ✓ Within authorization (Maria's tier)
- The Lagos green marker continues its rhythmic pulse
- Side panel shows the full recommendation card with "View in Agent Inbox" button

**Triggering event:** `RecommendationFinalized`
```python
class RecommendationFinalized(BaseModel):
    primary_option: SourcingOption       # Lagos
    naive_baseline: SourcingOption        # Darwin
    avoided_cost_usd: int                 # 380000
    risk_score: float                     # 0.91
    procurement_approval: bool            # True
    inbox_url: str
    request_id: UUID
```

**Narration:**
> "Three hundred and eighty thousand dollars. That's the difference between the naive option and what the agent surfaced. And the agent didn't just save the money — it surfaced the reasoning, the customer compatibility, the workforce confirmation, the risk score, and a procurement gate approval, all in less than two minutes. Maria approves it from her Agent Inbox and it's done."

---

### Beat 8 — The "how did it know?" drill-down (1:35–2:00) — *optional interactive moment*

This beat is held in reserve for live demos where the customer asks the inevitable question. If the demoer chooses to play it, this is what happens.

**Trigger:** Demoer clicks the Knowledge Catalog entity in the side panel (or types a follow-up: "How did the agent know these were equivalent?").

**On canvas:**
The Knowledge Catalog side panel expands into a fuller view:
- The canonical Tool X entity (large central node)
- Branches radiating outward to each system alias:
  - SAP Material Master `MAT-67890` (with a small SAP logo)
  - Maximo Equipment ID `EQ-12345` (with a Maximo logo)
  - FDP Customer Configuration `TX-CONFIG-A`
  - InTouch References `Spec §3.2, CC-204`
- A separate branch showing the `functional_equivalence` edge to Tool X-V7, with the spec citation `InTouch §3.2: "V7 substitutable for original V where customer config permits"`
- Each branch is clickable for further detail (don't drill further unless asked)

**Narration:**
> "Here's why the agent never got confused. In every system, this Tool X is identified differently — SAP calls it MAT-67890, Maximo calls it EQ-12345, FDP has its own ID. The agent never sees that chaos. It reasons against the canonical entity in Knowledge Catalog — and the catalog knows about all the aliases, all the equivalence relationships, all the spec citations. This is your Issue 4. It's not solved by retraining the agent or writing custom ETL. It's solved structurally by Knowledge Catalog as the substrate."

---

## Closing state (2:00 onward)

The canvas remains visible as Maria's Agent Inbox approval flows through. The map shows:
- Green Lagos-Luanda arc prominent and pulsing
- Darwin arc faint, almost ghosted
- $380K banner remains visible
- Knowledge Catalog drawer closed (returns to summary view)
- Reasoning trace remains accessible on side for procurement audit narration

The demoer transitions to closing narration about governance and audit trail (which segues into Persona 6 if playing the full arc) or to "any questions" pause.

---

## Technical specifications

### Event flow architecture

```
Capacity Orchestrator Agent (ADK on Agent Runtime)
        |
        | emits structured events via Pydantic schemas
        v
WebSocket Gateway (Cloud Run service, persistent connection per demo session)
        |
        | streams typed events as JSON
        v
Operations Canvas frontend (Next.js, useWebSocket hook)
        |
        | handles event by type, triggers animation
        v
Mapbox GL / Framer Motion render
```

### WebSocket message envelope

All events wrapped in a standard envelope:

```json
{
  "event_type": "CapacityGapDetected",
  "request_id": "uuid-v4",
  "timestamp": "ISO-8601",
  "payload": { /* event-specific schema */ }
}
```

### Color palette (locked)

| Semantic | Color | Hex |
|---|---|---|
| Capacity gap (urgent) | Red | `#ef4444` |
| In-use / committed | Yellow / Orange | `#f59e0b` / `#fb923c` |
| Recommended / available | Green | `#10b981` |
| Dimmed / excluded | Slate grey | `#64748b` |
| Knowledge Catalog accent | Blue | `#3b82f6` |
| Banner / chrome | Tailwind slate-900 / slate-100 | `#0f172a` / `#f1f5f9` |
| Map base | Mapbox dark v11 with custom corporate tint |

### Motion design principles

- All transitions use Framer Motion springs (not linear easings) — feels alive
- Cost banner number rolls via `useMotionValue` + `useTransform` (1.2s duration)
- Map arcs draw via SVG path animation `stroke-dasharray` technique
- Camera transitions use Mapbox `flyTo` with `duration: 1500, essential: true`
- Marker pulses use a separate Framer Motion `animate` loop, not Mapbox-native
- Avoid simultaneous motion in more than 2 visual regions — let beats breathe

### Layout (16:9 reference, 1920×1080)

```
+--------------------------------------------------+
|  Customer logo / "Operations Canvas"      Maria  |
+--------------------------------------------------+
|                                                  |
|                                                  |
|              [Map fills 70%]                     |
|                                                  |
|                                          +-----+ |
|                                          |Side | |
|                                          |panel| |
|                                          |30%  | |
|                                          |     | |
|                                          +-----+ |
|              [Bottom badges row]                 |
+--------------------------------------------------+
```

Side panel toggles between "Active gap" → "Knowledge Catalog entity" → "Recommendation summary" as beats progress.

---

## Fallback mode (no network / failed WebSocket)

If the WebSocket connection drops mid-demo (real risk on conference WiFi), the canvas must continue. Two fallback strategies:

**Fallback A — Pre-recorded timeline replay (preferred).**
- A `demoMode: "live" | "playback"` toggle in canvas state
- In playback mode, a hardcoded timeline file (`storyboard-replay.json`) fires events at preset timestamps matching this storyboard
- Demoer can toggle to playback via hotkey (Ctrl+Shift+P) if network drops
- Playback finishes in exactly 2 minutes regardless of agent latency

**Fallback B — Frozen final-state mode.**
- If both live and playback fail, canvas shows the final-state visualization (green Lagos route, savings banner) as a static image
- Demoer narrates over the still image
- Less impressive but salvageable

Both fallback modes should be tested in dry-run before any customer-facing demo.

---

## Open design questions

To resolve before engineering kicks off Week 3:

1. **Map provider — Mapbox or Google Maps?** Mapbox has stronger vector styling and Framer Motion compatibility; Google Maps is the "consistency with rest of GCP" choice. Recommendation: Mapbox for visual quality, but worth checking if there's a Google Cloud / Maps team preference.
2. **Animation library — Framer Motion or React Spring?** Framer Motion is more popular and has better documentation; React Spring is more performant for complex orchestration. Recommendation: Framer Motion for this scope.
3. **Camera path during Beat 4 (global scan)** — single smooth zoom-out, or a sequence of "pings" at each location? Recommendation: smooth zoom-out with the locations populating during the move. Cleaner.
4. **Side panel transitions** — full replacement on each new beat, or stacked card carousel? Recommendation: full replacement with subtle fade-cross. Less visual noise.
5. **Live vs. pre-staged Maria input** — does Maria type the question live during the demo, or is it pre-staged for predictable timing? Recommendation: pre-staged for reliability, with the demoer triggering "Maria sends" at the right pacing.
6. **Sound design** — any subtle audio cues (whoosh on arc-draw, gentle ding on Beat 7)? Recommendation: no audio for v1. Easy to add later if it lands well; harder to remove if it's annoying.

---

## Rehearsal checklist

Before any customer demo:

- [ ] All 8 beats triggered cleanly via WebSocket from a test agent run
- [ ] Fallback playback mode tested with the demoer's keyboard
- [ ] Frozen final-state mode renders correctly
- [ ] Demoer can recite the narration without looking at the script
- [ ] Pacing rehearsed three times end-to-end (full Persona 3 segment, including canvas)
- [ ] At least one rehearsal done on conference-WiFi-quality network
- [ ] Backup laptop / device with the demo loaded and warmed up
- [ ] Customer skin verified (logos, colors, terminology, locations)

---

*End of storyboard.*
