---
name: asset-equivalence
description: >
  Expert reasoning over the canonical asset taxonomy to identify functionally
  equivalent equipment variants. Queries the canonical entity model and
  traverses functional_equivalence relationships, returning ranked candidates
  with confidence scores and rationale citations.
metadata:
  adk_additional_tools:
    - resolve_canonical_asset
    - find_functional_equivalents
    - score_equivalence_confidence
---

# Asset Equivalence

When a planner needs an asset that isn't directly available, this skill helps
you find functionally equivalent alternatives that may be located closer or
more readily deployable.

## Workflow

1. **Resolve the requested asset** to its canonical entity using
   `resolve_canonical_asset`. The planner may give a local name from any
   source system (SAP material number, Maximo equipment ID, customer-specific
   label, or the canonical id itself). This tool returns the canonical entity
   with all aliases.

2. **Find functional equivalents** with `find_functional_equivalents`. Returns
   a list of canonical entities that are functionally interchangeable, each
   with a confidence score and the rationale source (typically an InTouch
   spec reference).

3. **Score for the specific customer config** with
   `score_equivalence_confidence`. Functional equivalence in general doesn't
   guarantee customer-specific compatibility — some customers have
   configuration overrides that restrict substitutions. This tool returns a
   customer-conditioned confidence score.

## Decision-making guidance

- Always start with `resolve_canonical_asset` — never reason about local
  identifiers directly. The agent must reason against canonical entities.
- If `find_functional_equivalents` returns no results, the asset has no known
  substitutes and the planner must use the original.
- Confidence below 0.7 should surface a "high uncertainty" finding to the
  planner; below 0.5 means the substitution is effectively blocked.

## References

- `references/equivalence_rules.md`: engineering rules for substitution.
- `references/customer_overrides.md`: known customer-specific restrictions.
