"""Tools for the Capacity Planning Agent.

Lazy-loads the ``scheduling-probability`` skill via SkillToolset, plus
PreloadMemoryTool.
"""

from __future__ import annotations

import logging
import pathlib

from google.adk.skills import load_skill_from_dir
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.skill_toolset import SkillToolset

logger = logging.getLogger(__name__)


def _load_skills() -> list:
    skills_dir = pathlib.Path(__file__).parent.parent / "skills"
    if not skills_dir.exists():
        return []
    return [
        load_skill_from_dir(d)
        for d in sorted(skills_dir.iterdir())
        if d.is_dir() and not d.name.startswith("_") and (d / "SKILL.md").exists()
    ]


def get_tools() -> list:
    """Capacity Planning tool list: SkillToolset + PreloadMemoryTool."""
    skills = _load_skills()
    skill_toolset = SkillToolset(skills=skills) if skills else None
    logger.info("Loaded %d skills for Capacity Planning Agent", len(skills))

    tools: list = [PreloadMemoryTool()]
    if skill_toolset is not None:
        tools.append(skill_toolset)
    return tools
