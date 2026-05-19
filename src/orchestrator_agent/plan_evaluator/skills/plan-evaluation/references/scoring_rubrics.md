# Scoring rubrics — 7 criteria

Each criterion is scored 0.0 to 1.0. Weights live in the agent (`agent.py`).

## safety_compliance (0.20)
- 1.0: HSE clearance + certifications current + workforce on-site
- 0.7: clearance present but one certification expires within 24h
- 0.4: missing one clearance category
- 0.0: blocked by safety findings

## customer_compatibility (0.20)
- 1.0: FDP config explicitly approves the canonical asset + substitution (if used)
- 0.7: approved canonical but substitution not yet validated
- 0.4: customer config silent — would need exception approval
- 0.0: customer config explicitly blocks substitution

## logistics_feasibility (0.15)
- Use the deterministic value from `evaluate_plan_deterministic`

## cost_optimality (0.15)
- Use the deterministic value from `evaluate_plan_deterministic`

## equivalence_confidence (0.10)
- 1.0: source asset is exactly what was requested (no substitution)
- 0.9–0.7: substitution with confidence ≥ 0.9
- 0.6–0.4: substitution with confidence 0.7–0.9
- ≤ 0.3: confidence < 0.7 — high uncertainty

## regulatory_compliance (0.10)
- 1.0: no cross-border, no export controls applicable
- 0.8: cross-border but routine route with documented clearance path
- 0.5: cross-border on a non-routine route (extra review needed)
- 0.0: export-controlled to a restricted destination

## schedule_feasibility (0.10)
- Use the deterministic value from `evaluate_plan_deterministic`
