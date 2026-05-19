---
name: forecast-rationale
description: >
  Extracts structured rationale tags from a basin leader's freeform
  explanation of a forecast override, computes override significance, and
  prepares the record for BigQuery write-back (so the next ML retrain
  ingests human judgement).
metadata:
  adk_additional_tools:
    - extract_rationale_tags
    - compute_override_significance
---

# Forecast Rationale

## Workflow

1. **`extract_rationale_tags(freeform_text)`** — match the freeform text
   against the structured tag taxonomy in `references/rationale_tags.md`.
2. **`compute_override_significance(original, override)`** — single float
   that captures how meaningful this override is (large magnitude + tight
   confidence interval = high significance).

The agent assembles a `ForecastRationale` schema instance from the tags +
freeform text + significance, returns it, and (in TASK-05) writes to
BigQuery for inclusion in the next retrain.
