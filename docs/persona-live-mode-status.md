# Per-persona Live Mode wiring status

Snapshot of how each persona's canvas scenario is wired to the deployed
agents. Reflects state as of 2026-05-21.

| Persona | Canvas page | Deployed agent | Live mode | Notes |
|---|---|---|---|---|
| **3 — Maria (OCC West Africa)** | `/scenarios/cargo-plane` | Capacity Orchestrator (Workflow) | ✅ **Live** | Full canvas-event emission. Hitting `L` drives the canvas off the deployed Orchestrator's `streamQuery` SSE. Verified end-to-end yesterday: TX-007 from Lagos, $474K avoided. |
| **1 — David (Basin Leader)** | `/scenarios/forecast-review` | Forecast Review Agent (LlmAgent) | ⚠️ Partial | `NEXT_PUBLIC_FORECAST_REVIEW_STREAM_URL` plumbed. The deployed agent responds to `streamQuery` with a structured `ForecastOverride` JSON, but does not emit `canvas_events` for the page's BasinTile / ForecastDeltaBanner reducer. The page falls back to static beats. Adding canvas-event emission is a future task. |
| **2 — Tomas (Fleet)** | `/scenarios/buffer-planning` | Capacity Planning Agent (LlmAgent) | ⚠️ Partial | `NEXT_PUBLIC_CAPACITY_PLANNING_STREAM_URL` plumbed. The deployed agent responds with a structured `OptimalBuffer` JSON. Same gap as David — no `canvas_events` emission. |
| **4 — Priya (Deep Research)** | `/scenarios/deep-research` | Orchestrator's `deep-research` skill (no standalone deploy) | 🔘 Static-only | The skill tools (`search_bsee_incidents`, `search_mcc_contracts`, `search_intouch_specs`) are deployed inside the Orchestrator, but no dedicated canvas-event coordination exists. Priya's research notebook is currently driven entirely by canned beats. |
| **5 — Rafael (Agent Studio)** | `/scenarios/agent-studio` | None | 🔘 Static-only | Agent Studio is a Google Agent Platform Console workflow (skill builder, YAML preview, test results, publish card). No backing agent in this repo. Page is static-only by design. |
| **6 — Ayesha (Audit/Governance)** | `/audit/registry` | None | 🔘 Static-only | Registry / Gateway / Model Armor panels are static A2UI surfaces. The actual governance configuration lives in `infra/governance/` terraform; the canvas is a console mock. |

## What's the gap for personas 1 + 2?

Both agents respond cleanly to `streamQuery`. The missing piece is the
canvas-event emission layer that exists for the Orchestrator. The
Orchestrator's Workflow nodes call `events/emit.py` to append
`CanvasEvent`s to `ctx.state["canvas_events"]`, which the deployed
runtime drains via the `state_delta` on each ADK Event chunk.

To wire either persona into Live mode the same way:

1. Define new `CanvasEvent` subtypes for the persona's specific UI moves
   (e.g. `forecast.basin_override`, `buffer.risk_slider_committed`).
2. Wrap the LlmAgent in a tiny callback that maps its structured output
   into one or more events and writes them to `ctx.state["canvas_events"]`
   (mirror `agents/orchestrator_agent/nodes/equivalence_lookup.py:
   _emit_equivalence_events`).
3. Extend `canvas/src/lib/canvas-events.ts` + the page's reducer to
   handle the new event types.
4. Wire `L` on the page to call the agent via
   `canvas/src/lib/agent-stream.ts` with the right `streamUrl` env.

Estimated effort per persona: ~2-3 hours.

## Why not done now

The cargo-plane Live mode took most of yesterday to get working
end-to-end — the workflow had multiple state-passing bugs that took
several iterations to surface and fix. Replicating that for two
non-workflow LlmAgents is real work that warrants a dedicated task per
persona rather than bundling it into a "finish everything" sweep.

Recommendation: when the demo team wants Live mode for David or Tomas,
file a focused task per persona using the 4-step checklist above.
