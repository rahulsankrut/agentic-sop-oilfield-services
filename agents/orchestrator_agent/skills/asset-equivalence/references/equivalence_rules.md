# Functional-equivalence engineering rules

Functional equivalence between two canonical assets is asserted only when ALL
of the following hold:

1. **Operating envelope overlap**: temperature, pressure, and outer-diameter
   specifications of the substitute are within ±5% of the original, OR
   exceed it (e.g., HT/HP variants are forward-compatible).
2. **Interface compatibility**: the substitute connects to the same BHA /
   surface package without machined adapters.
3. **Spec citation**: an InTouch spec or OEM technical bulletin documents
   the interchangeability with at most one-step approval depth.

Below 0.7 confidence the agent treats the substitution as "high uncertainty"
and surfaces a finding. Below 0.5 the substitution is effectively blocked
and the agent should look for alternative options.
