"""Register MCP servers with Gemini Enterprise Agent Platform Agent Registry.

Registers four MCP servers so they become discoverable to agents and
governable by Agent Gateway:

  - sap-mcp-server          (custom, Cloud Run)
  - maximo-mcp-server       (custom, Cloud Run)
  - fdp-mcp-server          (custom, Cloud Run)
  - knowledge-catalog-mcp   (platform-provided, https://dataplex.googleapis.com/mcp)

The script is **idempotent**: it tries `GET` first, `PATCH` if the resource
exists, otherwise `POST` to create. Re-running is safe.

Run from repo root with the venv active:

    poetry run python scripts/register_mcp_servers.py

Required env vars:
    GOOGLE_CLOUD_PROJECT       — target project id
    GOOGLE_CLOUD_LOCATION      — region (default "us-central1")
    SAP_MCP_URL                — Cloud Run URL of the SAP MCP server
    MAXIMO_MCP_URL             — Cloud Run URL of the Maximo MCP server
    FDP_MCP_URL                — Cloud Run URL of the FDP MCP server

Optional:
    AGENT_REGISTRY_DRY_RUN=1   — log requests, don't call the API.

Why REST and not the Python SDK
-------------------------------
Agent Registry is a recent Gemini Enterprise Agent Platform component
(announced 2026). As of 2026-05 the official `google-cloud-aiplatform`
release on PyPI does not yet expose a typed Python client for the
`projects.locations.mcpServers` collection. We therefore call the REST
surface directly with `httpx` + a `google.auth` access token. When the SDK
ships first-class support, swap the `_registry_request(...)` helper for the
typed client (see TODO markers below).
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
logger = logging.getLogger("register-mcp-servers")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
DRY_RUN = os.environ.get("AGENT_REGISTRY_DRY_RUN") == "1"

# Agent Registry REST endpoint. The platform is regional; us-central1 is the
# v1 region for this build (see CLAUDE.md). The path is:
#   projects/{project}/locations/{location}/mcpServers/{mcp_server_id}
#
# TODO(SDK): replace with `google.cloud.aiplatform_v1beta1.AgentRegistryClient`
# or the dedicated `google-cloud-agent-registry` package once on PyPI.
_REGISTRY_HOST = os.environ.get(
    "AGENT_REGISTRY_HOST",
    "https://aiplatform.googleapis.com",
)
_REGISTRY_API_VERSION = os.environ.get("AGENT_REGISTRY_API_VERSION", "v1beta1")


@dataclass(frozen=True)
class McpRegistration:
    """One MCP server's Agent Registry record."""

    server_id: str
    display_name: str
    description: str
    mcp_url: str
    owner_service_account: str
    # Tags surface in `gcloud ai mcp-servers list` for the audit team to grep.
    tags: tuple[str, ...] = ()

    def resource_path(self) -> str:
        return (
            f"projects/{PROJECT}/locations/{LOCATION}/mcpServers/{self.server_id}"
        )

    def to_payload(self) -> dict[str, Any]:
        """Build the REST request body.

        Field names mirror the patterns visible in adjacent Agent Platform
        APIs (Reasoning Engine, Agent Engines). Verify against the live
        Agent Registry reference once published.
        """
        return {
            "displayName": self.display_name,
            "description": self.description,
            "mcpEndpoint": {
                "url": self.mcp_url,
                # streamable-http is the current MCP transport standard
                # (SSE is deprecated per the MCP spec 2025-rev).
                "transport": "STREAMABLE_HTTP",
            },
            "owner": {
                "serviceAccount": self.owner_service_account,
            },
            "labels": {
                "managed-by": "agentic-sop-oilfield-services",
                "mcp-server": self.server_id,
            },
            "tags": list(self.tags),
        }


# ---------------------------------------------------------------------------
# Registrations
# ---------------------------------------------------------------------------


def _registrations() -> list[McpRegistration]:
    """Resolve registrations from env. Done at call time so DRY_RUN can run
    without the per-server URLs set."""
    sap_url = os.environ.get("SAP_MCP_URL", "https://sap-mcp-server.run.app")
    maximo_url = os.environ.get("MAXIMO_MCP_URL", "https://maximo-mcp-server.run.app")
    fdp_url = os.environ.get("FDP_MCP_URL", "https://fdp-mcp-server.run.app")

    sa = lambda name: f"{name}@{PROJECT}.iam.gserviceaccount.com"  # noqa: E731

    return [
        # DEMO NARRATION: "First registration — the SAP MCP server. Agent
        # Registry now knows there's a tool called `sap_get_material_master`
        # that resolves SAP material numbers, owned by the SAP MCP service
        # account. Any agent that wants to call it has to go through Agent
        # Gateway, which checks IAM."
        McpRegistration(
            server_id="sap-mcp-server",
            display_name="SAP S/4HANA MCP Server",
            description=(
                "Exposes SAP S/4HANA material master, workforce, and plant "
                "maintenance reads as MCP tools. Synthetic backend for the "
                "demo; production swap-in is a customer's real SAP via the "
                "same MCP interface."
            ),
            mcp_url=sap_url.rstrip("/") + "/mcp",
            owner_service_account=sa("sap-mcp-sa"),
            tags=("sap", "enterprise-system", "oilfield-services"),
        ),
        McpRegistration(
            server_id="maximo-mcp-server",
            display_name="IBM Maximo MCP Server",
            description=(
                "Exposes Maximo equipment status, location, and availability "
                "lookups as MCP tools. Synthetic backend for the demo; "
                "production swap-in is the customer's real Maximo."
            ),
            mcp_url=maximo_url.rstrip("/") + "/mcp",
            owner_service_account=sa("maximo-mcp-sa"),
            tags=("maximo", "enterprise-system", "oilfield-services"),
        ),
        McpRegistration(
            server_id="fdp-mcp-server",
            display_name="FDP Customer Config MCP Server",
            description=(
                "Exposes the customer-configuration store (FDP) as MCP "
                "tools — substitution approvals, contract terms, allowed "
                "asset mappings. Synthetic backend for the demo."
            ),
            mcp_url=fdp_url.rstrip("/") + "/mcp",
            owner_service_account=sa("fdp-mcp-sa"),
            tags=("fdp", "enterprise-system", "oilfield-services"),
        ),
        # DEMO NARRATION: "Fourth registration — Knowledge Catalog's MCP
        # server. We didn't build it. It ships with Dataplex / Knowledge
        # Catalog. Registering it here brings Knowledge Catalog tools
        # (search_entries, lookup_context, search_aspect_types) under the
        # same Agent Gateway policy + Model Armor scan that protects the
        # custom servers. One audit story for everything."
        McpRegistration(
            server_id="knowledge-catalog-mcp",
            display_name="Knowledge Catalog MCP Server",
            description=(
                "Platform-managed Knowledge Catalog (Dataplex) MCP server. "
                "Provides prebuilt tools search_entries, lookup_entry, "
                "lookup_context, search_aspect_types. Registered so all "
                "calls flow through the same Agent Gateway + Model Armor "
                "pipeline as our custom MCP servers."
            ),
            mcp_url="https://dataplex.googleapis.com/mcp",
            # Owner is the platform-managed Dataplex service agent. Agents
            # call it as themselves via Agent Identity; this field records
            # which SA the platform considers the owner for audit purposes.
            owner_service_account=(
                "service-{project_number}@gcp-sa-dataplex.iam.gserviceaccount.com"
            ),
            tags=("knowledge-catalog", "platform-managed", "oilfield-services"),
        ),
    ]


# ---------------------------------------------------------------------------
# REST plumbing
# ---------------------------------------------------------------------------


def _access_token() -> str:
    """Resolve an OAuth access token from Application Default Credentials."""
    creds, _ = google_auth_default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    creds.refresh(GoogleAuthRequest())
    return creds.token  # type: ignore[no-any-return]


def _registry_url(path: str) -> str:
    """Build a full Agent Registry REST URL.

    `path` is a relative path beneath /{API_VERSION}/, e.g.
    "projects/.../locations/.../mcpServers/sap-mcp-server".
    """
    return f"{_REGISTRY_HOST}/{_REGISTRY_API_VERSION}/{path}"


def _registry_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response | None:
    """Issue a Cloud Platform REST request with bearer auth.

    Returns the Response or None if DRY_RUN is set.
    """
    url = _registry_url(path)
    headers = {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json",
        "User-Agent": "agentic-sop-oilfield-services/register-mcp-servers/1.0",
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
        return client.request(
            method, url, headers=headers, params=params, json=json_body
        )


def _get_or_none(reg: McpRegistration) -> dict[str, Any] | None:
    """GET the existing registration; return None on 404."""
    resp = _registry_request("GET", reg.resource_path())
    if resp is None:
        return None
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _create(reg: McpRegistration) -> dict[str, Any] | None:
    """POST to create. Returns the created resource or None on dry-run."""
    parent = f"projects/{PROJECT}/locations/{LOCATION}"
    resp = _registry_request(
        "POST",
        f"{parent}/mcpServers",
        params={"mcpServerId": reg.server_id},
        json_body=reg.to_payload(),
    )
    if resp is None:
        return None
    if resp.status_code in (200, 201):
        return resp.json()
    raise RuntimeError(
        f"Create failed for {reg.server_id}: {resp.status_code} {resp.text}"
    )


def _update(reg: McpRegistration) -> dict[str, Any] | None:
    """PATCH to update. `updateMask` covers the mutable fields."""
    resp = _registry_request(
        "PATCH",
        reg.resource_path(),
        params={
            "updateMask": ",".join(
                ["displayName", "description", "mcpEndpoint", "labels", "tags"]
            ),
        },
        json_body=reg.to_payload(),
    )
    if resp is None:
        return None
    if resp.status_code in (200, 201):
        return resp.json()
    raise RuntimeError(
        f"Update failed for {reg.server_id}: {resp.status_code} {resp.text}"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def register_one(reg: McpRegistration) -> None:
    """Idempotent register-or-update for a single MCP server."""
    logger.info(
        "Registering %s -> %s (owner=%s)",
        reg.server_id,
        reg.mcp_url,
        reg.owner_service_account,
    )
    existing = _get_or_none(reg)
    if existing is None:
        _create(reg)
        logger.info("  created %s", reg.resource_path())
    else:
        _update(reg)
        logger.info("  updated %s", reg.resource_path())


# DEMO NARRATION: "Step one of the production deployment is this script:
# register every MCP server with Agent Registry. This is the central catalog
# — your audit team can pull a list of every tool every agent can call,
# every external system being touched, every endpoint. By default, the
# platform blocks calls to unregistered servers. That's the security
# posture out of the box."
def main() -> int:
    if not PROJECT:
        logger.error("GOOGLE_CLOUD_PROJECT is required")
        return 2

    if DRY_RUN:
        logger.info("AGENT_REGISTRY_DRY_RUN=1 — no live API calls will be made")

    failures: list[str] = []
    for reg in _registrations():
        try:
            register_one(reg)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to register %s: %s", reg.server_id, exc)
            failures.append(reg.server_id)

    if failures:
        logger.error("Registration failures: %s", ", ".join(failures))
        return 1
    logger.info("All MCP servers registered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
