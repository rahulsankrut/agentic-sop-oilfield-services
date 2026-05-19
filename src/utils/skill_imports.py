"""Direct imports for skill-tool Python functions.

ADK skill directories use hyphens (e.g. ``asset-equivalence/``), which Python
cannot import via the normal ``import`` statement. ``skill_tools.py`` solves
this for the LlmAgent path (wraps functions as ``FunctionTool`` instances by
parsing SKILL.md frontmatter). The Workflow path is different: function nodes
call the skill functions DIRECTLY as Python callables, not as tools.

This module loads each skill's ``scripts/tools.py`` via importlib and re-
exports the named functions. Workflow nodes import from here so the
hyphenated-skill-dir constraint stays a private detail.
"""

from __future__ import annotations

import importlib.util
import pathlib
import types
from typing import Any

_ORCHESTRATOR_SKILLS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "orchestrator_agent" / "skills"
)


def _load_skill_tools_module(skill_dir_name: str) -> types.ModuleType:
    """Load ``orchestrator_agent/skills/<skill_dir_name>/scripts/tools.py``."""
    tools_path = _ORCHESTRATOR_SKILLS_DIR / skill_dir_name / "scripts" / "tools.py"
    if not tools_path.exists():
        raise ImportError(f"Skill tools module not found: {tools_path}")
    module_alias = f"_orch_skill_{skill_dir_name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_alias, tools_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not build import spec for {tools_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get(module: types.ModuleType, name: str) -> Any:
    if not hasattr(module, name):
        raise AttributeError(f"{module.__name__} has no attribute {name!r}")
    return getattr(module, name)


# Lazy module handles (imported once per process)
_asset_equivalence = _load_skill_tools_module("asset-equivalence")
_enterprise_systems = _load_skill_tools_module("enterprise-systems")
_sourcing_logistics = _load_skill_tools_module("sourcing-logistics")


# asset-equivalence
resolve_canonical_asset = _get(_asset_equivalence, "resolve_canonical_asset")
find_functional_equivalents = _get(_asset_equivalence, "find_functional_equivalents")
score_equivalence_confidence = _get(_asset_equivalence, "score_equivalence_confidence")

# enterprise-systems
query_maximo_availability = _get(_enterprise_systems, "query_maximo_availability")
query_sap_workforce = _get(_enterprise_systems, "query_sap_workforce")
query_fdp_customer_config = _get(_enterprise_systems, "query_fdp_customer_config")
query_intouch_specs = _get(_enterprise_systems, "query_intouch_specs")

# sourcing-logistics
estimate_transit = _get(_sourcing_logistics, "estimate_transit")
calculate_sourcing_cost = _get(_sourcing_logistics, "calculate_sourcing_cost")
identify_blockers = _get(_sourcing_logistics, "identify_blockers")


__all__ = [
    "calculate_sourcing_cost",
    "estimate_transit",
    "find_functional_equivalents",
    "identify_blockers",
    "query_fdp_customer_config",
    "query_intouch_specs",
    "query_maximo_availability",
    "query_sap_workforce",
    "resolve_canonical_asset",
    "score_equivalence_confidence",
]
