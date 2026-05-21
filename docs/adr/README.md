# Architecture Decision Records

Numbered, dated, status-tracked records of the architectural choices
that shape this codebase. New ADRs get the next number. Once
`Accepted`, edit only with an addendum or by marking
`Superseded by ADR-NNNN`.

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-adopt-adk-2-workflow.md) | Adopt ADK 2.0 Workflow for the Capacity Orchestrator | Accepted (TASK-04) |
| [0002](0002-poetry-not-uv.md) | Poetry over `uv` for Python dependency management | Accepted |
| [0003](0003-plan-evaluator-bundled.md) | Plan Evaluator bundled in-process via `AgentTool` | Accepted (TASK-02) |
| [0004](0004-streamquery-sse-not-websocket.md) | `streamQuery` SSE proxy instead of WebSocket gateway | Accepted (TASK-10) |
| [0005](0005-mcp-skill-composers-bq-direct.md) | MCP skill composers go BigQuery-direct | Accepted (TASK-MCP-REFACTOR) |
| [0006](0006-global-gemini-routing.md) | `GlobalGemini` for routing model calls to the `global` endpoint | Accepted (TASK-02) |

## Why ADRs

The inline "Deviation" notes in `SPECS.md` and the "Known gotchas"
list in `CLAUDE.md` capture *what* changed and *what to do about it*.
ADRs add the *why* — the context that produced the decision and the
consequences we accepted. Pair them: SPECS / CLAUDE.md are the
running checklist; ADRs are the audit trail.
