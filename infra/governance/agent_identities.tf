# Agent Identities — one per agent, each bound to the matching service account.
#
# Agent Identity is the cryptographic principal that Agent Gateway authenticates
# every MCP call against. It's a thin wrapper around the service account, but
# the binding step is required for the Gateway IAM checks to recognize the
# caller as a known agent (vs. a generic GCP workload).
#
# -----------------------------------------------------------------------------
# Status (verified 2026-05-20 against ~/.claude/references/gemini-enterprise-agent-platform.md):
#
#   - `google_ai_platform_agent_identity` does NOT exist in google-beta as of
#     provider 6.x. Same for `google_agent_platform_identity`.
#   - The gcloud verb is Preview: `gcloud ai agent-identities create …`
#     (may also live at `gcloud agent-platform identities create …` —
#     CLAUDE.md flags the verb tree as in flux).
#   - The REST endpoint shape lives at:
#       POST projects/{p}/locations/{l}/agentIdentities?agentIdentityId={id}
#     on the `agentplatform.googleapis.com` host.
#
# Fallback: `null_resource` + `local-exec` calling the gcloud Preview verb,
# with a try-the-other-verb-tree shell fallback for the in-flux command path.
# Triggers re-run when SA email or bound engine id changes.
#
# TODO: replace with typed `google_ai_platform_agent_identity` (or whatever
# the GA resource is named) when the provider ships it. The conceptual surface
# we need: `name`, `service_account`, optional `bound_agent`, `display_name`,
# `project`, `location`.
# -----------------------------------------------------------------------------

resource "null_resource" "agent_identity" {
  for_each = toset(var.agent_slugs)

  triggers = {
    # Force recreate when the SA changes, the bound engine changes, or the
    # project/region changes. Keeping the trigger set narrow so re-applies
    # don't churn unless the underlying binding really changed.
    service_account = google_service_account.agent[each.value].email
    bound_agent_id  = lookup(var.agent_engine_ids, each.value, "")
    project_id      = var.project_id
    region          = var.region
  }

  # DEMO NARRATION: "Each identity is bound to a service account.
  # mTLS + DPoP at the Gateway are issued against the identity, not the
  # raw service account — that's the SPIFFE-style separation the platform
  # gives you for free."
  provisioner "local-exec" {
    command = <<-EOT
      set -euo pipefail

      IDENTITY="${each.value}-identity"
      SA="${google_service_account.agent[each.value].email}"
      BOUND="${lookup(var.agent_engine_ids, each.value, "")}"
      PROJECT="${var.project_id}"
      LOCATION="${var.region}"
      DISPLAY="${each.value} Agent Identity"

      BOUND_FLAG=""
      if [ -n "$BOUND" ]; then
        # Accept either a bare numeric id or a full resource path; normalize
        # to the full path the API expects.
        case "$BOUND" in
          projects/*) BOUND_PATH="$BOUND" ;;
          *) BOUND_PATH="projects/$PROJECT/locations/$LOCATION/reasoningEngines/$BOUND" ;;
        esac
        BOUND_FLAG="--bound-agent=$BOUND_PATH"
      fi

      # Try the two known verb trees in order. The CLI surface for Agent
      # Identity is Preview and has moved at least once (CLAUDE.md). We do
      # NOT swallow non-"unknown command" errors — those should bubble up.
      try_create() {
        local cmd="$1"
        echo ">>> Trying: $cmd create $IDENTITY ..."
        if $cmd create "$IDENTITY" \
             --service-account="$SA" \
             $BOUND_FLAG \
             --display-name="$DISPLAY" \
             --project="$PROJECT" \
             --location="$LOCATION" 2>/tmp/agent_identity_err.$$; then
          return 0
        fi
        local err
        err=$(cat /tmp/agent_identity_err.$$)
        rm -f /tmp/agent_identity_err.$$
        # If identity already exists, treat as success (idempotent).
        if echo "$err" | grep -q -i "already exists\|ALREADY_EXISTS"; then
          echo ">>> $IDENTITY already exists — skipping create."
          return 0
        fi
        # If the verb is unknown, signal to caller so we can try the other tree.
        if echo "$err" | grep -q -i "unknown command\|Invalid choice"; then
          echo "$err" >&2
          return 2
        fi
        # Real error — surface it.
        echo "$err" >&2
        return 1
      }

      try_create "gcloud ai agent-identities" && exit 0
      rc=$?
      if [ "$rc" -eq 2 ]; then
        try_create "gcloud agent-platform identities" && exit 0
        rc=$?
      fi

      if [ "$rc" -ne 0 ]; then
        echo "ERROR: failed to create agent identity '$IDENTITY' via gcloud (both verb trees)." >&2
        echo "Fall back to REST per docs/governance.md §3.1 or run scripts/configure_agent_identity.py." >&2
        exit "$rc"
      fi
    EOT
  }

  # Destroy hook — same fallback dance. Best-effort; we don't fail apply on
  # a 404 during destroy. Destroy provisioners can only reference `self.*`
  # (and `each.key`) — so the SA email, slug, project, region all have to
  # be threaded through `triggers`.
  provisioner "local-exec" {
    when = destroy
    command = <<-EOT
      set -u
      IDENTITY="${each.key}-identity"
      PROJECT="${self.triggers.project_id}"
      LOCATION="${self.triggers.region}"

      gcloud ai agent-identities delete "$IDENTITY" \
        --project="$PROJECT" --location="$LOCATION" --quiet 2>/dev/null \
      || gcloud agent-platform identities delete "$IDENTITY" \
           --project="$PROJECT" --location="$LOCATION" --quiet 2>/dev/null \
      || true
    EOT
  }

  depends_on = [google_service_account.agent]
}
