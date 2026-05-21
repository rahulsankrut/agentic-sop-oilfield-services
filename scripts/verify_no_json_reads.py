"""Static check — fails if any agent production code path still imports
from `agents.utils.synthetic_data`.

This is the load-bearing TASK-16 Step 13 verification: after the
migration, every skill / node / agent module must read its data via BQ
(directly or through an MCP server), not from `data/*.json`. The
`synthetic_data` module stays around as a test fixture (some legacy
integration tests still reference it), but importing it from production
code is a regression that this script catches.

Exit codes:
  0 — clean. No `agents.utils.synthetic_data` imports under
      `agents/{orchestrator_agent,procurement_approval_agent,
              forecast_review_agent,capacity_planning_agent}/`.
  1 — found offending imports; the file path + line is printed.

Usage:
    python scripts/verify_no_json_reads.py

Wired into `make verify` as part of TASK-16 Step 13 end-to-end smoke.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules that are PRODUCTION code paths — these must not read JSON.
PRODUCTION_DIRS = [
    "agents/orchestrator_agent",
    "agents/procurement_approval_agent",
    "agents/forecast_review_agent",
    "agents/capacity_planning_agent",
]

# Exclusions: tests + the synthetic_data module itself + the seeder.
EXCLUDE_GLOBS = [
    "**/tests/**",
    "**/test_*.py",
    "**/__pycache__/**",
]

# The pattern catches every shape of import:
#   from agents.utils.synthetic_data import ...
#   import agents.utils.synthetic_data
#   from .synthetic_data import ...   (relative inside utils/)
OFFENDING_PATTERN = re.compile(
    r"^\s*(from\s+agents\.utils\.synthetic_data\s+import|"
    r"import\s+agents\.utils\.synthetic_data|"
    r"from\s+\.+synthetic_data\s+import)",
    re.MULTILINE,
)


def main() -> int:
    offenses: list[tuple[Path, int, str]] = []
    for d in PRODUCTION_DIRS:
        root = REPO_ROOT / d
        if not root.is_dir():
            continue
        for py in root.rglob("*.py"):
            if any(py.match(g) for g in EXCLUDE_GLOBS):
                continue
            text = py.read_text(encoding="utf-8")
            for m in OFFENDING_PATTERN.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                line_text = text.splitlines()[line_no - 1]
                offenses.append((py, line_no, line_text))

    if offenses:
        print("✗ Found agents.utils.synthetic_data imports in production code:")
        for path, line, snippet in offenses:
            rel = path.relative_to(REPO_ROOT)
            print(f"  {rel}:{line}: {snippet.strip()}")
        print()
        print("  Production code must read via BQ / MCP servers, not JSON fixtures.")
        print("  synthetic_data.py is retained only for test fixtures.")
        return 1

    print("✓ No agents.utils.synthetic_data imports in production code paths.")
    print(f"  Scanned: {', '.join(PRODUCTION_DIRS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
