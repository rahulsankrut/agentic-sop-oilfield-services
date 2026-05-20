"""Tools for the asset-equivalence skill."""

from __future__ import annotations

from agents.schemas import AssetIdentifier
from agents.utils.synthetic_data import (
    load_canonical_assets,
    load_cross_system_aliases,
    load_customers,
    load_functional_equivalences,
    normalize_customer_id,
)


def resolve_canonical_asset(
    local_identifier: str,
    source_system: str | None = None,
) -> dict:
    """Resolve a system-local identifier to its canonical asset.

    Args:
        local_identifier: identifier as it appears in any source system
            (e.g. ``MAT-67890`` from SAP, ``EQ-12345`` from Maximo, or
            ``TX-001`` for the canonical id directly).
        source_system: optional hint (``sap``, ``maximo``, ``fdp``,
            ``canonical``). Currently informational only — the lookup
            searches all alias maps regardless.

    Returns:
        Dict with the canonical id, label and every known cross-system alias.

    Raises:
        ValueError: if no canonical match is found.
    """
    _ = source_system  # reserved for future use; full-text search is fine for now
    # DEMO NARRATION: "This is the resolution moment — the agent doesn't reason
    # about MAT-67890 or EQ-12345; it reasons about TX-001 the canonical entity.
    # Issue 4 — taxonomic chaos — is resolved here."
    aliases = load_cross_system_aliases()
    assets_by_id = {a["canonical_id"]: a for a in load_canonical_assets()}

    # Direct canonical match
    if local_identifier in assets_by_id:
        canonical_id = local_identifier
    else:
        canonical_id = None
        # Search alias maps (exact)
        for cid, alias in aliases.items():
            if local_identifier in (
                alias.get("sap_material_number"),
                alias.get("maximo_equipment_id"),
                alias.get("fdp_config_id"),
            ):
                canonical_id = cid
                break
        # Search by canonical_label, case-insensitive substring. Planners type
        # "Tool X" or "Tool X variant", not "TX-001".
        if canonical_id is None:
            needle = local_identifier.lower().strip()
            for asset in assets_by_id.values():
                label = asset["canonical_label"].lower()
                if label == needle or label in needle or needle in label:
                    canonical_id = asset["canonical_id"]
                    break
        if canonical_id is None:
            raise ValueError(f"No canonical asset found for identifier: {local_identifier}")

    asset = assets_by_id[canonical_id]
    alias = aliases.get(canonical_id, {})
    return AssetIdentifier(
        canonical_id=asset["canonical_id"],
        canonical_label=asset["canonical_label"],
        sap_material_number=alias.get("sap_material_number"),
        maximo_equipment_id=alias.get("maximo_equipment_id"),
        fdp_config_id=alias.get("fdp_config_id"),
        intouch_spec_refs=alias.get("intouch_spec_refs", []),
    ).model_dump()


def find_functional_equivalents(canonical_id: str) -> list[dict]:
    """Find functionally equivalent variants of a canonical asset.

    Returns a list ordered by descending confidence. Each entry is::

        {"canonical_id": "<id>", "confidence": <float>, "rationale_source": "<doc ref>"}
    """
    # DEMO NARRATION: "This is where the cargo-plane scenario pivots. The agent
    # reaches into Knowledge Catalog's functional_equivalence relationships and
    # finds Tool X-V7 is interchangeable with Tool X per InTouch spec §3.2."
    equivalences = load_functional_equivalences()
    results: list[dict] = []
    for eq in equivalences:
        if eq["canonical_id_a"] == canonical_id:
            results.append(
                {
                    "canonical_id": eq["canonical_id_b"],
                    "confidence": eq["confidence"],
                    "rationale_source": eq["rationale_source"],
                }
            )
        elif eq["canonical_id_b"] == canonical_id:
            results.append(
                {
                    "canonical_id": eq["canonical_id_a"],
                    "confidence": eq["confidence"],
                    "rationale_source": eq["rationale_source"],
                }
            )
    return sorted(results, key=lambda r: r["confidence"], reverse=True)


def score_equivalence_confidence(
    canonical_id_source: str,
    canonical_id_substitute: str,
    customer_id: str,
) -> float:
    """Score equivalence confidence conditioned on a specific customer's config.

    Returns 0.0 if no known equivalence; the base confidence if no customer
    restrictions; a customer override value (if present in the equivalence
    entry); or ``base_confidence * 0.3`` if the customer's
    ``substitution_restrictions`` list contains the substitute.
    """
    customer_id = normalize_customer_id(customer_id)
    equivalences = load_functional_equivalences()
    customers_by_id = {c["customer_id"]: c for c in load_customers()}

    base_confidence = 0.0
    for eq in equivalences:
        pair = {eq["canonical_id_a"], eq["canonical_id_b"]}
        if {canonical_id_source, canonical_id_substitute} == pair:
            base_confidence = eq["confidence"]
            for override in eq.get("customer_compatibility_overrides", []):
                if override.get("customer_id") == customer_id:
                    return float(override.get("override_confidence", 0.0))
            break

    if base_confidence == 0.0:
        return 0.0

    customer = customers_by_id.get(customer_id, {})
    restricted = customer.get("substitution_restrictions", [])
    if canonical_id_substitute in restricted:
        return base_confidence * 0.3

    return base_confidence
