"""SKILL.md compliance tests.

Enforces the race-condition skill-compliance pattern across every
``agents/**/skills/**/SKILL.md`` in the repo.

Rules enforced (mirroring race-condition's ``docs/guides/implementing_skills.md``):

1. ``name`` exists and is kebab-case.
2. ``description`` exists, is non-empty, and starts with "Use when"
   (case-insensitive). The description is the LLM's primary signal for skill
   selection — it must list triggering conditions, not summarize what the
   skill does.
3. ``license`` field is present (any non-empty string; we recommend
   ``Apache-2.0``).
4. ``scripts/tools.py`` exists in the same skill directory (this is where
   ``SkillToolset`` + ``load_skill_function_tools`` reads the Python functions
   that get wrapped as ``FunctionTool`` instances).

Each skill is a separate parametrized test so failure messages identify the
offending SKILL.md directly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# Repo root = two levels up from this file (agents/tests/test_skill_compliance.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPO_ROOT / "agents"

_KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def _discover_skill_files() -> list[Path]:
    """Return every ``SKILL.md`` under ``agents/**/skills/**``."""
    if not AGENTS_ROOT.exists():
        return []
    # Glob picks up both ``agents/<agent>/skills/<skill>/SKILL.md`` and
    # nested layouts like ``agents/orchestrator_agent/plan_evaluator/skills/<skill>/SKILL.md``.
    return sorted(p for p in AGENTS_ROOT.rglob("SKILL.md") if "skills" in p.parts)


def _parse_frontmatter(skill_md_path: Path) -> dict:
    """Return the YAML frontmatter as a dict, or raise AssertionError."""
    text = skill_md_path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), (
        f"{skill_md_path}: missing YAML frontmatter (must start with '---')"
    )
    # Split on the closing '---' delimiter.
    parts = text.split("\n---\n", 1)
    assert len(parts) == 2, f"{skill_md_path}: malformed frontmatter (no closing '---' delimiter)"
    frontmatter_text = parts[0][len("---\n") :]
    data = yaml.safe_load(frontmatter_text)
    assert isinstance(data, dict), f"{skill_md_path}: frontmatter did not parse to a mapping"
    return data


SKILL_FILES = _discover_skill_files()


def _skill_id(path: Path) -> str:
    """Pretty parametrize id: path relative to the repo root."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=[_skill_id(p) for p in SKILL_FILES])
def test_skill_has_kebab_case_name(skill_md: Path) -> None:
    """``name`` is present and kebab-case."""
    frontmatter = _parse_frontmatter(skill_md)
    name = frontmatter.get("name")
    assert name, f"{skill_md}: frontmatter missing 'name' field"
    assert isinstance(name, str), f"{skill_md}: 'name' must be a string, got {type(name)}"
    assert _KEBAB_CASE_RE.match(name), (
        f"{skill_md}: 'name' must be kebab-case (lowercase letters/digits with "
        f"single hyphens), got {name!r}"
    )


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=[_skill_id(p) for p in SKILL_FILES])
def test_skill_description_starts_with_use_when(skill_md: Path) -> None:
    """``description`` exists, is non-empty, and starts with 'Use when' (case-insensitive)."""
    frontmatter = _parse_frontmatter(skill_md)
    description = frontmatter.get("description")
    assert description, f"{skill_md}: frontmatter missing 'description' field"
    assert isinstance(description, str), (
        f"{skill_md}: 'description' must be a string, got {type(description)}"
    )
    stripped = description.strip()
    assert stripped, f"{skill_md}: 'description' is empty after stripping whitespace"
    assert stripped.lower().startswith("use when"), (
        f"{skill_md}: 'description' must start with 'Use when' (case-insensitive) "
        f"to list triggering conditions for skill selection. "
        f"Got: {stripped[:80]!r}"
    )


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=[_skill_id(p) for p in SKILL_FILES])
def test_skill_has_license(skill_md: Path) -> None:
    """``license`` field is present (any non-empty string; Apache-2.0 recommended)."""
    frontmatter = _parse_frontmatter(skill_md)
    license_value = frontmatter.get("license")
    assert license_value, (
        f"{skill_md}: frontmatter missing 'license' field (recommend 'Apache-2.0')"
    )
    assert isinstance(license_value, str), (
        f"{skill_md}: 'license' must be a string, got {type(license_value)}"
    )
    assert license_value.strip(), f"{skill_md}: 'license' is empty after stripping whitespace"


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=[_skill_id(p) for p in SKILL_FILES])
def test_skill_has_tools_py(skill_md: Path) -> None:
    """``scripts/tools.py`` exists alongside the SKILL.md."""
    tools_py = skill_md.parent / "scripts" / "tools.py"
    assert tools_py.exists(), (
        f"{skill_md}: missing companion file {tools_py.relative_to(REPO_ROOT)} "
        f"(every skill's Python tool functions live in scripts/tools.py)"
    )


def test_at_least_one_skill_was_discovered() -> None:
    """Sanity check: the discovery glob actually found SKILL.md files.

    Without this, an empty parametrize list would silently produce zero
    assertions and the suite would falsely pass.
    """
    assert SKILL_FILES, (
        f"No SKILL.md files discovered under {AGENTS_ROOT}. "
        "Either the skills haven't been laid down yet or the discovery glob "
        "is wrong."
    )
