"""Eval-suite runner for the bundled Plan Evaluator (TASK-EVALS).

The Plan Evaluator ships in-process with the Capacity Orchestrator (ADR-0003
— bundled, not deployed standalone). That means there's no
PLAN_EVALUATOR_AGENT_RESOURCE_NAME; the live layer here drives the
Orchestrator and infers Plan Evaluator behavior from the workflow outcome
(the Orchestrator's routing guarantees no SourcingPlan returns until the
Plan Evaluator scores it >= the threshold).

Fast layer checks:
  - PlanEvaluation schema conformance
  - 7-criterion weight scheme sums to 1.0 (the "weighted-1" claim)
  - overall_score ∈ [0, 1]
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from agents.orchestrator_agent.plan_evaluator.agent import CRITERION_WEIGHTS
from agents.schemas import PlanEvaluation, SourcingPlan
from agents.utils.eval_helpers import (
    extract_first_json_object,
    extract_user_query,
    load_evalset,
    stream_query_text,
)

EVALSET_PATH = Path(__file__).parent / "plan_evaluator.evalset.json"

# The Orchestrator's plan-evaluation score router rejects plans below this
# threshold and either revises or exhausts — so a successful end-to-end
# return implies the Plan Evaluator scored >= ACCEPT_THRESHOLD.
ACCEPT_THRESHOLD = 0.85


# ---------------------------------------------------------------------------
# Fast layer
# ---------------------------------------------------------------------------


def test_criterion_weights_sum_to_one():
    """Load-bearing: the 7 weighted criteria must sum to 1.0.

    Per the task spec, the Plan Evaluator returns 'PlanEvaluation with
    overall_score ∈ [0, 1] and 7 criterion_scores summing to weighted-1'.
    This is the weight scheme, not the individual scores; the weight
    scheme is what we can verify offline without an LLM call.
    """
    assert len(CRITERION_WEIGHTS) == 7, f"Expected 7 criteria, got {len(CRITERION_WEIGHTS)}"
    total = sum(CRITERION_WEIGHTS.values())
    assert math.isclose(total, 1.0, abs_tol=1e-4), f"CRITERION_WEIGHTS sum to {total}, not 1.0"


def test_evalset_file_exists_and_parses():
    evalset = load_evalset(EVALSET_PATH)
    eval_ids = {c["eval_id"] for c in evalset["eval_cases"]}
    assert "happy_path_good_plan_scores_above_threshold" in eval_ids
    assert "edge_weak_plan_triggers_revision" in eval_ids


def test_expected_overall_scores_match_weighted_sum():
    """For every fixture, overall_score must equal Σ wᵢ·sᵢ within tolerance.

    The weight scheme is what makes overall_score "weighted-1" rather than
    a free-floating LLM guess. A fixture that violates this either has a
    typo in the criterion scores or drifts the weight scheme silently —
    both bugs the demo can't tolerate.
    """
    evalset = load_evalset(EVALSET_PATH)
    for case in evalset["eval_cases"]:
        text = case["conversation"][0]["final_response"]["parts"][0]["text"]
        ev = PlanEvaluation.model_validate_json(text)
        expected = sum(
            c.score * CRITERION_WEIGHTS[c.criterion] for c in ev.criterion_scores
        )
        assert math.isclose(ev.overall_score, expected, abs_tol=0.02), (
            f"{case['eval_id']}: overall_score={ev.overall_score} but weighted sum is "
            f"{expected:.4f}. Fixture inconsistent with CRITERION_WEIGHTS."
        )


def test_weak_plan_fixture_actually_recommends_revision():
    """The weak-plan fixture has overall_score < threshold and
    revision_recommended=True. If either flips, the fixture stops
    exercising the revise-loop path.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "edge_weak_plan_triggers_revision"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    ev = PlanEvaluation.model_validate_json(text)
    assert ev.overall_score < ACCEPT_THRESHOLD, (
        f"Weak-plan fixture scored {ev.overall_score} but threshold is {ACCEPT_THRESHOLD}; "
        "fixture no longer triggers the revise router."
    )
    assert ev.revision_recommended is True


def test_all_expected_evaluations_satisfy_constraints():
    """Every expected PlanEvaluation must obey the score range + criterion shape."""
    evalset = load_evalset(EVALSET_PATH)
    for case in evalset["eval_cases"]:
        text = case["conversation"][0]["final_response"]["parts"][0]["text"]
        ev = PlanEvaluation.model_validate_json(text)
        assert 0.0 <= ev.overall_score <= 1.0, (
            f"{case['eval_id']}: overall_score={ev.overall_score} ∉ [0, 1]"
        )
        assert len(ev.criterion_scores) == 7, (
            f"{case['eval_id']}: expected 7 criterion_scores, got {len(ev.criterion_scores)}"
        )
        for c in ev.criterion_scores:
            assert 0.0 <= c.score <= 1.0, (
                f"{case['eval_id']}: criterion {c.criterion} score={c.score} ∉ [0, 1]"
            )
            assert c.criterion in CRITERION_WEIGHTS, (
                f"{case['eval_id']}: unknown criterion {c.criterion!r}"
            )


def test_good_plan_scores_above_threshold():
    """The happy-path expected eval must have overall_score >= the accept threshold."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c
        for c in evalset["eval_cases"]
        if c["eval_id"] == "happy_path_good_plan_scores_above_threshold"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    ev = PlanEvaluation.model_validate_json(text)
    assert ev.overall_score >= ACCEPT_THRESHOLD, (
        f"Happy path score {ev.overall_score} < accept threshold {ACCEPT_THRESHOLD}"
    )
    assert ev.revision_recommended is False


def test_weak_plan_triggers_revision():
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "edge_weak_plan_triggers_revision"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    ev = PlanEvaluation.model_validate_json(text)
    assert ev.overall_score < ACCEPT_THRESHOLD
    assert ev.revision_recommended is True


def test_plan_evaluation_schema_roundtrips():
    from agents.schemas import CriterionScore, Severity

    ev = PlanEvaluation(
        request_id="00000000-0000-0000-0000-000000000000",
        overall_score=0.91,
        criterion_scores=[
            CriterionScore(
                criterion="safety_compliance",
                score=0.9,
                severity=Severity.LOW,
                rationale="test",
            )
        ],
    )
    rebuilt = PlanEvaluation.model_validate_json(ev.model_dump_json())
    assert rebuilt.overall_score == 0.91


# ---------------------------------------------------------------------------
# Live layer
# ---------------------------------------------------------------------------


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("ORCHESTRATOR_AGENT_RESOURCE_NAME"),
    reason=(
        "ORCHESTRATOR_AGENT_RESOURCE_NAME not set "
        "(Plan Evaluator runs in-process inside the Orchestrator)"
    ),
)
def test_live_plan_evaluator_passes_good_plan_via_orchestrator():
    """The bundled Plan Evaluator is exercised via the Orchestrator's :streamQuery.

    The Orchestrator's evaluation-score router only forwards to finalize
    when overall_score >= the accept threshold. A successful SourcingPlan
    return implies the Plan Evaluator scored the plan above threshold.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c
        for c in evalset["eval_cases"]
        if c["eval_id"] == "happy_path_good_plan_scores_above_threshold"
    )
    prompt = extract_user_query(case)
    text = stream_query_text(
        "ORCHESTRATOR_AGENT_RESOURCE_NAME",
        prompt,
        user_id="eval-plan-evaluator-good",
    )
    # If we got a SourcingPlan back at all, the Plan Evaluator accepted
    # the plan (the workflow router's PROCEED branch is gated on it).
    # The Orchestrator appends routing narratives after the JSON;
    # extract just the leading SourcingPlan object.
    plan = SourcingPlan.model_validate(
        extract_first_json_object(text, must_contain=("requested_asset", "primary_option"))
    )
    assert plan.primary_option.estimated_cost_usd > 0
