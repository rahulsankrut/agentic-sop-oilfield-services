# TASK-03 — overnight autonomous run status

## Done (committed b45663c + this commit)

- [x] Synthetic data substrate (data/ — 8 JSON files + 2 basin variance files)
- [x] `src/utils/synthetic_data.py` lru_cached loaders
- [x] 7 ADK skills with `SKILL.md` + `scripts/tools.py` + `references/`:
  - asset-equivalence, sourcing-logistics, enterprise-systems (Orchestrator)
  - plan-evaluation (Plan Evaluator)
  - procurement-prerequisites (Procurement Approval)
  - forecast-rationale (Forecast Review)
  - scheduling-probability (Capacity Planning)
- [x] Skill toolset wiring in each agent's `core/tools.py`
- [x] 38 unit tests for deterministic skill tools (all passing)
- [x] Expanded prompts referencing each skill by name with explicit workflow
  (Orchestrator, Plan Evaluator, Procurement Approval, Forecast Review,
  Capacity Planning)
- [x] Cargo-plane integration test (`tests/integration/test_cargo_plane_scenario.py`)
- [x] CLAUDE.md still current (no new gotchas surfaced overnight)

## Pending (needs live deploys — morning checklist)

- [ ] Re-deploy all 5 agents with the expanded prompts + wired skills (run
  `make deploy-all-agents` per `docs/reference_demo_runs/TASK-02-deploy-checklist.md`).
- [ ] Verify the cargo-plane integration test passes against live agents.
  Expected: Maria's prompt → Lagos-sourced TX-007 → ~$216K primary cost vs.
  ~$700K Darwin cargo-charter baseline → avoided_cost_usd > $300K.
- [ ] If the LLM doesn't follow the workflow precisely (common failure mode
  on first deploy), iterate on prompts. The skeleton tests pin the
  deterministic tool logic, so any failure is in the LLM's planning, not
  the tools.

## Risks tracked (re-stated for morning)

1. **Pydantic AgentCard patch is unit-tested only.** Procurement Gate
   deploy is the live exercise — if it fails with a different protobuf/
   Pydantic shape, widen `patch_message_to_json_for_pydantic`.
2. **`gemini-3.1-pro-preview` structured-output adherence** for
   `output_schema=SourcingPlan`. The Orchestrator's prompt is now detailed
   enough that the model has clear shape guidance; if it still emits
   malformed JSON, fall back to `gemini-2.5-pro` via `ORCHESTRATOR_MODEL`.
3. **Memory Bank API surface for `customization_configs`** — vertexai
   preview API; may have drifted. Failure mode: deploy succeeds but Memory
   Bank calls return errors at runtime (the agent still responds; we see
   warnings in logs from `auto_save_memories`).

## Total test count when fully wired

- 78 unit tests (including 38 skill-tool tests)
- 1 schema round-trip integration test (no live deps)
- 9 live integration tests gated on `ORCHESTRATOR_AGENT_RESOURCE_NAME` —
  3 in test_orchestrator_skeleton.py + 6 in test_cargo_plane_scenario.py
