"""Utilities shared across all agents.

Importing this package applies the ADK 2.0 ↔ Vertex AI Agent Engine
compatibility patch (see ``adk_compat.py``). Every agent's deployable code
imports from ``src.utils.*`` somewhere (``GlobalGemini``, ``skill_tools``,
``deploy`` helpers), so the patch is active by the time the deployed
Reasoning Engine container constructs ``App(name=<reasoning_engine_id>)``
via ``AdkApp.set_up``.
"""

from __future__ import annotations

from . import adk_compat  # noqa: F401 — imported for side-effect patch

__all__ = ["adk_compat"]
