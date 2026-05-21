# SPECS.md
## Agentic S&OP for Oilfield Services — Master Project Specification

A specification for Claude Code to build a reference solution for Gemini Enterprise + Gemini Enterprise Agent Platform, targeted at tier-one oilfield services majors (SLB, Halliburton, Baker Hughes, NOV, Weatherford).

---

## For Claude Code

You are building a deployable bundle ("domain pack") that runs inside an actual Gemini Enterprise tenant on Gemini Enterprise Agent Platform. The pack consists of:

- **5 ADK agents** that collaborate via A2A protocol and AgentTool
- **6 ADK Skills** providing domain knowledge (loaded lazily by agents)
- **3 mocked MCP servers** simulating SAP, Maximo, and FDP enterprise systems
- **Knowledge Catalog content** unifying cross-system entity references
- **Memory Bank profiles** for six demo personas
- **Synthetic data** (canonical asset catalog, scenarios, history) supporting all of the above
- **A Next.js Operations Canvas** for two spatial visualization moments
- **Terraform infrastructure** and a `Makefile` automating end-to-end deployment

The project follows the structure and patterns established by the Next '26 developer keynote demo (`github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-2`). This is your primary reference implementation.

**Read this entire SPECS.md before starting any task.** Then proceed task-by-task in numerical order. Each task spec is in `tasks/TASK-NN-name.md`. Each task has prerequisites; do not skip ahead.

---

## Project goal

Demonstrate that Gemini Enterprise + Gemini Enterprise Agent Platform is the right platform for agentic transformation in oilfield services. The demo addresses four operational pain points framed as Sales & Operations Planning (S&OP) cycle breakpoints:

1. **Demand sensing** — ML revenue forecasts lose fidelity at human review boundary
2. **Demand-to-supply planning** — Volatile customer start dates force over-buffering, tying up fleet
3. **Supply response** — Capacity gaps trigger panicked logistics (the "cargo plane from Australia" scenario)
4. **Foundational data** — Misaligned naming conventions across SAP, Maximo, FDP break automation

A single demo runs through six personas — Basin Leader (David), Fleet Scheduler (Tomas), OCC Planner (Maria, the centerpiece), Operations Executive (Priya), Citizen Developer (Rafael), Audit Director (Ayesha) — covering all four pain points and showcasing the full Gemini Enterprise Agent Platform.

The cargo-plane scenario (Maria, Persona 3) is the centerpiece: an OCC planner asks for "Tool X variant in Luanda by Friday," and the system surfaces a functionally equivalent sub-variant in a Lagos repair shop 50km away, saving ~$380K vs. a cargo charter from Australia.

---

## Architectural principles

### 1. The platform is the hero

Gemini Enterprise app is the demo surface for five of six personas. The Operations Canvas (Next.js) is the disciplined exception for two personas where spatial visualization is essential. Every demo moment must be attributable to a named Google Cloud product. **Build platform components, not custom applications.**

### 2. Follow the reference implementation

The marathon planner demo at `github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-2` is the reference. Patterns to preserve verbatim:

- `PromptBuilder` for prompt composition (ordered named sections)
- `SkillToolset` with `load_skill_from_dir` for lazy skill loading
- `RemoteA2aAgent` wrapped in `AgentTool` for A2A collaboration
- Standardized per-agent layout: `core/`, `skills/`, `runtime/`, `services/`
- `auto_save_memories` `after_agent_callback` for Memory Bank integration
- Iterative refinement with score threshold pattern from the marathon Evaluator
- Pydantic schemas attached to `LlmAgent(output_schema=...)` for structured outputs

When in doubt about an implementation choice, look at how the marathon demo did it and adapt.

### 3. Industry-credible synthetic data

The demo is reusable across multiple oilfield services majors. Synthetic data must be industry-generic enough to feel real to anyone in the sector, anonymized customers ("Gulf Petroleum", "North Atlantic Resources"), realistic oilfield terminology (basins, rigs, MWD/LWD, downhole tools, completions equipment), realistic geographies (Permian, North Sea, Gulf of Guinea, Bohai).

### 4. Configuration over code for customer skinning

Customer-specific content (logos, terminology, scenarios, hero locations) lives in `customer.yaml`. Changing customers means editing one config file plus a few asset files, not changing code. Build with this constraint from the start.

### 5. Workflow agents for deterministic flow, LlmAgent for reasoning

ADK 2.0 introduces `Workflow` agents — explicit graphs of nodes where each node is either an LLM agent, a deterministic function, a tool call, or a sub-workflow. This is the architectural target for the **Capacity Orchestrator** and **Capacity Planning Agent**. Single-purpose reasoning agents (Plan Evaluator, Forecast Review Agent, Procurement Approval Agent) remain `LlmAgent`s. The principle: LLM reasoning happens at decision nodes; deterministic code handles routing, parallel dispatch, threshold checks, and structured-data shaping.

This makes agent execution traces predictable, debuggable, and defensible to procurement audit — three things that matter for enterprise buyers. It is also a core piece of the Gemini Enterprise Agent Platform story Google leads with at Next '26: control, predictability, reliability.

### 6. Platform-visibility narration cues in code comments

For every demo moment, include a `# DEMO NARRATION:` comment in the code explaining what Google Cloud product this moment showcases. This becomes the rehearsal script later.

---

## Reference repository (clone before starting)

```bash
git clone https://github.com/GoogleCloudPlatform/next-26-keynotes.git /tmp/next-26-keynotes
```

Primary directories you will reference repeatedly:

- `/tmp/next-26-keynotes/devkey/demo-2/` — The multi-agent reference (Planner + Evaluator + Simulator). Fork this as your starting point.
- `/tmp/next-26-keynotes/devkey/demo-1/` — Single-agent foundation (skills + MCP). Pattern reference.
- `/tmp/next-26-keynotes/devkey/enhancing-agents-with-memory/` — Memory Bank + AlloyDB MCP + Document AI patterns. Useful for InTouch ingestion.
- `/tmp/next-26-keynotes/devkey/debugging-agents/` — Cloud Trace / Cloud Assist patterns for the governance demo.

---

## Repository structure (target)

The pack should be a single Git repository with this structure:

```
agentic-sop-oilfield-services/
├── README.md
├── SPECS.md (this file)
├── Makefile
├── pyproject.toml
├── cloudbuild.yaml
├── customer.yaml.example       # Template for customer skin
│
├── src/
│   ├── __init__.py
│   ├── config.py               # Global config (project ID, region)
│   ├── schemas.py              # Shared Pydantic schemas (SourcingPlan, PlanEvaluation, etc.)
│   ├── utils/                  # PromptBuilder, common helpers
│   │
│   ├── orchestrator_agent/     # Persona 3 lead agent (Cloud Run)
│   │   ├── core/               # agent.py, config.py, prompts.py, schemas.py, tools.py, auth.py
│   │   ├── skills/             # 4 skills consumed by this agent
│   │   ├── runtime/            # agent_card.py, agent_executor.py, deploy.py, local_server.py
│   │   ├── services/           # memory_manager.py, session_manager.py
│   │   └── plan_evaluator/      # Bundled Plan Evaluator (in-process AgentTool)
│   │
│   ├── procurement_approval_agent/ # Approval gate (Agent Engine, A2A)
│   │   ├── core/
│   │   ├── skills/
│   │   ├── runtime/
│   │   └── services/
│   │
│   ├── forecast_review_agent/  # Persona 1 (Agent Engine)
│   │   └── ...                 # Same layout
│   │
│   └── capacity_planning_agent/ # Persona 2 (Agent Engine, long-running)
│       └── ...                 # Same layout
│
├── mcp_servers/                # Mocked enterprise system MCP servers
│   ├── sap/                    # SAP material master, workforce — via Apigee pattern
│   ├── maximo/                 # Equipment status, location, availability
│   └── fdp/                    # Customer configurations
│
├── data/                       # Synthetic data
│   ├── canonical_assets.json   # 80-120 canonical asset entries
│   ├── cross_system_aliases.json
│   ├── functional_equivalences.json
│   ├── customers.json          # 5-10 anonymized customers
│   ├── start_date_variance/    # 6 quarters per basin (Persona 2 substrate)
│   ├── operational_history/    # 24 months sourcing events
│   ├── forecast_history/       # 6 quarters of forecasts + overrides
│   └── intouch_docs/           # 200-300 synthetic PDFs
│
├── knowledge_catalog/          # Knowledge Catalog setup scripts and seed data
│   ├── setup.py
│   ├── entities.yaml
│   └── relationships.yaml
│
├── canvas/                     # Operations Canvas (Next.js)
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── GlobalAssetView.tsx     # Persona 3
│   │   │   ├── FleetUtilizationView.tsx # Persona 2
│   │   │   └── ...
│   │   ├── lib/
│   │   │   └── websocket.ts            # Event consumer
│   │   └── types/                       # TypeScript types matching agent event schemas
│   └── public/
│
├── terraform/                  # Infrastructure as Code
│   ├── main.tf
│   ├── agents.tf
│   ├── canvas.tf
│   ├── mcp_servers.tf
│   └── terraform.tfvars.example
│
├── demo/                       # Demo runner and scenarios
│   ├── scenarios.py            # cargo_plane, forecast_review, fleet_buffer, etc.
│   ├── test_endpoints.py
│   └── deploy/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── docs/                       # Internal documentation
│   ├── architecture.md
│   ├── demo_storyboard.md
│   └── customer_skin_guide.md
│
└── tasks/                      # Claude Code task specs (this directory)
    ├── TASK-01-environment-and-fork.md
    ├── TASK-02-agent-skeletons.md
    ├── TASK-03-skills.md
    └── (more added as needed)
```

---

## Tech stack (locked)

### Backend / Agents

- **Python 3.11+**
- **uv** as the package manager (matches the reference demo)
- **Google ADK (Agent Development Kit) 2.0 Beta** — `google-adk>=2.0.0b1,<2.1` installed with `--pre` flag. Workflow agents, deterministic graph routing, and AI-at-decision-points patterns are the architectural target. Existing LlmAgent code from TASK-01–03 remains forward-compatible.
- **Gemini 3.1 Pro** for the Orchestrator (reasoning depth matters)
- **Gemini 3 Flash** for sub-agents where speed matters more than depth
- **Pydantic 2.x** for schemas
- **Vertex AI Python SDK** (`google-cloud-aiplatform`)
- **A2A Python library** (`a2a`)
- **FastAPI** for the WebSocket gateway and any custom HTTP endpoints
- **Cloud Run + Agent Engine** for deployment

### Frontend / Canvas

- **Next.js 15.x** with App Router
- **TypeScript 5.x**
- **Tailwind CSS 4.x**
- **shadcn/ui** components
- **Google Maps Platform** via `@vis.gl/react-google-maps` — aligns the canvas with the rest of the Google stack, exposes geodesic Polylines + cloud-managed Map IDs for styling, and bills against the same GCP project as Agent Engine
- **Framer Motion** for animations
- **Native WebSocket API** with reconnection logic for live event consumption

### Infrastructure

- **Terraform 1.x**
- **Google Cloud Build** for CI/CD
- **GitHub** for version control

---

## Phase 1 task sequence

These are the task specs in `tasks/`. Execute in order. Each task has prerequisites checked at the top of its spec.

| # | Task | Estimated effort | Stream |
|---|---|---|---|
| 01 | Environment setup and reference repo fork | 1-2 days | Backend |
| 02 | Agent skeletons (rename, deploy bare scaffold) | 3-5 days | Backend |
| 03 | Build the seven ADK Skills | 5-7 days | Backend |
| **04** | **ADK 2.0 migration + Capacity Orchestrator Workflow refactor** | **5-7 days** | **Backend** |
| 05 | MCP servers via genai-toolbox (SAP, Maximo, FDP mocks + Knowledge Catalog MCP wiring) | 3-5 days | Backend |
| 06 | Knowledge Catalog setup with custom Aspect Types and canonical Entries | 3-5 days | Backend |
| 07 | Memory Bank profiles and persona context | 2-3 days | Backend |
| 08 | Operations Canvas scaffold and Global Asset View | 5-7 days | Frontend |
| 09 | Operations Canvas Fleet Utilization View | 3-5 days | Frontend |
| 10 | WebSocket integration: agent events → canvas | 3-5 days | Both |
| 11 | Governance configuration (Identity, Gateway, Model Armor) | 2-3 days | Backend |
| 12 | Demo storyboard wiring and rehearsal mode | 3-5 days | Both |
| 13 | Customer skin templating and `customer.yaml` system | 2-3 days | Both |
| 14 | Terraform end-to-end deployment (or agents-cli adoption) | 3-5 days | Backend |
| 15 | Internal review, polish, fail-safe modes | 5-7 days | Both |

The initial drop covered tasks 01-03. The current drop covers tasks 04-06 (the ADK 2.0 migration with Workflow refactor, plus MCP servers and Knowledge Catalog setup). Subsequent specs will be issued as the build progresses.

---

## Acceptance criteria for v1 complete

When v1 is complete, the following must all be true:

1. `make deploy` deploys the full stack to a Google Cloud project from a clean clone
   - **Deviation 2026-05-21:** deferred to the end-of-project reproducibility
     pass (TASK-14). Until then, deploy is done piecewise via the per-agent
     `make deploy-<agent>` targets + `make deploy-mcp-servers`.
2. `make demo-cargo-plane` runs the Persona 3 scenario end-to-end with the Operations Canvas rendering the spatial choreography in real time
3. `make demo-forecast` runs the Persona 1 scenario in Gemini Enterprise app's Connected Sheets surface
4. `make demo-fleet-buffer` runs the Persona 2 scenario with the Fleet Utilization View
5. All five agents are visible in Agent Registry with cryptographic Agent Identity
   - **Deviation 2026-05-21:** 4 standalone agents on Agent Runtime
     (Orchestrator, Procurement Approval, Forecast Review, Capacity Planning) +
     the Plan Evaluator **bundled in-process** via `AgentTool(agent=…)` inside
     the Orchestrator's Reasoning Engine. Matches the marathon-planner
     reference repo's pattern. Agent Registry shows 4 standalone identities.
6. Agent Gateway policies enforce the $500K human-review threshold
7. Cloud Trace shows full reasoning chains for any agent invocation
8. Customer skinning works: changing `customer.yaml` and redeploying changes branding, terminology, and hero scenario location
9. Fallback playback mode works for the canvas when WebSocket is unavailable
   - **Deviation 2026-05-21:** "WebSocket" was a spec assumption that didn't
     match the actual Vertex AI surface. Streaming uses the deployed
     Reasoning Engine's `:streamQuery` REST endpoint via a same-origin
     Next.js API proxy (`canvas/src/app/api/orchestrator/stream/route.ts`).
     See TASK-10's "SHIPPED PATTERN" banner for the full pivot. Fallback
     Static + Replay modes still apply and remain a hard requirement.
10. `make teardown` removes all resources cleanly
    - **Deviation 2026-05-21:** deferred to the reproducibility pass
      (TASK-14), same as `make deploy`.

### Architectural deviations from earlier drafts (full list)

Quick reference; the *why* + consequences live in `docs/adr/`:
[0002](docs/adr/0002-poetry-not-uv.md) · [0003](docs/adr/0003-plan-evaluator-bundled.md) ·
[0004](docs/adr/0004-streamquery-sse-not-websocket.md) ·
[0005](docs/adr/0005-mcp-skill-composers-bq-direct.md) ·
[0006](docs/adr/0006-global-gemini-routing.md).


- **Package manager:** Poetry instead of `uv`. The original tech-stack lock
  was `uv`, but `uv` doesn't work on the user's corp laptop where this code
  will eventually run. Poetry mirrors the existing `earnings_analyst`
  workflow. CLAUDE.md captures the porting convention (`[tool.poetry]`,
  `poetry-core` build backend).
- **Streaming protocol:** Vertex AI `streamQuery` SSE (NDJSON over `?alt=sse`)
  instead of WebSocket. See TASK-10 "SHIPPED PATTERN" banner.
- **5th agent:** Plan Evaluator bundled in-process, not a 5th standalone
  Reasoning Engine deploy. See acceptance criterion #5 above.
- **MCP skill composer transport:** BQ-direct via `agents/utils/enterprise_data.py`
  instead of HTTP-via-MCP-server. The Cloud Run MCP servers (sap/maximo/fdp)
  are still deployed as a tech demo but aren't on the critical path. The
  toolbox-fronted container has an unresolved uvicorn startup issue documented
  in `docs/architecture.md` once that file lands.
- **Gemini 3 preview model routing:** preview models live on the `global`
  endpoint, not `us-central1`. `agents/utils/global_gemini.GlobalGemini`
  subclass routes model calls to `global` while keeping Agent Engine +
  Memory Bank on `us-central1`. CLAUDE.md captures the pattern.

---

## Out of scope (explicit non-goals)

These are explicitly NOT being built in v1. Do not start work on them.

- A custom application that hides Gemini Enterprise app
- 3D drilling rig animations or downhole tool renderings
- Real SAP / Maximo / FDP connections (mocked only in v1; customer-specific real connections happen in Phase 2)
- Production-grade load capacity (v1 supports demo concurrency only)
- Multi-tenancy (one customer skin active at a time)
- A2UI dynamic UI generation (still v0.9 Preview; defer)
- Mobile responsiveness for the canvas (desktop-only for demos)
- i18n / localization (English only for v1)
- Real-user authentication (demo-only with hardcoded persona switching)

If something feels like it might be out of scope, check this list first. If it's not on the list and you're uncertain, stop and ask before building.

---

## Coding conventions

### Python

- Use `ruff` for linting and formatting (config in `pyproject.toml`)
- Use type hints throughout — Pydantic for data, plain types for everything else
- Use `logging` module, not `print`
- Test with `pytest` — unit tests for skills, integration tests for agent flows
- Use `uv` for all dependency management (`uv add`, `uv sync`, `uv run`)

### TypeScript / Frontend

- Use Prettier for formatting and ESLint for linting (standard Next.js setup)
- Strict TypeScript mode — no `any` without justification
- Server Components where possible; Client Components only when needed
- All agent event schemas mirrored as TypeScript types in `canvas/src/types/`

### Git conventions

- Commits use conventional commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`, etc.)
- Feature branches; squash on merge
- PR descriptions reference the task spec (e.g., "Implements TASK-03 step 2")

### Documentation

- Every agent has a `README.md` in its directory explaining role, model, dependencies, deployment
- Every skill has a complete `SKILL.md` per ADK conventions (frontmatter + instructions + tools listing)
- Architecture decisions captured as `docs/adr/NNNN-decision.md` (Architecture Decision Records)

---

## Demo narration cues in code

For every significant agent action, prompt, or response transformation, include a `# DEMO NARRATION:` comment with the line the demoer will say when that moment appears. Example:

```python
# DEMO NARRATION: "Here's the agent calling Knowledge Catalog via MCP.
# Notice it queries the canonical entity, not the SAP-specific material number —
# that translation happens upstream in the catalog itself."
async def query_canonical_asset(canonical_id: str) -> AssetEntity:
    ...
```

These comments become the source for the demo rehearsal script in `docs/demo_storyboard.md`.

---

## References

External:
- Next '26 keynote demo repo: `github.com/GoogleCloudPlatform/next-26-keynotes`
- ADK documentation: `cloud.google.com/agent-builder/docs`
- Knowledge Catalog: `cloud.google.com/dataplex/docs/knowledge-catalog`
- A2A protocol: `github.com/google/A2A` (Linux Foundation Agentic AI Foundation)

Internal (the planning docs that produced this spec):
- `customer_engagement_brief.md` — strategic context, pre-sales motion
- `keynote_adaptation_plan.md` — technical adaptation of demo-2
- `agentic_sop_oilfield_services_brief.md` — full product brief with all six personas and Operations Canvas
- `persona3_canvas_storyboard.md` — beat-by-beat canvas choreography spec

Read these in order if you need additional context beyond this spec.

---

## When you are stuck

If you encounter ambiguity, follow this priority order:

1. **The reference demo (`next-26-keynotes/devkey/demo-2`)** — does it solve a similar problem? Adapt that solution.
2. **This SPECS.md** — does it answer the question? Re-read carefully.
3. **The task spec you're working on** — check the "Common pitfalls" section.
4. **The planning docs** — `agentic_sop_oilfield_services_brief.md` has the why behind most decisions.
5. **Stop and ask.** Better to clarify than to build the wrong thing.

Do not invent platform features that don't exist. Do not assume APIs work a particular way without checking. When in doubt about an Anthropic / Google API contract, look at how the reference demo uses it.

---

*End of master spec. Proceed to `tasks/TASK-01-environment-and-fork.md`.*
