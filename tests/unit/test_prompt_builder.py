"""Unit tests for the PromptBuilder utility.

Verifies the immutable section-based builder behaves correctly:
- build() joins non-empty sections with double newlines
- static(...) selects named sections in order
- override() returns a new instance (immutability)
- dynamic() returns a callable async provider
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from unittest.mock import MagicMock

import pytest

from agents.utils.prompt_builder import PromptBuilder


def _make_builder() -> PromptBuilder:
    return PromptBuilder(
        OrderedDict(
            role="# Role\nYou are an agent.",
            rules="# Rules\nBe honest.",
            workflow="# Workflow\nPlan, then act.",
        )
    )


def test_build_joins_sections_with_double_newline():
    builder = _make_builder()
    result = builder.build()
    assert result == (
        "# Role\nYou are an agent.\n\n# Rules\nBe honest.\n\n# Workflow\nPlan, then act."
    )


def test_build_skips_empty_sections():
    builder = PromptBuilder(OrderedDict(role="A", blank="", tail="B"))
    assert builder.build() == "A\n\nB"


def test_static_selects_sections_in_arg_order():
    builder = _make_builder()
    assert builder.static("rules", "role") == "# Rules\nBe honest.\n\n# Role\nYou are an agent."


def test_static_silently_skips_unknown_keys():
    builder = _make_builder()
    assert builder.static("role", "missing") == "# Role\nYou are an agent."


def test_override_returns_new_instance():
    original = _make_builder()
    overridden = original.override(role="# Role\nNew role.")
    assert original is not overridden
    assert original.sections["role"] == "# Role\nYou are an agent."
    assert overridden.sections["role"] == "# Role\nNew role."


def test_override_adds_new_section_preserving_order():
    builder = PromptBuilder(OrderedDict(a="A", b="B"))
    extended = builder.override(c="C")
    assert list(extended.sections.keys()) == ["a", "b", "c"]
    assert extended.build() == "A\n\nB\n\nC"


def test_dynamic_returns_async_provider():
    builder = _make_builder()
    provider = builder.dynamic()
    # ReadonlyContext shape doesn't matter for the closure
    ctx = MagicMock()
    result = asyncio.run(provider(ctx))
    assert result == builder.build()


def test_dynamic_respects_exclude():
    builder = _make_builder()
    provider = builder.dynamic(exclude=("workflow",))
    result = asyncio.run(provider(MagicMock()))
    assert "Workflow" not in result
    assert "# Role" in result
    assert "# Rules" in result


def test_sections_property_returns_copy():
    builder = _make_builder()
    sections = builder.sections
    sections["role"] = "MUTATED"
    assert builder.sections["role"] == "# Role\nYou are an agent."


def test_init_copies_input_dict():
    """Mutating the dict passed in shouldn't mutate the builder's internal state."""
    src = OrderedDict(a="A")
    builder = PromptBuilder(src)
    src["a"] = "MUTATED"
    assert builder.sections["a"] == "A"


@pytest.mark.parametrize(
    "sections,expected",
    [
        (OrderedDict(), ""),
        (OrderedDict(only="single"), "single"),
        (OrderedDict(a="A", b=""), "A"),
    ],
)
def test_build_edge_cases(sections, expected):
    assert PromptBuilder(sections).build() == expected
