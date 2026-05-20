"""Helpers for exposing ADK Skills' Python functions as direct ``FunctionTool``s.

ADK's ``SkillToolset`` exposes only ``load_skill``, ``list_skills``,
``run_skill_script``, and ``load_skill_resource`` — NOT the Python functions
in each skill's ``scripts/tools.py``. Without explicit ``FunctionTool``
wrappers, the LLM reads the SKILL.md and then tries to invoke each
tool via ``run_skill_script`` pointing at a per-function ``.py`` file that
doesn't exist (each function lives inside ``scripts/tools.py``, not in its
own file). The model then loops on SCRIPT_NOT_FOUND errors and eventually
gives up and hallucinates structured output.

The reference repo (next-26-keynotes/devkey/demo-2/src/planner_agent/core/
tools.py) handles this by explicitly loading every tool function from each
skill's ``tools.py`` and adding it as a ``FunctionTool``. This module is
the shared version of that loader so every agent can use the same wiring.

Use it from each agent's ``core/tools.py``::

    from agents.utils.skill_tools import load_skill_function_tools

    def get_tools() -> list:
        skills_dir = pathlib.Path(__file__).parent.parent / "skills"
        return [
            SkillToolset(skills=[...]),
            *load_skill_function_tools(skills_dir),
            ...  # AgentTool wrappers, A2A tools, etc.
        ]

``preload_memory`` is added at the ``LlmAgent`` level in each agent's
``core/agent.py``, not in ``get_tools()``.
"""

from __future__ import annotations

import importlib.util
import logging
import pathlib

from google.adk.tools.function_tool import FunctionTool

logger = logging.getLogger(__name__)


def load_skill_function_tools(skills_dir: pathlib.Path) -> list[FunctionTool]:
    """Return one ``FunctionTool`` per function listed in every skill's frontmatter.

    For each subdirectory of ``skills_dir`` that contains ``SKILL.md`` and
    ``scripts/tools.py``, parses ``metadata.adk_additional_tools`` from the
    SKILL.md frontmatter and imports each named function from ``tools.py``,
    wrapping it as a ``FunctionTool``.

    Args:
        skills_dir: parent directory of the skill subdirectories. Typically
            ``<agent_pkg>/skills`` or ``<agent_pkg>/<sub_pkg>/skills``.

    Returns:
        Flat list of ``FunctionTool`` instances, ready to splice into the
        agent's ``tools=`` list alongside ``SkillToolset(...)``.
    """
    if not skills_dir.exists():
        return []

    # Lazy import yaml — only needed when this loader runs, not at module
    # import time.
    import yaml  # noqa: PLC0415

    tools: list[FunctionTool] = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not (skill_dir.is_dir() and (skill_dir / "SKILL.md").exists()):
            continue
        tools_module_path = skill_dir / "scripts" / "tools.py"
        if not tools_module_path.exists():
            continue

        # Parse SKILL.md frontmatter
        skill_md = (skill_dir / "SKILL.md").read_text()
        if not skill_md.startswith("---"):
            continue
        end = skill_md.find("---", 3)
        if end == -1:
            continue
        frontmatter = yaml.safe_load(skill_md[3:end]) or {}
        fn_names = (frontmatter.get("metadata") or {}).get("adk_additional_tools") or []
        if not fn_names:
            continue

        # Import the skill's tools.py by file path (the skill dir uses a
        # hyphen, which isn't a valid Python identifier for `import`).
        module_alias = f"_skill_tools_{skill_dir.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_alias, tools_module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for fn_name in fn_names:
            fn = getattr(module, fn_name, None)
            if fn is None:
                logger.warning(
                    "Skill %s frontmatter lists %r but %s has no such function",
                    skill_dir.name,
                    fn_name,
                    tools_module_path,
                )
                continue
            tools.append(FunctionTool(func=fn))

    logger.info("Loaded %d skill function tools from %s", len(tools), skills_dir)
    return tools
