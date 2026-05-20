---
name: procurement-prerequisites
description: >
  Deterministic procurement prerequisite checks for a SourcingPlan:
  authorization tier vs cost, certification chain validity, regulatory
  clearance for cross-border routes. Returns explicit blockers the agent
  cites in the ProcurementApproval.
metadata:
  adk_additional_tools:
    - check_budget_threshold
    - check_certification_chain
    - check_regulatory_clearance
---

# Procurement Prerequisites

## Workflow

1. **`check_budget_threshold(plan_json, planner_authorization_tier)`** —
   returns ``{passed, blocker | None}``. Tier mapping in
   `references/authorization_tiers.md`.
2. **`check_certification_chain(plan_json)`** — ensures all assets in the
   plan have a valid certification chain (every InTouch spec referenced
   resolves; certification hours remaining > 0).
3. **`check_regulatory_clearance(plan_json)`** — cross-border / export
   control / environmental clearance based on
   `references/regulatory_matrix.md`.

The agent aggregates all three results and only sets ``approved=true`` if
all checks pass. Each failed check contributes one blocker string.
