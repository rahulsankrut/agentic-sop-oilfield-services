# Five service accounts, one per agent. Naming pattern: `<slug>-agent-sa`.
#
# These are the principals every Agent Gateway policy, every IAM binding,
# and every Agent Identity record references. Keep names stable — they
# show up in `gateway_policies.yaml` resource paths and in audit logs that
# Persona 6 (Ayesha) reads during the demo.
#
# DEMO NARRATION: "Five agents. Five service accounts. Five Agent
# Identities. Audit can answer 'what can the Plan Evaluator reach?'
# without reading code — they read the bindings on
# plan-evaluator-agent-sa."

locals {
  # Map slug → SA email so every downstream resource can index by slug.
  service_account_emails = {
    for slug in var.agent_slugs :
    slug => "${slug}-agent-sa@${var.project_id}.iam.gserviceaccount.com"
  }
}

resource "google_service_account" "agent" {
  for_each = toset(var.agent_slugs)

  project      = var.project_id
  account_id   = "${each.value}-agent-sa"
  display_name = "Service account for ${each.value} agent"
  description  = "Identity principal for the ${each.value} agent. Used by Agent Identity bindings, Agent Gateway policies (infra/gateway_policies.yaml), and per-agent IAM (TASK-11)."
}
