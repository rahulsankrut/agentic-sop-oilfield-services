"""Unit tests for agents/utils/a2ui.py — the A2UI v0.9 emitter (TASK-45)."""

from __future__ import annotations

import pytest

from agents.utils.a2ui import (
    begin_rendering,
    cost_rollup,
    kc_drawer,
    message_batch,
    surface_update,
    text,
)


def test_surface_update_envelope_shape():
    comps = [text("t1", "hi")]
    env = surface_update("kc-drawer", comps)
    assert env["surfaceUpdate"]["surfaceId"] == "kc-drawer"
    assert env["surfaceUpdate"]["components"] == comps


def test_begin_rendering_envelope_shape():
    env = begin_rendering("kc-drawer", "root")
    assert env["beginRendering"]["surfaceId"] == "kc-drawer"
    assert env["beginRendering"]["root"] == "root"


def test_text_component_node_shape():
    node = text("t1", "hello", variant="h1")
    assert node["id"] == "t1"
    assert node["component"]["Text"] == {
        "text": {"literalString": "hello"},
        "variant": "h1",
    }


def test_message_batch_two_messages():
    msgs = message_batch("s1", "root", [text("root", "x")])
    assert len(msgs) == 2
    assert "surfaceUpdate" in msgs[0]
    assert "beginRendering" in msgs[1]
    assert msgs[1]["beginRendering"]["root"] == "root"
    assert msgs[1]["beginRendering"]["surfaceId"] == "s1"


def test_kc_drawer_produces_valid_batch():
    msgs = kc_drawer(
        "TX-007",
        "Tool X-V7",
        aspects={
            "cross_system_aliases": {
                "sap_material_number": "MAT-67899",
                "maximo_equipment_id": "EQ-12399",
                "fdp_config_id": "TX-CONFIG-V7",
            },
            "functional_equivalences": [
                {"canonical_id": "TX-001", "confidence": 0.92, "rationale_source": "InTouch §3.2"},
            ],
            "asset_specification": {"manufacturer": "Schlumberger", "introduced_year": 2021},
        },
    )
    assert len(msgs) == 2
    components = msgs[0]["surfaceUpdate"]["components"]
    ids = {c["id"] for c in components}
    assert {"root", "body", "title", "alias-sap", "spec-mfr"}.issubset(ids)
    root = next(c for c in components if c["id"] == "root")
    assert root["component"]["Card"]["child"] == "body"


@pytest.mark.parametrize(
    ("doomed", "rec", "avoided"),
    [
        (420_000, 40_000, 380_000),
        (100_000, 50_000, 50_000),
    ],
)
def test_cost_rollup_renders_three_columns(doomed: int, rec: int, avoided: int):
    msgs = cost_rollup(doomed_usd=doomed, recommended_usd=rec, avoided_usd=avoided)
    components = msgs[0]["surfaceUpdate"]["components"]
    column_ids = [c["id"] for c in components if "Column" in c["component"]]
    assert {"doomed", "rec", "avoid"}.issubset(set(column_ids))
    body = next(c for c in components if c["id"] == "body")
    assert body["component"]["Row"]["children"] == {
        "explicitList": ["doomed", "rec", "avoid"],
    }
    rec_value = next(c for c in components if c["id"] == "rec-value")
    assert rec_value["component"]["Text"]["text"] == {"literalString": f"${rec:,}"}
