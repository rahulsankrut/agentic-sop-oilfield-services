"""Helper to build ADK MCP toolsets pointing at our deployed Cloud Run MCP servers.

Canonical ADK MCP pattern per https://adk.dev/tools-custom/mcp-tools/ —
register `McpToolset(connection_params=StreamableHTTPConnectionParams(...))`
on each LlmAgent's `tools=` list and the LLM can directly call any
tool the MCP server exposes (via `tools/list`).

Used by Procurement Approval, Forecast Review, and Capacity Planning
agents so a demo can prove the MCP path end-to-end. The Orchestrator's
skill composers go BQ-direct via `agents.utils.enterprise_data`
(different code path); the MCP path here is the LLM-driven side.

Env vars consumed (all optional — missing URL means that server's
toolset is skipped):
    SAP_MCP_URL     — toolbox front of the SAP-shaped FastAPI backend
    MAXIMO_MCP_URL  — toolbox front of the Maximo-shaped backend
    FDP_MCP_URL     — toolbox front of the FDP-shaped backend
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_mcp_toolsets(servers: list[str] | None = None) -> list[Any]:
    """Return one McpToolset per deployed MCP server URL.

    Args:
        servers: subset of ``["sap", "maximo", "fdp"]`` to register. If
            None, registers all three (skipping any whose URL env var
            isn't set).

    Returns:
        List of McpToolset instances. Splice into the agent's ``tools=``
        list alongside SkillToolset / FunctionTool entries.
    """
    if servers is None:
        servers = ["sap", "maximo", "fdp"]

    # Lazy ADK imports — heavy modules; keep agent-module-load fast for
    # callers that don't actually need MCP (e.g. unit tests).
    # Note: full module paths required — google.adk.tools.mcp_tool's
    # __init__.py doesn't re-export McpToolset (verified on adk 2.0.0,
    # Python 3.10 deploy runtime).
    from google.adk.tools.mcp_tool.mcp_session_manager import (  # noqa: PLC0415
        StreamableHTTPConnectionParams,
    )
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset  # noqa: PLC0415

    env_keys = {
        "sap": "SAP_MCP_URL",
        "maximo": "MAXIMO_MCP_URL",
        "fdp": "FDP_MCP_URL",
    }

    toolsets: list[Any] = []
    for name in servers:
        env_key = env_keys.get(name)
        if env_key is None:
            logger.warning("build_mcp_toolsets: unknown MCP server %r — skipping", name)
            continue
        url = os.environ.get(env_key)
        if not url:
            logger.info(
                "build_mcp_toolsets: %s not set — skipping %s toolset", env_key, name
            )
            continue
        endpoint = url.rstrip("/") + "/mcp"
        toolsets.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(url=endpoint),
            )
        )
        logger.info("build_mcp_toolsets: registered %s -> %s", name, endpoint)

    return toolsets


__all__ = ["build_mcp_toolsets"]
