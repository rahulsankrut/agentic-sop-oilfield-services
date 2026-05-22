"""Shared helpers for the per-agent eval suites (TASK-EVALS).

These wrap the two things every eval suite needs:

1. Loading the agent's `.evalset.json` file as the ADK ``EvalSet`` pydantic
   model. The evalset is the canonical source of truth for what we send the
   deployed agent and what we expect back. ADK's :func:`AgentEvaluator.evaluate`
   would normally run the agent in-process, but our agents are deployed to
   Vertex AI Reasoning Engine and we want to exercise the *deployed* surface,
   so we load the evalset directly and drive ``stream_query`` against the
   resource name in the ``.env``.

2. Driving ``stream_query`` and concatenating the streamed text into a single
   string the per-agent eval can validate against its Pydantic output schema.

Both helpers intentionally degrade gracefully when ADK/Vertex SDKs are
absent (e.g. lint-only environments) — the live tests are pytest-skipped
in that case via the ``evals_live`` marker + the resource-name env var
guard.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Module-level cache of the active skin so each eval doesn't re-parse the
# YAML on every helper call.
_active_skin = None


def load_evalset(evalset_path: str | Path) -> dict[str, Any]:
    """Read the agent's ``.evalset.json`` from disk.

    Returns the raw dict (not the ADK ``EvalSet`` pydantic — we avoid the
    import to keep the helpers usable from environments that don't have
    google-adk installed, e.g. a CI-only lint job).
    """
    path = Path(evalset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Eval set not found at {path}")
    with path.open() as f:
        return json.load(f)


def get_skin_scenario(scenario_slug: str = "cargo-plane") -> dict[str, Any]:
    """Return the active skin's scenario config as a plain dict.

    Tries ``agents.utils.skin_loader.get_active_skin`` first; falls back to
    a hardcoded default for the cargo-plane scenario if the loader can't
    import (lint-only envs, missing PyYAML, etc.). Keeping the fallback
    here lets these eval files import without the full agent runtime.
    """
    try:
        from agents.utils.skin_loader import get_active_skin

        skin = get_active_skin()
        scenario = skin.scenario(scenario_slug)
        return scenario.model_dump()
    except Exception:
        # Hardcoded default mirrors skins/default/customer.yaml so the
        # eval-set defaults work without the loader.
        return _DEFAULT_CARGO_PLANE_SCENARIO


_DEFAULT_CARGO_PLANE_SCENARIO: dict[str, Any] = {
    "customer_account_slug": "gulf-petroleum",
    "customer_account_name": "Gulf Petroleum Services",
    "customer_account_short": "Gulf Petroleum",
    "location_focus_label": "Luanda, Angola",
    "naive_origin_label": "Darwin, Australia",
    "recommended_origin_label": "Lagos, Nigeria",
    "asset_focus_canonical_id": "TX-001",
    "asset_focus_label": "Tool X",
    "naive_cost_usd": 420000,
    "recommended_cost_usd": 40000,
    "avoided_cost_usd": 380000,
    "deadline_phrase": "by Friday",
    "opening_prompt": ("I need a Tool X variant in Luanda by Friday — what are my options?"),
}


def stream_query_text(
    resource_name_env: str,
    prompt: str,
    user_id: str = "eval-runner",
) -> str:
    """Drive the deployed Reasoning Engine's :streamQuery endpoint via REST,
    return concatenated text.

    Bypasses ``vertexai.agent_engines.get(...).stream_query()`` because the
    SDK's method registration intermittently fails on AdkApp-wrapped engines
    ("Failed to register API methods... 'NoneType' object has no attribute
    '__name__'"), leaving the AgentEngine wrapper without ``stream_query``.
    The REST endpoint always works and is the same path the canvas uses
    (canvas/src/app/api/orchestrator/stream/route.ts).
    """
    import google.auth
    import google.auth.transport.requests
    import requests

    resource = os.environ.get(resource_name_env)
    if not resource:
        raise RuntimeError(
            f"{resource_name_env} not set; live eval cannot run. Source the project .env first."
        )
    location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
        "GOOGLE_CLOUD_LOCATION", "us-central1"
    )
    url = (
        f"https://{location}-aiplatform.googleapis.com/v1beta1/"
        f"{resource}:streamQuery?alt=sse"
    )

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())

    body = {
        "class_method": "async_stream_query",
        "input": {
            "message": {"role": "user", "parts": [{"text": prompt}]},
            "user_id": user_id,
        },
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
        json=body,
        stream=True,
        timeout=600,
    )
    if not resp.ok:
        raise RuntimeError(
            f"streamQuery HTTP {resp.status_code}: {resp.text[:500]}"
        )

    buf: list[str] = []
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        # SSE frames are "data: <json>"; the deployed surface sometimes
        # sends bare JSON lines too. Strip the prefix when present.
        line = raw_line[6:] if raw_line.startswith("data: ") else raw_line
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for part in (event.get("content") or {}).get("parts") or []:
            text = part.get("text")
            if text:
                buf.append(text)
    return "".join(buf)


class WorkflowDidNotFinalizeError(RuntimeError):
    """Raised when the Capacity Orchestrator's :streamQuery response does not
    contain the final-node JSON (e.g. the Plan Evaluator scored below the
    accept threshold and the workflow routed to REVISE without recovering).

    LLM-derived scoring is non-deterministic; some runs hit the PROCEED
    branch (workflow finalizes, emits SourcingPlan JSON), others hit
    REVISE and stop. Callers that need a SourcingPlan back should catch
    this and ``pytest.skip(...)`` with a reason that points at the
    non-determinism rather than failing.
    """


def extract_first_json_object(
    text: str,
    must_contain: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Pull the first complete JSON object out of a free-form string.

    The Capacity Orchestrator's :streamQuery response interleaves node-
    narration prefixes ("Parsed capacity-gap request: ...", "Resolved
    'Tool X' → TX-001 ...", "Routing on evaluation: score=0.86 ...") with
    the final-node JSON output (a ``SourcingPlan``) and nested sub-objects
    (asset cards, route legs). We scan every ``{`` position, ``raw_decode``
    each one, and return the first match.

    ``must_contain`` filters to only return an object that has *all* the
    given top-level keys — required because raw_decode happily parses
    nested ``{canonical_id: ...}`` asset cards before the outer
    SourcingPlan. Pass e.g. ``("requested_asset", "primary_option")`` to
    pin to the SourcingPlan wrapper.

    Raises ValueError if no matching JSON object is found.
    """
    decoder = json.JSONDecoder()
    pos = 0
    while True:
        brace = text.find("{", pos)
        if brace < 0:
            break
        try:
            obj, _end = decoder.raw_decode(text[brace:])
        except json.JSONDecodeError:
            pos = brace + 1
            continue
        if isinstance(obj, dict):
            if must_contain is None or all(k in obj for k in must_contain):
                return obj
        pos = brace + 1
    # If we got here, no JSON object satisfied must_contain. For
    # Orchestrator callers pinning the SourcingPlan wrapper, this is
    # almost always a non-deterministic REVISE-without-recovery —
    # signal it so callers can pytest.skip rather than fail.
    if must_contain and "Routing on evaluation:" in text and "REVISE" in text:
        raise WorkflowDidNotFinalizeError(
            "Workflow routed to REVISE without finalizing; no SourcingPlan "
            "emitted. Plan Evaluator scoring is non-deterministic per run."
        )
    raise ValueError(
        f"No JSON object matching {must_contain} found in response "
        f"(len={len(text)}): {text[:200]!r}"
    )


def extract_expected_text(eval_case: dict[str, Any]) -> str | None:
    """Pull the expected final-response text from an ADK eval case dict.

    ADK schema: ``eval_case.conversation[i].final_response.parts[j].text``.
    Returns the first non-empty text part; ``None`` if the case has no
    final-response (some intermediate-state cases).
    """
    for inv in eval_case.get("conversation") or []:
        final = inv.get("final_response") or {}
        for part in final.get("parts") or []:
            text = part.get("text")
            if text:
                return text
    return None


def extract_user_query(eval_case: dict[str, Any]) -> str:
    """Pull the user query from the first invocation of an ADK eval case."""
    conv = eval_case.get("conversation") or []
    if not conv:
        raise ValueError(f"eval_case {eval_case.get('eval_id')!r} has no conversation")
    user_content = conv[0].get("user_content") or {}
    parts = user_content.get("parts") or []
    for p in parts:
        if p.get("text"):
            return p["text"]
    raise ValueError(f"eval_case {eval_case.get('eval_id')!r} has no user text part")
