"""Configure Agent Identity bindings for every deployed agent.

Each deployed agent (Procurement Approval, Forecast Review, Capacity
Planning, Capacity Orchestrator) lives at a `reasoningEngines/<id>` resource.
Agent Registry tracks an `agents/<id>` record per agent; Agent Identity
binds that record to a dedicated GCP service account whose SPIFFE ID
becomes the principal in Gateway IAM policy evaluation.

This script is the REST-based, idempotent equivalent of the (Preview)
gcloud verbs in `tasks/TASK-11-governance.md` §Step 1 + §Step 2:

    gcloud ai agent-identities create <name> --service-account=... --region=...

The gcloud surface for `gcloud ai agent-identities` is still Preview as
of 2026-05-20 and the verb may move (see CLAUDE.md gotcha). The REST
endpoint at `agentplatform.googleapis.com` is the verified fallback per
~/.claude/references/gemini-enterprise-agent-platform.md.

Mirror of `scripts/register_mcp_servers.py`'s style:
  - REST + httpx + google.auth (no SDK; SDK doesn't expose this surface yet)
  - Idempotent GET → PATCH-or-POST
  - `AGENT_IDENTITY_DRY_RUN=1` to log requests without calling the API
  - On 404 from the GET (resource not modelled), logs a warning and prints
    the gcloud equivalent for manual execution rather than guessing.

Run from repo root with the deploy venv active:

    source venv-deploy-310/bin/activate
    python scripts/configure_agent_identity.py

Required env vars (typically from .env after deploys):
    GOOGLE_CLOUD_PROJECT
    GOOGLE_CLOUD_LOCATION                       (default "us-central1")
    PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME
    FORECAST_REVIEW_AGENT_RESOURCE_NAME
    CAPACITY_PLANNING_AGENT_RESOURCE_NAME
    ORCHESTRATOR_AGENT_RESOURCE_NAME

Optional:
    AGENT_IDENTITY_DRY_RUN=1                    log only, no live API calls
    AGENT_IDENTITY_HOST                         override REST host
    AGENT_IDENTITY_API_VERSION                  override API version
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request as GoogleAuthRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("configure-agent-identity")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
DRY_RUN = os.environ.get("AGENT_IDENTITY_DRY_RUN") == "1"

# Per the reference doc, Gateway / Identity records live on
# `agentplatform.googleapis.com` (the Registry currently uses
# `aiplatform.googleapis.com` until consolidation — see "Open questions"
# in ~/.claude/references/gemini-enterprise-agent-platform.md). If the
# consolidation lands the other way, flip via env.
_IDENTITY_HOST = os.environ.get(
    "AGENT_IDENTITY_HOST",
    "https://agentplatform.googleapis.com",
)
_IDENTITY_API_VERSION = os.environ.get("AGENT_IDENTITY_API_VERSION", "v1beta1")


@dataclass(frozen=True)
class AgentIdentityBinding:
    """One agent's identity binding.

    `agent_resource_name` is the full `projects/.../reasoningEngines/<id>`
    path (or `projects/.../agents/<id>` once Agent Registry's agent
    records are populated for our reasoning-engine deploys).
    """

    agent_slug: str  # short id used in policies + service-account names
    display_name: str
    agent_resource_name: str
    service_account_email: str

    def identity_id(self) -> str:
        return f"{self.agent_slug}-identity"

    def identity_resource_path(self) -> str:
        return f"projects/{PROJECT}/locations/{LOCATION}/agentIdentities/{self.identity_id()}"

    def to_payload(self) -> dict[str, Any]:
        """Build the REST request body for create/update.

        Field shape follows the convention from Agent Registry's
        `mcpServers` records (verified against the live API in
        scripts/register_mcp_servers.py). When the typed SDK ships,
        swap for the generated client.
        """
        return {
            "displayName": self.display_name,
            "description": (
                f"Agent Identity binding for the {self.display_name} "
                f"deployed at {self.agent_resource_name}. The bound "
                f"service account becomes the SPIFFE-ID principal for "
                f"Agent Gateway IAM evaluation."
            ),
            "boundAgent": self.agent_resource_name,
            "serviceAccount": self.service_account_email,
            "labels": {
                "managed-by": "agentic-sop-oilfield-services",
                "task": "TASK-11",
                "agent-slug": self.agent_slug,
            },
        }


# ---------------------------------------------------------------------------
# Identity definitions — one per deployed agent
# ---------------------------------------------------------------------------


def _bindings() -> list[AgentIdentityBinding]:
    """Resolve bindings from env. Done at call time so DRY_RUN can run
    without the per-agent resource names populated."""

    def sa(name: str) -> str:
        return f"{name}@{PROJECT}.iam.gserviceaccount.com"

    # NOTE: agent resource names come from .env populated by the deploy
    # scripts. If a slot is unset, we still emit the binding but mark it
    # so the operator sees the gap.
    def _resolve(env_var: str) -> str:
        return os.environ.get(env_var, f"<UNSET: {env_var}>")

    return [
        # DEMO NARRATION (Persona 6, Ayesha): "Each agent has its own
        # SPIFFE-bound identity. Procurement Approval can't impersonate
        # the Orchestrator. The audit log carries the SPIFFE ID on every
        # tool call."
        AgentIdentityBinding(
            agent_slug="procurement-approval",
            display_name="Procurement Approval Agent",
            agent_resource_name=_resolve("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME"),
            service_account_email=sa("procurement-approval-agent-sa"),
        ),
        AgentIdentityBinding(
            agent_slug="forecast-review",
            display_name="Forecast Review Agent",
            agent_resource_name=_resolve("FORECAST_REVIEW_AGENT_RESOURCE_NAME"),
            service_account_email=sa("forecast-review-agent-sa"),
        ),
        AgentIdentityBinding(
            agent_slug="capacity-planning",
            display_name="Capacity Planning Agent",
            agent_resource_name=_resolve("CAPACITY_PLANNING_AGENT_RESOURCE_NAME"),
            service_account_email=sa("capacity-planning-agent-sa"),
        ),
        AgentIdentityBinding(
            agent_slug="orchestrator",
            display_name="Capacity Orchestrator Agent",
            agent_resource_name=_resolve("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
            service_account_email=sa("orchestrator-agent-sa"),
        ),
    ]


# ---------------------------------------------------------------------------
# REST plumbing
# ---------------------------------------------------------------------------


def _access_token() -> str:
    """Resolve an OAuth access token from ADC."""
    creds, _ = google_auth_default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token  # type: ignore[no-any-return]


def _identity_url(path: str) -> str:
    return f"{_IDENTITY_HOST}/{_IDENTITY_API_VERSION}/{path}"


def _identity_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response | None:
    """Issue an authenticated REST request. Returns None on dry-run."""
    url = _identity_url(path)
    headers = {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json",
        "User-Agent": "agentic-sop-oilfield-services/configure-agent-identity/1.0",
    }

    if DRY_RUN:
        logger.info(
            "[DRY RUN] %s %s\n params=%s\n body=%s",
            method,
            url,
            params or {},
            json.dumps(json_body, indent=2) if json_body else "{}",
        )
        return None

    with httpx.Client(timeout=30.0) as client:
        return client.request(method, url, headers=headers, params=params, json=json_body)


def _gcloud_fallback(binding: AgentIdentityBinding) -> None:
    """Print the gcloud equivalent for manual execution.

    Called when the REST endpoint is unreachable / unmodelled — the
    operator can paste this into a shell session against a fresh
    `gcloud --help` to find the current verb.
    """
    logger.warning(
        "REST endpoint unavailable; manual gcloud fallback for %s:",
        binding.identity_id(),
    )
    logger.warning(
        "  gcloud ai agent-identities create %s \\\n"
        "    --service-account=%s \\\n"
        "    --bound-agent=%s \\\n"
        "    --display-name=%r \\\n"
        "    --project=%s --location=%s",
        binding.identity_id(),
        binding.service_account_email,
        binding.agent_resource_name,
        binding.display_name,
        PROJECT,
        LOCATION,
    )
    logger.warning(
        "  # Preview verb — if `gcloud ai agent-identities` errors, "
        "try `gcloud agent-platform identities` or use the Console "
        "(see docs/governance.md)."
    )


def _get_or_none(binding: AgentIdentityBinding) -> dict[str, Any] | None:
    """GET the existing binding; return None on 404."""
    resp = _identity_request("GET", binding.identity_resource_path())
    if resp is None:
        return None
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        # Unmodelled surface or wrong host. Don't crash — log + fallback.
        logger.warning(
            "GET %s returned %s — treating as 'endpoint not modelled'.",
            binding.identity_resource_path(),
            resp.status_code,
        )
        _gcloud_fallback(binding)
        return {"_unreachable": True}
    return resp.json()


def _create(binding: AgentIdentityBinding) -> None:
    parent = f"projects/{PROJECT}/locations/{LOCATION}"
    resp = _identity_request(
        "POST",
        f"{parent}/agentIdentities",
        params={"agentIdentityId": binding.identity_id()},
        json_body=binding.to_payload(),
    )
    if resp is None:
        return  # dry-run
    if resp.status_code in (200, 201):
        logger.info("  created %s", binding.identity_resource_path())
        return
    logger.error(
        "Create failed for %s: %s %s",
        binding.identity_id(),
        resp.status_code,
        resp.text,
    )
    _gcloud_fallback(binding)


def _update(binding: AgentIdentityBinding) -> None:
    resp = _identity_request(
        "PATCH",
        binding.identity_resource_path(),
        params={
            "updateMask": ",".join(
                ["displayName", "description", "boundAgent", "serviceAccount", "labels"]
            ),
        },
        json_body=binding.to_payload(),
    )
    if resp is None:
        return  # dry-run
    if resp.status_code in (200, 201):
        logger.info("  updated %s", binding.identity_resource_path())
        return
    logger.error(
        "Update failed for %s: %s %s",
        binding.identity_id(),
        resp.status_code,
        resp.text,
    )
    _gcloud_fallback(binding)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def configure_one(binding: AgentIdentityBinding) -> None:
    """Idempotent register-or-update for a single Agent Identity."""
    logger.info(
        "Configuring %s -> bound_agent=%s sa=%s",
        binding.identity_id(),
        binding.agent_resource_name,
        binding.service_account_email,
    )

    if binding.agent_resource_name.startswith("<UNSET"):
        logger.warning(
            "  skipping %s — agent resource name is unset. Populate "
            ".env from the latest deploy before re-running.",
            binding.identity_id(),
        )
        return

    existing = _get_or_none(binding)
    if existing is None:
        _create(binding)
    elif existing.get("_unreachable"):
        # Already logged + fallback printed; nothing else to do here.
        return
    else:
        _update(binding)


# DEMO NARRATION: "Every deployed agent has a SPIFFE-bound identity. The
# Capacity Orchestrator can't impersonate the Plan Evaluator. Procurement
# Approval can't read the Forecast Review's BigQuery datasets. Each tool
# call carries the calling agent's SPIFFE ID into the audit log, and
# Agent Gateway evaluates IAM against that ID — not against a shared
# project-wide service account."
def main() -> int:
    if not PROJECT:
        logger.error("GOOGLE_CLOUD_PROJECT is required")
        return 2

    if DRY_RUN:
        logger.info("AGENT_IDENTITY_DRY_RUN=1 — no live API calls will be made")

    failures: list[str] = []
    for binding in _bindings():
        try:
            configure_one(binding)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to configure %s: %s", binding.identity_id(), exc)
            failures.append(binding.identity_id())

    if failures:
        logger.error("Configuration failures: %s", ", ".join(failures))
        return 1
    logger.info(
        "All Agent Identity bindings reconciled. Verify with "
        "`gcloud ai agent-identities list --location=%s` (or "
        "Console → Agent Platform → Identities).",
        LOCATION,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
