"""Cross-skin behavioural tests (TASK-13 Step 5).

Exercises the agent-side splice points to verify that swapping
``CUSTOMER_SKIN`` actually changes what the deployed agents emit.
These are NOT integration tests — they call the splice functions
directly to confirm the skin lookup is wired correctly.
"""

from __future__ import annotations

import pytest

from agents.utils import skin_loader


@pytest.fixture(autouse=True)
def _reset_skin_cache():
    skin_loader._cached_skin = None
    skin_loader._cached_slug = None
    yield
    skin_loader._cached_skin = None
    skin_loader._cached_slug = None


# ---------------------------------------------------------------------------
# parse_request — heuristic asset + location + customer extraction
# ---------------------------------------------------------------------------


def _call_parse(query: str):
    """Invoke parse_capacity_gap_request_node with a minimal Context stub."""
    from agents.orchestrator_agent.nodes.parse_request import (
        parse_capacity_gap_request,
    )

    class _Ctx:
        state: dict = {"workflow_id": "test-wf", "session_id": "test-sess"}

    return parse_capacity_gap_request(query, _Ctx())


def test_default_skin_routes_to_luanda(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    skin_loader.reload_active_skin()
    event = _call_parse("I need a Tool X variant in Luanda by Friday")
    request = event.output
    assert "Luanda" in request["target_location"]["label"]


def test_halliburton_skin_routes_to_buzios(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "halliburton")
    skin_loader.reload_active_skin()
    event = _call_parse('I need a Drill Bit 5.5" in Búzios by Friday')
    request = event.output
    label = request["target_location"]["label"]
    # Halliburton's cargo-plane scenario points at Búzios Pre-salt (Brazil)
    assert "Búzios" in label or "Buzios" in label, f"got label={label!r}"


# ---------------------------------------------------------------------------
# finalize — naive baseline fallback hub derives from skin
# ---------------------------------------------------------------------------


def test_finalize_skin_hub_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    skin_loader.reload_active_skin()
    from agents.orchestrator_agent.nodes.finalize import _skin_fallback_hub

    hub = _skin_fallback_hub()
    # Default skin's cargo-plane naive origin is Darwin, Australia.
    assert hub is not None
    assert "Darwin" in hub.label


def test_finalize_skin_hub_halliburton(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "halliburton")
    skin_loader.reload_active_skin()
    from agents.orchestrator_agent.nodes.finalize import _skin_fallback_hub

    hub = _skin_fallback_hub()
    # Halliburton skin's cargo-plane naive origin is Singapore.
    assert hub is not None
    assert "Singapore" in hub.label


# ---------------------------------------------------------------------------
# procurement_approval agent_card examples
# ---------------------------------------------------------------------------


def test_procurement_card_examples_change_per_skin(monkeypatch: pytest.MonkeyPatch):
    from agents.procurement_approval_agent.agent_card import _build_examples

    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    skin_loader.reload_active_skin()
    default_examples = _build_examples()

    monkeypatch.setenv("CUSTOMER_SKIN", "halliburton")
    skin_loader.reload_active_skin()
    halliburton_examples = _build_examples()

    # The 3rd example is hardcoded (off-scenario region); the first two
    # are skin-derived and must diverge.
    assert default_examples[0] != halliburton_examples[0]
    assert default_examples[1] != halliburton_examples[1]
    # Default skin references Lagos → Luanda; Halliburton references the
    # Macaé / Singapore / Búzios geography from skins/halliburton/customer.yaml.
    assert any("Lagos" in e or "Luanda" in e for e in default_examples)
    assert any(
        "Macaé" in e or "Macae" in e or "Singapore" in e or "Búzios" in e or "Buzios" in e
        for e in halliburton_examples
    )
