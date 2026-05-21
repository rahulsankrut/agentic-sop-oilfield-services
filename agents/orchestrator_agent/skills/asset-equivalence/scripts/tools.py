"""Tools for the asset-equivalence skill.

TASK-16 Step 8 — backend migration. Three changes versus the TASK-03
JSON-file implementation:

1. `resolve_canonical_asset` queries `oilfield_kc.cross_system_aliases` +
   `oilfield_kc.canonical_assets` in BigQuery via `agents.utils.bq_query`.
   The substring-on-label path ("Tool X" → `TX-001`) is preserved.
2. `find_functional_equivalents` queries `oilfield_kc.functional_equivalences`
   (BQ).
3. `score_equivalence_confidence` combines that BQ query with an FDP MCP
   call to `fdp_list_customer_restrictions(customer_id)`. The 0.3 penalty
   stays as policy code — only the data source moved.

`agents.utils.synthetic_data` is no longer imported.
"""

from __future__ import annotations

import json
import logging

from agents.schemas import AssetIdentifier
from agents.utils import mcp_client
from agents.utils.bq_query import BQ_PROJECT, bq_query

logger = logging.getLogger(__name__)

# Qualified BQ table names — KC dataset is fixed per SPECS.md §Data.
_T_CANONICAL_ASSETS = f"`{BQ_PROJECT}.oilfield_kc.canonical_assets`"
_T_CROSS_SYSTEM_ALIASES = f"`{BQ_PROJECT}.oilfield_kc.cross_system_aliases`"
_T_FUNCTIONAL_EQUIVALENCES = f"`{BQ_PROJECT}.oilfield_kc.functional_equivalences`"


def _alias_row_to_dict(row: dict) -> dict:
    """Normalize a `cross_system_aliases` row into the legacy dict shape.

    The legacy in-memory map keyed each canonical_id with the field names
    ``sap_material_number / maximo_equipment_id / fdp_config_id /
    intouch_spec_refs``. The BQ column names are uppercase MATNR/ITEMNUM/
    CONFIG_ID. We map to the legacy keys so callers (and the
    ``AssetIdentifier`` schema) stay unchanged.
    """
    return {
        "canonical_id": row.get("CANONICAL_ID"),
        "sap_material_number": row.get("SAP_MATNR"),
        "maximo_equipment_id": row.get("MAXIMO_ITEMNUM"),
        "fdp_config_id": row.get("FDP_CONFIG_ID"),
        "intouch_spec_refs": list(row.get("INTOUCH_SPEC_REFS") or []),
    }


def _fetch_canonical_with_alias(canonical_id: str) -> dict | None:
    """Join canonical_assets + cross_system_aliases for one canonical_id."""
    rows = bq_query(
        f"""
        SELECT ca.CANONICAL_ID, ca.CANONICAL_LABEL,
               a.SAP_MATNR, a.MAXIMO_ITEMNUM, a.FDP_CONFIG_ID, a.INTOUCH_SPEC_REFS
        FROM {_T_CANONICAL_ASSETS} ca
        LEFT JOIN {_T_CROSS_SYSTEM_ALIASES} a USING (CANONICAL_ID)
        WHERE ca.CANONICAL_ID = @cid
        LIMIT 1
        """,
        {"cid": canonical_id},
    )
    return rows[0] if rows else None


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
            ``canonical``). Narrows the alias-column lookup; when None,
            we try every column then fall back to substring-on-label.

    Returns:
        Dict with the canonical id, label and every known cross-system alias.

    Raises:
        ValueError: if no canonical match is found.
    """
    # DEMO NARRATION: "This is the resolution moment — the agent doesn't reason
    # about MAT-67890 or EQ-12345; it reasons about TX-001 the canonical entity.
    # Issue 4 — taxonomic chaos — is resolved here."

    canonical_id: str | None = None

    # 1. source_system-hinted exact match on the corresponding alias column.
    src = (source_system or "").lower()
    column_for_src = {
        "sap": "SAP_MATNR",
        "maximo": "MAXIMO_ITEMNUM",
        "fdp": "FDP_CONFIG_ID",
    }.get(src)
    if column_for_src is not None:
        rows = bq_query(
            f"""
            SELECT CANONICAL_ID
            FROM {_T_CROSS_SYSTEM_ALIASES}
            WHERE {column_for_src} = @needle
            LIMIT 1
            """,
            {"needle": local_identifier},
        )
        if rows:
            canonical_id = rows[0]["CANONICAL_ID"]

    # 2. No hint (or hint missed): try the canonical_id direct-match path,
    #    then a wildcard over all three alias columns.
    if canonical_id is None:
        rows = bq_query(
            f"""
            SELECT CANONICAL_ID
            FROM {_T_CANONICAL_ASSETS}
            WHERE CANONICAL_ID = @needle
            LIMIT 1
            """,
            {"needle": local_identifier},
        )
        if rows:
            canonical_id = rows[0]["CANONICAL_ID"]

    if canonical_id is None:
        rows = bq_query(
            f"""
            SELECT CANONICAL_ID
            FROM {_T_CROSS_SYSTEM_ALIASES}
            WHERE SAP_MATNR = @needle
               OR MAXIMO_ITEMNUM = @needle
               OR FDP_CONFIG_ID = @needle
            LIMIT 1
            """,
            {"needle": local_identifier},
        )
        if rows:
            canonical_id = rows[0]["CANONICAL_ID"]

    # 3. Substring-on-label fallback: planners type "Tool X" / "Tool X variant",
    #    not "TX-001". Case-insensitive bidirectional substring match.
    if canonical_id is None:
        needle = local_identifier.lower().strip()
        rows = bq_query(
            f"""
            SELECT CANONICAL_ID, CANONICAL_LABEL
            FROM {_T_CANONICAL_ASSETS}
            WHERE LOWER(CANONICAL_LABEL) = @needle
               OR LOWER(CANONICAL_LABEL) LIKE CONCAT('%', @needle, '%')
               OR @needle LIKE CONCAT('%', LOWER(CANONICAL_LABEL), '%')
            ORDER BY LENGTH(CANONICAL_LABEL)
            LIMIT 1
            """,
            {"needle": needle},
        )
        if rows:
            canonical_id = rows[0]["CANONICAL_ID"]

    if canonical_id is None:
        raise ValueError(f"No canonical asset found for identifier: {local_identifier}")

    # Materialize the full record + aliases.
    full = _fetch_canonical_with_alias(canonical_id)
    if full is None:
        # Defensive: alias row pointed at a canonical_id that's not in
        # canonical_assets. Shouldn't happen, but raise rather than 500.
        raise ValueError(f"Canonical id {canonical_id} resolved but no asset row found")

    return AssetIdentifier(
        canonical_id=full["CANONICAL_ID"],
        canonical_label=full["CANONICAL_LABEL"] or full["CANONICAL_ID"],
        sap_material_number=full.get("SAP_MATNR"),
        maximo_equipment_id=full.get("MAXIMO_ITEMNUM"),
        fdp_config_id=full.get("FDP_CONFIG_ID"),
        intouch_spec_refs=list(full.get("INTOUCH_SPEC_REFS") or []),
    ).model_dump()


def find_functional_equivalents(canonical_id: str) -> list[dict]:
    """Find functionally equivalent variants of a canonical asset.

    Returns a list ordered by descending confidence. Each entry is::

        {"canonical_id": "<id>", "confidence": <float>,
         "rationale_source": "<doc ref>",
         "customer_compatibility_overrides": [...]}

    ``customer_compatibility_overrides`` is parsed from the JSON column in
    ``oilfield_kc.functional_equivalences``.
    """
    # DEMO NARRATION: "This is where the cargo-plane scenario pivots. The agent
    # reaches into Knowledge Catalog's functional_equivalence relationships and
    # finds Tool X-V7 is interchangeable with Tool X per InTouch spec §3.2."
    rows = bq_query(
        f"""
        SELECT CANONICAL_ID_A, CANONICAL_ID_B, CONFIDENCE, RATIONALE_SOURCE,
               CUSTOMER_OVERRIDES
        FROM {_T_FUNCTIONAL_EQUIVALENCES}
        WHERE CANONICAL_ID_A = @cid OR CANONICAL_ID_B = @cid
        """,
        {"cid": canonical_id},
    )
    results: list[dict] = []
    for row in rows:
        other = (
            row["CANONICAL_ID_B"]
            if row["CANONICAL_ID_A"] == canonical_id
            else row["CANONICAL_ID_A"]
        )
        overrides_raw = row.get("CUSTOMER_OVERRIDES")
        if isinstance(overrides_raw, str):
            try:
                overrides = json.loads(overrides_raw)
            except (TypeError, ValueError):
                overrides = []
        else:
            overrides = overrides_raw or []
        results.append(
            {
                "canonical_id": other,
                "confidence": float(row.get("CONFIDENCE") or 0.0),
                "rationale_source": row.get("RATIONALE_SOURCE"),
                "customer_compatibility_overrides": overrides,
            }
        )
    return sorted(results, key=lambda r: r["confidence"], reverse=True)


def _normalize_customer_id(raw: str) -> str:
    """Accept either a slug ("gulf-petroleum") or a display name ("Gulf
    Petroleum") and return the canonical slug.

    Strategy:
      1. Lowercase + strip.
      2. If the input contains a space, try SAP customer lookup to find a
         real NAME1 match; if found, derive a slug from the matched NAME1.
      3. Otherwise treat as a slug already (the LLM-side common case).
      4. Fallback: lowercase + spaces-to-hyphens.

    This is a backward-compat shim — the LLM passes slugs and display
    names interchangeably; both paths must resolve to the same downstream
    FDP customer_id key.
    """
    if not raw:
        return ""
    needle = raw.strip()
    lower = needle.lower()

    # Slug-style input: lowercase, hyphens, no spaces — pass through.
    if " " not in needle and lower == needle:
        return lower

    # Display-name input: probe SAP. If it matches, derive a slug from NAME1.
    if " " in needle:
        try:
            customers = mcp_client.sap_resolve_customer_by_name(needle) or []
            if customers:
                name1 = (customers[0].get("name1") or "").strip()
                if name1:
                    return name1.lower().replace(" ", "-")
        except Exception as exc:  # noqa: BLE001 — degrade to local normalization
            logger.debug("sap_resolve_customer_by_name failed (%s); falling back", exc)

    # Final fallback: lowercase + spaces-to-hyphens.
    return lower.replace(" ", "-")


def _canonical_id_to_matnr(canonical_id: str) -> str | None:
    """Map a canonical_id to its SAP_MATNR via the KC alias table."""
    rows = bq_query(
        f"""
        SELECT SAP_MATNR
        FROM {_T_CROSS_SYSTEM_ALIASES}
        WHERE CANONICAL_ID = @cid
        LIMIT 1
        """,
        {"cid": canonical_id},
    )
    return rows[0]["SAP_MATNR"] if rows and rows[0].get("SAP_MATNR") else None


def score_equivalence_confidence(
    canonical_id_source: str,
    canonical_id_substitute: str,
    customer_id: str,
) -> float:
    """Score equivalence confidence conditioned on a specific customer's config.

    Returns:
        ``0.0`` if no known equivalence; the base confidence if no
        customer restrictions; a customer override value (if present in
        the equivalence entry's ``customer_compatibility_overrides``); or
        ``base_confidence * 0.3`` if the customer's FDP restriction list
        contains the (matnr_original, matnr_substitute) pair.
    """
    customer_id = _normalize_customer_id(customer_id)

    # 1. Base confidence + any customer override from the KC equivalence row.
    equivalents = find_functional_equivalents(canonical_id_source)
    matching = next((e for e in equivalents if e["canonical_id"] == canonical_id_substitute), None)
    if matching is None:
        return 0.0

    base_confidence = float(matching.get("confidence") or 0.0)
    if base_confidence == 0.0:
        return 0.0

    # Customer-specific override takes precedence over the restriction multiplier.
    for override in matching.get("customer_compatibility_overrides") or []:
        if override.get("customer_id") == customer_id:
            return float(override.get("override_confidence", 0.0))

    # 2. FDP restriction check — keyed by SAP MATNR pair. If MATNR mapping
    # is missing or the FDP call fails, fall through to base_confidence.
    matnr_orig = _canonical_id_to_matnr(canonical_id_source)
    matnr_sub = _canonical_id_to_matnr(canonical_id_substitute)
    restrictions: list[dict] = []
    if matnr_orig is not None and matnr_sub is not None:
        try:
            restrictions = mcp_client.fdp_list_customer_restrictions(customer_id) or []
        except Exception as exc:  # noqa: BLE001 — degrade to base confidence
            logger.debug("fdp_list_customer_restrictions failed (%s); using base", exc)
            restrictions = []

    is_restricted = any(
        r.get("matnr_original") == matnr_orig and r.get("matnr_substitute_rejected") == matnr_sub
        for r in restrictions
    )
    return base_confidence * 0.3 if is_restricted else base_confidence
