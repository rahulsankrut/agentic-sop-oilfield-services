"""Active customer skin loader for agents (TASK-13 Step 5).

Agents reading customer-specific labels (persona names, hero asset
labels, scenario fixtures, terminology) call ``get_active_skin()``.
The result is a typed `CustomerSkin` (see `agents/utils/skin_schema.py`)
parsed from `skins/<slug>/customer.yaml`.

Skin selection:
  CUSTOMER_SKIN env var picks the slug. Default: ``default``.
  Same env var the canvas's `scripts/compile_skin.py` consumes when
  the operator runs `make use-skin SKIN=<slug>`.

Caching:
  Module-level cache. First call reads the YAML; subsequent calls
  return the cached instance. ``reload_active_skin()`` exists for tests.

Why a Python-side loader (vs. just importing the canvas's generated TS):
  The deployed agents run in Vertex AI Reasoning Engine — no Node, no
  canvas. They need a Python-native skin view. The JSON Schema in
  `skins/schema/customer.schema.json` stays the cross-language source of
  truth; both `skin_schema.py` (pydantic) and `skin.generated.ts`
  (TypeScript const) bind against it.

Substitution path: a customer with their own skin copies
`skins/default/customer.yaml` to `skins/<their-slug>/customer.yaml`,
edits, then deploys with `CUSTOMER_SKIN=<their-slug>` as a deploy-time
env var. No agent code changes.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from agents.utils.skin_schema import CustomerSkin

# Resolve `skins/` relative to repo root — two levels up from this file
# (agents/utils/skin_loader.py → agents/utils/ → agents/ → <repo>).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKINS_DIR = _REPO_ROOT / "skins"

_cached_skin: CustomerSkin | None = None
_cached_slug: str | None = None


def get_active_skin() -> CustomerSkin:
    """Return the parsed `CustomerSkin` for the currently selected slug.

    First call reads + validates the YAML; subsequent calls return the
    cached instance unless ``CUSTOMER_SKIN`` changes (handles
    test scenarios that swap the env var mid-run).
    """
    global _cached_skin, _cached_slug  # noqa: PLW0603 — small intentional cache
    slug = os.environ.get("CUSTOMER_SKIN", "default")
    if _cached_skin is not None and _cached_slug == slug:
        return _cached_skin
    path = _SKINS_DIR / slug / "customer.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"customer.yaml not found for skin {slug!r} at {path} — "
            f"check the CUSTOMER_SKIN env var and that the skin dir exists."
        )
    with path.open() as f:
        raw = yaml.safe_load(f)
    _cached_skin = CustomerSkin.model_validate(raw)
    _cached_slug = slug
    return _cached_skin


def reload_active_skin() -> CustomerSkin:
    """Force a re-read from disk. Used by tests that flip ``CUSTOMER_SKIN``."""
    global _cached_skin, _cached_slug  # noqa: PLW0603 — small intentional cache
    _cached_skin = None
    _cached_slug = None
    return get_active_skin()
