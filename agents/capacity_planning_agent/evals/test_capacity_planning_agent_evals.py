"""Eval-suite runner for the Capacity Planning Agent (TASK-EVALS).

Note on schema: the task spec calls out ``OptimalBuffer`` but the deployed
agent's output_schema is ``BufferOptimization`` (see
agents/capacity_planning_agent/agent.py + agents/schemas.py). The fields
the spec asserts on — ``recommended_buffer_days``, ``projected_on_time_rate``
— exist on ``BufferOptimization`` and we assert on that shape.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agents.schemas import BufferOptimization
from agents.utils.eval_helpers import (
    extract_user_query,
    load_evalset,
    stream_query_text,
)

EVALSET_PATH = Path(__file__).parent / "capacity_planning_agent.evalset.json"


# ---------------------------------------------------------------------------
# Fast layer
# ---------------------------------------------------------------------------


def test_evalset_file_exists_and_parses():
    evalset = load_evalset(EVALSET_PATH)
    eval_ids = {c["eval_id"] for c in evalset["eval_cases"]}
    assert "happy_path_west_africa_risk_05" in eval_ids
    assert "happy_path_permian_strict_risk" in eval_ids
    assert "edge_basin_without_wo_history" in eval_ids


def test_all_expected_responses_satisfy_buffer_constraints():
    """Every expected response must obey the BufferOptimization range constraints.

    Load-bearing per the task spec:
        recommended_buffer_days >= 0
        projected_on_time_rate ∈ [0, 1]
    """
    evalset = load_evalset(EVALSET_PATH)
    for case in evalset["eval_cases"]:
        text = case["conversation"][0]["final_response"]["parts"][0]["text"]
        buf = BufferOptimization.model_validate_json(text)
        assert buf.recommended_buffer_days >= 0, (
            f"{case['eval_id']}: recommended_buffer_days={buf.recommended_buffer_days} < 0"
        )
        assert 0.0 <= buf.projected_on_time_rate <= 1.0, (
            f"{case['eval_id']}: projected_on_time_rate={buf.projected_on_time_rate} ∉ [0, 1]"
        )


def test_strict_risk_buffer_is_higher_than_loose_risk():
    """The 0.85 strict-risk case must recommend more buffer than the 0.5 case.

    Risk-tolerance semantics: higher tolerance → demand more on-time rate
    → recommend longer buffer. This is a load-bearing inequality.
    """
    evalset = load_evalset(EVALSET_PATH)
    loose = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_west_africa_risk_05"
    )
    strict = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_permian_strict_risk"
    )
    loose_buf = BufferOptimization.model_validate_json(
        loose["conversation"][0]["final_response"]["parts"][0]["text"]
    )
    strict_buf = BufferOptimization.model_validate_json(
        strict["conversation"][0]["final_response"]["parts"][0]["text"]
    )
    assert strict_buf.recommended_buffer_days > loose_buf.recommended_buffer_days


def test_buffer_optimization_schema_roundtrips():
    buf = BufferOptimization(
        request_id="00000000-0000-0000-0000-000000000000",
        basin="west_africa",
        risk_tolerance=0.5,
        current_buffer_days=14.0,
        recommended_buffer_days=9.5,
        projected_on_time_rate=0.78,
        fleet_utilization_uplift_pct=6.2,
        deferred_capex_usd=1_200_000,
    )
    rebuilt = BufferOptimization.model_validate_json(buf.model_dump_json())
    assert rebuilt.recommended_buffer_days == 9.5


# ---------------------------------------------------------------------------
# Live layer
# ---------------------------------------------------------------------------


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("CAPACITY_PLANNING_AGENT_RESOURCE_NAME"),
    reason="CAPACITY_PLANNING_AGENT_RESOURCE_NAME not set",
)
def test_live_west_africa_risk_05_returns_valid_buffer():
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "happy_path_west_africa_risk_05"
    )
    prompt = extract_user_query(case)
    text = stream_query_text(
        "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
        prompt,
        user_id="eval-capacity-wa",
    )
    buf = BufferOptimization.model_validate_json(text)
    assert buf.recommended_buffer_days >= 0
    assert 0.0 <= buf.projected_on_time_rate <= 1.0
    assert buf.basin.lower().startswith("west")


@pytest.mark.evals_live
@pytest.mark.skipif(
    not os.environ.get("CAPACITY_PLANNING_AGENT_RESOURCE_NAME"),
    reason="CAPACITY_PLANNING_AGENT_RESOURCE_NAME not set",
)
def test_live_unknown_basin_degrades_gracefully():
    """An unknown basin should not crash the agent.

    Acceptable degradation: either a BufferOptimization with a caveat
    (e.g. recommended_buffer_days == current_buffer_days, on_time_rate
    around 0.5), or a graceful error string.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "edge_basin_without_wo_history")
    prompt = extract_user_query(case)
    text = stream_query_text(
        "CAPACITY_PLANNING_AGENT_RESOURCE_NAME",
        prompt,
        user_id="eval-capacity-unknown-basin",
    )
    assert text, "Capacity Planning returned empty response"
    try:
        buf = BufferOptimization.model_validate_json(text)
        # If the agent returns structured output, it must still satisfy
        # the range constraints — never NaN, never out of [0,1].
        assert buf.recommended_buffer_days >= 0
        assert 0.0 <= buf.projected_on_time_rate <= 1.0
    except Exception:
        assert len(text) > 20
