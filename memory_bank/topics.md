# Memory Bank topics — Oilfield S&OP

Consolidated inventory of all Memory Bank topics declared across the four
deployed agents. Each topic is declared in exactly one agent's
`services/memory_manager.py` and attached to that agent's Agent Engine
resource at deploy time via `context_spec.memory_bank_config.customization_configs`.

Memories under any topic are scoped by `user_id`; topics are global within
the agent that declared them. Read with
`VertexAiMemoryBankService.search_memories(user_id=..., topic=...)`; write
happens automatically via each agent's
`after_agent_callback=auto_save_memories` (defined in the same `memory_manager.py`).

The seed script at `memory_bank/seed_memories.py` (TASK-07 Step 3) uses
this inventory's "agent" column to route persona memories to the correct
Memory Bank backend.

## Topics by agent

| Agent | Topic label | Source file | What it captures |
| --- | --- | --- | --- |
| Capacity Orchestrator | `sourcing_history` | `src/orchestrator_agent/services/memory_manager.py` | Asset + basin + savings + approval outcome per sourcing decision |
| Capacity Orchestrator | `planner_preferences` | same | Per-planner basin, authorization tier, default transit modes, units |
| Capacity Orchestrator | `equivalence_patterns` | same | Canonical asset → variant substitutions with spec refs |
| Procurement Approval | `approval_history` | `src/procurement_approval_agent/services/memory_manager.py` | Tier + amount + outcome per procurement-approval verdict |
| Procurement Approval | `blocker_patterns` | same | Recurring procurement blockers per customer / basin |
| Forecast Review | `rationale_patterns` | `src/forecast_review_agent/services/memory_manager.py` | Rationale tags that accompany large basin-leader overrides |
| Forecast Review | `leader_profiles` | same | Per-leader override patterns and signal quality |
| Capacity Planning | `risk_tolerance` | `src/capacity_planning_agent/services/memory_manager.py` | Per-planner buffer / late-start cost tradeoff settings |
| Capacity Planning | `buffer_outcomes` | same | Realized vs. recommended buffer per scenario |

Nine topics total, four backends.

## Seed memory routing — topic → Agent Engine env var

Used by `memory_bank/seed_memories.py` to pick the right
`VertexAiMemoryBankService` for each seed memory:

```python
TOPIC_TO_AGENT_ENV: dict[str, str] = {
    "sourcing_history":     "ORCHESTRATOR_AGENT_ENGINE_ID",
    "planner_preferences":  "ORCHESTRATOR_AGENT_ENGINE_ID",
    "equivalence_patterns": "ORCHESTRATOR_AGENT_ENGINE_ID",
    "approval_history":     "PROCUREMENT_APPROVAL_AGENT_ENGINE_ID",
    "blocker_patterns":     "PROCUREMENT_APPROVAL_AGENT_ENGINE_ID",
    "rationale_patterns":   "FORECAST_REVIEW_AGENT_ENGINE_ID",
    "leader_profiles":      "FORECAST_REVIEW_AGENT_ENGINE_ID",
    "risk_tolerance":       "CAPACITY_PLANNING_AGENT_ENGINE_ID",
    "buffer_outcomes":      "CAPACITY_PLANNING_AGENT_ENGINE_ID",
}
```

Each `*_AGENT_ENGINE_ID` env var resolves to the deployed Reasoning Engine
resource name (the numeric suffix of
`projects/.../reasoningEngines/<id>`). `seed_memories.py` strips the prefix
before constructing the `VertexAiMemoryBankService`.

## Adding a new topic

1. Pick the agent that owns the data domain (e.g., new "agent_identity_audit" topic → Procurement).
2. Add the `MemoryTopic` definition to that agent's `services/memory_manager.py` and include it in the agent's `create_*_memory_topics()` return list.
3. Redeploy that agent (`make deploy-<agent>`) so the new topic lands in the Reasoning Engine's `context_spec`.
4. Update this file's table + the `TOPIC_TO_AGENT_ENV` mapping in `seed_memories.py`.
5. Topics added without a redeploy will silently fail to receive memories — Memory Bank does not retroactively create topics.

## Topic label naming conventions

- Lowercase snake_case.
- Singular when possible (`risk_tolerance` not `risk_tolerances`).
- Past tense or noun phrase, not imperative (`approval_history` not `approve_decisions`).
- Don't prefix with the agent name (the routing is via `TOPIC_TO_AGENT_ENV`, not the label).

## References

- ADK Memory Bank integration: `~/.claude/references/google-adk-2.0.md` §Memory Bank
- Vertex AI Agent Engine Memory Bank config: `~/.claude/references/vertex-agent-engine-deploys.md` §Memory Bank — `context_spec`
- Persona seed memories: `memory_bank/seed_memories.py`
- Deterministic demo sessions: `memory_bank/seed_demo_sessions.py`
