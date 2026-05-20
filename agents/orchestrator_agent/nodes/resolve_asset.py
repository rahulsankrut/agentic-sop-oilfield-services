"""Resolve the requested asset string to a canonical Knowledge Catalog id.

Second node — deterministic, calls the asset-equivalence skill directly.
"""

from __future__ import annotations

from google.adk import Event

from agents.schemas import CapacityGapRequest
from agents.utils.skill_imports import resolve_canonical_asset


# DEMO NARRATION: "Second node: resolving the asset to a canonical id. The
# Knowledge Catalog answers in canonical entities — TX-001, not MAT-67890 or
# EQ-12345. Issue 4 — taxonomic chaos — is resolved here, before any
# enterprise-system query goes out. Still deterministic, still no LLM."
def resolve_canonical_asset_node(node_input: dict) -> Event:
    """Resolve ``requested_asset`` to its canonical id + cross-system aliases.

    Reads the ``CapacityGapRequest`` from ``node_input`` (the previous node's
    ``Event.output``), fills in ``canonical_asset_id`` + ``target_region``,
    and forwards the updated request.

    For the hero scenario "Tool X variant" → TX-001 (West Africa basin).
    """
    request = CapacityGapRequest(**node_input)

    # Resolve via the skill tool (the same one the LlmAgent used to call).
    asset = resolve_canonical_asset(local_identifier=request.requested_asset)

    # Map target_location.label to a Maximo region tag. The heuristic is small
    # by design — same mapping the v1 prompt encoded.
    region: str | None = None
    label = (request.target_location.label or "").lower()
    if any(k in label for k in ("luanda", "angola", "gabon", "nigeria")):
        region = "west_africa"
    elif any(k in label for k in ("permian", "houston", "midland", "texas")):
        region = "north_america"
    elif any(k in label for k in ("aberdeen", "north sea", "norway", "uk")):
        region = "europe"
    elif any(k in label for k in ("bohai", "china", "shanghai")):
        region = "asia_pacific"

    updated = request.model_copy(
        update={
            "canonical_asset_id": asset["canonical_id"],
            "target_region": region,
        }
    )

    return Event(
        message=(
            f"Resolved {request.requested_asset!r} → {asset['canonical_id']} (region={region})"
        ),
        output=updated.model_dump(),
    )
