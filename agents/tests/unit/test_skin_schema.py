"""TASK-13 — customer.yaml schema + compile pipeline unit tests.

Validates that every shipped skin under ``skins/`` parses, conforms to the
JSON Schema, and round-trips through ``scripts/compile_skin.py`` without
losing fields. The compile script is the contract between the
customer-agnostic core (canvas) and the customer-specific config (the YAML),
so a regression here would silently break the skin loader at canvas build
time.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SKINS_DIR = REPO_ROOT / "skins"
SCHEMA_PATH = SKINS_DIR / "schema" / "customer.schema.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "compile_skin.py"

SHIPPED_SKINS = ["default", "halliburton"]


def _load_yaml(slug: str) -> dict[str, Any]:
    path = SKINS_DIR / slug / "customer.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"skin {slug} root must be a mapping"
    return data


def _load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return _load_schema()


def test_schema_file_exists_and_is_valid_json_schema(schema: dict[str, Any]) -> None:
    """The schema itself must be a valid Draft 2020-12 JSON Schema."""
    # `jsonschema.Draft202012Validator.check_schema` raises on malformed schemas.
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("slug", SHIPPED_SKINS)
def test_shipped_skin_validates(slug: str, schema: dict[str, Any]) -> None:
    """Every shipped skin must validate against the schema."""
    data = _load_yaml(slug)
    jsonschema.validate(data, schema)


@pytest.mark.parametrize("slug", SHIPPED_SKINS)
def test_skin_has_six_personas_with_canonical_ids(slug: str) -> None:
    """The six persona slugs are part of the contract — code branches on them."""
    data = _load_yaml(slug)
    persona_ids = {p["id"] for p in data["personas"]}
    assert persona_ids == {"david", "tomas", "maria", "priya", "rafael", "ayesha"}, (
        f"skin {slug} persona ids drifted: {sorted(persona_ids)}"
    )
    # Numbers must be the canonical 1..6 ordering.
    numbers = sorted(p["number"] for p in data["personas"])
    assert numbers == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("slug", SHIPPED_SKINS)
def test_skin_brand_colors_are_hex(slug: str) -> None:
    """Brand colors must be six-digit hex — Tailwind/CSS need them in that form."""
    data = _load_yaml(slug)
    meta = data["meta"]
    for key in ("color_primary", "color_secondary", "color_accent"):
        value = meta[key]
        assert value.startswith("#") and len(value) == 7, (
            f"skin {slug} {key} must be six-digit hex; got {value!r}"
        )


@pytest.mark.parametrize("slug", SHIPPED_SKINS)
def test_skin_cargo_plane_scenario_complete(slug: str) -> None:
    """The cargo-plane scenario is the hero — it must have all map + cost fields."""
    data = _load_yaml(slug)
    scenarios = data["scenarios"]
    assert "cargo-plane" in scenarios, f"skin {slug} missing cargo-plane scenario"
    cp = scenarios["cargo-plane"]
    for required in (
        "customer_account_name",
        "location_focus_label",
        "location_focus_lng",
        "location_focus_lat",
        "naive_origin_label",
        "naive_origin_lng",
        "naive_origin_lat",
        "recommended_origin_label",
        "recommended_origin_lng",
        "recommended_origin_lat",
        "asset_focus_label",
        "naive_cost_usd",
        "recommended_cost_usd",
        "opening_prompt",
    ):
        assert required in cp, (
            f"skin {slug} cargo-plane scenario missing required field {required!r}"
        )

    # Cost story must be coherent: naive > recommended.
    assert cp["naive_cost_usd"] > cp["recommended_cost_usd"], (
        f"skin {slug} cargo-plane naive cost must exceed recommended cost"
    )


def _load_compile_script_module():
    """Load ``scripts/compile_skin.py`` as an importable module for direct
    function calls. We can't import via dotted path because ``scripts/`` is
    not a Python package; ``importlib.util`` is the supported escape hatch."""
    spec = importlib.util.spec_from_file_location("compile_skin_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["compile_skin_under_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("slug", SHIPPED_SKINS)
def test_compile_skin_dry_run(slug: str) -> None:
    """``compile_skin.py`` should load + validate without writing files."""
    module = _load_compile_script_module()
    data = module.compile_skin(slug, write=False)
    # Round-trip check: the dict should equal the raw YAML load.
    assert data == _load_yaml(slug)


def test_two_shipped_skins_differ_meaningfully() -> None:
    """The whole point of the skin system: two skins must produce different
    customer-facing display content. Specifically, the customer display name,
    persona names, hero asset label, and cargo-plane customer account must
    all differ. If this test fires, the Halliburton skin has been over-aligned
    with the default."""
    default = _load_yaml("default")
    halliburton = _load_yaml("halliburton")

    assert default["meta"]["customer_display_name"] != halliburton["meta"]["customer_display_name"]
    assert default["meta"]["color_primary"] != halliburton["meta"]["color_primary"]
    hero_default = default["taxonomy"]["hero_asset"]["canonical_label"]
    hero_halli = halliburton["taxonomy"]["hero_asset"]["canonical_label"]
    assert hero_default != hero_halli

    default_persona_names = {p["name"] for p in default["personas"]}
    halliburton_persona_names = {p["name"] for p in halliburton["personas"]}
    # All six persona names should differ across skins.
    overlap = default_persona_names & halliburton_persona_names
    assert overlap == set(), f"skins share persona names: {overlap}"

    default_cargo = default["scenarios"]["cargo-plane"]
    halliburton_cargo = halliburton["scenarios"]["cargo-plane"]
    assert default_cargo["customer_account_name"] != halliburton_cargo["customer_account_name"]
    assert default_cargo["location_focus_label"] != halliburton_cargo["location_focus_label"]
