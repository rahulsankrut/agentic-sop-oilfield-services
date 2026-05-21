# ADR 0002: Poetry over `uv` for Python dependency management

## Status

Accepted (project bootstrap, 2026-05). Captured in CLAUDE.md.

## Context

`SPECS.md` §Tech stack originally locked `uv` (astral-sh/uv) as the
Python package manager. `uv` is the project's stated preference: it's
fast, hermetic, and Rust-native; it's also what the
`next-26-keynotes/devkey/demo-2` reference repo uses, so porting the
`pyproject.toml` template would be near-zero-friction.

Two problems surfaced before any code shipped:

1. **`uv` doesn't run on the user's corporate laptop.** The eventual
   home for this code is a corp-managed Mac where `uv` is blocked at
   the install/exec layer (signed-binary policy, allow-listed package
   managers). Discovery happened during TASK-01 setup — not a "we'll
   fix the policy" path on the demo timeline.
2. **The sibling `earnings_analyst` project at the same org uses
   Poetry.** Reusing one toolchain across projects is meaningfully
   cheaper for the operator than supporting both.

## Decision

Adopt **Poetry** instead of `uv`. Install Poetry inside the
project's `venv/` (`pip install poetry`), mirroring the
`earnings_analyst` pattern. All project commands run via Poetry
(`poetry install`, `poetry add`, `poetry run pytest`, `poetry run
ruff …`).

When porting templates from `next-26-keynotes/devkey/demo-2` (uv-based),
convert to Poetry shape:

- `[project]` → `[tool.poetry]`
- `dependencies = [...]` → `[tool.poetry.dependencies]`
- `[dependency-groups.dev]` → `[tool.poetry.group.dev.dependencies]`
- Build backend `hatchling` → `poetry-core`

Bare `pip install <pkg>` is disallowed for project deps (only
`pip install poetry` to bootstrap is acceptable).

## Consequences

**Positive**

- Code runs on the operator's corp laptop without IT escalation.
- Toolchain consistency with `earnings_analyst`.
- Poetry's `pyproject.toml` shape is well-understood by every Python
  CI runner the org uses.

**Negative**

- `uv install` is 5-10× faster than `poetry install` on cold caches.
  Local dev iteration is marginally slower.
- Every porting pass from the reference repo's templates requires a
  hand conversion of `pyproject.toml`. Captured as a step in
  CLAUDE.md so future contributors don't accidentally land a `uv`
  manifest.

**Risk**

- If the operator ever runs `uv pip install -e .` by reflex against
  this `pyproject.toml`, the manifest format won't match. Mitigated by
  the CLAUDE.md call-out and by the fact that `uv` doesn't run on the
  laptop in question anyway.

## Related work

- CLAUDE.md "Environment" §
- `pyproject.toml` carries the Poetry build backend pin.
- ADR 0001 (ADK 2.0 Workflow) — unrelated.
