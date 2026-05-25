# Demo walkthrough — Agentic S&OP for Oilfield Services

One doc, two jobs: learn what's built, run the demo. Replaces `demo_guide.md` + `demo-handbook.md` + `demo_storyboard.md` (currently still present alongside this — delete once you're confident this covers what you need).

**Principle:** every beat in this doc is honestly labelled `[LIVE]`, `[STATIC + live moment]`, `[STATIC]`, or `[PLATFORM PRODUCT]`. If a beat narrates the agent doing X, X actually happens. The demo's credibility depends on never narrating fiction.

**Per-beat structure:**
- **On screen** — what the audience sees
- **Under the hood** — the file/code path, *why* this design exists vs. alternatives
- **Say** — bullet cues you improvise from, not verbatim
- **Likely questions** — what a sharp customer asks, with the answer
- **Gaps** — empty for you to fill as you practice

---

## 1. State of the demo (verified 2026-05-22)

| Persona | Surface | Backend | Live moments |
|---|---|---|---|
| **3 — Maria (cargo-plane)** | `/scenarios/cargo-plane` | Orchestrator Workflow on Agent Engine (`3863088474458423296`) + Procurement Approval over A2A (`3638823286764208128`) | **Full workflow live** — 13 beats, real SSE stream, real $474K math |
| **1 — David (forecast)** | `/scenarios/forecast-review` | Forecast Review Agent on Agent Engine (`5040779777015808000`) | **Beat 3 live** — agent classifies David's freeform note into rationale tags. Beats 0–2, 4–5 are scripted choreography. |
| **2 — Tomas (buffer)** | `/scenarios/buffer-planning` | Capacity Planning Agent on Agent Engine (`2734936767802114048`) | **Beats 2 + 3 live** — agent computes the 14→8 day model (risk 0.5), then the counter-proposal (risk 0.7). Other beats are scripted. |
| 4 — Priya (deep research) | `/scenarios/deep-research` | Stub at `/api/deep-research/run` returns 501 honestly until DRA is wired | **Beat 1 fires live call** (returns "not provisioned" today; gap-fix is one file). Seeded briefing grounded in real BLS / Baker Hughes / SAP MARC data. **Interactive citation drill-down** opens source records. |
| 5 — Rafael (agent studio) | `/scenarios/agent-studio` | Launchpad page — links out to real Agent Studio in tenant + recorded fallback + inline rehearsal script. No scripted preview. | None on-page (Agent Studio is external — Rafael's actual experience starts in the new tab). Env vars `NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL` + `NEXT_PUBLIC_AGENT_STUDIO_RECORDING_URL` enable the buttons. |
| 6 — Ayesha (audit) | `/audit/registry` | Three A2UI panels (Registry / Gateway / Model Armor) reading from `data/a2uiSamples.ts`. Passive viewer — no trigger buttons. | Mock data with honest `data: mock` indicator. Auditor's role IS to view recent activity; she doesn't trigger anything. |

The platform line ("everything you see runs on Gemini Enterprise Agent Platform — Agent Runtime, Agent Registry, Agent Gateway, Model Armor") is **defensible for Personas 1, 2, 3**. For 4, 5, 6 today, it's an *aspiration backed by infra* — be careful with that claim in front of an audit-minded customer.

---

## 2. Pre-demo verification

Run 45 minutes before the demo from the repo root:

```bash
source venv/bin/activate
set -a && source .env && set +a

# Programmatic smoke — data flow, no LLM, ~5s
make smoke-cargo-plane            # 11/11 checks

# Fast evals — schema + trajectory, no LLM, ~2s
make evals                        # 33 passed, ~22 skipped (live-gated)

# Live evals — exercises all 4 deployed agents, ~13 min, ~$1
source venv-deploy-310/bin/activate
python -m pytest agents/*_agent/evals/ \
  agents/orchestrator_agent/plan_evaluator/evals/ \
  --run-live-evals -q             # 52 passed, 1 xfailed (known persona-1 multi-tag gap)
```

Then start the canvas:

```bash
cd canvas && npm run dev          # localhost:3000
```

Press `1`-`6` to cycle the launcher tiles once. Pre-warm Persona 3 by pressing `3` then `Space` through all 13 beats; reset with `R`.

If any of the above fails, **fix before walking in.** Common causes documented inline in the existing `demo-handbook.md §0`.

---

## 3. The canonical numbers (Persona 3)

Baked into the eval suite — change here only by changing the eval first.

| Field | Value |
|---|---|
| Requested asset | Tool X |
| Canonical substitute | TX-007 (Tool X-V7) |
| Source location | Lagos, Nigeria (repair shop) |
| Primary cost | **$162,210** |
| Naive baseline | Darwin → Luanda cargo charter, $636,353 |
| **Avoided cost** | **$474,143** |
| Blockers | 1 (cert hours remaining on TX-007-LGS-001) |
| Workflow runtime | ~115 seconds |

If your demo doesn't surface these, something has drifted — run `make smoke-cargo-plane` and the live eval before continuing.

---

## 4. Keyboard reference

**The hotkeys exist for the demoer's rehearsal flow, not for the real-world experience.** In live mode every persona auto-plays — you don't press anything; you narrate. In static mode (for rehearsal without burning agent budget) the keys below take over.

Plain letters/digits only — no Cmd/Ctrl combos (they conflict with the browser).

| Key | Action | When relevant |
|---|---|---|
| `1`–`6` | Jump to persona N | Always |
| `0` / `Home` | Launcher | Always |
| `Space` | Advance beat (manual override) | Static mode; live mode also accepts it to skip ahead |
| `Shift+Space` / `B` | Previous beat | Static / rehearsal |
| `R` | Reset current scenario | Always |
| `L` | Toggle live ↔ static (Personas 1, 2, 3, 4) | Pick once at demo start |
| `P` | Pause auto-advance | Live mode (when you want to talk longer between beats) |
| `\` | Backstage panel (presenter cues) | Always |
| `?` | Help overlay | Always |

**In live mode you'll typically only press `1`–`6` and `\`.** Everything else is rehearsal scaffolding.

---

## 5. Persona 3 — Maria (OCC West Africa) — centerpiece, 5 min

The only persona where every beat reflects real agent work. The whole demo's credibility lives here — don't rush it.

**Opening prompt (verbatim, eval-locked):**
> "I need a Tool X variant on site in Luanda, Angola by Friday. Customer: Gulf Petroleum. Authorization tier: standard. What are my options?"

### Beat 0 — Workflow graph reveal (pre-typing)
- **On screen:** map of West Africa at rest, Maria's identity badge top-right
- **Under the hood:** `agents/orchestrator_agent/agent.py:75` — the ADK 2.0 Workflow primitive's graph. Each node is either deterministic Python or one LLM agent. Routing is policy expressed as edges, not LLM judgment inside a prompt.
- **Say:** show the workflow graph (Cloud Trace or docs). Frame: "this is the planning surface — explicit graph, not a conversation."
- **Likely questions:**
  - *"Why not just one big agent?"* → Predictability + audit defensibility. Each node has one job; the routing is a Python conditional you can point at.
- **Gaps:** ___

### Beat 1 — Parse request `[deterministic]`
- **On screen:** `capacity.gap_detected` event fires → map zooms to Luanda, "Friday" deadline chip
- **Under the hood:** `agents/orchestrator_agent/nodes/parse_request.py:20` — heuristic extraction, no LLM. Customer-skin-scoped. If ambiguous, the workflow stops and asks for clarification rather than guessing.
- **Say:** "deterministic parse — pulls out asset, location, deadline. If anything is unclear, the workflow stops here."
- **Likely questions:** none usually.
- **Gaps:** ___

### Beat 2 — Resolve canonical asset `[deterministic]`
- **On screen:** side panel switches to "Active gap"; canonical id chip resolves to `TX-001`
- **Under the hood:** `agents/orchestrator_agent/nodes/resolve_asset.py:14` — maps "Tool X variant" → canonical `TX-001` via Knowledge Catalog. Taxonomic chaos dies here before parallel queries leave the building.
- **Say:** "Knowledge Catalog answers in canonical entities. Issue 4 (taxonomic chaos) resolved before any enterprise-system query."
- **Likely questions:**
  - *"How does it know 'Tool X' maps to TX-001?"* → Knowledge Catalog equivalence Aspect (in InTouch spec §3.2). Click the canonical id chip — drawer opens with all 4 system aliases.
- **Gaps:** ___

### Beat 3 — Parallel system queries `[deterministic fan-out]`
- **On screen:** four `mcp.call.started` pills appear simultaneously (Maximo, SAP, FDP, KC), flip green as they complete
- **Under the hood:** `agents/orchestrator_agent/nodes/parallel_queries.py:460` — four concurrent MCP calls. In production they route through Agent Gateway (IAM + Model Armor + audit log per call). Locally we short-circuit to in-process skill calls for latency + reproducibility — the `via_gateway` toggle is the only line that differs.
- **Say:** "four parallel MCP calls. Code decides WHAT to ask; platform handles WHO is asking and whether it's safe."
- **Likely questions:**
  - *"Are these calls actually parallel?"* → Yes — `asyncio.gather`. Cloud Trace confirms.
  - *"What if one fails?"* → Each query is independent; downstream nodes degrade gracefully. The evaluator scores partial-data plans lower.
- **Gaps:** ___

### Beat 4 — Evaluate direct availability `[deterministic]`
- **On screen:** Maximo pill annotates "0 deployable instances in West Africa"
- **Under the hood:** `agents/orchestrator_agent/nodes/evaluate_availability.py:44` — reads Maximo response, filters to deployable-in-region, stamps a boolean. Router downstream just reads that boolean.
- **Say:** "deterministic availability check — no LLM judgment, no surprise routing."
- **Gaps:** ___

### Beat 5 — Route on availability `[router]`
- **On screen:** `router.decision` event — "No direct availability — proceeding to equivalence reasoning"
- **Under the hood:** `agents/orchestrator_agent/nodes/routers.py:67` — checks `direct_available=False` → equivalence path.
- **Say:** "first routing decision. If direct available existed, we'd take the fast path. Predictable enough for procurement audit."
- **Gaps:** ___

### Beat 6 — Equivalence lookup `[FIRST LLM NODE]`
- **On screen:** `equivalence.found` event → drawer slides in with TX-001 → TX-007 mapping, confidence score, "Source: InTouch spec §3.2"
- **Under the hood:** `agents/orchestrator_agent/nodes/equivalence_lookup.py:275` — first LLM call. Reaches Knowledge Catalog through Agent Gateway → managed Dataplex MCP. The catalog returns canonical entry + functional-equivalence aspect. Gemini returns `EquivalentAssetCandidate` (confidence + rationale source). One job, structured output.
- **Say:** "first AI in the workflow. Knowledge Catalog is the managed MCP — Google hosts it, we don't. One canonical call, no taxonomic chaos."
- **Likely questions:**
  - *"Why pick V7 not V6 or V8?"* → InTouch spec §3.2 lists V7 as the approved substitute. Open the drawer's citation link.
  - *"What if the LLM hallucinates?"* → Output schema (`EquivalentAssetCandidate`) enforces structure. The rationale_source must reference a real KC entry — validated in the next node.
- **Gaps:** ___

### Beat 7 — Build equivalent plan `[deterministic]`
- **On screen:** side panel updates — source Lagos, destination Luanda, asset chip flips to TX-007
- **Under the hood:** `agents/orchestrator_agent/nodes/build_plans.py:144` — pure data join. LLM picked the substitute; this node grounds it in Maximo instance data (`TX-007-LGS-001`).
- **Say:** "AI identified the substitute; workflow grounds the plan in real tool data. Clean separation."
- **Gaps:** ___

### Beat 8 — Sourcing logistics `[SECOND LLM NODE]`
- **On screen:** `route.recommended` event — route line drawn Lagos → Luanda, cost chip $162,210, "Sea freight", "4 cert hours remaining" blocker
- **Under the hood:** `agents/orchestrator_agent/nodes/sourcing_logistics.py:126` — Gemini applies logistics judgment (transit mode, customs, cert hours). Grounded in Google Maps + Maximo work-order data.
- **Say:** "second AI node — logistics reasoning. Rules can't capture 'this customs route adds 12 hours'; LLM does."
- **Gaps:** ___

### Beat 9 — Plan Evaluator `[LLM-as-Judge, in-process]`
- **On screen:** ring chart appears — overall score (e.g. 0.91), seven criterion breakdowns
- **Under the hood:** `agents/orchestrator_agent/plan_evaluator/agent.py:103` — bundled via `AgentTool` inside Orchestrator (sub-second response, no network hop). Seven oilfield-specific criteria, each weighted.
- **Say:** "LLM-as-Judge — same pattern as the Next '26 marathon demo. Seven criteria, weighted into an overall score."
- **Likely questions:**
  - *"Why bundled not deployed separately?"* → ADR-0003 (`docs/governance.md §3.0`). Sub-second judging, zero A2A overhead, same `LlmAgent` definition.
- **Gaps:** ___

### Beat 10 — Route on evaluation score `[router]`
- **On screen:** `router.decision` — "Score 0.91 >= threshold 0.85"
- **Under the hood:** `agents/orchestrator_agent/nodes/routers.py:87` — score ≥ 0.85 → PROCEED. Else REVISE (max 2 iterations).
- **Say:** "control structure as a Python conditional — loop limit is an integer, not a polite request to the model."
- **Gaps:** ___

### Beat 11 — Route on procurement threshold `[router]`
- **On screen:** `router.decision` — "Cost $162,210 under threshold but 1 blocker present — procurement approval required"
- **Under the hood:** `agents/orchestrator_agent/nodes/routers.py:148` — > $500K or any blocker → REQUIRES_APPROVAL.
- **Say:** "threshold is policy. Lives next to the audit log, not inside a prompt."
- **Gaps:** ___

### Beat 12 — Procurement Approval `[remote A2A call]`
- **On screen:** A2A call pill (different shape from MCP pills) → approval verdict with the cert-hours exception
- **Under the hood:** `agents/orchestrator_agent/tools.py:139` + `agents/procurement_approval_agent/agent.py:38` — separate Agent Engine deployment, called via A2A. The only inter-agent hop in the workflow.
- **Say:** "A2A protocol — open standard. Same one that bridges to SAP Joule agents."
- **Gaps:** ___

### Beat 13 — Finalize (the money shot) `[deterministic]`
- **On screen:** three big numbers fly in: `$636K doomed` / `$162K recommended` / `$474K avoided`
- **Under the hood:** `agents/orchestrator_agent/nodes/finalize.py:64` — computes naive baseline (Darwin charter), subtracts primary. Pure arithmetic, fully traceable.
- **Say:** "the number wasn't typed in. It fell out of the math. Every step traceable."
- **Likely questions:**
  - *"How do I know the $636K baseline is realistic?"* → It's the actual market rate for Darwin → Luanda cargo charter (1 stop, 13,200 km). Tunable via `data/anchors/`.
- **Gaps:** ___

**Closing line:** "One agent, four enterprise systems, one Knowledge Catalog, one canonical answer. The cargo plane never had to take off."

---

## 6. Persona 1 — David (Permian Basin Director), 3 min

Forecast review with one live LLM moment (rationale-tag extraction). In live mode the page auto-plays — David's review unfolds without you touching the keyboard. The live call to the Forecast Review Agent fires at the moment David submits his override; the beat after that waits for the response before advancing.

**Opening prompt (David's chat bubble):**
> "Show me Q4 by basin — I want to override two basins where the model is missing the rig-count slowdown."

### Beat 0 — At rest `[STATIC]`
- **On screen:** seven basin tiles loading area; David's chat bubble shows his opening line
- **Under the hood:** `canvas/src/data/scenarios/forecastReview.ts:165`
- **Say:** "David owns the Q4 forecast for the largest US shale basin. He's about to argue with the model."
- **Gaps:** ___

### Beat 1 — Forecast loaded `[STATIC]`
- **On screen:** seven basin tiles render (Permian $215M, Gulf $145M, …); confidence pills
- **Under the hood:** synthetic Q4 baseline from `BASELINE_TILES`. In production this would come from BQ ML; for the demo we use a stable dataset so numbers don't shift.
- **Say:** "ML baseline from BigQuery. Confidence pills from the model itself."
- **Likely questions:**
  - *"Is this real BQ ML output?"* → Static synthetic data calibrated to look like a real oilfield major's Q4 mix. Live wiring is a customer-deploy step.
- **Gaps:** ___

### Beat 2 — Override prompt `[STATIC]`
- **On screen:** Permian tile shows `promptOpen: true` — "Why is the model wrong here?"
- **Under the hood:** `forecastReview.ts:194`
- **Say:** "Agent Inbox surfaces a structured prompt. David picks a freeform reason."
- **Gaps:** ___

### Beat 3 — Rationale extracted `[LIVE]` ★
- **On screen:** rationale chips appear under the Permian tile (`rig_count_decline`, `operator_pause`, `permian_specific`). Chat panel shows a sky-blue `LiveAgentBubble`: "Forecast Review Agent · live" with the returned tags + confidence.
- **Under the hood:**
  - `canvas/src/app/scenarios/forecast-review/page.tsx` triggers `useAgentCall<ForecastRationale>` on entry to beat 3
  - POSTs through `/api/orchestrator/stream` proxy → deployed Forecast Review Agent (`5040779777015808000`)
  - Consumes the SSE stream; final structured `ForecastRationale` output's `rationale_tags` replace the static `PERMIAN_TAGS` on the Permian tile
  - On error: falls back to static `PERMIAN_TAGS`. `LiveStatusPill` top-left reflects state
- **Say:** "this beat is the agent. Watch the tags appear — they came from a real Gemini call classifying David's freeform note."
- **Likely questions:**
  - *"How does it know to pick those specific tags?"* → Skill at `agents/forecast_review_agent/skills/forecast-rationale/references/rationale_tags.md` defines the tag taxonomy. Gemini matches the text against it.
  - *"What if the agent times out?"* → `LiveAgentBubble` shows error; UI falls back to static tags so the rest of the demo continues. Press `L` to flip to static-only.
- **Gaps:** ___

### Beat 4 — Overrides applied `[STATIC]`
- **On screen:** Permian → $186M, Gulf → $130M; bottom delta banner rolls up
- **Under the hood:** scripted — the Gulf override is shown for narrative completeness but only the Permian call is live. Honest framing in narration: "and the same flow runs for Gulf."
- **Say:** "delta banner rolls up — $44M off the Q4 plan. Model gets retrained with David's rationale."
- **Gaps:** ___

### Beat 5 — Saved confirmation `[STATIC]`
- **On screen:** toast — "Q4 forecast saved as v2"
- **Say:** "every override now lives in Memory Bank's `rationale_patterns` topic. Next quarter's model ingests it."
- **Gaps:** ___

---

## 7. Persona 2 — Tomas (Permian Fleet Scheduler), 3 min

Buffer planning with two live LLM moments (initial 14→8 drop, then risk-adjusted counter-proposal). In live mode the page auto-plays — Tomas's session unfolds without you touching the keyboard. Each live call gates its beat: tiles update from the agent's real response before the next beat lands.

**Opening prompt (Tomas's chat bubble):**
> "Show me Permian fleet utilization and the buffer trade-off — I want to drop the buffer from 14 to 8 days and see what the on-time rate does."

### Beat 0 — Permian overview `[STATIC]`
- **On screen:** 30-day fleet timeline at 14-day buffer; Tomas's chat bubble
- **Under the hood:** `canvas/src/data/scenarios/bufferPlanning.ts:160`
- **Say:** "Tomas runs West Texas fleet allocation. Static 14-day buffer = real CapEx idle."
- **Gaps:** ___

### Beat 1 — Current state surfaces `[STATIC]`
- **On screen:** stat tiles: 14d / 92% on-time / 68% utilization / $0 deferred
- **Under the hood:** deterministic mapping in `bufferPlanning.ts:fleetStatsForBuffer(14)`
- **Say:** "status quo. 14-day buffer, 92% on-time, 68% utilization. Risk tolerance at 0.5."
- **Gaps:** ___

### Beat 2 — Buffer drop modeled `[LIVE]` ★
- **On screen:** stat tiles flip to ~84% utilization, ~65% on-time, ~$4.5M deferred (live numbers may differ — that's the point). Chat shows `LiveAgentBubble`: "Capacity Planning Agent · 14→8 day model @ risk 0.5".
- **Under the hood:**
  - `canvas/src/app/scenarios/buffer-planning/page.tsx` triggers `dropCall.run(BUFFER_DROP_PROMPT)` on entry to beat 2
  - Posts to the Capacity Planning Agent (`2734936767802114048`)
  - Returns `BufferOptimization { recommended_buffer_days, projected_on_time_rate, fleet_utilization_uplift_pct, deferred_capex_usd }`
  - Stat tiles + timeline (`buildTimeline(recommended_buffer_days)`) reflect live values
- **Say:** "the agent ran BQ ML against Permian start-date distributions. Those numbers are real. Utilization climbs, on-time collapses — that's the trade-off."
- **Likely questions:**
  - *"Why doesn't the live result exactly match the script?"* → Different BQ ML run + LLM stochasticity. Static values are a calibrated representative case. The point is the *relationship* — buffer drop → utilization up, on-time down.
  - *"How does the agent compute these?"* → Skill `scheduling-probability` with three BQ ML functions: distribution, optimal buffer, utilization impact. See `agents/capacity_planning_agent/skills/scheduling-probability/`.
- **Gaps:** ___

### Beat 3 — Counter-proposal `[LIVE]` ★
- **On screen:** stat tiles re-flow to ~76%/78%/$3.2M (the 10-day compromise). `LiveAgentBubble` updates to "counter-proposal @ risk 0.7".
- **Under the hood:**
  - `counterCall.run(BUFFER_COUNTER_PROMPT)` fires on entry to beat 3
  - At risk_tolerance=0.7 the agent should counter-propose a more conservative buffer
- **Say:** "Tomas bumps risk tolerance to 0.7. Agent re-runs the optimization — counter-proposes a 10-day buffer instead. Safer compromise for an XOM commitment."
- **Likely questions:**
  - *"What if it counter-proposes something other than 10d?"* → It might — risk_tolerance 0.7 is a continuous parameter. The narration shifts to whatever number lands. The story is the agent rebalancing, not the specific number.
- **Gaps:** ___

### Beat 4 — Accept `[STATIC]`
- **On screen:** `BufferCommitBanner` appears at bottom
- **Say:** "Tomas accepts. Plan saves as Q4 fleet schedule v3. CapEx deferred number lands on the budget review."
- **Gaps:** ___

### Beat 5 — Confirmed `[STATIC]`
- **On screen:** confirmation toast; timer rolls
- **Say:** "synced to Maximo. Memory Bank stores the outcome under `buffer_outcomes`."
- **Gaps:** ___

---

## 8. Persona 4 — Priya (EVP Eastern Hemisphere), 2 min

**Status: AUTO-PLAY in live mode + live stub.** Seeded briefing grounded in real source data (BLS QCEW, Baker Hughes rig count, SAP MARC + ZHR_WORKFORCE internal extracts). The numbers are not fabricated — they're pulled from the same datasets the other agents reach for. In live mode the page auto-plays — Priya's question is up, the live call fires automatically, the briefing assembles on its own.

The live call POSTs to `/api/deep-research/run` (currently a stub that returns 501 with a structured "Deep Research Agent not provisioned" reason). The page surfaces that honestly via `LiveAgentBubble` and `LiveStatusPill` and keeps the seeded briefing visible.

**Opening prompt (Priya's chat bubble):**
> "Why did our Permian utilization underperform last quarter? Compare to public Baker Hughes data."

### Beat 0 — Question posed `[STATIC]`
- **On screen:** notebook header with Priya's question; empty placeholders for sources / synthesis / recommendation
- **Under the hood:** `canvas/src/data/scenarios/deepResearch.ts:emptyState()`
- **Say:** "Priya's an EVP. Asks the kind of cross-domain question that used to take a research analyst two weeks."
- **Gaps:** ___

### Beat 1 — Sources gathered `[STATIC, LIVE-CALL FIRES]` ★
- **On screen:** three citation chips render — BLS QCEW (public), Baker Hughes (public), SAP MARC + ZHR_WORKFORCE (internal). `LiveAgentBubble` in chat: "Deep Research Agent · live" → either "researching…" → "stub · using seeded briefing" (501 today) or "ok" (when DRA is wired).
- **Under the hood:**
  - `canvas/src/app/scenarios/deep-research/page.tsx` fires `fetch('/api/deep-research/run')` on entry to beat 1 in live mode
  - The stub at `canvas/src/app/api/deep-research/run/route.ts` returns 501 with `{ provisioned: false, reason, hint }`
  - Page surfaces honestly; static briefing remains the source of truth
- **Say:** "two public sources, one internal — Deep Research Agent grounds everything before synthesis. Click any chip and the underlying record opens."
- **Likely questions:**
  - *"Are these citations live?"* → The citation **content** is real (BLS NAICS 211 series, Baker Hughes Permian rig count, our internal SAP MARC + ZHR_WORKFORCE). The live agent **call** is stubbed in this tenant — the route fires, returns 501 with a structured reason, the page tells the truth in the LiveAgentBubble. Gap-fix is one file: `canvas/src/app/api/deep-research/run/route.ts`.
  - *"What grounding sources would the live agent use?"* → Per TASK-18 §2: Knowledge Catalog (canonical assets), the operational-status data store (commitments, fleet, on-time history), the BQ ML demand forecasts. Web grounding off (internal exposure analysis only).
- **Gaps:** ___

### Beat 2 — Synthesis populates `[STATIC]`
- **On screen:** sectioned synthesis renders inline — three contributing factors (demand softened, crew availability flat, leading indicator missed)
- **Under the hood:** pre-authored from real data the citations cite (e.g. "Permian rig count fell from 311 to 290" is the Baker Hughes series in the citation drill-down). Renders via `SimpleMarkdown` in `ResearchNotebook`.
- **Say:** "three factors. Each anchored to a citation above — every claim has a source the exec can click."
- **Likely questions:**
  - *"How do I know these numbers are real and not made up?"* → Click the BLS chip → drawer shows the QCEW series with the +2.1% YoY number that's in the synthesis. Click Baker Hughes → drawer shows the weekly 311→290 series. The synthesis pulls from the same numbers the drill-down surfaces.
- **Gaps:** ___

### Beat 3 — Recommendation surfaces `[STATIC]`
- **On screen:** blue recommendation card — "Cut Permian crew rotation cadence by 1 week; reallocate 2 crews to Eagle Ford"
- **Say:** "strategic next move, surfaced with reasoning intact."
- **Gaps:** ___

### Beat 4 — Saved + follow-up `[STATIC]`
- **On screen:** save toast — "Insight saved to Priya's research notebook. Follow-up scheduled in 2 weeks."
- **Say:** "two minutes. End-to-end."
- **Gaps:** ___

### Cross-cut: citation drill-down `[INTERACTIVE]`
- **What it is:** click any citation chip → right drawer opens with the source's summary, structured facts the synthesis pulled, raw excerpt, and "View source" link (public sources open the real BLS / Baker Hughes URL).
- **Why it matters:** the spec's "exec can audit her own briefing" moment. Works in any beat from 1 onward, in either mode.
- **Under the hood:** `canvas/src/components/research/CitationDrawer.tsx` consumes `Citation.detail` from `deepResearch.ts`. The structured shape is uniform across public + internal sources.
- **Say:** "click any chip — the actual record opens. NAICS code, plant ID, the row from the table. No hand-waving."

**To make it fully real:** replace the body of `canvas/src/app/api/deep-research/run/route.ts` with a real call to Gemini Enterprise's Deep Research Agent (likely Vertex AI Search Conversation API or DRA-specific surface, depending on the tenant). Stream the research-plan + section-assembly events back as NDJSON. Resolve the result to a structured briefing payload matching the seeded shape. Everything else (citations, drill-down, beat choreography) keeps working unchanged.

---

---

## 9. Persona 5 — Rafael (Citizen Developer), 2 min

**Status: LAUNCHPAD only.** Per `tasks/TASK-19`, Agent Studio is a real Gemini Enterprise feature; we do not build it and we do not simulate it. The canvas page is a launchpad — Rafael's actual experience in production starts by opening Agent Studio in a browser tab. Two honest paths:

1. **Open Agent Studio** — links to the pre-staged "Rig-Down Notification Agent" project URL (env var `NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL`). The live build happens in the new tab, against the real product. Strongest demo moment.
2. **Recorded fallback** — links to a recorded mp4 of the full 60-second build (env var `NEXT_PUBLIC_AGENT_STUDIO_RECORDING_URL`). Use when live is risky (slow network, etc.).

If env vars are missing, the corresponding buttons render disabled with a tooltip naming what's not configured. The page also surfaces the full 7-step rehearsal script (times + cues + actions) so the demoer can narrate the live build in the other tab without context-switching to a separate document.

There is intentionally **no scripted-preview component** on this canvas. The old `SkillBuilder` was a simulation of Agent Studio — exactly what the spec warns against. Removed (the file is gone).

**Rafael's request (shown in a prominent card on the launchpad):**
> "I want to add a quick custom check: alert me when any Permian crew has been deployed > 21 days continuously."

### How to demo this today
- **Best case:** Open Agent Studio in tenant, pre-stage the project per `TASK-19 §3`, set the env var. Click "Open Agent Studio" during the demo; do the 60-second build live (in a separate tab). Return to this canvas page (or jump to `6`) for the governance hand-off.
- **Fallback:** record the live build once, set the recording URL env var, click "Recorded fallback" during the demo.
- **No-staging fallback:** narrate over the rehearsal script on this page while explaining what the audience would normally see in Agent Studio. Less impressive; honest about what's missing.

**To make it real:** TASK-19 Steps 3 (pre-stage) + 6 (record). Both are manual platform work that needs you in Agent Studio with a tenant account. The launchpad will pick up the URLs as soon as you set the env vars.

**Gaps:** ___

---

## 10. Persona 6 — Ayesha (Audit Director), 3 min — closer

**Status: MOCK panels with honest indicator.** Three A2UI panels (Registry / Gateway / Model Armor) render mock data — surfaced via the top-right `data: mock` pill. The page is a passive viewer the auditor opens; **no buttons that simulate attacks** (the old "Trigger attempt" button was removed because an auditor doesn't trigger attacks in real life — attacks happen organically and Model Armor blocks them; the audit view is just where she sees them).

### Walking the page (3 min)

One scrollable document. Ayesha walks down top to bottom; the demoer narrates per section. No keys to press.

- **Top — "Governance posture" header.** Persona name + the platform claim: Agent Identity / Gateway / Model Armor. The `data: mock` pill is intentionally visible — surfacing it is the audit-credibility move ("we don't pretend mock data is real").
- **Section 1: Agent Registry.** Four MCP servers + agents catalogued. Default-deny: anything not here is unreachable.
- **Section 2: Agent Gateway — recent decisions.** Every authz check, ALLOW/DENY mix. Cite the Plan Evaluator's denied SAP write as the least-privilege example.
- **Section 3: Model Armor — recent blocks.** *"Here's what was blocked. Real attacks land in production constantly; this is the view an auditor opens to see they were caught. Top row: prompt injection at HIGH confidence, blocked at the MCP boundary before any agent reasoned over it."* Narrate over what's already on screen — no button click.

### Likely questions
- *"Is this data real?"* → No, mock. The policies and infra it describes are real (see `infra/gateway_policies.yaml`, `infra/model_armor.yaml`, `infra/governance/`). The Cloud Logging tail is the missing wiring.
- *"What happens when we deploy?"* → The `data: mock` pill flips to `data: live` (TASK-11 §Step 6 / TASK-13). The shape stays the same; only the source changes from `a2uiSamples.ts` to Cloud Logging queries.
- *"Could you show an attack being blocked live?"* → In a customer pilot, yes — set up a known-malicious payload and a one-click test path. Out of scope for this reference solution; the seeded blocks are representative.

**To make it fully real:**
1. Finish TASK-11 governance terraform apply — provisions Model Armor template + Agent Gateway authorization policies
2. Replace `data/a2uiSamples.ts` mock arrays with Cloud Logging tail queries (TASK-13)
3. Add the four tabs the spec wants (Registry / Gateway / Identities / Model Armor) — current page has 3 stacked sections instead

**Gaps:** ___

---

## 11. Wrap, 1 min

`0` returns to launcher. Six tiles, recap the four pain points:

- Issue 1 (volatile start dates → over-buffered fleets) — Persona 2
- Issue 2 (forecast review boundary → qualitative knowledge lost) — Persona 1
- Issue 3 (capacity gaps → panic logistics) — Persona 3
- Issue 4 (taxonomic chaos across SAP/Maximo/FDP/InTouch) — surfaced as substrate in Personas 1, 2, 3 via Knowledge Catalog

**Honest closing line today:** "Persona 3 is fully live on Agent Engine. Personas 1, 2, 4 fire live calls at their moments of agent intelligence (or surface the gap honestly when a backend isn't provisioned). Persona 5 hands off to real Agent Studio (in a separate tab). Persona 6 walks a real governance posture — the panels show illustrative data today; the policies and the infra are real and the live-attack trigger is one route fix away once the governance terraform applies." Adapt aggressiveness to your audience.

---

## 12. Recovery one-liners

| Symptom | Recovery |
|---|---|
| Cargo-plane beat hangs > 15s | Press `L` to flip to Replay |
| Canvas WebSocket disconnects | Click reconnect banner, or `R` |
| Browser freezes | Reload, press persona number key, `R` |
| P1/P2 live call errors | `LiveAgentBubble` shows "fallback → static". Demo continues with scripted numbers. Press `L` to disable live mode entirely. |
| P4 live call returns "not provisioned" | Expected today (DRA not wired). `LiveAgentBubble` says so. Frame: "the seeded briefing here is grounded in the same real data DRA would query — gap-fix is one route file." |
| P6 customer asks for a live attack demo | Out of scope today — say so. Pre-seeded blocks in the Model Armor panel are representative; in a customer pilot you'd wire a one-click test path. |
| Plan Evaluator scores < 0.85 (workflow loops) | Press `R` to retry; temp=0 build is deterministic so this shouldn't happen — investigate after the demo |
| "Is this real?" question | "Synthetic data, real platform. Show `make smoke-cargo-plane` or the Cloud Trace." |

Full recovery scripts: `demo-handbook.md` §3.

---

## 13. Skin switching

```bash
export CUSTOMER_SKIN=default          # SLB-pattern
export CUSTOMER_SKIN=halliburton      # Halliburton-pattern
make deploy-orchestrator              # for skin change to take effect
```

Identifiers (memoryProfileUserId, sessionId) stay stable across skins. Only display names + colors + scenario copy change.

---

## 14. Where the source of truth lives

| Question | File |
|---|---|
| Why this demo? | `docs/planning/agentic_sop_oilfield_services_brief.md` |
| What numbers will the demo show? | The eval suite — `agents/*/evals/` |
| What's deployed right now? | `.env` (resource IDs) |
| Architecture decisions (ADRs) | `docs/governance.md` |
| Per-task specs | `tasks/TASK-*.md` |
| Pre-demo verification | §2 above |
| Recovery scripts | §12 above + `demo-handbook.md §3` (until that doc is retired) |

---

*Keep this doc in sync with what's actually wired. If you wire a new live moment, update §1 and the relevant persona section. If a beat's narration would lie about what's running, the beat's wrong — not the narration.*
