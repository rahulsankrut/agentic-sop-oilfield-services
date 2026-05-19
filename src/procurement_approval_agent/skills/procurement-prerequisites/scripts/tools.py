"""Tools for the procurement-prerequisites skill."""

from __future__ import annotations

import json

# Tier → threshold mapping (USD)
TIER_THRESHOLDS = {
    "junior": 200_000,
    "standard": 500_000,
    "senior": 1_500_000,
    "director": 5_000_000,
    "strict": 200_000,  # alias for tighter customers
}


def _parse(plan_json):
    return json.loads(plan_json) if isinstance(plan_json, str) else plan_json


def check_budget_threshold(plan_json: str, planner_authorization_tier: str = "standard") -> dict:
    """Verify the plan's primary-option cost is within the planner's tier.

    Returns ``{passed: bool, blocker: str | None, threshold_usd: int}``.
    """
    plan = _parse(plan_json)
    cost = plan.get("primary_option", {}).get("estimated_cost_usd", 0)
    threshold = TIER_THRESHOLDS.get(planner_authorization_tier, TIER_THRESHOLDS["standard"])
    if cost > threshold:
        return {
            "passed": False,
            "threshold_usd": threshold,
            "blocker": (
                f"Cost ${cost:,} exceeds {planner_authorization_tier} authorization tier "
                f"threshold ${threshold:,} — escalate to next tier."
            ),
        }
    return {"passed": True, "threshold_usd": threshold, "blocker": None}


def check_certification_chain(plan_json: str) -> dict:
    """Verify InTouch spec citations are present and certification hours look sane.

    For TASK-03 this is a structural check (presence of intouch_spec_refs in
    primary_option.asset and certification_hours <= 48). TASK-04 replaces with
    a live InTouch query.
    """
    plan = _parse(plan_json)
    asset = plan.get("primary_option", {}).get("asset", {})
    refs = asset.get("intouch_spec_refs", [])
    cert_hours = plan.get("primary_option", {}).get("certification_hours", 0) or 0

    if not refs:
        return {"passed": False, "blocker": "Primary option lacks InTouch spec citations."}
    if cert_hours > 48:
        return {
            "passed": False,
            "blocker": f"Certification requires {cert_hours}h — exceeds 48h policy cap.",
        }
    return {"passed": True, "blocker": None}


def check_regulatory_clearance(plan_json: str) -> dict:
    """Cross-border / export-control check.

    For TASK-03 this is a heuristic on the source/destination coordinates +
    a deny-list of country pairs. TASK-04 replaces with a real regulatory
    matrix lookup.
    """
    plan = _parse(plan_json)
    src = plan.get("primary_option", {}).get("source_location", {})
    dst = plan.get("primary_option", {}).get("destination", {})

    # Crude cross-border: very different longitudes / latitudes ⇒ likely cross-border.
    # Customs check is the real signal; here we only guard against the deny-list.
    src_label = (src.get("label") or "").lower()
    dst_label = (dst.get("label") or "").lower()
    deny = {("iran", "us"), ("us", "iran"), ("russia", "us"), ("us", "russia")}
    for a, b in deny:
        if a in src_label and b in dst_label:
            return {"passed": False, "blocker": f"Export control: {src_label} → {dst_label}"}

    return {"passed": True, "blocker": None}
