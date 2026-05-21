# Inputs for the governance module.
#
# Keep this list minimal — every additional variable is one more thing the
# operator has to set correctly. The defaults match the values pinned in
# CLAUDE.md (`vertex-ai-demos-468803` / `us-central1`) so a bare
# `terraform apply` against the demo project Just Works.

variable "project_id" {
  description = "GCP project that owns the agents, MCP servers, Gateway, and Model Armor template."
  type        = string
  default     = "vertex-ai-demos-468803"
}

variable "region" {
  description = "Regional location for Agent Gateway, Agent Identity, and Model Armor template. v1 of the demo pins everything to us-central1 (see CLAUDE.md)."
  type        = string
  default     = "us-central1"
}

variable "agent_engine_ids" {
  description = <<-EOT
    Optional map of agent slug → Reasoning Engine resource id (the trailing
    numeric id, NOT the full resource path). When provided, each Agent
    Identity is bound to its specific Reasoning Engine. When omitted, the
    identity is created in unbound form and bound later via the runbook.
    Keys: orchestrator, plan-evaluator, procurement-approval, forecast-review,
    capacity-planning.
  EOT
  type        = map(string)
  default     = {}
}

variable "agent_slugs" {
  description = "Canonical agent slugs in stable iteration order. Drives SA naming, IAM bindings, and Agent Identity creation."
  type        = list(string)
  default = [
    "orchestrator",
    "plan-evaluator",
    "procurement-approval",
    "forecast-review",
    "capacity-planning",
  ]
}

variable "gateway_policies_yaml_path" {
  description = "Path (relative to this module) to the source-of-truth gateway policies YAML. Resolved + applied via gcloud at apply time."
  type        = string
  default     = "../gateway_policies.yaml"
}

variable "model_armor_yaml_path" {
  description = "Path (relative to this module) to the source-of-truth Model Armor template YAML. Resolved + imported via gcloud at apply time."
  type        = string
  default     = "../model_armor.yaml"
}

variable "model_armor_template_id" {
  description = "Logical id used when importing the Model Armor template. Matches the metadata.name in infra/model_armor.yaml."
  type        = string
  default     = "oilfield-services-mcp-template"
}

variable "gateway_policy_bundle_id" {
  description = "Logical id of the gateway policy bundle. Matches metadata.name in infra/gateway_policies.yaml."
  type        = string
  default     = "oilfield-services-mcp-policies"
}

variable "enable_floor_settings_enforcement" {
  description = "When true, the project-level Model Armor floor setting is enabled and points at the imported template — every registered MCP server gets the template applied. Set false during initial bring-up if you need to test in INSPECT_ONLY first."
  type        = bool
  default     = true
}
