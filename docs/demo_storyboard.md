# Demo Storyboard — Cargo-Plane Scenario (Persona 3, Maria)

Single source of demo narration for the Agentic S&OP for Oilfield Services live demo. Every beat below is anchored to a `# DEMO NARRATION` cue in the orchestrator codebase. Read this top-to-bottom while rehearsing; the lines in quotes are exactly what the presenter says.

---

## Scenario header

- **Scenario name:** Cargo-plane / capacity-gap (Persona 3)
- **Persona:** Maria Chen — OCC Planner, West Africa region (Gulf Petroleum account)
- **Prompt (typed into Gemini Enterprise):**
  > "I need a Tool X variant in Luanda by Friday — what are my options?"
- **Expected outcome (verified end-to-end 2026-05-20):**
  - `asset:   Tool X-V7 (TX-007)`
  - `src:     Lagos repair shop, Nigeria`
  - `cost:    $162,210`
  - `naive:   $636,353  (Darwin → Luanda cargo charter baseline)`
  - `avoided: $474,143`
  - `blockers: ['Equipment TX-007-LGS-001 has 4 cert hours remaining']`
- **Workflow runtime:** Capacity Orchestrator Workflow (ADK 2.0 graph) on Vertex AI Agent Engine, streamed to the canvas via Vertex AI `streamQuery` REST endpoint.

---

## Beat 0 — Workflow graph reveal (before Maria types)

What's happening: Demoer pulls up the workflow graph in Cloud Trace / docs so the audience sees the shape before any execution.

> **"Here's the workflow graph. This is the Capacity Orchestrator Agent rebuilt as an explicit graph using ADK 2.0's Workflow primitive. Each node is either deterministic code or AI reasoning, and the routing between them is policy expressed as graph edges, not LLM judgment encoded in a prompt. Watch the Cloud Trace as this executes — you'll see the same shape."**
> — `agents/orchestrator_agent/agent.py:75`

Canvas: at rest. Map of West Africa, basin shapefiles dimmed, Maria's identity badge top-right.

---

## Beat 1 — Parse the request (deterministic)

What's happening: `parse_capacity_gap_request` extracts requested asset, target location, and deadline from Maria's natural-language query. No LLM — heuristic extraction scoped to the active customer skin.

> **"First node: parsing Maria's request into a structured form. This is deterministic — no LLM. It pulls out the requested asset, the target location, and the deadline. If anything is ambiguous, the workflow stops here and asks Maria for clarification rather than guessing."**
> — `agents/orchestrator_agent/nodes/parse_request.py:20`

Then, as the first canvas event fires:

> **"And right here we emit the first canvas event — a capacity gap detected at Luanda. The canvas picks this up via the A2A SSE stream and zooms the map onto West Africa."**
> — `agents/orchestrator_agent/nodes/parse_request.py:83`

Canvas: `capacity.gap_detected` — map zooms to Luanda, deadline chip "Friday" appears.

---

## Beat 2 — Resolve to canonical asset (deterministic)

What's happening: `resolve_canonical_asset_node` maps "Tool X variant" to the canonical Knowledge Catalog id (TX-001) and tags the target region as `west_africa`. This is where taxonomic chaos dies before the parallel queries even leave the building.

> **"Second node: resolving the asset to a canonical id. The Knowledge Catalog answers in canonical entities — TX-001, not MAT-67890 or EQ-12345. Issue 4 — taxonomic chaos — is resolved here, before any enterprise-system query goes out. Still deterministic, still no LLM."**
> — `agents/orchestrator_agent/nodes/resolve_asset.py:14`

Supporting line from inside the skill (use if a customer asks "how does the agent know what Tool X means?"):

> **"This is the resolution moment — the agent doesn't reason about aliases, the catalog does."**
> — `agents/orchestrator_agent/skills/asset-equivalence/scripts/tools.py:89`

Canvas: side panel switches to "Active gap" view; canonical id chip resolves to `TX-001`.

---

## Beat 3 — Parallel system queries (deterministic fan-out)

What's happening: `parallel_system_queries` fans out four concurrent MCP calls — Maximo (asset availability), SAP ZHR_WORKFORCE (workforce by basin), FDP (customer config), Knowledge Catalog (InTouch specs).

Setup line (delivered before the fan-out, while pointing at the toolset config):

> **"Notice the MCP toolsets are pointed at Agent Gateway — not at the SAP / Maximo / FDP Cloud Run URLs directly. Every call goes through Gateway: IAM authorization on the Orchestrator's Agent Identity, Model Armor scan against prompt injection, audit log line, then routed to the registered MCP server. Our code reasons about WHAT to ask; the platform handles WHO is asking and whether it's safe."**
> — `agents/orchestrator_agent/nodes/parallel_queries.py:279`

Main beat line (delivered as the four pills light up):

> **"Now the workflow fans out — four parallel queries against Maximo, SAP, FDP, and Knowledge Catalog. All running concurrently, all through MCP. In production every call routes via Agent Gateway with Model Armor in the path; locally we short-circuit to in-process skill calls for fast iteration. No LLM in this step; the agent isn't deciding what to do, the workflow is. This is what makes agentic AI defensible to procurement audit — predictable steps, parallel execution, full trace."**
> — `agents/orchestrator_agent/nodes/parallel_queries.py:460`

Reinforcer (delivered if the demoer wants to pause on the canvas animation):

> **"Notice the trace — and the canvas. Four parallel MCP calls light up as pills, one per system. The canvas is consuming events from the Workflow via the A2A SSE stream. This isn't polling; it's the agent broadcasting its state."**
> — `agents/orchestrator_agent/nodes/parallel_queries.py:479`

Canvas: four `mcp.call.started` pills appear simultaneously (Maximo, SAP, FDP, KC), then four matching `mcp.call.completed` events flip them green.

---

## Beat 4 — Evaluate direct availability (deterministic)

What's happening: `evaluate_direct_availability` reads the Maximo response, filters for deployable instances in West Africa, and stamps a boolean. In the cargo-plane scenario, no deployable TX-001 exists in West Africa — flag is `False`, kicking off the equivalence path.

> **"Third node: deterministic availability check. We look at the Maximo instances the parallel query returned, filter to the ones that are actually deployable, and stamp a boolean on the payload. The router downstream just reads that boolean — no LLM judgment, no surprise routing. Predictable enough to put in front of a procurement audit."**
> — `agents/orchestrator_agent/nodes/evaluate_availability.py:44`

Canvas: Maximo pill annotates "0 deployable instances in West Africa." No structured event for this beat in canvas_events.py — the router decision event in Beat 5 carries the visible state.

---

## Beat 5 — Route on availability (router)

What's happening: `route_on_availability` reads `direct_available=False` and routes to the equivalence-reasoning path.

> **"First routing decision. If direct availability exists, we take the fast path — build a plan with the existing asset. If not, we go into the equivalence pathway, where the agent reasons about functional substitutes. This is a deterministic check, not an LLM judgment."**
> — `agents/orchestrator_agent/nodes/routers.py:67`

Canvas: `router.decision` event — side panel shows the branch chosen with rationale "No direct availability — proceeding to equivalence reasoning."

---

## Beat 6 — Equivalence lookup (FIRST LLM node)

What's happening: `equivalence_lookup_agent` is the first AI in the workflow. It calls Knowledge Catalog via the managed Dataplex MCP server through Agent Gateway, reads Tool X's functional-equivalence aspect (InTouch §3.2 → TX-007 is an approved substitute), and returns a structured `EquivalentAssetCandidate` with confidence + rationale source.

> **"First AI node in the workflow — and this is where Issue 4 dissolves visibly. The equivalence agent is calling Knowledge Catalog through Agent Gateway. The MCP server itself is managed by Google Cloud — we don't host it, we don't run it. When the Dataplex API is enabled the remote MCP server at dataplex.googleapis.com/mcp is enabled automatically. The catalog returns the canonical Tool X entry with all its aliases — SAP material number, Maximo equipment ID, FDP config ID — and the functional equivalence Aspect listing Tool X-V7 as a substitute per InTouch spec §3.2. One call. One canonical entity. No taxonomic chaos. No infrastructure we own. Gemini reasons against that canonical entity and returns a structured candidate with confidence score and rationale source. One job. Predictable input, structured output, no instruction sprawl."**
> — `agents/orchestrator_agent/nodes/equivalence_lookup.py:275`

Supporting line from inside the skill (use to underline the pivot moment):

> **"This is where the cargo-plane scenario pivots. The agent ..."**
> — `agents/orchestrator_agent/skills/asset-equivalence/scripts/tools.py:200`

Canvas: `equivalence.found` event — drawer slides in with TX-001 → TX-007 mapping, confidence score, "Source: InTouch spec §3.2."

---

## Beat 7 — Build the equivalent plan (deterministic)

What's happening: `build_equivalent_plan` takes the LLM's chosen substitute (TX-007), picks a Maximo instance of it (TX-007-LGS-001 at Lagos repair shop), and assembles a `SourcingPlan`. Pure data join — the LLM identified WHAT, the workflow grounds the plan in concrete tool-returned data.

> **"Equivalence-path plan builder. The equivalence LLM node already returned a candidate substitute canonical id; we pick a Maximo instance of that substitute, assemble a SourcingPlan, and forward. Again, no LLM here — the AI's job was to identify the substitute; the workflow's job is to ground the plan in concrete tool-returned data."**
> — `agents/orchestrator_agent/nodes/build_plans.py:144`

Companion line (in case the demo accidentally takes the direct path — not in cargo-plane, but worth knowing for Q&A):

> **"Direct-path plan builder. We found a deployable instance in the target region — assemble the SourcingPlan from Maximo location data, transit estimates, and the customer's FDP config. Pure data join. The LLM in the next node will refine the logistics narrative on top of this shape."**
> — `agents/orchestrator_agent/nodes/build_plans.py:100`

Canvas: side panel updates with source = Lagos, destination = Luanda, asset chip flips to TX-007.

---

## Beat 8 — Sourcing logistics (SECOND LLM node)

What's happening: `sourcing_logistics_agent` refines the deterministically-built plan with logistics reasoning grounded in Google Maps — transit mode (Lagos → Luanda sea freight, ~$162K), transit hours, blocker identification ("4 cert hours remaining on TX-007-LGS-001").

> **"Second AI node: refining the plan with logistics judgment. Transit mode, cost envelope, blocker identification. Gemini's role here is to apply real-world logistics reasoning that's hard to encode in pure rules — like 'this customs route adds 12 hours, recommend sea freight instead.'"**
> — `agents/orchestrator_agent/nodes/sourcing_logistics.py:126`

Canvas: `route.recommended` event — route line drawn Lagos → Luanda, cost chip $162,210, transit mode badge ("Sea freight"), blocker chip "4 cert hours remaining."

---

## Beat 9 — Plan Evaluator (LLM-as-Judge, bundled in-process)

What's happening: `plan_evaluator_tool` (AgentTool wrapping the bundled Plan Evaluator) scores the SourcingPlan on 7 weighted criteria and returns a structured `PlanEvaluation`. In the cargo-plane scenario the plan scores ≥0.85 on the first pass — no revision loop needed.

> **"The Plan Evaluator is an LLM-as-Judge — same pattern Google showed in the Next '26 keynote marathon demo. Seven criteria specific to oilfield services: safety, customer compatibility, logistics feasibility, cost, equivalence confidence, regulatory, schedule. Each weighted, all aggregated into an overall_score the Orchestrator iterates against."**
> — `agents/orchestrator_agent/plan_evaluator/agent.py:103`

Architecture note (delivered when the customer asks "is the evaluator a separate agent?"):

> **"The Plan Evaluator is bundled in-process via AgentTool — no network hop, sub-second response. Seven weighted criteria specific to oilfield services sourcing decisions."**
> — `agents/orchestrator_agent/tools.py:126`

Canvas: side panel shows score breakdown ring chart; overall score 0.91 (or similar — exact number varies per run).

---

## Beat 10 — Route on evaluation score (router)

What's happening: `route_on_evaluation_score` checks 0.91 ≥ 0.85 threshold → routes `PROCEED` (no revision needed). If it had been lower, the workflow would loop through `revise_plan_agent` up to 2 times before exhausting.

> **"After the Plan Evaluator scores the plan, we check the threshold. Score of 0.85 or higher: we proceed. Below: we send the plan back to be revised. Maximum of two revision loops to avoid runaway iteration. This is the kind of control structure that's hard to enforce in a pure LLM agent — here it's just a Python conditional."**
> — `agents/orchestrator_agent/nodes/routers.py:87`

Backup line (use if the live run trips into a revise loop):

> **"If the Plan Evaluator scores below threshold, we revise. This node takes the original plan plus the evaluator's findings and produces an improved plan. The workflow then re-evaluates. Up to two iterations. This is the kind of self-improvement loop that's structural in our Workflow, not behavioral in a prompt — the loop limit is a Python integer, not a request to the model to please stop after two tries."**
> — `agents/orchestrator_agent/nodes/revise_plan.py:58`

Canvas: `router.decision` event with rationale "Score 0.91 >= threshold 0.85."

---

## Beat 11 — Route on procurement threshold (router)

What's happening: `route_on_procurement_threshold` reads the $162,210 cost and the one blocker. Cost is below $500K — but the blocker (`4 cert hours remaining`) forces `REQUIRES_APPROVAL`. The plan goes to the Procurement Approval Agent over A2A.

> **"Final routing — does this plan need procurement approval? Above $500K or any non-trivial blocker, yes. Below that threshold the OCC planner can self-approve. This threshold is policy, not LLM judgment — it lives right here in the workflow next to the audit log."**
> — `agents/orchestrator_agent/nodes/routers.py:148`

Canvas: `router.decision` event — rationale "Cost $162,210 under threshold but 1 blocker present — procurement approval required."

---

## Beat 12 — Procurement Approval Agent (remote A2A call)

What's happening: The Orchestrator calls the Procurement Approval Agent over A2A. This is the only remote agent-to-agent hop in the workflow. It runs on Agent Engine, checks prerequisites deterministically (budget, customer auth, cert chain, regulatory), and returns a `ProcurementApproval` verdict.

> **"The Procurement Approval Agent runs on Agent Engine, called via A2A protocol — the open standard that bridges to SAP Joule agents. Cryptographically signed agent cards, runtime policy enforcement via Agent Gateway."**
> — `agents/orchestrator_agent/tools.py:139`

Companion line (from the agent's own definition; use during the architecture overview slide, not during live execution):

> **"The Procurement Approval Agent is the final gate before logistics dollars commit. Fast — no LLM reasoning depth needed, just deterministic prerequisite checks. Runs on Agent Engine. Called by the Orchestrator via A2A — the same protocol that bridges to SAP Joule agents."**
> — `agents/procurement_approval_agent/agent.py:38`

Canvas: A2A call pill appears (different shape from MCP pills to make the agent-to-agent distinction visible). Approval verdict surfaces with the cert-hours blocker called out as an accepted exception.

---

## Beat 13 — Finalize (deterministic — the money shot)

What's happening: `finalize_sourcing_plan` builds the naive baseline (Darwin → Luanda cargo charter, $636,353), computes `avoided_cost_usd = $636,353 − $162,210 = $474,143`, and emits the `workflow.completed` event with the full final output.

> **"Final node: compute avoided_cost_usd against the naive-baseline option — the cargo charter Maria would have ordered without the workflow. This is the number the OCC director sees on the canvas: 'saved $380K vs. baseline.' Deterministic, traceable, defensible."**
> — `agents/orchestrator_agent/nodes/finalize.py:64`

> Note: the narration line says "$380K" because it was written during an earlier tuning pass; current numbers settle at **$474K avoided**. Demoer should say the live number, not the comment number.

Canvas: cost rollup A2UI surface drains and renders — three big numbers side by side (`$636K doomed` / `$162K recommended` / `$474K avoided`). `workflow.completed` event closes out the trace.

---

## Final state — what the OCC director sees

The canvas freezes on the final summary. Maria's Agent Inbox shows one item awaiting approval:

```
Asset:     Tool X-V7 (TX-007)
Source:    Lagos repair shop, Nigeria
Cost:      $162,210         (sea freight, Lagos → Luanda)
Naive:     $636,353         (Darwin → Luanda cargo charter)
Avoided:   $474,143
Blockers:  ['Equipment TX-007-LGS-001 has 4 cert hours remaining']
```

The OCC director's headline: **half a million dollars avoided, with full provenance — every alias resolved through Knowledge Catalog, every cross-system query auditable through Agent Gateway, every decision traceable to either a deterministic policy or an LLM node with structured output.**

---

## Spec deviations to acknowledge during demo

A handful of pragmatic deviations from SPECS.md. If a customer architect calls them out, acknowledge upfront — don't get caught defending.

- **Plan Evaluator is bundled in-process via AgentTool, not a 5th standalone agent.** SPECS describes five agents; we ship four (Orchestrator + Procurement Approval + Forecast Review + Capacity Planning) and run the Plan Evaluator as an in-process `AgentTool` inside the Orchestrator. Sub-second judging, zero A2A overhead, same `LlmAgent` definition — just no separate Agent Engine deploy. The change is visible in `agents/orchestrator_agent/tools.py:create_plan_evaluator_tool`.
- **Streaming uses Vertex AI `streamQuery` REST endpoint, not a WebSocket gateway.** Per TASK-10's SHIPPED PATTERN note, the canvas consumes `state_delta` events directly off the Agent Engine `streamQuery` REST endpoint over SSE rather than the originally-planned WebSocket gateway service. One less component to deploy, identical event semantics on the wire.
- **MCP skill composers go BQ-direct on the critical path.** The Cloud Run MCP servers (Maximo / SAP / FDP) exist and are deployed as a tech demo proving the Agent-Gateway-mediated path works, but the live demo's parallel-query node runs in-process against BigQuery synthetic data for reproducibility and latency. Same skill function signatures either way — the `via_gateway` toggle in `parallel_queries.py` is the only line that differs.

---

## Fallback modes (per TASK-10)

If wifi craps out or Vertex AI Agent Engine throws a `503`, the demo still runs. Two backups, both producing identical canvas behavior to Live mode:

- **Static mode** — `make demo-static` plays the canvas straight from a pre-recorded JSON trace of a Live run. No backend dependencies. Use this if the demo machine has zero network.
- **Replay mode** — `make demo-replay` runs the Orchestrator locally (in-process skill calls, no Agent Gateway, no Agent Engine) and streams its real events to the canvas. Use this if Google Cloud is unreachable but the demo laptop is healthy. All beats fire; only the platform-side narration lines (Agent Gateway, Model Armor) require the demoer to say "in production this routes through Gateway" instead of pointing at the live trace.

Pick the fallback mode at the start of the demo (don't hot-swap mid-run). Replay is the preferred fallback because it still exercises real Python code; Static is the panic button.
