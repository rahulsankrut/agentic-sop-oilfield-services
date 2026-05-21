# Agent Gateway authorization policies.
#
# Source of truth: `../gateway_policies.yaml` (var.gateway_policies_yaml_path).
# This file does NOT duplicate the policy definitions — it only:
#   1. Resolves the `${PROJECT}` and `${LOCATION}` placeholders in the YAML
#      against this module's variables and writes the resolved bundle to a
#      stable path under `${path.module}/.terraform_render/`.
#   2. Applies the resolved bundle via `gcloud agent-platform gateway-policies
#      apply` (with the documented verb-tree fallback).
#
# -----------------------------------------------------------------------------
# Status (verified 2026-05-20):
#
#   - `google_gateway_authorization_policy` does NOT exist in google or
#     google-beta provider as of v6.x. The Agent Gateway typed resource set
#     hasn't shipped (CLI verbs themselves are still Preview).
#   - REST endpoint shape (per ~/.claude/references/gemini-enterprise-agent-platform.md):
#       https://agentplatform.googleapis.com/v1beta1/projects/{p}/locations/{l}/gatewayPolicies/{id}
#     Idempotent GET → PATCH-or-POST works.
#
# Fallback: null_resource + local-exec calling the Preview gcloud verb, with
# a try-the-other-verb-tree shell fallback. The `local_file` resource is the
# rendered bundle Terraform owns — re-applies when project/location/source
# YAML change.
#
# TODO: replace with typed `google_gateway_authorization_policy` (or
# `google_agent_platform_gateway_policy`, whatever the GA name is) when the
# provider ships it. Until then, this file is the authoritative way to drive
# the bundle through IaC.
# -----------------------------------------------------------------------------

# Resolve ${PROJECT} and ${LOCATION} in the YAML against module variables.
# Using `replace` (not `templatefile`) because the YAML uses the
# envsubst-style `${PROJECT}` syntax — `templatefile` would try to interpret
# them as TF interpolations and fail on the unquoted dollar signs.
locals {
  gateway_policies_raw = file("${path.module}/${var.gateway_policies_yaml_path}")

  gateway_policies_resolved = replace(
    replace(local.gateway_policies_raw, "$${PROJECT}", var.project_id),
    "$${LOCATION}", var.region
  )

  gateway_policies_rendered_path = "${path.module}/.terraform_render/gateway_policies.resolved.yaml"
}

resource "local_file" "gateway_policies_resolved" {
  content         = local.gateway_policies_resolved
  filename        = local.gateway_policies_rendered_path
  file_permission = "0644"

  # Don't commit the rendered file; .terraform_render/ is gitignored at the
  # module root. It exists only as the artifact `gcloud apply` reads from.
}

resource "null_resource" "gateway_policies_apply" {
  triggers = {
    # Re-apply when the resolved content changes (which captures changes to
    # both the source YAML and the project_id/region).
    content_sha = sha256(local.gateway_policies_resolved)
    bundle_id   = var.gateway_policy_bundle_id
    project_id  = var.project_id
    region      = var.region
  }

  # DEMO NARRATION: "The policy bundle here — `oilfield-services-mcp-policies`
  # — is checked into IaC. The audit director can read the YAML, then see
  # the same three policies in the Gateway console. No drift between code
  # and runtime."
  provisioner "local-exec" {
    command = <<-EOT
      set -euo pipefail

      RESOLVED="${local_file.gateway_policies_resolved.filename}"
      PROJECT="${var.project_id}"
      LOCATION="${var.region}"

      try_apply() {
        local cmd="$1"
        echo ">>> Trying: $cmd apply --policy-file=$RESOLVED ..."
        if $cmd apply \
             --policy-file="$RESOLVED" \
             --project="$PROJECT" \
             --location="$LOCATION" 2>/tmp/gw_policy_err.$$; then
          return 0
        fi
        local err
        err=$(cat /tmp/gw_policy_err.$$)
        rm -f /tmp/gw_policy_err.$$
        if echo "$err" | grep -q -i "unknown command\|Invalid choice"; then
          echo "$err" >&2
          return 2
        fi
        echo "$err" >&2
        return 1
      }

      try_apply "gcloud agent-platform gateway-policies" && exit 0
      rc=$?
      if [ "$rc" -eq 2 ]; then
        # Verb tree alternative observed across Preview revs.
        try_apply "gcloud agentplatform gateway-policies" && exit 0
        rc=$?
      fi

      if [ "$rc" -ne 0 ]; then
        echo "ERROR: failed to apply gateway policies via gcloud (both verb trees)." >&2
        echo "Fall back to REST per docs/governance.md §3.3:" >&2
        echo "  POST https://agentplatform.googleapis.com/v1beta1/projects/$PROJECT/locations/$LOCATION/gatewayPolicies" >&2
        echo "with the body translated from $RESOLVED." >&2
        exit "$rc"
      fi
    EOT
  }

  # Destroy hook — best-effort delete of the bundle so terraform destroy is
  # symmetric. Failure is non-fatal (the bundle may already be gone).
  provisioner "local-exec" {
    when = destroy
    command = <<-EOT
      set -u
      BUNDLE="${self.triggers.bundle_id}"
      PROJECT="${self.triggers.project_id}"
      LOCATION="${self.triggers.region}"

      gcloud agent-platform gateway-policies delete "$BUNDLE" \
        --project="$PROJECT" --location="$LOCATION" --quiet 2>/dev/null \
      || gcloud agentplatform gateway-policies delete "$BUNDLE" \
           --project="$PROJECT" --location="$LOCATION" --quiet 2>/dev/null \
      || true
    EOT
  }

  depends_on = [
    local_file.gateway_policies_resolved,
    google_service_account.agent, # principals must exist before policies bind to them
    null_resource.agent_identity, # identities exist before policies authorize them
  ]
}
