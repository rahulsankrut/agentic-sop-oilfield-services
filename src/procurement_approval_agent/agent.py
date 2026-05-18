"""Re-export of root_agent for ADK CLI and Agent Engine compatibility.

See CLAUDE.md "Per-agent package layout" gotcha — the canonical definition
lives at ``core/agent.py``; this shim makes it discoverable by tools that
expect ``<pkg>/agent.py``.
"""

from .core.agent import root_agent

__all__ = ["root_agent"]
