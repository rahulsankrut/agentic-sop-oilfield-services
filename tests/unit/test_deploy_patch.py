"""Regression test for the Pydantic AgentCard ↔ protobuf MessageToJson patch.

Verifies that `patch_message_to_json_for_pydantic()` makes
`json_format.MessageToJson(<pydantic_model>)` succeed instead of raising
`AttributeError: ... has no attribute 'DESCRIPTOR'`.

Also verifies that the patch leaves real protobuf messages alone and is
idempotent.
"""

from __future__ import annotations

import json

import pytest
from a2a.types import AgentCapabilities, AgentCard
from google.protobuf import descriptor_pb2, json_format

from src.utils.deploy import patch_message_to_json_for_pydantic


def _make_card(name: str = "test_agent") -> AgentCard:
    return AgentCard(
        name=name,
        description="test",
        url="https://example.invalid",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[],
    )


def test_unpatched_pydantic_messagetojson_raises():
    """Sanity check: without the patch, MessageToJson on a Pydantic model fails.

    Skipped if the patch has already been applied earlier in the test session
    (the patched MessageToJson handles Pydantic fine, so we can't observe the
    original failure).
    """
    if getattr(json_format.MessageToJson, "_patched_for_pydantic", False):
        pytest.skip("MessageToJson already patched in this session")

    with pytest.raises(AttributeError, match="DESCRIPTOR"):
        json_format.MessageToJson(_make_card())


def test_patched_messagetojson_handles_pydantic():
    """After the patch, MessageToJson on a Pydantic model returns valid JSON."""
    patch_message_to_json_for_pydantic()

    card = _make_card("procurement_approval_agent")
    result = json_format.MessageToJson(card)
    parsed = json.loads(result)
    assert parsed["name"] == "procurement_approval_agent"
    assert parsed["version"] == "0.1.0"


def test_patch_is_idempotent():
    """Calling the patch twice doesn't double-wrap."""
    patch_message_to_json_for_pydantic()
    first = json_format.MessageToJson
    patch_message_to_json_for_pydantic()
    second = json_format.MessageToJson
    assert first is second


def test_patched_messagetojson_passes_through_protobuf():
    """Real protobuf messages still use the original implementation."""
    patch_message_to_json_for_pydantic()

    proto_msg = descriptor_pb2.FileDescriptorProto(name="example.proto", syntax="proto3")
    out = json_format.MessageToJson(proto_msg)
    parsed = json.loads(out)
    assert parsed["name"] == "example.proto"
    assert parsed["syntax"] == "proto3"
