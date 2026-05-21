# Outputs — every artifact the module creates, exposed for chaining /
# verification.

output "service_account_emails" {
  description = "Map of agent slug → service account email."
  value       = local.service_account_emails
}

output "service_account_ids" {
  description = "Map of agent slug → fully-qualified service account resource id."
  value = {
    for slug in var.agent_slugs :
    slug => google_service_account.agent[slug].id
  }
}

output "agent_identity_names" {
  description = "Map of agent slug → Agent Identity resource name (logical id, not full path)."
  value = {
    for slug in var.agent_slugs :
    slug => "${slug}-identity"
  }
}

output "agent_identity_resource_paths" {
  description = "Map of agent slug → full Agent Identity resource path on agentplatform.googleapis.com."
  value = {
    for slug in var.agent_slugs :
    slug => "projects/${var.project_id}/locations/${var.region}/agentIdentities/${slug}-identity"
  }
}

output "gateway_policy_bundle_id" {
  description = "Logical id of the applied gateway policy bundle (the metadata.name in infra/gateway_policies.yaml)."
  value       = var.gateway_policy_bundle_id
}

output "gateway_policy_resource_path" {
  description = "Full resource path of the gateway policy bundle on agentplatform.googleapis.com."
  value       = "projects/${var.project_id}/locations/${var.region}/gatewayPolicies/${var.gateway_policy_bundle_id}"
}

output "gateway_policies_rendered_path" {
  description = "Local filesystem path where the resolved gateway policies YAML was written."
  value       = local_file.gateway_policies_resolved.filename
}

output "model_armor_template_id" {
  description = "Logical id of the imported Model Armor template."
  value       = var.model_armor_template_id
}

output "model_armor_template_resource" {
  description = "Full resource path of the Model Armor template."
  value       = local.model_armor_template_resource
}

output "model_armor_rendered_path" {
  description = "Local filesystem path where the resolved Model Armor YAML was written."
  value       = local_file.model_armor_resolved.filename
}

output "policy_summary" {
  description = "Human-readable summary of the policies created. Useful for `terraform output -raw policy_summary` during demos."
  value = <<-EOT
    Governance posture for project ${var.project_id} (region ${var.region}):

      Service accounts (5):
        - ${local.service_account_emails["orchestrator"]}
        - ${local.service_account_emails["plan-evaluator"]}
        - ${local.service_account_emails["procurement-approval"]}
        - ${local.service_account_emails["forecast-review"]}
        - ${local.service_account_emails["capacity-planning"]}

      Agent Identities (5):
        - orchestrator-identity, plan-evaluator-identity,
          procurement-approval-identity, forecast-review-identity,
          capacity-planning-identity

      Gateway policy bundle:
        ${var.gateway_policy_bundle_id}
        (default-DENY + 3 explicit ALLOW policies — see infra/gateway_policies.yaml)

      Model Armor:
        Template: ${var.model_armor_template_id}
        Floor enforcement enabled: ${var.enable_floor_settings_enforcement}
        Filters: prompt injection (BOTH/MEDIUM+), sensitive data (RESPONSE),
                 responsible AI (RESPONSE), malicious URI (RESPONSE)
  EOT
}
