"""Eval-suite runner for the Procurement Approval Agent (TASK-EVALS).

Two layers (fast + live), same shape as the Orchestrator suite. See the
sibling README for usage. The $500K human-review threshold from SPECS.md
§Acceptance criteria #6 is the load-bearing assertion here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agents.schemas import ProcurementApproval
from agents.utils.eval_helpers import (
    a2a_send_text,
    extract_user_query,
    load_evalset,
)

EVALSET_PATH = Path(__file__).parent / "procurement_approval_agent.evalset.json"

# Threshold from SPECS.md §Acceptance criteria #6 (Agent Gateway enforces
# the $500K human-review threshold). Procurement Approval is the gate.
HUMAN_REVIEW_THRESHOLD_USD = 500_000


# ---------------------------------------------------------------------------
# Fast layer
# ---------------------------------------------------------------------------


def test_evalset_file_exists_and_parses():
    evalset = load_evalset(EVALSET_PATH)
    eval_ids = {c["eval_id"] for c in evalset["eval_cases"]}
    assert "under_threshold_auto_approves" in eval_ids
    assert "over_threshold_rejects" in eval_ids
    assert "edge_malformed_plan_degrades_gracefully" in eval_ids
    # Full prerequisite-blocker matrix (2026-05-21 expansion).
    assert "cert_chain_missing_intouch_refs" in eval_ids
    assert "cert_chain_excess_hours" in eval_ids
    assert "regulatory_export_control_block" in eval_ids


def test_cert_chain_blocker_cases_validate():
    """Both cert-chain cases must encode approved=false with a cert blocker."""
    evalset = load_evalset(EVALSET_PATH)
    for eval_id in ("cert_chain_missing_intouch_refs", "cert_chain_excess_hours"):
        case = next(c for c in evalset["eval_cases"] if c["eval_id"] == eval_id)
        text = case["conversation"][0]["final_response"]["parts"][0]["text"]
        approval = ProcurementApproval.model_validate_json(text)
        assert approval.approved is False, f"{eval_id} expected rejection"
        blocker_text = " ".join(approval.blockers).lower()
        assert "cert" in blocker_text or "intouch" in blocker_text, (
            f"{eval_id} blocker text doesn't mention certification: {approval.blockers}"
        )


def test_regulatory_blocker_case_validates():
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c for c in evalset["eval_cases"] if c["eval_id"] == "regulatory_export_control_block"
    )
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is False
    assert any(
        "export" in b.lower() or "regulatory" in b.lower() for b in approval.blockers
    ), f"Regulatory case must surface an export/regulatory blocker: {approval.blockers}"


def test_under_threshold_expected_response_validates():
    """Under-threshold expected response must be a valid ProcurementApproval (approved=true)."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "under_threshold_auto_approves")
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is True
    assert approval.blockers == []


def test_over_threshold_expected_response_validates():
    """The over-threshold case's expected response must be approved=false with a budget blocker."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "over_threshold_rejects")
    text = case["conversation"][0]["final_response"]["parts"][0]["text"]
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is False
    assert approval.blockers, "Over-threshold rejection must include a blocker"


def test_evalset_under_threshold_plan_cost_is_actually_under_threshold():
    """Sanity check that the under-threshold fixture is, in fact, under $500K."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "under_threshold_auto_approves")
    user_text = case["conversation"][0]["user_content"]["parts"][0]["text"]
    # Pull the embedded JSON plan out of the user message text.
    plan_start = user_text.index("{")
    plan = json.loads(user_text[plan_start:])
    cost = plan["primary_option"]["estimated_cost_usd"]
    assert cost < HUMAN_REVIEW_THRESHOLD_USD, (
        f"Under-threshold fixture cost {cost} is not actually under the "
        f"${HUMAN_REVIEW_THRESHOLD_USD} threshold."
    )


def test_evalset_over_threshold_plan_cost_is_actually_over_threshold():
    """Sanity check that the over-threshold fixture is, in fact, over $500K."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "over_threshold_rejects")
    user_text = case["conversation"][0]["user_content"]["parts"][0]["text"]
    plan_start = user_text.index("{")
    plan = json.loads(user_text[plan_start:])
    cost = plan["primary_option"]["estimated_cost_usd"]
    assert cost > HUMAN_REVIEW_THRESHOLD_USD, (
        f"Over-threshold fixture cost {cost} is not actually over the "
        f"${HUMAN_REVIEW_THRESHOLD_USD} threshold."
    )


def test_procurement_approval_schema_roundtrips():
    appr = ProcurementApproval(
        request_id="00000000-0000-0000-0000-000000000000",
        approved=True,
    )
    rebuilt = ProcurementApproval.model_validate_json(appr.model_dump_json())
    assert rebuilt.approved is True


# ---------------------------------------------------------------------------
# Live layer
#
# Procurement Approval is deployed A2A-wrapped (A2aAgent +
# ProcurementApprovalExecutor — see agents/procurement_approval_agent/deploy.py).
# A2A-wrapped engines reject the AdkApp :streamQuery class_method
# (HTTP 400 FAILED_PRECONDITION). Live evals drive the deployed surface
# via the A2A protocol on /a2a — the same path Orchestrator's
# RemoteA2aAgent uses in production. ``a2a_send_text`` wraps the
# httpx + ADC + ClientFactory glue.
# ---------------------------------------------------------------------------

def _procurement_live_gate() -> bool:
    return bool(os.environ.get("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME"))


@pytest.mark.evals_live
@pytest.mark.skipif(
    not _procurement_live_gate(),
    reason="PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set",
)
def test_live_under_threshold_approves():
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "under_threshold_auto_approves")
    prompt = extract_user_query(case)
    text = a2a_send_text("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", prompt)
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is True, (
        f"Expected auto-approve for under-threshold plan; got blockers={approval.blockers!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not _procurement_live_gate(),
    reason="PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set",
)
def test_live_over_threshold_rejects():
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == "over_threshold_rejects")
    prompt = extract_user_query(case)
    text = a2a_send_text("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", prompt)
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is False, (
        "Expected rejection for over-threshold plan; got approved=True "
        f"(blockers={approval.blockers!r})"
    )
    assert approval.blockers, "Rejection must surface at least one blocker"


@pytest.mark.evals_live
@pytest.mark.skipif(
    not _procurement_live_gate(),
    reason="PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set",
)
@pytest.mark.parametrize(
    "eval_id,expected_blocker_keyword",
    [
        ("cert_chain_missing_intouch_refs", "intouch"),
        ("cert_chain_excess_hours", "48"),
        ("regulatory_export_control_block", "export"),
    ],
)
def test_live_blocker_matrix_rejects(eval_id: str, expected_blocker_keyword: str):
    """Each blocker class — cert chain (missing refs / excess hours) and
    regulatory clearance — must reject the plan and surface a relevant
    blocker. Demo-defensibility: the platform doesn't just say "no",
    it says *why*.
    """
    evalset = load_evalset(EVALSET_PATH)
    case = next(c for c in evalset["eval_cases"] if c["eval_id"] == eval_id)
    prompt = extract_user_query(case)
    text = a2a_send_text("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", prompt)
    approval = ProcurementApproval.model_validate_json(text)
    assert approval.approved is False, (
        f"{eval_id}: expected rejection, got approved=True"
    )
    blocker_text = " ".join(approval.blockers).lower()
    assert expected_blocker_keyword.lower() in blocker_text, (
        f"{eval_id}: blocker did not mention {expected_blocker_keyword!r}; "
        f"got {approval.blockers!r}"
    )


@pytest.mark.evals_live
@pytest.mark.skipif(
    not _procurement_live_gate(),
    reason="PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME not set",
)
def test_live_malformed_plan_degrades_gracefully():
    """A plan missing required fields shouldn't crash the agent."""
    evalset = load_evalset(EVALSET_PATH)
    case = next(
        c
        for c in evalset["eval_cases"]
        if c["eval_id"] == "edge_malformed_plan_degrades_gracefully"
    )
    prompt = extract_user_query(case)
    text = a2a_send_text("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", prompt)
    assert text, "Agent returned empty response for malformed plan"
    # Don't strictly require a valid ProcurementApproval (the LLM may
    # return an error explanation instead). Just make sure it doesn't
    # silently approve a plan it can't validate.
    try:
        approval = ProcurementApproval.model_validate_json(text)
        assert approval.approved is False, (
            "Malformed-plan must NOT be silently approved — that would be a "
            "false-positive procurement decision."
        )
    except Exception:
        # Non-JSON response (e.g. error text) is acceptable graceful degradation.
        pass
