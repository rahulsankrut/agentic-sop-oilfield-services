# ADR 0006: `GlobalGemini` for routing model calls to the `global` endpoint

## Status

Accepted (TASK-02, 2026-05). Pattern ported from
`github.com/GoogleCloudPlatform/race-condition/agents/utils/
global_gemini.py`.

## Context

Vertex AI Agent Engine (Reasoning Engine) only exists in regional
locations — `us-central1`, `us-east5`, `europe-west4`, etc. Same for
Memory Bank and Sessions: they're regional services. The natural
`vertexai.init(location="us-central1")` covers all of those.

The model layer is different. Gemini 3 **preview** models —
`gemini-3.1-pro-preview` and `gemini-3-flash-preview` — only live on
the `global` endpoint. A vanilla `vertexai.init(location='us-central1')`
attempt to invoke them returns 404 NotFound. We hit this on TASK-02
when the Orchestrator's first deployment couldn't reach
`gemini-3.1-pro-preview` from its `us-central1` Reasoning Engine
even though the model is generally available to the project.

Options considered:

1. **Pin to GA-only models** (`gemini-2.5-flash` etc.). Loses the
   reasoning quality of pro-preview, which the Orchestrator's
   equivalence + sourcing + plan-evaluation nodes meaningfully
   benefit from.
2. **Switch the whole project to `global`**. Breaks Agent Engine,
   which doesn't have a `global` endpoint.
3. **Per-call endpoint routing.** Model calls hit `global`; Agent
   Engine + Memory Bank + Sessions stay regional.

## Decision

`agents/utils/global_gemini.py` defines a `GlobalGemini(Gemini)`
subclass that overrides the `api_client` property to return a
separate `genai.Client(location='global')`. Wherever an agent
declares its model, it instantiates `GlobalGemini` instead of plain
`Gemini`:

```python
from agents.utils.global_gemini import GlobalGemini

root_agent = LlmAgent(
    model=GlobalGemini(model="gemini-3.1-pro-preview"),
    ...
)
```

Agents that don't need reasoning depth (Procurement Approval,
Forecast Review, Capacity Planning) use
`GlobalGemini(model="gemini-3-flash-preview")` — same routing
pattern, smaller model.

The rest of the SDK surface (`vertexai.init(...)`, Memory Bank
construction, Sessions construction) continues to use the regional
location (`us-central1`).

## Consequences

**Positive**

- Pro-preview reasoning quality is available to nodes that need it
  (Orchestrator workflow LLM nodes) without giving up Agent Engine
  deployment.
- Pattern is local — no global config bleed. Each agent module
  imports `GlobalGemini` explicitly, so it's obvious in code review
  which calls route where.

**Negative**

- One more import to remember when adding a new agent. If a future
  contributor uses plain `Gemini(model="gemini-3.1-pro-preview")`,
  it'll 404 at first invocation. Mitigated by the CLAUDE.md "Known
  gotchas" entry calling this out by name.
- The `global` endpoint has different latency characteristics from
  `us-central1`. Observable as +50-200ms per model call, which adds
  up across the 6-8 LLM calls in the cargo-plane workflow but
  doesn't change the demo story.

**Risk**

- When the preview models reach GA, they may move to regional
  endpoints. We'd want to swap back to plain `Gemini` to reduce the
  per-call latency. Mechanical change — drop `GlobalGemini` from
  the imports — but worth a follow-up audit when that happens.

## Related work

- `agents/utils/global_gemini.py` — the subclass.
- Used by all 5 agents (4 standalone + Plan Evaluator).
- CLAUDE.md "Known gotchas" §"Gemini 3 preview models live on the
  `global` endpoint" — explains the failure mode and links the
  canonical fix.
- Reference pattern from
  `github.com/GoogleCloudPlatform/race-condition/agents/utils/
  global_gemini.py`.
