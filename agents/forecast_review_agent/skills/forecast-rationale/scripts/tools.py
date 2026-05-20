"""Tools for the forecast-rationale skill."""

from __future__ import annotations

# Keyword → tag mapping (TASK-03 heuristic; TASK-05 swaps in BigQuery measures).
TAG_KEYWORDS = {
    "rig_count_decline": ["rig count", "rig drop", "fewer rigs", "rig demobilization"],
    "operator_delay": ["operator delay", "delayed program", "deferred", "operator deferred"],
    "weather_disruption": ["weather", "hurricane", "storm", "winter shutdown", "freeze-off"],
    "regulatory_change": ["regulatory", "permit", "compliance", "regulation"],
    "demand_shift": ["demand", "spot price", "commodity price", "macro"],
    "customer_program_pause": ["program pause", "customer pause", "wells deferred"],
    "geopolitical": ["sanctions", "geopolitical", "tariff", "export control"],
    "pricing_shift": ["pricing", "service price", "rate cut"],
}


def extract_rationale_tags(freeform_text: str) -> list[str]:
    """Match freeform text against the rationale tag taxonomy.

    Case-insensitive keyword scan. Returns the set of matched tags
    (preserving the taxonomy's canonical ordering for determinism).
    """
    text = (freeform_text or "").lower()
    tags = [tag for tag, keywords in TAG_KEYWORDS.items() if any(k in text for k in keywords)]
    return tags


def compute_override_significance(
    original_value: float,
    override_value: float,
    historical_volatility_pct: float = 0.05,
) -> float:
    """Score how significant this override is, 0.0 to 1.0.

    Args:
        original_value: ML model's forecast.
        override_value: the leader's override.
        historical_volatility_pct: normal quarter-to-quarter volatility for
            this metric (default 5%). Overrides much larger than this are
            higher significance.

    Returns:
        Significance score from 0.0 (trivial) to 1.0 (highly significant).
    """
    if original_value == 0:
        return 1.0 if override_value != 0 else 0.0
    pct_change = abs((override_value - original_value) / original_value)
    # Normalize: an override 4× the typical volatility is full significance
    ratio = pct_change / (4 * historical_volatility_pct)
    return float(min(1.0, max(0.0, ratio)))
