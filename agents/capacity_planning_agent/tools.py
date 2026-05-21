"""Tools for the Capacity Planning Agent.

Lazy-loads the ``scheduling-probability`` skill via SkillToolset.
``preload_memory`` is added at the LlmAgent level in ``agent.py``.
"""

from __future__ import annotations

import logging
import pathlib

from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

from agents.utils.mcp_toolsets import build_mcp_toolsets
from agents.utils.skill_tools import load_skill_function_tools

logger = logging.getLogger(__name__)

_SKILLS_DIR = pathlib.Path(__file__).parent / "skills"


def _load_skills() -> list:
    if not _SKILLS_DIR.exists():
        return []
    return [
        load_skill_from_dir(d)
        for d in sorted(_SKILLS_DIR.iterdir())
        if d.is_dir() and not d.name.startswith("_") and (d / "SKILL.md").exists()
    ]


def get_tools() -> list:
    """Capacity Planning tool list: SkillToolset + per-function tools.

    preload_memory is added at the LlmAgent level in agent.py, not here.
    """
    skills = _load_skills()
    skill_toolset = SkillToolset(skills=skills) if skills else None
    fn_tools = load_skill_function_tools(_SKILLS_DIR)
    logger.info(
        "Capacity Planning: %d skills, %d direct function tools", len(skills), len(fn_tools)
    )

    # MCP toolsets — Maximo holds the workorder + asset data this agent
    # reasons about (variance distributions, deployable instances).
    mcp_toolsets = build_mcp_toolsets(servers=["maximo"])

    tools: list = []
    if skill_toolset is not None:
        tools.append(skill_toolset)
    tools.extend(fn_tools)
    tools.extend(mcp_toolsets)
    return tools
