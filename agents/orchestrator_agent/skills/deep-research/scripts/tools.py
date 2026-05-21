"""Tools for the deep-research skill — thin re-export of the shared
``agents.utils.vertex_ai_search`` wrappers so the SKILL.md frontmatter's
``adk_additional_tools`` list resolves to real callable functions.

Keeping the implementation in ``agents.utils`` (rather than duplicating it
per skill) means the Procurement Approval agent's `regulatory-precedents`
skill reuses the same code path.
"""

from __future__ import annotations

from agents.utils.vertex_ai_search import (
    search_bsee_incidents,
    search_intouch_specs,
    search_mcc_contracts,
)

__all__ = [
    "search_bsee_incidents",
    "search_mcc_contracts",
    "search_intouch_specs",
]
