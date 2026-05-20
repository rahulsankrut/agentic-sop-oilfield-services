#!/usr/bin/env bash
# Governance runbook (TASK-11) — operator shell wrapper.
#
# This script bundles the *verifiable* gcloud / REST commands needed to
# stand up the governance posture (Identity + Gateway policies + Model
# Armor) on top of an already-deployed environment.
#
# IMPORTANT: This script DOES NOT execute anything by itself. It echoes
# each command and waits for the operator to confirm before running. The
# Preview-surface gcloud verbs (gcloud agent-platform, gcloud model-armor)
# may not exist as drafted — when a verb errors, follow the fallback
# pointer printed alongside it.
#
# The canonical reference for what each step does (and the manual Console
# fallbacks) is docs/governance.md. Read that first.
#
# Usage:
#   ./infra/governance_runbook.sh           # interactive — confirms each step
#   ./infra/governance_runbook.sh --dry-run # print everything, run nothing
#   ./infra/governance_runbook.sh identity  # run only the identity step
#   ./infra/governance_runbook.sh gateway   # run only the gateway-policies step
#   ./infra/governance_runbook.sh armor     # run only the model-armor step
#   ./infra/governance_runbook.sh attack    # run only the blocked-attack seed step
#
# Required env (sourced from .env or shell):
#   GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION (default us-central1)
#   PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME
#   FORECAST_REVIEW_AGENT_RESOURCE_NAME
#   CAPACITY_PLANNING_AGENT_RESOURCE_NAME
#   ORCHESTRATOR_AGENT_RESOURCE_NAME
#   AGENT_GATEWAY_ENDPOINT (for the blocked-attack seed)

set -euo pipefail

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

DRY_RUN=0
ONLY_STEP=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    identity|gateway|armor|attack) ONLY_STEP="$arg" ;;
    -h|--help)
      sed -n '1,30p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Load .env if present, but don't overwrite anything already in the shell.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT is required (export or set in .env)}"
: "${GOOGLE_CLOUD_LOCATION:=us-central1}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Print + confirm + run a command. With --dry-run, only print.
run_step() {
  local label="$1"
  shift
  echo ""
  echo "---- ${label} ----"
  echo "  \$ $*"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  [dry-run: not executing]"
    return 0
  fi
  read -r -p "  Run this command? [y/N] " ans
  case "$ans" in
    y|Y|yes|YES)
      if "$@"; then
        echo "  -> OK"
      else
        echo "  -> command exited non-zero. Check the fallback pointer in docs/governance.md."
      fi
      ;;
    *)
      echo "  -> skipped"
      ;;
  esac
}

want_step() {
  [[ -z "$ONLY_STEP" || "$ONLY_STEP" == "$1" ]]
}

# ---------------------------------------------------------------------------
# Step 1 — Agent Identity bindings
# ---------------------------------------------------------------------------
#
# The Python script handles idempotent get-or-create over REST. The
# gcloud verb (`gcloud ai agent-identities`) is Preview as of 2026-05-20
# and may have moved; the REST path inside the script is the verified
# fallback. See CLAUDE.md gotcha for status.

if want_step identity; then
  echo ""
  echo "============================================================"
  echo "  STEP 1 — Configure Agent Identity for each deployed agent"
  echo "============================================================"
  echo "Bindings to be reconciled (4 agents):"
  echo "  procurement-approval -> ${PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME:-<UNSET>}"
  echo "  forecast-review      -> ${FORECAST_REVIEW_AGENT_RESOURCE_NAME:-<UNSET>}"
  echo "  capacity-planning    -> ${CAPACITY_PLANNING_AGENT_RESOURCE_NAME:-<UNSET>}"
  echo "  orchestrator         -> ${ORCHESTRATOR_AGENT_RESOURCE_NAME:-<UNSET>}"

  run_step "Dry-run identity reconcile (preview the REST calls)" \
    env AGENT_IDENTITY_DRY_RUN=1 poetry run python scripts/configure_agent_identity.py

  run_step "Live identity reconcile" \
    poetry run python scripts/configure_agent_identity.py

  # Verification — the gcloud list verb (Preview).
  run_step "Verify identities" \
    gcloud ai agent-identities list \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --location="$GOOGLE_CLOUD_LOCATION"
fi

# ---------------------------------------------------------------------------
# Step 2 — Gateway policies
# ---------------------------------------------------------------------------

if want_step gateway; then
  echo ""
  echo "============================================================"
  echo "  STEP 2 — Apply Agent Gateway authorization policies"
  echo "============================================================"
  echo "Source: infra/gateway_policies.yaml"
  echo "Policies: 3 (orchestrator_full_mcp_access, plan_evaluator_readonly_kc,"
  echo "             orchestrator_a2a_procurement_approval)"

  run_step "Resolve \${PROJECT}/\${LOCATION} placeholders + apply via gcloud" \
    make apply-gateway-policies

  run_step "Verify policy bundle landed" \
    gcloud agent-platform gateway-policies list \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --location="$GOOGLE_CLOUD_LOCATION"
fi

# ---------------------------------------------------------------------------
# Step 3 — Model Armor
# ---------------------------------------------------------------------------

if want_step armor; then
  echo ""
  echo "============================================================"
  echo "  STEP 3 — Import + attach Model Armor template"
  echo "============================================================"
  echo "Source: infra/model_armor.yaml"
  echo "Template: oilfield-services-mcp-template"
  echo "Filters: promptInjectionAndJailbreak, sensitiveDataProtection,"
  echo "         responsibleAi, maliciousUriFilterSettings"

  run_step "Import the Model Armor template via gcloud" \
    make enable-model-armor

  run_step "Confirm template was created" \
    gcloud model-armor templates describe oilfield-services-mcp-template \
    --project="$GOOGLE_CLOUD_PROJECT" \
    --location="$GOOGLE_CLOUD_LOCATION"

  run_step "Confirm floor settings attach the template project-wide" \
    gcloud model-armor floorsettings describe \
    --project="$GOOGLE_CLOUD_PROJECT"
fi

# ---------------------------------------------------------------------------
# Step 4 — Seed a blocked-attack example
# ---------------------------------------------------------------------------

if want_step attack; then
  echo ""
  echo "============================================================"
  echo "  STEP 4 — Seed a blocked-attack example in Cloud Logging"
  echo "============================================================"
  echo "Target: \$AGENT_GATEWAY_ENDPOINT (must be set)"
  echo "Payload: synthetic prompt-injection (placeholders only, no real names)"

  if [[ -z "${AGENT_GATEWAY_ENDPOINT:-}" ]]; then
    echo "  AGENT_GATEWAY_ENDPOINT is unset; skipping seed step."
    echo "  Populate it (terraform output or Console) and re-run with 'attack' arg."
  else
    run_step "Dry-run the attack payload (preview only)" \
      env BLOCKED_ATTACK_DRY_RUN=1 poetry run python scripts/seed_blocked_attack_example.py

    run_step "Send the attack (expect HTTP 4xx with Model Armor block)" \
      poetry run python scripts/seed_blocked_attack_example.py

    run_step "Confirm the block landed in Cloud Logging" \
      gcloud logging read 'jsonPayload.modelArmor.blocked=true' \
      --project="$GOOGLE_CLOUD_PROJECT" \
      --limit=5 \
      --freshness=10m
  fi
fi

echo ""
echo "============================================================"
echo "  Runbook complete."
echo "  Full operator instructions + fallbacks: docs/governance.md"
echo "============================================================"
