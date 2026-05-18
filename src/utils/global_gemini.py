# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Ported verbatim from
# github.com/GoogleCloudPlatform/race-condition/agents/utils/global_gemini.py

"""Gemini model subclass that routes to the global endpoint.

Agent Engine auto-configures vertexai with location='us-central1', which
prevents access to Gemini 3 preview models that only live on the global
endpoint. This module provides GlobalGemini — a drop-in replacement for
the standard ADK Gemini class that explicitly creates a genai Client with
location='global', bypassing AE's platform-level vertexai.init() override.

Memory Bank, Sessions, and Agent Engine itself keep using us-central1 (the
AE-default region) because we don't touch vertexai.init — only the model
call routes elsewhere.

Usage in LlmAgent definitions:

    from src.utils.global_gemini import GlobalGemini

    agent = LlmAgent(
        model=GlobalGemini(model="gemini-3.1-pro-preview"),
        ...
    )

Per-agent location override (e.g., a GA model that has a regional endpoint):

    model = GlobalGemini(model="gemini-2.5-pro", location="us-central1")
"""

import os
from functools import cached_property
from typing import TYPE_CHECKING

from google.adk.models.google_llm import Gemini
from google.genai import types

if TYPE_CHECKING:
    from google.genai import Client


class GlobalGemini(Gemini):
    """Gemini model with explicit location control for Vertex AI.

    On Agent Engine, vertexai is auto-initialized with the AE region
    (us-central1). The standard Gemini class creates Client() which
    inherits that location. GlobalGemini overrides api_client to create
    a Client with an explicit location, defaulting to 'global' for
    Gemini 3 preview models.
    """

    location: str = "global"
    """Vertex AI API location. Defaults to 'global' for Gemini 3 preview models.
    Set to a region (e.g. 'us-central1') for GA models."""

    @cached_property
    def api_client(self) -> "Client":
        """Create a genai Client with the configured location."""
        from google.genai import Client  # noqa: PLC0415 — lazy to defer heavy import

        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        return Client(
            vertexai=True,
            project=project,
            location=self.location,
            http_options=types.HttpOptions(
                headers=self._tracking_headers(),
                retry_options=self.retry_options,
                base_url=self.base_url,
            ),
        )
