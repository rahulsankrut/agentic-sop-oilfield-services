"""Tools for the regulatory-precedents skill — re-exports the shared
``agents.utils.vertex_ai_search`` wrappers for BSEE incidents and MCC
contracts. InTouch specs are deliberately omitted (Orchestrator domain).
"""

from __future__ import annotations

from agents.utils.vertex_ai_search import (
    search_bsee_incidents,
    search_mcc_contracts,
)

__all__ = [
    "search_bsee_incidents",
    "search_mcc_contracts",
]
