# Per-agent IAM bindings — least privilege per TASK-11 Step 2.
#
# The role names are aligned to the spec (`roles/mcp.toolUser`,
# `roles/aiplatform.memoryBankUser`, `roles/dataplex.catalogViewer`,
# `roles/bigquery.dataViewer`). docs/governance.md §3.2 flags
# `roles/mcp.toolUser` as a Preview role name that may rename to
# `roles/agentplatform.mcpToolUser` at GA — when that flip happens, swap
# every `roles/mcp.toolUser` here in one edit.
#
# Deviation note vs docs/governance.md:
#   The runbook lists FOUR service accounts (Plan Evaluator is currently
#   in-process inside the Orchestrator deploy). The Terraform module is the
#   forward-looking source of truth and creates all FIVE — Plan Evaluator
#   gets its own SA + Identity so the policy in `infra/gateway_policies.yaml`
#   (`plan_evaluator_readonly_kc`) has a real principal to bind to. When
#   Plan Evaluator splits into its own Reasoning Engine, no IaC change
#   needed.

locals {
  # SA email getter — explicit local makes every binding readable.
  sa = local.service_account_emails
}

# -----------------------------------------------------------------------------
# Orchestrator — full MCP tool user, Memory Bank read/write, Knowledge Catalog viewer.
# Drives the workflow, calls every backend, persists demo memories.
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "orchestrator_mcp_tool_user" {
  project = var.project_id
  role    = "roles/mcp.toolUser"
  member  = "serviceAccount:${local.sa["orchestrator"]}"

  depends_on = [google_service_account.agent]
}

resource "google_project_iam_member" "orchestrator_memory_bank" {
  project = var.project_id
  role    = "roles/aiplatform.memoryBankUser"
  member  = "serviceAccount:${local.sa["orchestrator"]}"

  depends_on = [google_service_account.agent]
}

resource "google_project_iam_member" "orchestrator_kc_viewer" {
  project = var.project_id
  role    = "roles/dataplex.catalogViewer"
  member  = "serviceAccount:${local.sa["orchestrator"]}"

  depends_on = [google_service_account.agent]
}

# -----------------------------------------------------------------------------
# Plan Evaluator — MCP tool user ONLY. Read-only KC is enforced by Gateway
# policy (`plan_evaluator_readonly_kc`), not by an IAM role. No Memory Bank,
# no BigQuery, no Catalog viewer.
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "plan_evaluator_mcp_tool_user" {
  project = var.project_id
  role    = "roles/mcp.toolUser"
  member  = "serviceAccount:${local.sa["plan-evaluator"]}"

  depends_on = [google_service_account.agent]
}

# -----------------------------------------------------------------------------
# Procurement Approval — MCP tool user. For the demo, only invoked via A2A
# from the Orchestrator; doesn't need BigQuery or Memory Bank.
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "procurement_approval_mcp_tool_user" {
  project = var.project_id
  role    = "roles/mcp.toolUser"
  member  = "serviceAccount:${local.sa["procurement-approval"]}"

  depends_on = [google_service_account.agent]
}

# -----------------------------------------------------------------------------
# Forecast Review — BigQuery viewer (reads forecast tables) + Memory Bank
# reader (reads cached defaults). Read-only by IAM, no MCP role.
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "forecast_review_bq_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${local.sa["forecast-review"]}"

  depends_on = [google_service_account.agent]
}

resource "google_project_iam_member" "forecast_review_memory_bank_reader" {
  project = var.project_id
  # Memory Bank doesn't yet split read/write into distinct roles; the
  # `memoryBankUser` role is the closest available. Gateway policy denies
  # writes (no write policy for this SA). When a `memoryBankViewer` role
  # ships, swap this for the stricter form.
  role   = "roles/aiplatform.memoryBankUser"
  member = "serviceAccount:${local.sa["forecast-review"]}"

  depends_on = [google_service_account.agent]
}

# -----------------------------------------------------------------------------
# Capacity Planning — BigQuery viewer + MCP tool user (read-only enforced by
# Gateway policy `capacity_planning_read_mcp`).
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "capacity_planning_bq_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${local.sa["capacity-planning"]}"

  depends_on = [google_service_account.agent]
}

resource "google_project_iam_member" "capacity_planning_mcp_tool_user" {
  project = var.project_id
  role    = "roles/mcp.toolUser"
  member  = "serviceAccount:${local.sa["capacity-planning"]}"

  depends_on = [google_service_account.agent]
}

# -----------------------------------------------------------------------------
# Logging — every agent SA gets `roles/logging.logWriter` so traces and audit
# events from Gateway / Model Armor are attributable. Strictly necessary or
# the Gateway decision logs show "(unknown principal)" for the agent's leg.
# -----------------------------------------------------------------------------

resource "google_project_iam_member" "agent_log_writer" {
  for_each = toset(var.agent_slugs)

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${local.sa[each.value]}"

  depends_on = [google_service_account.agent]
}
