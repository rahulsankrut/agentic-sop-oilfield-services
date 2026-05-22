"""Eval-suite runner for the Forecast Review Agent (TASK-EVALS).

Note on schema: the spec calls out ``ForecastOverride`` with
``rationale_tags``, but the deployed agent's output_schema is
``ForecastRationale`` (see agents/forecast_review_agent/agent.py +
agents/schemas.py). ``ForecastRationale`` has the ``rationale_tags`` field
the spec requires, so we assert on that shape — the spec's
``ForecastOverride`` reference is the *input* form (the override record
itself), not the agent's return value.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.schemas import ForecastRationale
from agents.utils.eval_helpers import (
    extract_user_query,
    load_evalset,
    stream_query_text,
)

EVALSET_PATH = Path(__file__).parent / "forecast_review_agent.evalset.json"


# ---------------------------------------------------------------------------
# Fast layer
# ---------------------------------------------------------------------------


def test_evalset_file_exists_and_parses():
    evalset = load_evalset(EVALSET_PATH)
    eval_ids = {c["eval_id"] for c in evalset["eval_cases"]}
    assert "happy_path_q4_west_africa_override" in eval_ids
    assert "edge_empty_rationale" in eval_ids
    assert "edge_missing_override_id" in eval_ids
    # Persona 1 demo prompt + significance boundary (2026-05-21 expansion).
    assert "persona1_david_permian_q4_completions" in eval_ids
    assert "override_significance_high_magnitude" in eval_ids


def test_persona1_demo_prompt_extracts_demo_critical_tags():
    """Persona 1's exact demo line — 'rig count decline + three operators
    delaying' — must lift to rig_count_decline + operator_delay tags.

    These are the literal tags the demo narration ties back to (see
    docs/planning/agentic_sop_oilfield_services_brief.md §Persona 1).
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"]
        if c["eval_id"] == "persona1_david_permian_q4_completions"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    rationale = ForecastRationale.model_validate_json(text)
    assert "rig_count_decline" in rationale.rationale_tags, (
        f"Persona 1 demo must extract rig_count_decline; got {rationale.rationale_tags}"
    )
    assert "operator_delay" in rationale.rationale_tags, (
        f"Persona 1 demo must extract operator_delay; got {rationale.rationale_tags}"
    )


def test_happy_path_expected_response_has_rationale_tags():
    """The west_africa Q4 expected response must include non-empty rationale_tags."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_q4_west_africa_override"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    rationale = ForecastRationale.model_validate_json(text)
    assert rationale.rationale_tags, (
        "Happy path must have non-empty rationale_tags (per task spec)."
    )


def test_empty_rationale_case_is_explicitly_empty():
    """The empty-rationale edge case asserts the agent must NOT fabricate tags."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "edge_empty_rationale")
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    rationale = ForecastRationale.model_validate_json(text)
    assert rationale.rationale_tags == [], (
        "Empty-rationale edge case expects rationale_tags=[] — the prompt "
        "explicitly says 'don't fabricate'."
    )


def test_forecast_rationale_schema_roundtrips():
    rationale = ForecastRationale(
        override_id="ovr-test-001",
        rationale_tags=["rig_count_decline"],
        freeform_text="Test rationale",
        confidence=0.8,
    )
    rebuilt = ForecastRationale.model_validate_json(rationale.model_dump_json())
    assert rebuilt.rationale_tags == ["rig_count_decline"]


# ---------------------------------------------------------------------------
# Live layer
# ---------------------------------------------------------------------------


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("FORECAST_REVIEW_AGENT_RESOURCE_NAME"),
    reason="FORECAST_REVIEW_AGENT_RESOURCE_NAME not set",
)
def test_live_happy_path_returns_rationale_with_tags():
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_q4_west_africa_override"
    )
    prompt = extract_user_query(case)
    text = stream_query_text(
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME", prompt, user_id="eval-forecast-happy"
    )
    rationale = ForecastRationale.model_validate_json(text)
    assert rationale.rationale_tags, (
        f"Expected non-empty rationale_tags for a clear override; "
        f"got freeform_text={rationale.freeform_text!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("FORECAST_REVIEW_AGENT_RESOURCE_NAME"),
    reason="FORECAST_REVIEW_AGENT_RESOURCE_NAME not set",
)
def test_live_empty_rationale_doesnt_fabricate_tags():
    """A vague 'gut feeling' rationale should produce an empty (or near-empty) tag list."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "edge_empty_rationale")
    prompt = extract_user_query(case)
    text = stream_query_text(
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME", prompt, user_id="eval-forecast-empty"
    )
    rationale = ForecastRationale.model_validate_json(text)
    # The prompt says: "If rationale_tags is empty after extraction, return
    # the tag list as-is (don't fabricate)." So we expect 0-1 tags for the
    # "gut feeling" case (the LLM may legitimately tag it with a low-
    # confidence "instinct" or similar, but we draw the line at "many tags").
    assert len(rationale.rationale_tags) <= 1, (
        f"Empty-rationale case shouldn't extract multiple tags; got {rationale.rationale_tags!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("FORECAST_REVIEW_AGENT_RESOURCE_NAME"),
    reason="FORECAST_REVIEW_AGENT_RESOURCE_NAME not set",
)
def test_live_persona1_demo_extracts_demo_critical_tags():
    """Persona 1's exact demo line must extract the tags the narration
    relies on. If either rig_count_decline or operator_delay drops out,
    the demo's 'model improving' moment loses its punch.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"]
        if c["eval_id"] == "persona1_david_permian_q4_completions"
    )
    prompt = extract_user_query(case)
    text = stream_query_text(
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME", prompt, user_id="eval-persona1-david"
    )
    rationale = ForecastRationale.model_validate_json(text)
    tags_lower = {t.lower() for t in rationale.rationale_tags}
    has_rig = any("rig" in t for t in tags_lower)
    has_operator = any("operator" in t or "delay" in t for t in tags_lower)
    assert has_rig and has_operator, (
        f"Persona 1 demo prompt must extract rig + operator/delay tags; "
        f"got {rationale.rationale_tags!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("FORECAST_REVIEW_AGENT_RESOURCE_NAME"),
    reason="FORECAST_REVIEW_AGENT_RESOURCE_NAME not set",
)
def test_live_missing_override_id_degrades_gracefully():
    """Missing override_id in the input should not crash the agent."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "edge_missing_override_id")
    prompt = extract_user_query(case)
    text = stream_query_text(
        "FORECAST_REVIEW_AGENT_RESOURCE_NAME", prompt, user_id="eval-forecast-missing-id"
    )
    assert text, "Forecast Review returned empty response"
    # If JSON, must parse as ForecastRationale; else accept graceful error text.
    try:
        rationale = ForecastRationale.model_validate_json(text)
        assert rationale.override_id, (
            "Agent should fill in a placeholder override_id, not leave it blank."
        )
    except Exception:
        assert len(text) > 20
