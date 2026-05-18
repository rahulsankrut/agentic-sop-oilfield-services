"""Re-export of root_agent for ADK CLI / Agent Engine compatibility shim.

See CLAUDE.md "Per-agent package layout" gotcha — canonical definition lives
in ``core/agent.py``; this shim makes it discoverable.
"""

from .core.agent import root_agent

__all__ = ["root_agent"]
