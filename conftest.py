"""Repo-root pytest config for the eval suites (TASK-EVALS).

Why repo-root and not inside ``agents/tests/conftest.py``: the per-agent
eval suites live under ``agents/<agent>/evals/``, which is a sibling
subtree to ``agents/tests/``. Pytest only picks up a ``conftest.py``
along the test file's parent chain, so a conftest under ``agents/tests/``
wouldn't be visible to ``agents/orchestrator_agent/evals/test_*.py``.
A repo-root conftest is visible to every subtree.

The unit-test autouse mocks intentionally stay in
``agents/tests/conftest.py`` so they don't accidentally apply to the
live eval suites (which need the real Vertex SDK calls).

Two responsibilities here:

* Register the ``evals_live`` marker so eval files can mark slow,
  expensive, deploy-dependent tests with it.
* Add the ``--run-live-evals`` CLI flag and auto-skip ``evals_live`` tests
  unless that flag is passed. This lets ``poetry run pytest`` stay safe to
  run on every PR without burning Gemini tokens.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live-evals",
        action="store_true",
        default=False,
        help=(
            "Run the live eval layer (agents/<agent>/evals/ tests marked "
            "@pytest.mark.evals_live). Hits the deployed Reasoning Engines "
            "via :streamQuery — requires ADC + costs real money."
        ),
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "evals_live: live agent evals against deployed Reasoning Engines "
        "(slow, costs $). Use --run-live-evals to opt in.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``evals_live`` items unless ``--run-live-evals`` was passed."""
    if config.getoption("--run-live-evals"):
        return
    skip_live = pytest.mark.skip(reason="live eval skipped (pass --run-live-evals to run)")
    for item in items:
        if "evals_live" in item.keywords:
            item.add_marker(skip_live)
