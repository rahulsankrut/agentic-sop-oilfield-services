"""Re-export of root_agent for `adk deploy agent_engine` compatibility.

The ADK CLI generates an `agent_engine_app.py` that imports via `from .agent
import root_agent`. Our standardized per-agent layout puts the canonical
definition in `core/agent.py` (per SPECS.md and the reference demo-2
layout), so this module re-exports it from there.
"""

from .core.agent import root_agent

__all__ = ["root_agent"]
