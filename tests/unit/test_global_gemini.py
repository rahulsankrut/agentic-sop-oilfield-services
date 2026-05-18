"""Unit tests for the GlobalGemini ADK model subclass.

Verifies the class is wired correctly without making live model calls. The
canonical "did it work end-to-end" check happens in an integration test that
hits the real Gemini API; here we just exercise instantiation + location
plumbing.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from google.adk.models.google_llm import Gemini

from src.utils.global_gemini import GlobalGemini


def test_globalgemini_is_a_gemini_subclass():
    """ADK callers must accept GlobalGemini wherever Gemini works."""
    assert issubclass(GlobalGemini, Gemini)


def test_default_location_is_global():
    model = GlobalGemini(model="gemini-3.1-pro-preview")
    assert model.location == "global"


def test_location_can_be_overridden():
    model = GlobalGemini(model="gemini-2.5-pro", location="us-central1")
    assert model.location == "us-central1"


def test_api_client_uses_configured_location_and_project():
    """`api_client` should construct a Client with vertexai=True and our location."""
    model = GlobalGemini(model="gemini-3.1-pro-preview")

    with (
        patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=False),
        patch("google.genai.Client") as mock_client,
    ):
        _ = model.api_client  # trigger cached_property

    mock_client.assert_called_once()
    kwargs = mock_client.call_args.kwargs
    assert kwargs["vertexai"] is True
    assert kwargs["project"] == "test-project"
    assert kwargs["location"] == "global"


def test_api_client_is_cached():
    """Repeated access should not re-create the underlying Client."""
    model = GlobalGemini(model="gemini-3.1-pro-preview")

    with (
        patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=False),
        patch("google.genai.Client") as mock_client,
    ):
        first = model.api_client
        second = model.api_client

    assert first is second
    assert mock_client.call_count == 1


@pytest.mark.parametrize(
    "location",
    ["global", "us-central1", "us-east5", "europe-west4"],
)
def test_api_client_honors_arbitrary_location(location: str):
    model = GlobalGemini(model="gemini-3-flash-preview", location=location)
    with (
        patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=False),
        patch("google.genai.Client") as mock_client,
    ):
        _ = model.api_client
    assert mock_client.call_args.kwargs["location"] == location
