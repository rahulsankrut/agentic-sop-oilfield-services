"""Unit tests for `agents.utils.skin_loader` (TASK-13 Step 5)."""

from __future__ import annotations

import pytest

from agents.utils import skin_loader


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch: pytest.MonkeyPatch):
    """Each test starts with an empty skin cache."""
    skin_loader._cached_skin = None
    skin_loader._cached_slug = None
    yield
    skin_loader._cached_skin = None
    skin_loader._cached_slug = None


def test_default_skin_loads(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CUSTOMER_SKIN", raising=False)
    skin = skin_loader.get_active_skin()
    assert skin.meta.customer_slug == "default"
    # Persona 3 is canonically Maria for the cargo-plane scenario.
    persona = skin.persona("maria")
    assert persona.number == 3
    assert persona.scenario_slug == "cargo-plane"


def test_halliburton_skin_loads(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "halliburton")
    skin = skin_loader.get_active_skin()
    assert skin.meta.customer_slug == "halliburton"
    # Halliburton-pattern persona names diverge from default.
    persona_3 = skin.persona(3)
    assert persona_3.id == "maria"  # ids stay stable
    assert persona_3.name != "Maria Reyes"  # but the display name diverges


def test_unknown_skin_errors(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "no-such-customer")
    with pytest.raises(FileNotFoundError, match="customer.yaml not found"):
        skin_loader.reload_active_skin()


def test_cache_returns_same_instance(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    a = skin_loader.get_active_skin()
    b = skin_loader.get_active_skin()
    assert a is b


def test_cache_invalidated_on_slug_change(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    a = skin_loader.get_active_skin()
    monkeypatch.setenv("CUSTOMER_SKIN", "halliburton")
    b = skin_loader.get_active_skin()
    assert a is not b
    assert a.meta.customer_slug == "default"
    assert b.meta.customer_slug == "halliburton"


def test_cargo_plane_scenario_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CUSTOMER_SKIN", "default")
    s = skin_loader.get_active_skin().scenario("cargo-plane")
    # Sanity-check the cargo-plane scenario carries all the strings we'll
    # splice into agent prompts.
    assert s.asset_focus_label
    assert s.location_focus_label
    assert s.opening_prompt
