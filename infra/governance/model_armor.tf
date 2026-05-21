# Model Armor template + floor settings.
#
# Source of truth: `../model_armor.yaml` (var.model_armor_yaml_path).
# This file does NOT duplicate the template definition — it resolves the
# placeholders and imports the YAML via the Preview gcloud verb, then sets
# the project-level floor settings to attach the template to every
# registered MCP server in one shot (per the YAML's design — see comment
# at the bottom of `infra/model_armor.yaml`).
#
# -----------------------------------------------------------------------------
# Status (verified 2026-05-20):
#
#   - `google_model_armor_template` and `google_model_armor_floor_setting`
#     DO exist in google-beta (5.30+) but their schema is YAML-shape-sensitive
#     and the resource has known issues with the four-filter nested form used
#     in `infra/model_armor.yaml`. To avoid TF/YAML drift, we use the canonical
#     `gcloud model-armor templates import` path against the YAML, with a
#     REST-fallback note for when the verb is missing.
#   - The floor settings PATCH endpoint is stable and trivial; could be done
#     via typed resource but is kept consistent (single source of truth =
#     the YAML).
#
# Fallback: null_resource + local-exec for both the template import and the
# floor settings attach. Re-runs when the rendered YAML changes.
#
# TODO: when google-beta's `google_model_armor_template` reaches schema
# parity with the four-filter template in `infra/model_armor.yaml`, swap the
# null_resource shim for the typed resource (it'll consume the YAML directly
# via `yamldecode(file(...))` into the resource block).
# -----------------------------------------------------------------------------

locals {
  model_armor_raw = file("${path.module}/${var.model_armor_yaml_path}")

  model_armor_resolved = replace(
    replace(local.model_armor_raw, "$${PROJECT}", var.project_id),
    "$${LOCATION}", var.region
  )

  model_armor_rendered_path = "${path.module}/.terraform_render/model_armor.resolved.yaml"

  # Canonical resource path used when wiring floor settings.
  model_armor_template_resource = "projects/${var.project_id}/locations/${var.region}/templates/${var.model_armor_template_id}"
}

resource "local_file" "model_armor_resolved" {
  content         = local.model_armor_resolved
  filename        = local.model_armor_rendered_path
  file_permission = "0644"
}

# -----------------------------------------------------------------------------
# Step 1 — Import the Model Armor template from the resolved YAML.
# -----------------------------------------------------------------------------

resource "null_resource" "model_armor_template" {
  triggers = {
    content_sha = sha256(local.model_armor_resolved)
    template_id = var.model_armor_template_id
    project_id  = var.project_id
    region      = var.region
  }

  # DEMO NARRATION: "Model Armor template is also code. Four filter
  # categories — Responsible AI, prompt injection, sensitive data,
  # malicious URI. The audit director can read the YAML and see exactly
  # what thresholds are set."
  provisioner "local-exec" {
    command = <<-EOT
      set -euo pipefail

      RESOLVED="${local_file.model_armor_resolved.filename}"
      TEMPLATE="${var.model_armor_template_id}"
      PROJECT="${var.project_id}"
      LOCATION="${var.region}"

      echo ">>> Importing Model Armor template '$TEMPLATE' from $RESOLVED ..."
      if gcloud model-armor templates import "$TEMPLATE" \
           --source="$RESOLVED" \
           --project="$PROJECT" \
           --location="$LOCATION" 2>/tmp/ma_template_err.$$; then
        rm -f /tmp/ma_template_err.$$
        exit 0
      fi

      err=$(cat /tmp/ma_template_err.$$)
      rm -f /tmp/ma_template_err.$$

      if echo "$err" | grep -q -i "unknown command\|Invalid choice"; then
        echo "$err" >&2
        echo "ERROR: 'gcloud model-armor' verb missing. Fall back to REST per docs/governance.md §3.4:" >&2
        echo "  POST https://modelarmor.googleapis.com/v1/projects/$PROJECT/locations/$LOCATION/templates?templateId=$TEMPLATE" >&2
        exit 2
      fi

      echo "$err" >&2
      exit 1
    EOT
  }

  provisioner "local-exec" {
    when = destroy
    command = <<-EOT
      set -u
      TEMPLATE="${self.triggers.template_id}"
      PROJECT="${self.triggers.project_id}"
      LOCATION="${self.triggers.region}"

      gcloud model-armor templates delete "$TEMPLATE" \
        --project="$PROJECT" --location="$LOCATION" --quiet 2>/dev/null \
      || true
    EOT
  }

  depends_on = [local_file.model_armor_resolved]
}

# -----------------------------------------------------------------------------
# Step 2 — Attach the template to all registered MCP servers via project-level
# Model Armor floor settings. The Gateway picks up the association
# automatically (per infra/model_armor.yaml comments lines 107-119).
# -----------------------------------------------------------------------------

resource "null_resource" "model_armor_floor_settings" {
  count = var.enable_floor_settings_enforcement ? 1 : 0

  triggers = {
    template_resource = local.model_armor_template_resource
    project_id        = var.project_id
    enforcement       = "ENABLED"
  }

  # DEMO NARRATION: "Floor settings are the project-wide knob. Set once,
  # applied to every registered MCP server — SAP, Maximo, FDP, Knowledge
  # Catalog. New MCP servers inherit the template automatically."
  provisioner "local-exec" {
    command = <<-EOT
      set -euo pipefail

      TEMPLATE_PATH="${local.model_armor_template_resource}"
      PROJECT="${var.project_id}"

      echo ">>> Updating Model Armor floor settings to enforce template '$TEMPLATE_PATH' ..."
      if gcloud model-armor floorsettings update \
           --full-uri="projects/$PROJECT/locations/global/floorSetting" \
           --enable-floor-setting-enforcement=TRUE \
           --add-integrated-services=GOOGLE_MCP_SERVER \
           --google-mcp-server-enforcement-type=INSPECT_AND_BLOCK \
           --enable-google-mcp-server-cloud-logging \
           --project="$PROJECT" 2>/tmp/ma_floor_err.$$; then
        rm -f /tmp/ma_floor_err.$$
      else
        err=$(cat /tmp/ma_floor_err.$$)
        rm -f /tmp/ma_floor_err.$$
        if echo "$err" | grep -q -i "unknown command\|Invalid choice"; then
          echo "$err" >&2
          echo "ERROR: 'gcloud model-armor floorsettings' verb missing. Fall back to REST per docs/governance.md §3.4:" >&2
          echo "  PATCH https://modelarmor.googleapis.com/v1/projects/$PROJECT/floorSettings" >&2
          exit 2
        fi
        echo "$err" >&2
        exit 1
      fi

      # Separately PATCH the agentplatform floor setting that points the
      # Gateway at this template (the gcloud verb above enables MCP enforcement
      # at the Model Armor side; agentplatform needs the template *id* on its
      # own floor setting so the Gateway knows which template to invoke).
      echo ">>> Attaching template to Agent Gateway floor settings via REST ..."
      ACCESS_TOKEN=$(gcloud auth print-access-token)
      curl -sS -X PATCH \
        "https://agentplatform.googleapis.com/v1beta1/projects/$PROJECT/floorSettings?updateMask=mcpArmorTemplate" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        --data "{\"mcpArmorTemplate\":\"$TEMPLATE_PATH\"}" \
        --fail-with-body || {
          echo "WARN: agentplatform.floorSettings PATCH failed — Preview endpoint may be unavailable." >&2
          echo "Re-attach via Console: https://console.cloud.google.com/security/model-armor/floor-settings" >&2
          # Don't fail apply on this — the Model Armor side enforcement is the
          # critical control; the agentplatform pointer is a convenience.
        }
    EOT
  }

  depends_on = [null_resource.model_armor_template]
}
