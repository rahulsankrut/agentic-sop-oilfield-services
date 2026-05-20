"""Runtime compatibility shim for ADK 2.0 + Vertex AI Agent Engine.

ADK 2.0 added a strict validator on ``google.adk.apps.app.App.name`` that
requires the name to start with a letter and consist only of
``[A-Za-z0-9_-]``. The Vertex AI Agent Engine runtime template (the code
under ``/code/app/api/factory/`` inside the deployed Reasoning Engine
container) instantiates ``App(name=<reasoning_engine_id>)`` via
``AdkApp.set_up`` → ``adk.Runner`` → ``google.adk.runners._resolve_app``.
Reasoning Engine IDs are numeric, so the validator raises::

    Value error, Invalid app name '7861563663935602688': must start with
    a letter and can only consist of letters, digits, underscores, and
    hyphens.

Verified 2026-05-20 via ``inspect.signature(AdkApp.__init__)`` in
``venv-deploy-310/``: ``AdkApp`` does NOT accept an ``app_name=`` kwarg.
The internal ``_tmpl_attrs["app_name"]`` is set from
``GOOGLE_CLOUD_AGENT_ENGINE_ID`` at ``set_up`` time — that's the numeric
id. The clean upstream fix would be inside ``AdkApp.set_up``; until that
lands, the only workable workaround at user-code level is the monkey-patch
below.

The fallback alternative (use ``A2aAgent`` instead of ``AdkApp``) does
not hit this bug because the A2A wrapper bypasses ADK's ``App``
construction entirely — that's why Procurement deploys clean without
this patch.

This module monkey-patches ``validate_app_name`` to be permissive: numeric
prefixes are accepted (alphanumeric-and-hyphen rule otherwise preserved).
Import for side effects from any module that runs at deploy/runtime
startup. ``src/utils/__init__.py`` imports it so any code that does
``from agents.utils import ...`` triggers the patch.

Remove this shim when Vertex AI's runtime template starts using a
sanitized identifier-safe name (e.g., ``ae_<numeric_id>``) instead of
the bare numeric reasoning_engine_id.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Identifier-safe permissive regex: accepts anything that's [A-Za-z0-9_-]+,
# with no leading-letter requirement. This matches what Vertex AI's runtime
# template effectively passes (a numeric reasoning_engine_id).
_PERMISSIVE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _patched_validate_app_name(name: str) -> None:
    """Replacement for ``google.adk.apps.app.validate_app_name``.

    Same as the original but drops the leading-letter requirement. Keeps
    the ``name == 'user'`` rejection (semantic reservation).
    """
    if not _PERMISSIVE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid app name '{name}': must consist of letters, digits, "
            "underscores, and hyphens."
        )
    if name == "user":
        raise ValueError("App name cannot be 'user'; reserved for end-user input.")


def patch_adk_app_name_validator() -> None:
    """Replace ADK 2.0's strict ``validate_app_name`` with the permissive shim.

    Idempotent — safe to call multiple times.
    """
    try:
        from google.adk.apps import app as _adk_app  # noqa: PLC0415
    except ImportError:
        # ADK 2.0 not installed (e.g., a venv that's still on 1.x); nothing
        # to do.
        return

    if getattr(_adk_app.validate_app_name, "_permissive_patch", False):
        return

    _patched_validate_app_name._permissive_patch = True  # type: ignore[attr-defined]
    _adk_app.validate_app_name = _patched_validate_app_name
    logger.info(
        "Patched google.adk.apps.app.validate_app_name to accept numeric "
        "prefixes (Vertex AI Agent Engine compat — see src/utils/adk_compat.py)."
    )


# Apply immediately on import — that's the whole point.
patch_adk_app_name_validator()
