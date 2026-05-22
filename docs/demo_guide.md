# Demo guide — Agentic S&OP for Oilfield Services

Quick-start for running the live demo. Pairs with:
- `docs/demo-handbook.md` — full 18-minute presenter playbook (recovery scripts, customer Q&A)
- `docs/demo_storyboard.md` — per-node narration cues for the cargo-plane centerpiece
- `docs/testing_guide.md` — pre-demo verification

If you have 30 minutes before the demo, read **only this guide**. If you have an hour, also skim the handbook. If you have a day, rehearse against the storyboard until you can recite Beat 3 in your sleep.

---

## What's deployed (verified 2026-05-22)

Four agents on Vertex AI Agent Engine, `us-central1`:

| Agent | Resource ID | Surface |
|---|---|---|
| Capacity Orchestrator | `3863088474458423296` | streamQuery (canvas + evals) |
| Procurement Approval | `3638823286764208128` | A2A (Orchestrator + evals) |
| Forecast Review | `5040779777015808000` | streamQuery |
| Capacity Planning | `2734936767802114048` | streamQuery |

Plus the Plan Evaluator (bundled in-process inside Orchestrator — ADR-0003).

Resource IDs live in `.env` and `canvas/.env.local`. If those env files don't have these IDs, the demo will hit stale deployments.

---

## Pre-demo verification (run 45 min before)

```bash
# 1. Activate venv + source env
source venv/bin/activate
set -a && source .env && set +a

# 2. Programmatic smoke (data-flow, no LLM, ~5s)
make smoke-cargo-plane
# Expect: 11/11 checks passed

# 3. Fast evals (schema + trajectory, no LLM, ~2s)
make evals
# Expect: 33 passed, ~22 skipped (live-gated)

# 4. Live evals (drives all 4 deployed agents, ~13 min, ~$1)
source venv-deploy-310/bin/activate
python -m pytest agents/orchestrator_agent/evals/ \
  agents/procurement_approval_agent/evals/ \
  agents/forecast_review_agent/evals/ \
  agents/capacity_planning_agent/evals/ \
  agents/orchestrator_agent/plan_evaluator/evals/ \
  --run-live-evals -q
# Expect: 52 passed, 1 xfailed (known persona-1 multi-tag gap)
```

If anything fails, **stop and fix before walking into the room.** Common causes documented in `docs/demo-handbook.md` §0.

---

## The verified demo numbers (Persona 3 / Maria)

These are baked into the eval suite and confirmed in repeated live runs:

| Field | Value | Source |
|---|---|---|
| Requested asset | "Tool X" | Maria's prompt |
| Canonical substitute | TX-007 (Tool X-V7) | Knowledge Catalog equivalence |
| Source location | Lagos, Nigeria (repair shop) | Maximo |
| Primary cost | **$162,210** | finalize_sourcing_plan |
| Naive baseline | Darwin → Luanda cargo charter, $636,353 | _skin_fallback_hub |
| **Avoided cost** | **$474,143** | naive − primary |
| Blockers | 1 (cert hours remaining on TX-007-LGS-001) | Maximo work-order check |
| Workflow runtime | ~115 seconds | end-to-end |

If your demo doesn't surface these numbers, something has drifted — check `make smoke-cargo-plane` and the live eval first.

---

## Demo flow at a glance

| Time | Persona | Surface | Key beat |
|---|---|---|---|
| 0:00 | Opening | Launcher | Six tiles, platform framing |
| 1:00 | **P1 — David** (Permian basin lead) | Gemini Enterprise + Connected Sheets | Q4 forecast override → rationale tags |
| 4:00 | **P2 — Tomas** (West Texas fleet) | Gemini Enterprise + Canvas | Risk-tolerance slider → buffer + utilization |
| 7:00 | **P3 — Maria** (West Africa OCC) ★ | Gemini Enterprise + Canvas | **Tool X / cargo-plane / $474K avoided** |
| 12:00 | P4 — Priya (EVP) | Deep Research Agent | Eastern-hemisphere portfolio briefing |
| 14:00 | P5 — Rafael (citizen dev) | Agent Designer | No-code guardrail agent in 2 min |
| 16:00 | P6 — Ayesha (audit) | `/audit/registry` | Agent Registry, Gateway decisions, Model Armor |
| 19:00 | Wrap | Launcher | Six personas, four issues resolved |

★ = centerpiece. Do not rush it. The $474K avoided-cost moment is the demo's strongest beat — let the number land.

---

## Exact prompts to type

**Persona 3 — Maria** (the only one with verified live-deployment behavior):

```
I need a Tool X variant on site in Luanda, Angola by Friday. Customer: Gulf Petroleum. Authorization tier: standard. What are my options?
```

This is the canonical eval prompt. Drift in wording can drift the LLM's behavior — if you change it, re-verify with `pytest agents/orchestrator_agent/evals/ --run-live-evals -k cargo_plane`.

**Persona 1 — David**:

```
Q4 forecast review for the permian basin. override_id: ovr-pm-q4-david-001. The ML model projected Q4 completions revenue of $72M; I'm overriding to $56M (down 22%). Reason: rig count decline expected, three operators delaying programs into Q1.
```

**Persona 2 — Tomas**:

```
What's my buffer exposure on the permian basin (West Texas fleet) for Q3, given the rig count signals we're seeing? Risk tolerance: 0.65.
```

(Other personas are still mocked / scripted — see handbook for the planned prompts.)

---

## Skin switching (if presenting to a specific account)

The platform supports per-customer skinning. Two skins ship:

```bash
# Default — "Demo Major Services" (SLB-pattern)
export CUSTOMER_SKIN=default

# Halliburton-pattern
export CUSTOMER_SKIN=halliburton

# Redeploy the Orchestrator for the skin to take effect
make deploy-orchestrator
```

Customer names, colors, and demo scenarios re-skin automatically. Verified by `test_live_multi_skin_halliburton_returns_valid_plan` in the eval suite.

---

## Watch points (where this demo can drift)

The eval suite catches most regressions, but two are worth eyeballing live:

1. **Plan Evaluator score** — temperature=0 keeps scoring deterministic, but if you change the canonical prompt or skin data, re-verify the score stays ≥ 0.85 (otherwise the workflow routes to REVISE mid-demo).

2. **Cost numbers in the narrative** — finalize.py emits the corrected SourcingPlan as JSON; the canvas reads `plan.avoided_cost_usd` directly. If the canvas banner shows $0 instead of $474K, the deployed Orchestrator drifted from the local code. Redeploy: `make deploy-orchestrator`.

---

## Recovery one-liners

Quick reference. Full recovery scripts in `demo-handbook.md` §3.

| Symptom | Recovery |
|---|---|
| Cargo-plane beat hangs > 15s | Press `L` (Replay mode) |
| Canvas WebSocket disconnects | Click reconnect banner, or `R` to reset |
| Browser tab freezes | Reload tab, press persona number key, then `R` |
| Plan Evaluator returns < 0.85 (workflow loops) | Press `R` to retry; non-determinism should be fixed in deployed temp=0 build |
| "Is this real data?" question | "Synthetic data, real platform — show `make smoke-cargo-plane`" |

---

## The 5-line elevator pitch

Use these between scenarios if the customer's attention drifts:

1. "Gemini Enterprise is the front door for your people; Gemini Enterprise Agent Platform is the build-and-run surface for their agents."
2. "Every agent you've seen runs on Agent Runtime, registered in Agent Registry, called through Agent Gateway, scanned by Model Armor."
3. "Memory Bank is managed memory — every persona's context is preloaded without warm-up turns. That's the `preload_memory` you saw in Maria's opening."
4. "Knowledge Catalog is what made the cargo-plane scenario work — one canonical Tool X entity, all four enterprise-system aliases unified."
5. "Cloud Trace shows every reasoning step. Procurement and audit can defend any decision the agent made."

---

## Where the source of truth lives

| Question | File |
|---|---|
| Why this demo? | `docs/planning/agentic_sop_oilfield_services_brief.md` |
| How does each Persona 3 beat work? | `docs/demo_storyboard.md` |
| What's the full 18-min playbook? | `docs/demo-handbook.md` |
| How do I verify before the demo? | `docs/testing_guide.md` |
| What's deployed right now? | `.env` (resource IDs) |
| What numbers will the demo show? | The eval suite — `agents/*/evals/` |

---

*Keep this guide in sync with the deployment state. If resource IDs change, update the table at the top. If a verified demo number changes, fix the eval first, then this guide.*
