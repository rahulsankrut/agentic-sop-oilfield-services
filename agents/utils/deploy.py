"""Vertex AI Agent Engine deployment helpers.

Wraps the canonical `vertexai.Client.agent_engines` create + update pattern
with a monkey-patch around the Pydantic-vs-protobuf incompatibility in
`google-cloud-aiplatform >= 1.150` combined with `a2a-sdk` 0.x.

## The bug

When deploying an `A2aAgent` (or any agent with an `agent_card` attribute),
`vertexai._genai._agent_engines_utils._generate_class_methods_spec_or_raise`
calls:

    json_format.MessageToJson(agent.agent_card)

That call assumes `agent_card` is a protobuf `Message`. In `a2a-sdk` 0.3.x
`AgentCard` is a Pydantic model with no `DESCRIPTOR` attribute, so the call
raises `AttributeError: 'AgentCard' object has no attribute 'DESCRIPTOR'`.

## The fix

`patch_message_to_json_for_pydantic()` rebinds `google.protobuf.json_format.
MessageToJson` to a wrapper that detects Pydantic models and serializes them
via `model_dump_json()`. Protobuf messages still go through the original
implementation. Idempotent.

Call `patch_message_to_json_for_pydantic()` (or the higher-level
`deploy_a2a_agent_engine()`) **before** any code path that may hit the
buggy call site (i.e., before `client.agent_engines.create` /
`client.agent_engines.update` with an `A2aAgent`).

Track upstream and remove this patch when google-cloud-aiplatform ships a
release that handles Pydantic `AgentCard` natively.
"""

from __future__ import annotations

import logging
from typing import Any

from google.protobuf import json_format as _json_format

logger = logging.getLogger(__name__)


def patch_message_to_json_for_pydantic() -> None:
    """Patch `google.protobuf.json_format.{MessageToJson,MessageToDict}` for Pydantic.

    The vertexai SDK calls both ``MessageToJson`` (in
    ``_agent_engines_utils._generate_class_methods_spec_or_raise``) and
    ``MessageToDict`` (in ``agent_engines._create_config``) on the agent's
    ``agent_card`` attribute. Both blow up when the card is an ``a2a-sdk``
    0.x Pydantic model. We patch both with a single shim that feature-
    detects Pydantic v2 and routes through ``model_dump_json`` /
    ``model_dump`` respectively.

    Idempotent — safe to call multiple times.
    """
    original_to_json = _json_format.MessageToJson
    original_to_dict = _json_format.MessageToDict
    if getattr(original_to_json, "_patched_for_pydantic", False):
        return

    def patched_to_json(message: Any, *args: Any, **kwargs: Any) -> str:
        if hasattr(message, "model_dump_json") and not hasattr(message, "DESCRIPTOR"):
            return message.model_dump_json()
        return original_to_json(message, *args, **kwargs)

    def patched_to_dict(message: Any, *args: Any, **kwargs: Any) -> dict:
        if hasattr(message, "model_dump") and not hasattr(message, "DESCRIPTOR"):
            # exclude_none=True matches protobuf's "omit empty" default; the
            # Agent Engine API rejects null fields it doesn't expect.
            return message.model_dump(mode="json", exclude_none=True)
        return original_to_dict(message, *args, **kwargs)

    patched_to_json._patched_for_pydantic = True  # type: ignore[attr-defined]
    patched_to_dict._patched_for_pydantic = True  # type: ignore[attr-defined]
    _json_format.MessageToJson = patched_to_json
    _json_format.MessageToDict = patched_to_dict
    logger.info(
        "Patched google.protobuf.json_format.{MessageToJson,MessageToDict} to handle "
        "Pydantic models (workaround for vertexai/_genai/_agent_engines_utils.py:636 + "
        "_genai/agent_engines.py:2505 + a2a-sdk 0.x)"
    )


def deploy_a2a_agent_engine(  # noqa: PLR0913 — config-heavy deploy is naturally wide
    *,
    agent: Any,
    display_name: str,
    description: str,
    extra_packages: list[str],
    requirements: list[str],
    env_vars: dict[str, str] | None = None,
    context_spec: dict[str, Any] | None = None,
    project: str,
    location: str,
    staging_bucket: str,
) -> str:
    """Deploy an A2aAgent to Vertex AI Agent Engine.

    Mirrors the reference simulator's two-step create-then-update pattern,
    with the Pydantic patch applied beforehand.

    Args:
        agent: An `A2aAgent` instance (or any agent with `agent_card`).
        display_name: Display name shown in the Agent Engine console.
        description: Description shown in the Agent Engine console.
        extra_packages: List of package directories to upload (e.g.,
            `["agents/procurement_approval_agent"]`).
        requirements: PyPI dependency strings for the deployed env.
        env_vars: Environment variables baked into the deployment.
        context_spec: Optional Memory Bank / context configuration.
        project: GCP project id.
        location: GCP region (e.g., "us-central1").
        staging_bucket: `gs://...` URI for staging the deployment.

    Returns:
        Full resource name like
        `projects/.../locations/.../reasoningEngines/<id>`.
    """
    patch_message_to_json_for_pydantic()

    import vertexai  # noqa: PLC0415 — heavy import, kept lazy for fast module load

    client = vertexai.Client(project=project, location=location)

    create_config: dict[str, Any] = {
        "staging_bucket": staging_bucket,
        "display_name": display_name,
        "description": description,
    }
    if context_spec is not None:
        create_config["context_spec"] = context_spec

    logger.info("Creating Agent Engine '%s' in %s/%s", display_name, project, location)
    created = client.agent_engines.create(config=create_config)
    resource_name = created.api_resource.name
    logger.info("Created Agent Engine: %s", resource_name)

    update_config: dict[str, Any] = {
        "staging_bucket": staging_bucket,
        "requirements": requirements,
        "extra_packages": extra_packages,
    }
    if env_vars:
        update_config["env_vars"] = env_vars

    logger.info("Uploading agent code + dependencies to %s", resource_name)
    client.agent_engines.update(
        name=resource_name,
        agent=agent,
        config=update_config,
    )
    logger.info("Deploy complete: %s", resource_name)
    return resource_name
