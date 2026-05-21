# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Ported verbatim from
# github.com/GoogleCloudPlatform/next-26-keynotes/devkey/demo-1/planner_agent/utils.py

"""Immutable, section-based prompt builder for agent instruction composition.

DEVIATION NOTE (code-review LOW #24, 2026-05-21): SPECS.md §Architectural
principles mandates ``PromptBuilder`` for prompt composition, but every
agent's ``prompts.py`` currently uses a triple-quoted string. This module
is preserved as a tested, ready-to-use utility — retrofit when a prompt
genuinely benefits from section-based composition (variant injection,
A/B testing, runtime section reordering). The triple-quoted-string
shape is fine for the deterministic prompts we ship today.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Awaitable, Callable

from google.adk.agents.readonly_context import ReadonlyContext

# ADK InstructionProvider signature
InstructionProvider = Callable[[ReadonlyContext], str] | Callable[[ReadonlyContext], Awaitable[str]]


class PromptBuilder:
    """Ordered, named sections assembled into a single prompt.

    Immutable: every mutation returns a new instance.
    Child agents call ``override()`` to replace or add sections by key.
    """

    __slots__ = ("_sections",)

    def __init__(self, sections: OrderedDict[str, str]) -> None:
        self._sections: OrderedDict[str, str] = OrderedDict(sections)

    # -- Queries --

    @property
    def sections(self) -> OrderedDict[str, str]:
        """Return a copy of the sections dict."""
        return OrderedDict(self._sections)

    def build(self) -> str:
        """Join all non-empty sections with double newlines."""
        return "\n\n".join(v for v in self._sections.values() if v)

    def static(self, *keys: str) -> str:
        """Join named sections for ``LlmAgent.static_instruction``."""
        return "\n\n".join(self._sections[k] for k in keys if k in self._sections)

    def dynamic(
        self, *, exclude: tuple[str, ...] = ()
    ) -> Callable[[ReadonlyContext], Awaitable[str]]:
        """Return an async ``InstructionProvider`` for ``LlmAgent.instruction``.

        Joins all sections not in *exclude*. The callable receives
        ``ReadonlyContext`` and can inspect ``ctx.state`` if needed.
        """
        remaining = OrderedDict((k, v) for k, v in self._sections.items() if k not in exclude and v)

        async def _provider(ctx: ReadonlyContext) -> str:
            return "\n\n".join(remaining.values())

        return _provider

    # -- Mutations (return new instance) --

    def override(self, **sections: str) -> PromptBuilder:
        """Return a new builder with named sections replaced or added."""
        merged = OrderedDict(self._sections)
        merged.update(sections)
        return PromptBuilder(merged)
