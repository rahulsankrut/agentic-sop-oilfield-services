# Agentic S&OP for Oilfield Services
## A reference solution on Gemini Enterprise + Gemini Enterprise Agent Platform

*Product brief and build plan.*

---

## What we are building

We are building a **reference solution** — a deployable bundle of agents, skills, MCP servers, synthetic data, personas, and scenarios — that runs inside an actual Gemini Enterprise tenant on Gemini Enterprise Agent Platform. The solution makes the platform feel native to oilfield services for any tier-one services major (SLB, Halliburton, Baker Hughes, NOV, Weatherford). A senior CE can customize it for a specific customer in a couple of hours.

The pack is framed around **Sales and Operations Planning (S&OP)** — the recognized cross-functional business process every services major runs, with named owners and a quarterly cadence. The four pain points the customer surfaced are the four breakpoints in their S&OP cycle today; the demo addresses each one as a station in the same value chain.

| S&OP stage | Customer's pain point today | Demo persona addressing it |
|---|---|---|
| Demand sensing and forecasting | Issue 2 — ML forecast dies at Excel review boundary; qualitative regional knowledge never returns to the model | Persona 1 (Basin Leader / David) |
| Demand-to-supply planning | Issue 1 — Volatile customer start dates drive excessive static buffers, tying up fleet and forcing replacement CapEx | Persona 2 (Fleet Scheduler / Tomas) |
| Supply response (when planning fails) | Issue 3 — Multi-system stitching forces panicked logistics decisions when capacity gaps emerge | Persona 3 (OCC Planner / Maria) |
| Foundational data layer | Issue 4 — Misaligned naming conventions break automation everywhere upstream | Surfaced as substrate in the Knowledge Catalog views across Personas 1, 2, 3 |

We are not building a custom application. We are not building a skin over the platform that hides it. We are building **content for the platform** that lets it speak the customer's language convincingly, anchored on the S&OP cycle they already run.

## Why this distinction matters for the sale

The sale is Gemini Enterprise (as the front door for the customer's people) plus Gemini Enterprise Agent Platform (as the build-and-run surface for their agents). The demo has to make those two products *the visible heroes*, not relegate them to plumbing under a custom UI.

Two consequences:

**The Gemini Enterprise app is the demo surface for five of six personas.** Their experiences happen inside the real product — Agent Inbox, Agent Designer, Deep Research Agent, Agent Registry, Connected Sheets. When the customer says "I like this," they are saying they like a product they can buy and deploy this week.

**Two personas get a companion Operations Canvas.** Persona 3 (the cargo-plane scenario) and Persona 2 (the fleet scheduler) open a spatial visualization view alongside Gemini Enterprise — a polished operations canvas showing maps, assets, fleet utilization, and the agent's recommendation playing out geographically. This is the disciplined exception that gives the demo the same visual punch the keynote's marathon map had, without violating the platform-first framing. The canvas is narrated as "an example of what your ops team would build on top of the platform's structured outputs" — the platform produces decisions; the canvas is just one of many surfaces that can consume them. See the "Operations Canvas" section below for scope and narration discipline.

**Every platform component gets named, on every slide.** When we narrate the demo, we say "Capacity Orchestrator Agent — built on ADK, hosted on Agent Runtime" instead of "our agent." We say "Knowledge Catalog is what unifies SAP, Maximo, and FDP into one canonical entity" instead of "the system knows." This is not marketing repetition; it is product association. The customer should leave the room able to draw the architecture from memory.

A polished custom-branded application would sell an *application*. The platform-first framing sells the *platform*. Same demo flow, different framing, different deal at the end.

---

## The demo experience, persona by persona

Six personas, all anchored in Gemini Enterprise and mapped to the customer's S&OP cycle. Each persona showcases a different facet of the platform; together they cover the full keynote arc *and* resolve all four pain points the customer raised. The "incredible" comes from three sources: domain content quality, storyboard rehearsal, and one purpose-built Operations Canvas that gives the spatial moments their visual punch.

The first three personas walk the S&OP cycle in order — demand sensing, demand-to-supply planning, supply response. The remaining three personas address cross-cutting capabilities the customer's broader org will care about: executive research, citizen development, and governance.

### Persona 1 — Basin Leader / S&OP Demand Sensing (Issue 2)

**Persona:** David, Permian Basin Director — responsible for converting pipeline signals into a defensible quarterly forecast for his region.

**Surface:** Gemini Enterprise app with Connected Sheets for the forecast grid; Agent Inbox for review prompts.

**Flow:** David sees the ML-generated forecast in Connected Sheets backed by BigQuery. Overrides October completions revenue down 22%. Agent Inbox surfaces a prompt from the Forecast Review Agent asking what's driving the change. David selects "rig count decline expected, three operators delaying programs" from structured options plus a freeform note. Gemini extracts rationale tags. A small "model improving" indicator shows historical override magnitude shrinking quarter over quarter as the model has learned from prior rationale.

**Issue resolved:** Issue 2 — the human review boundary no longer breaks the data chain. Qualitative regional knowledge is captured as structured rationale, fed back into the model, and reduces future override magnitude over time.

**Platform components named:**
- Connected Sheets backed by BigQuery
- BigQuery measures (defining canonical "Permian Q4 completions revenue")
- Forecast Review Agent (ADK agent on Agent Runtime)
- Agent Inbox (the review surface)
- Memory Bank with Memory Profiles (per-leader rationale capture)
- Knowledge Catalog (grounding "Permian basin" as canonical entity)

**Time:** 3 minutes.

### Persona 2 — Fleet Scheduler / S&OP Demand-to-Supply Planning (Issue 1)

**Persona:** Tomas, West Texas Fleet Scheduler — responsible for translating regional forecasts into specific equipment allocations and buffer decisions across the next 4-13 weeks.

**Surface:** Gemini Enterprise app chat for the conversation; Operations Canvas (fleet view) for the spatial moment.

**Flow:** Tomas asks "What's my buffer exposure on the West Texas fleet next quarter, given the rig count signals we're seeing?" The Capacity Planning Agent — long-running, multi-week state — pulls probabilistic start-date distributions from BigQuery ML, surfaces the actual-vs-requested start date variance for the basin's last six quarters, and produces risk-calibrated buffer recommendations.

The Operations Canvas opens alongside, showing a basin-level fleet map: equipment locations across West Texas, utilization heatmap by sub-region, the buffer-vs-utilization tradeoff curve. Tomas drags a risk-tolerance slider; the canvas recalculates live — buffer days shrink, utilization rises, projected on-time delivery rate moves from 40% to 65%, and a deferred-CapEx number ticks up on a side panel. The Capacity Planning Agent's reasoning chain stays visible in Gemini Enterprise alongside the canvas — narration explicitly ties them: "the platform produces the optimization; the canvas is how Tomas's team would visualize it."

**Issue resolved:** Issue 1 — static worst-case buffers replaced with probabilistic, risk-calibrated recommendations grounded in actual start-date volatility data. Fleet utilization rises; replacement-tool CapEx is deferred.

**Platform components named:**
- Capacity Planning Agent (long-running, multi-week state on Agent Runtime)
- BigQuery ML for probabilistic forecasting
- Vertex AI Optimization (for risk-calibrated buffer allocation)
- Memory Profile (Tomas's risk tolerance, fleet, basin defaults)
- Agent Inbox for multi-week planning workflows
- Cloud Trace (the reasoning chain behind each buffer recommendation)
- Operations Canvas (the customer-built or partner-built visualization layer; structured agent output consumed via API)

**Time:** 3 minutes.

### Persona 3 — OCC Planner / S&OP Supply Response (Issue 3 and Issue 4) — the centerpiece

**Persona:** Maria, Operations Control Center, West Africa region — the planner who has to find equipment when planning fails and a real-world capacity gap emerges.

**Surface:** Gemini Enterprise app chat interface for the conversation; Operations Canvas (global asset view) for the spatial moment. This is the demo's "wow" segment — both surfaces visible side by side.

**Flow:** Maria types "I need a Tool X variant on site in Luanda by Friday. What are my options?"

The Capacity Orchestrator Agent begins reasoning in Gemini Enterprise — visible decomposition into Maximo, SAP, FDP, and InTouch queries, each running in parallel with live trace.

As the agent works, the Operations Canvas comes alive alongside. Globe view, dark cartographic style. Luanda highlighted with a pulsing red "capacity gap" marker. Tool X variants worldwide appear as dots — Australia rig site, Houston warehouse, Singapore, Aberdeen — color-coded by availability. The agent's first finding lands: no Tool X available in West Africa. The naive option draws itself on the map: a faded cargo charter arc from Darwin, Australia to Luanda, with an estimated cost of $420K banner.

Then the agent reasons across the Knowledge Catalog equivalence graph. A new dot appears in Lagos — Tool X-V7, in a repair shop, functionally equivalent per InTouch spec §3.2. The Lagos dot pulses green. A new arc draws itself: Lagos to Luanda, 50 km, ground transit, $40K. The savings number rolls up on a side panel: **$380K avoided cost**. The Knowledge Catalog entity for Tool X expands in a side drawer, showing its SAP material number, Maximo equipment ID, FDP config ID, and InTouch references — all aliases of the same canonical entity. Maria clicks "approve in Agent Inbox" and the recommendation is committed.

Throughout, narration ties the canvas back to the platform: "the agent is doing the work in Gemini Enterprise Agent Platform. The visualization is how Maria's ops team chooses to surface what the agent decides. Same structured output, any consuming surface works."

**Issues resolved:** Issue 3 — multi-system stitching collapses from manual hours into a single agent query; panicked logistics decisions avoided. *Issue 4 resolves visibly too* — the Knowledge Catalog drawer shows the agent does not see taxonomic chaos, only canonical entities with all cross-system aliases unified.

**Platform components named on-screen and in narration:**
- Gemini Enterprise app (the chat surface Maria uses)
- Capacity Orchestrator Agent on Agent Runtime
- Plan Evaluator Agent (in-process via `AgentTool`)
- Procurement Approval Agent (Agent Engine, A2A)
- Knowledge Catalog (grounding the equivalence reasoning — and where Issue 4 dissolves visibly)
- Apigee-managed MCP servers (SAP, Maximo, FDP)
- Memory Profile (Maria's basin, authorization tier, defaults)
- Cloud Trace (the visible reasoning chain)
- Operations Canvas (the visualization layer consuming the platform's structured outputs)

**Time:** 5 minutes (the centerpiece and S&OP-cycle climax).

### Persona 4 — Operations Executive (Deep Research Agent)

**Persona:** Priya, Senior VP, Eastern Hemisphere — needs to synthesize portfolio-level signals across her territory in real time.

**Surface:** Gemini Enterprise app, Deep Research Agent.

**Flow:** Priya asks "What's my exposure on West African deepwater fleet over the next two quarters, accounting for the three known program slips?" Deep Research Agent reasons across BigQuery operational data, Knowledge Catalog-grounded entity definitions, basin reports, and customer commits in Drive. Returns a citation-grounded briefing with charts and "what would change this" levers.

**Platform components named:**
- Deep Research Agent (the new Gemini Enterprise agent)
- Knowledge Catalog (the grounding layer)
- BigQuery and Cross-Cloud Lakehouse (the data layer, with note: "if your SAP runs on Azure, Cross-Cloud Lakehouse federates without copying")
- Cited sources visible in the response (procurement and audit defensibility)

**Time:** 2 minutes.

### Persona 5 — Citizen Developer (Agent Designer live)

**Persona:** Rafael, Operations Analyst, Latin America — knows his domain deeply, does not write code.

**Surface:** Gemini Enterprise app, Agent Designer.

**Flow:** Rafael builds a small basin-specific guardrail agent live, in two minutes: "any sourcing recommendation involving non-OEM parts in a deepwater context should flag for technical review." Drag, configure, name, publish. The new agent appears in Agent Registry, governed by Agent Gateway policies, with cryptographic Agent Identity, identical to the agents engineers built.

**Platform components named:**
- Agent Designer (no-code agent building)
- Agent Registry (the central library — every agent in the customer's environment lives here)
- Agent Gateway (the runtime policy enforcer)
- Agent Identity (the cryptographic identity for every agent)

**Time:** 2 minutes.

### Persona 6 — Audit / Security (governance posture)

**Persona:** Ayesha, Internal Audit Director — often the deal-blocker if the governance story isn't credible. Don't skip her segment.

**Surface:** Gemini Enterprise app + GCP console views for traces, policies, security.

**Flow:** Ayesha tours Agent Registry — every agent in the platform listed with owner, version, scope, change history. Drills into a sample agent's Identity card. Reviews a Gateway policy that prevents the Capacity Orchestrator from approving sourcing over $500K without human review. Sees a Cloud Trace from a real sourcing decision with full reasoning chain. Sees Wiz scan output of the agent infrastructure. Sees a Model Armor log of a prompt-injection attempt that was blocked at the agent's input boundary. Sees Google SecOps for SAP showing agent activity against SAP material master alongside other SAP security telemetry.

**Platform components named:**
- Agent Identity, Agent Registry, Agent Gateway, Model Armor (the governance stack — by product name)
- Cloud Observability + Cloud Trace
- Wiz integration (announced partnership)
- Google SecOps for SAP (announced at Sapphire 2026)
- Agent Simulation, Evaluation, Observability (the pre-production testing suite)

**Time:** 3 minutes.

---

## The Operations Canvas (companion view for Personas 2 and 3)

The canvas is a single small Next.js application — purpose-built for the spatial moments in Personas 2 and 3. It is the disciplined exception to the "everything in Gemini Enterprise app" rule, included because the cargo-plane scenario and the fleet utilization story land an order of magnitude more vividly with a map than without.

### What it actually is

A dark-mode, polished spatial visualization with two views:

**Global Asset View (Persona 3 / Maria).** Globe or world map, dark cartographic style (Mapbox Light/Dark or Google Maps vector). Asset locations as markers (color-coded by availability). Capacity gap origin highlighted. Logistics arcs drawn dynamically as the agent reasons (the doomed Australia → Luanda charter route in faint grey, the recommended Lagos → Luanda local route in pulsing green). Knowledge Catalog entity drawer expandable on the side. Cost differential and savings rolled up on a banner.

**Fleet Utilization View (Persona 2 / Tomas).** Basin-level map (West Texas / Permian for the demo). Equipment locations clustered by sub-region. Utilization heatmap overlay. Risk-tolerance slider that recalculates buffer recommendations live. Buffer-vs-utilization tradeoff curve. Deferred CapEx counter. Optional: a small "what shifted" log showing which probabilistic forecasts changed.

### How it stays inside the platform-first frame

The canvas is positioned in narration as **the visualization layer on top of the platform's structured outputs**. The Capacity Orchestrator Agent emits a structured `SourcingRecommendation` (Pydantic schema, A2A-emittable); the canvas consumes it. The Capacity Planning Agent emits a `BufferOptimization`; the canvas consumes it. The platform is the source of truth; the canvas is one of many surfaces that can render its outputs.

Narration discipline:

- "The platform produced the decision in Gemini Enterprise Agent Platform. The visualization is how Maria's team chose to surface it — using their preferred mapping tools and dashboard framework. Same structured output, any consuming surface works."
- "What you're seeing on the right is not the platform. It's an example of what your ops team would build on top of the platform. You could build this in your existing operations dashboard, in Looker, in a custom React app, or using Agent Designer + an embedded mapping component."
- "The point is: every value the canvas shows comes from a structured agent output. Cost, location, equivalence, savings — all from the platform. The canvas is just rendering."

Done well, the canvas amplifies the platform sale rather than competing with it: it makes the platform's outputs feel valuable enough that the customer's ops team will want to surface them everywhere.

### Technical stack

- **Next.js + TypeScript + Tailwind** — front-end shell
- **shadcn/ui** components for cards, drawers, controls
- **Mapbox GL** or **Google Maps JavaScript API** with custom dark vector style
- **Framer Motion** for the cost-banner roll-up, arc-drawing animations, dot pulses
- **WebSocket / Server-Sent Events** to receive structured agent outputs from Gemini Enterprise Agent Platform during the live demo
- Deployed as a Cloud Run service alongside the rest of the pack

No 3D. No bespoke physics. No CAD-style equipment renderings. Clean cartography, motion design discipline, and clear data visualization. Aim is "polished operations dashboard," not "video game."

### What we explicitly will not do

- 3D drilling rig animations (compete with the customer's own internal tools; will look worse)
- Bespoke downhole tool renderings (same reason)
- A2UI-driven dynamic UI generation (still v0.9 preview; risk does not justify benefit for this use case)
- Custom branding so heavy that it looks like a Google-built application competing with Gemini Enterprise. The canvas should look like *the customer's* visualization layer, not *Google's* visualization layer

### Customer skin

The canvas is customer-skinnable via the same `customer.yaml` that configures the rest of the pack. Logo, color palette, map style (corporate dark variant), terminology in the side panels, location of the hero scenario (Luanda by default, swappable for any oilfield geography the customer cares about), asset categories rendered. About 30 minutes of skin work per new customer once the templates exist.

### Build cost

Approximately one engineer-week added to Phase 1 (Week 6 or 7, parallel to other build streams). The reusable visualization framework is the work; per-scenario animation choreography is a few hours each. Reflected in the updated build plan below.

---

## Total runtime and pruned versions

About 18 minutes for the full six-persona arc. Two pruned versions for different audiences:

- **S&OP-focused (11 minutes)** — Personas 1, 2, 3 only. Walks the full S&OP cycle and resolves all four customer issues. Right for executive readouts where the operations/planning/procurement audience cares most about the cycle being whole.
- **Cold-open showstopper (5 minutes)** — Persona 3 only. The cargo-plane scenario as a standalone. Right for first 15-minute exec slots or competitive comparisons.

The 18-minute full arc is right for technical buyer audiences and pre-Gate-3 deep-dive readouts.

---

## The platform visibility checklist

A useful self-test for any moment in the demo: can the customer name the Google Cloud product responsible for what they just saw?

| If the customer sees... | They should be able to name... |
|---|---|
| The spatial visualization (map, fleet view) | Operations Canvas — *and crucially, "this is the customer's visualization layer consuming structured agent outputs, not the platform itself"* |
| The chat interface | Gemini Enterprise app |
| The agent reasoning live | Agent Runtime + Agent Observability |
| Recommendations queued for approval | Agent Inbox |
| Inter-agent communication | A2A protocol on Agent Platform |
| SAP / Maximo / FDP data being queried | MCP servers managed by Apigee |
| The "Tool X = MAT-67890" unification | Knowledge Catalog |
| InTouch PDFs being retrieved | Smart Storage + Object Context API |
| Per-user personalization | Memory Bank + Memory Profiles |
| The forecast grid | Connected Sheets + BigQuery measures |
| The executive research | Deep Research Agent |
| The live agent build | Agent Designer |
| The agent list with audit trail | Agent Registry + Agent Identity |
| The policy that prevented an over-budget approval | Agent Gateway |
| The blocked prompt injection | Model Armor |
| The trace of a failed reasoning chain | Cloud Trace + Gemini Cloud Assist |
| The infrastructure scan | Wiz + Agentic Defense |
| The SAP-aware security view | Google SecOps for SAP |

If the customer cannot, that's a demo bug. Fix the slide, the narration, or the on-screen label.

---

## What we build (the domain pack)

The pack is a Git repository, deployable to a Gemini Enterprise tenant. Customer-agnostic core plus a customer configuration layer.

### Customer-agnostic core (built once)

**Agents** — five ADK agents, deployed on Agent Runtime / Agent Engine:

1. **Capacity Orchestrator** (Cloud Run via Agent Engine) — lead agent, multi-system reasoning
2. **Plan Evaluator** (in-process AgentTool) — 7-criterion LLM-as-Judge
3. **Procurement Approval Agent** (Agent Engine, A2A) — prerequisite check + approval
4. **Forecast Review Agent** (Agent Engine) — rationale extraction on overrides
5. **Capacity Planning Agent** (Agent Engine, long-running) — multi-week scheduling state

**Skills** — six ADK Skills (SKILL.md + scripts/ + references/):

1. `asset-equivalence` — canonical asset resolution and functional equivalence reasoning
2. `sourcing-logistics` — transit estimation, cost calculation, blocker identification
3. `enterprise-systems` — abstracted SAP, Maximo, FDP query patterns
4. `forecast-rationale` — structured rationale extraction from human overrides
5. `procurement-prerequisites` — deterministic procurement readiness checks
6. `scheduling-probability` — probabilistic start-date reasoning

**MCP servers** — managed by Apigee (production pattern), backed by:

1. **SAP MCP** — material master, workforce, plant maintenance (mocked with realistic SAP-shaped responses; real if customer has test environment)
2. **Maximo MCP** — equipment status, location, availability
3. **FDP MCP** — historical customer configurations
4. **InTouch retrieval** — via Knowledge Catalog + Smart Storage rather than a dedicated MCP

**Knowledge Catalog content:**
- Canonical asset taxonomy (80-120 entries spanning major equipment categories)
- Cross-system aliases (SAP material number, Maximo equipment ID, FDP config ID per canonical entity)
- Functional equivalence relationships (15-25 documented equivalences with spec references)
- BigQuery measures defining canonical operational metrics
- Smart Storage configured on InTouch synthetic PDF bucket with auto-extraction

**Memory Bank content:**
- Six Memory Profiles for the six demo personas
- Pre-populated context for each persona (basin, fleet, risk tolerance, authorization)

**Governance configuration:**
- Agent Identity for every agent
- Agent Gateway policies (the over-$500K rule, the regulatory-clearance rule, the SAP authorization passthrough)
- Model Armor policies for SAP-touching agents
- Wiz scan baseline
- Cloud Monitoring alerts (cost threshold, error rate, policy violations)

**Synthetic data** (the credibility layer):
- 80-120 canonical asset entries with realistic oilfield naming
- 5-10 representative customers (anonymized: "Gulf Petroleum", "North Atlantic Resources", "Bohai Energy")
- 200-300 InTouch PDFs (synthesized technical specs, compatibility documents, customer configurations)
- 24 months of synthetic operational history (sourcing events, capacity gaps, fleet utilization)
- 6 quarters of synthetic forecast + override history
- **Synthetic start-date variance data** — 6 quarters of requested-vs-actual start dates per basin, the substrate for Persona 2's probabilistic buffer recommendations
- **Geographic data** — asset locations worldwide for the canvas, transit cost envelopes by route and asset class, basin boundaries and major hubs

**Operations Canvas** (Next.js app, Cloud Run deployment):
- Global Asset View for Persona 3 (cargo-plane scenario)
- Fleet Utilization View for Persona 2 (buffer/utilization tradeoff)
- Mapbox / Google Maps integration with custom dark vector style
- Framer Motion choreography for cost roll-ups, arc drawing, dot pulses
- WebSocket connection to consume structured agent outputs live
- Customer-skinnable via `customer.yaml`

**Demo storyboard:**
- Rehearsed 18-minute full arc plus 11-minute S&OP-focused and 5-minute cold-open variants
- Architecture slides between segments (showing the platform components in their conceptual layout)
- Fail-safe scripts (canned agent responses if network drops; canvas in pre-recorded mode if WebSocket drops)

### Customer configuration layer (per customer, 1-2 hours)

A single `customer.yaml` (plus a few asset files) configures everything customer-specific. New customer onboarding is editing this file and redeploying.

```yaml
customer:
  name: "Gulf Petroleum Services"
  logo_path: "branding/gulf_petroleum_logo.svg"
  color_primary: "#0B5394"

terminology:
  service_request: "service shipment"     # vs "service order", "service ticket"
  basin_term: "operating region"          # vs "basin", "geographic unit"
  asset_class: "downhole tool"            # vs "service tool", "equipment"

systems:
  cmms:
    name: "Maximo"                         # or "SAP PM", "Bentley AssetWise"
    mcp_endpoint: "https://..."            # real or mocked
  erp:
    name: "SAP S/4HANA"
    rise_deployment: "google-cloud"        # or "azure", "aws", "on-prem"
    mcp_endpoint: "https://..."

scenarios:
  hero:
    title: "West Africa capacity gap"
    target_location: "Luanda, Angola"
    target_coords: [-8.8390, 13.2894]
    equivalent_asset_location: "Lagos, Nigeria (50km)"
    equivalent_coords: [6.5244, 3.3792]
    naive_option_origin: "Darwin, Australia"
    estimated_savings_usd: 380000
  alternate:
    title: "North Sea winter readiness"
    # ...

canvas:
  map_style: "mapbox://styles/customer/dark-corporate"  # or default dark style
  asset_markers_palette:
    available: "#10b981"
    in_use: "#f59e0b"
    in_repair: "#3b82f6"
    unavailable: "#6b7280"
  basin_focus: "west_africa"   # default zoom region for Persona 3
  fleet_basin: "permian"       # default zoom region for Persona 2

personas:
  - role: "OCC Planner"
    name: "Maria Chen"
    region: "West Africa"
    # ...
```

A new customer engagement asks: do you have a real SAP test environment we should connect to (Pattern A), or do we mock (Pattern B)? What's your hero scenario? Who are your representative personas? Senior CE updates `customer.yaml`, redeploys, demos.

---

## Build plan

### Phase 1 — Core pack (7-9 weeks, two engineers + one frontend engineer part-time)

The Operations Canvas adds approximately one engineer-week to Phase 1. It can run in parallel to the core agent build, but a frontend engineer (separate from the two backend/ADK engineers) is the cleanest way to staff it.

| Week | Backend / ADK stream | Frontend / Canvas stream |
|---|---|---|
| 1 | Fork `next-26-keynotes/devkey/demo-2`, rename agents to our domain, get bare scaffold deploying to Agent Engine | — |
| 2 | Build the six ADK Skills (SKILL.md + scripts + references). Start with `asset-equivalence` and `enterprise-systems` | — |
| 3 | Stand up Apigee MCP proxies for SAP, Maximo, FDP. Mocked backends with realistic-shaped responses | Canvas scaffold: Next.js + Tailwind + shadcn/ui + Mapbox dark style. Static map with dummy asset markers |
| 4 | Knowledge Catalog setup: canonical asset taxonomy, cross-system aliases, functional equivalence graph. Smart Storage on synthetic InTouch bucket | Global Asset View (Persona 3): pulsing markers, arc drawing, Knowledge Catalog drawer, cost roll-up animation |
| 5 | Memory Bank profiles for the six personas. Forecast Review Agent (Persona 1) and Capacity Planning Agent (Persona 2 — long-running, multi-week scheduling agent that resolves Issue 1's over-buffering problem; needs probabilistic start-date forecasting via BigQuery ML and Vertex AI Optimization) | Fleet Utilization View (Persona 2): risk-tolerance slider, utilization heatmap, buffer/CapEx counter |
| 6 | Governance configuration: Agent Identity, Gateway policies, Model Armor, Wiz baseline, monitoring alerts | WebSocket integration between agents and canvas; structured agent output schemas finalized |
| 7 | Storyboard rehearsal, polish, fail-safe modes, architecture slide deck | Canvas polish, motion design pass, fail-safe pre-recorded mode |
| 8 | Internal review with one or two specialist CEs, iterate, lock v1 | Customer skin templating, `customer.yaml` canvas section, two example skins |
| 9 (buffer) | Address feedback from internal review, lock v1 | Final pass, demo dry-runs end-to-end |

### Phase 2 — First customer skin (1-2 weeks, one senior CE)

When the first real customer engagement begins:

| Step | Effort |
|---|---|
| Discovery: confirm customer's actual systems, scenarios, personas, terminology | 1 week |
| Update `customer.yaml`, swap logos and color palette | 2 hours |
| Optionally connect real SAP test environment via Apigee | 1-2 days |
| Optionally add 2-3 customer-specific scenarios to the asset catalog | 1 day |
| Rehearse with customer-specific narration | 1 day |

### Phase 3 — Vertical rollout (ongoing)

Once two customers have been demoed, the pack stabilizes. Subsequent customers should take a single senior CE 1-2 hours to onboard, assuming no real-system integrations.

---

## Reusability across the vertical

The pack is industry-credible because the underlying operational pattern is identical across oilfield services majors. Specifically reusable:

| Element | Reusability rationale |
|---|---|
| Canonical asset taxonomy | Generic oilfield equipment categories work for all majors (drilling tools, MWD/LWD, mud motors, completions equipment, wireline tools) |
| Basin / region terminology | All majors operate in Permian, Bakken, North Sea, Gulf of Guinea, Bohai, deepwater GoM — same geographic vocabulary |
| OCC operational pattern | All majors have OCC-style operations centers with planners doing capacity gap resolution |
| SAP as ERP | All five tier-one majors use SAP (most on RISE) |
| CMMS pattern | Maximo or equivalent in all majors; the abstraction works |
| Procurement audit requirement | All majors have stringent procurement audit; governance demo is universal |
| Cargo-plane / equivalent-asset scenario | Universal pain point across the industry |
| Forecast override pattern (basin leaders) | Universal across all majors with regional management structure |

What's specific to each customer:

| Element | Specific |
|---|---|
| Asset naming conventions (real ones) | Each major has its own internal asset taxonomy |
| Field data platform name | SLB has internal name, Halliburton has internal name, etc. |
| Technical document repository (InTouch is SLB's name) | Each major has its equivalent |
| Customer commercial relationships | Each major has different NOC/IOC customer mix |

The pack's customer-agnostic core is roughly 90% of the demo. The customer skin is 10%. That's the right reusability ratio for a high-volume vertical asset.

---

## Distribution and the path to a Google Cloud Reference Solution

If this lands at one or two customers as planned, the natural next steps move the asset out of your personal toolbox and into Google's:

| Stage | What |
|---|---|
| 1 | Internal Google asset — shared via the CE community, available for any CE engaging an oilfield services customer |
| 2 | Industry Solutions team adoption — listed as the Reference Solution for Oilfield Services in the Solutions catalog |
| 3 | Agent Garden contribution — the agents, skills, and patterns published as samples developers can adopt |
| 4 | Partner accelerator — Accenture / Deloitte / Wipro can use this as the starting point for paid engagements |
| 5 | Public reference architecture — published on the Google Cloud blog and at the next Next |

This trajectory is realistic. Google has done this with other verticals (Healthcare Data Engine, Retail Search). Oilfield services is an underserved vertical with concentrated buying power; an opinionated reference asset has unusually high leverage.

What it requires from you, beyond the build itself: clean documentation, a strong internal demo at Stage 1, willingness to evangelize across the CE community, and an Industry Solutions team relationship (which you may want to start cultivating in parallel to the build).

---

## What to do this week

In rough priority:

1. **Validate scope and ambition internally.** Share this brief with your skip-level and one or two trusted peers. The build is 7-9 weeks for two backend/ADK engineers plus a frontend engineer at ~50% allocation for the Operations Canvas. That staffing needs to be approved before you commit to a customer Gate 2 timeline that depends on it.
2. **Decide build sequencing.** Do Phase 1 first (build the asset) and then engage the first customer, or build for the first customer in Phase 1 and refactor into the reusable pack in Phase 2? Phase-1-first is cleaner; customer-first is faster to revenue. The right call depends on how soon your first customer demo is.
3. **Confirm Industry Solutions team interest.** A 30-minute conversation with the Industry Solutions team for Energy could change Phase 3 economics — if they want to back this asset, you get partner funding and visibility you can't get alone.
4. **Run the keynote demo end-to-end.** Same recommendation as before. The team building Phase 1 needs to have run `make demo-solo` and `make demo-full` on the marathon demo to understand the scaffold viscerally.
5. **Lock the persona scripts and canvas storyboards.** The six personas are the spine of everything; the canvas choreographies for Personas 2 and 3 are the spine of the spatial moments. If you change either later, you re-shoot demo segments. Write the persona briefs and canvas storyboards before engineering starts.

---

## Open questions worth resolving early

- **First customer.** Which of the five tier-one majors is the highest-probability Gate 2 conversion? Build the customer skin for that one first.
- **Staffing.** Two engineers for 6-8 weeks is the minimum. Where do they come from — your own time, specialist pool, partner engagement, Industry Solutions team?
- **SAP test environment access.** Pattern B (mocked) is fine for the core pack. Pattern A (real SAP) is the credibility unlock for any customer where you can get it. Worth asking each major.
- **Customer naming sensitivity.** Anonymized customer names ("Gulf Petroleum") work for the public asset. Per-customer demos use the real customer name. Make this configurable from Day 1.
- **A2UI investment.** The keynote showed A2UI for dynamic UI rendering. For our purposes, Gemini Enterprise app already renders agent responses well. A2UI is high-impact but late-preview; defer unless a customer specifically asks.

---

*End of brief.*
