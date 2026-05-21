#!/usr/bin/env bash
# Demo runner — stage-manager for the four customer-demo scenarios.
#
# Sequences the manual steps a presenter would otherwise do by hand:
#   1. Set the active customer skin (default vs halliburton).
#   2. Verify the deployed agent for the persona is reachable.
#   3. Pre-warm the Memory Bank seed session for the persona.
#   4. Print a presenter checklist + URLs.
#   5. (--canvas) start the canvas dev server in the foreground.
#
# Usage:
#   scripts/demo_runner.sh <persona> <scenario> [skin]
#
# Persona / scenario / skin combinations the project recognises:
#   maria   cargo-plane      default | halliburton
#   david   forecast-review  default | halliburton
#   tomas   buffer-planning  default | halliburton
#   priya   deep-research    default
#   rafael  agent-studio     default
#   ayesha  audit-registry   default
#
# Invoke directly, or via `make demo-cargo-plane` / `make demo-forecast`
# / `make demo-fleet-buffer` wrappers.

set -euo pipefail

PERSONA="${1:?persona required (maria|david|tomas|priya|rafael|ayesha)}"
SCENARIO="${2:?scenario required (cargo-plane|forecast-review|buffer-planning|...)}"
SKIN="${3:-default}"

CANVAS_PORT="${CANVAS_PORT:-3000}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Pretty banner.
hr() { printf '═%.0s' {1..68}; printf '\n'; }
section() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }

clear
hr
printf '  \033[1mDEMO RUNNER\033[0m — persona=%s  scenario=%s  skin=%s\n' "$PERSONA" "$SCENARIO" "$SKIN"
hr

# ----------------------------------------------------------------------
# Step 1 — active customer skin
# ----------------------------------------------------------------------
section "1. Active customer skin"
if [[ -f "skins/$SKIN/customer.yaml" ]]; then
    # Use the existing target; it copies skins/<slug>/* into canvas/
    # generated data + sets the agent-side env.
    make -s use-skin SKIN="$SKIN" 2>&1 | sed 's/^/    /'
else
    echo "  ERROR: skins/$SKIN/customer.yaml not found — known: $(ls skins/ | grep -v -E 'TODO|schema|README' | tr '\n' ' ')"
    exit 1
fi

# ----------------------------------------------------------------------
# Step 2 — deployed agent reachability
# ----------------------------------------------------------------------
section "2. Deployed agent reachability"

# Map persona → expected agent env var (case stmt for bash 3.2 portability).
VAR=""
case "$PERSONA" in
    maria)  VAR="ORCHESTRATOR_AGENT_RESOURCE_NAME" ;;
    david)  VAR="FORECAST_REVIEW_AGENT_RESOURCE_NAME" ;;
    tomas)  VAR="CAPACITY_PLANNING_AGENT_RESOURCE_NAME" ;;
    priya)  VAR="ORCHESTRATOR_AGENT_RESOURCE_NAME" ;;
    rafael) VAR="" ;;
    ayesha) VAR="" ;;
esac
if [[ -n "$VAR" ]]; then
    # Source .env safely (strip quotes, ignore comments).
    if [[ -f .env ]]; then
        VALUE="$(grep -E "^${VAR}=" .env | tail -1 | sed -E 's/^[^=]+=//' | sed -E 's/^"(.*)"$/\1/')"
    else
        VALUE=""
    fi
    if [[ -z "$VALUE" ]]; then
        echo "  ⚠️  ${VAR} not set in .env — deploy the agent first or skip live mode"
    else
        echo "  ✓  $VAR = ${VALUE##*/}"
    fi
else
    echo "  (persona has no live agent backend — static A2UI demo only)"
fi

# ----------------------------------------------------------------------
# Step 3 — Memory Bank pre-warm (idempotent)
# ----------------------------------------------------------------------
section "3. Memory Bank pre-warm"
SESSION_ID=""
case "$PERSONA" in
    maria)  SESSION_ID="demo-maria-cargo-plane-v1" ;;
    david)  SESSION_ID="demo-david-forecast-review-v1" ;;
    tomas)  SESSION_ID="demo-tomas-buffer-planning-v1" ;;
    priya)  SESSION_ID="demo-priya-rollup-v1" ;;
    rafael) SESSION_ID="demo-rafael-extension-v1" ;;
    ayesha) SESSION_ID="demo-ayesha-audit-v1" ;;
esac

if [[ -n "$SESSION_ID" ]]; then
    echo "  target session: $SESSION_ID"
    echo "  (run \`make seed-demo-sessions\` if Memory Bank needs re-seeding)"
else
    echo "  (no seed session for this persona)"
fi

# ----------------------------------------------------------------------
# Step 4 — presenter checklist
# ----------------------------------------------------------------------
section "4. Presenter URLs"

CANVAS_URL="http://localhost:${CANVAS_PORT}/scenarios/${SCENARIO}"
case "$PERSONA" in
    ayesha) CANVAS_URL="http://localhost:${CANVAS_PORT}/audit/registry" ;;
esac

printf '  Canvas (A2UI demo):  %s\n' "$CANVAS_URL"
printf '  Gemini Enterprise App: surface the deployed agent for live agent UX\n'
printf '\n'
printf '  Keyboard once the canvas page loads:\n'
printf '    Space    advance beat       Shift+Space  step back\n'
printf '    R        reset beats        P            pause\n'
printf '    L        toggle Live mode (cargo-plane only — others static)\n'

# ----------------------------------------------------------------------
# Step 5 — optionally start the canvas
# ----------------------------------------------------------------------
section "5. Canvas dev server"
if [[ "${SKIP_CANVAS:-0}" == "1" ]]; then
    echo "  (SKIP_CANVAS=1 — not starting canvas; presenter will start manually)"
    exit 0
fi

# Detect if the port is already in use; if so, assume canvas is up.
if lsof -ti :"${CANVAS_PORT}" >/dev/null 2>&1; then
    echo "  Port ${CANVAS_PORT} already in use — assuming canvas is running"
    echo "  Open: $CANVAS_URL"
    exit 0
fi

echo "  Starting canvas at $CANVAS_URL"
echo "  (Ctrl-C exits cleanly)"
cd canvas && exec npm run dev -- --port "${CANVAS_PORT}"
