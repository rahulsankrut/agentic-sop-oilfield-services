# TASK-13 Step 5 — Agent prompt templating (DEFERRED)

This file tracks the agent-side splice points that **were intentionally
left untouched** in the TASK-13 implementation. Step 5 of the spec
("Template the agents' prompts and Memory Profiles") is queued for a
follow-up task.

The TASK-13 build delivered:

- `skins/<slug>/customer.yaml` schema + two skins (default, halliburton)
- `scripts/compile_skin.py` → `canvas/src/data/skin.generated.ts`
- Canvas-side `useSkin()` / `getPersona()` / `getScenario()` helpers
- Brand CSS variables wired through `canvas/src/app/layout.tsx`
- Skin-driven persona registry, cargo-plane scenario beats, page chrome
- `make use-skin SKIN=<slug>` swap command
- `agents/tests/unit/test_skin_schema.py` (12 tests passing)

What's **not** done — agent code still references the default-skin
strings directly. When Step 5 runs, these are the splice points:

## Orchestrator agent

- `agents/orchestrator_agent/nodes/equivalence_lookup.py` — references
  "Tool X" / "Tool X-V7" in prompts. Replace with
  `skin.taxonomy.hero_asset.canonical_label` + `equivalent_canonical_label`.
- `agents/orchestrator_agent/nodes/sourcing_logistics.py` — references
  "Luanda" / "Lagos" / "Darwin" in prompts. Replace with
  `skin.scenarios["cargo-plane"].{location_focus_label, recommended_origin_label, naive_origin_label}`.
- `agents/orchestrator_agent/nodes/parse_request.py` — example phrasing
  in the few-shot prompt references "Tool X" / "Luanda" / "Friday".
- `agents/orchestrator_agent/nodes/finalize.py` — narration-side strings.
- `agents/orchestrator_agent/nodes/resolve_asset.py` — canonical-id default.
- `agents/orchestrator_agent/services/memory_manager.py` — persona memory
  seed records mention Maria/Lagos/Tool X by name.
- `agents/orchestrator_agent/skills/*/scripts/tools.py` — skill tool
  default arguments and example outputs hardcode customer values.

## Procurement approval agent

- `agents/procurement_approval_agent/agent_card.py` — agent description.
- `agents/procurement_approval_agent/services/memory_manager.py` — same
  pattern as orchestrator's memory manager.

## Shared utilities

- `agents/utils/synthetic_data.py` — fixture data; safe to keep
  customer-labeled because it's mock-only.
- `agents/schemas.py` — only mentions "Gulf Petroleum" etc. in docstring
  examples; not a functional dependency.

## Approach for Step 5

Recommended pattern (taken straight from the TASK-13 spec):

```python
# agents/utils/skin_loader.py
from pathlib import Path
import os
import yaml
from agents.utils.skin_schema import CustomerSkin  # pydantic mirror of the JSON Schema

_skin_cache: CustomerSkin | None = None

def get_active_skin() -> CustomerSkin:
    global _skin_cache
    if _skin_cache is None:
        slug = os.environ.get("CUSTOMER_SKIN", "default")
        path = Path(__file__).resolve().parents[2] / "skins" / slug / "customer.yaml"
        _skin_cache = CustomerSkin.model_validate(yaml.safe_load(path.read_text()))
    return _skin_cache
```

Then `PromptBuilder` sections that currently use f-strings against
hardcoded literals get rewritten to reference the loaded skin, and
Memory Bank seed scripts read persona names from the YAML.

Step 5 is best paired with TASK-13 Step 10 (`docs/customer-skinning.md`)
and TASK-13 Step 11 (commit + push). All deferred for the same follow-up
task.
