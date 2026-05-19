"""Synthetic data loader for skill development (TASK-03 preview substrate).

In production this data lives in Knowledge Catalog / BigQuery / GCS (wired up
in TASK-05). Here we load JSON files from `data/` into memory. Each loader is
``lru_cache``-d so repeat calls are cheap.

The data is a closed world covering the cargo-plane scenario at minimum
(Tool X → Tool X-V7 substitution in West Africa, customer Gulf Petroleum)
and a handful of additional canonical assets so the agents have realistic
choice when reasoning.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _load_json(filename: str) -> Any:
    with open(DATA_DIR / filename) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_canonical_assets() -> list[dict]:
    """The 30-entry canonical asset taxonomy."""
    return _load_json("canonical_assets.json")


@lru_cache(maxsize=1)
def load_cross_system_aliases() -> dict[str, dict]:
    """SAP/Maximo/FDP/InTouch aliases keyed by canonical_id."""
    return _load_json("cross_system_aliases.json")


@lru_cache(maxsize=1)
def load_functional_equivalences() -> list[dict]:
    """Engineering-documented equivalence relationships."""
    return _load_json("functional_equivalences.json")


@lru_cache(maxsize=1)
def load_customers() -> list[dict]:
    """Anonymized customer records with substitution restrictions."""
    return _load_json("customers.json")


@lru_cache(maxsize=1)
def load_maximo_inventory() -> list[dict]:
    """Equipment instances with location, status, certification, workforce."""
    return _load_json("maximo_inventory.json")


@lru_cache(maxsize=1)
def load_sap_workforce() -> dict[str, dict]:
    """Workforce availability indexed by basin/region."""
    return _load_json("sap_workforce.json")


@lru_cache(maxsize=1)
def load_fdp_configurations() -> dict[str, dict]:
    """FDP customer configurations keyed by customer_id, then canonical_id."""
    return _load_json("fdp_configurations.json")


@lru_cache(maxsize=1)
def load_intouch_index() -> dict[str, dict]:
    """InTouch document index keyed by spec ID."""
    return _load_json("intouch_index.json")


@lru_cache(maxsize=8)
def load_start_date_variance(basin: str) -> list[dict]:
    """Per-basin historical start-date variance records."""
    return _load_json(f"start_date_variance/{basin}.json")


def get_canonical_asset(canonical_id: str) -> dict | None:
    """Lookup a single canonical asset, or None if not found."""
    return next((a for a in load_canonical_assets() if a["canonical_id"] == canonical_id), None)


def normalize_customer_id(raw: str) -> str:
    """Accept either a slug or a display name and return the canonical slug.

    Planners (and the LLM) type "Gulf Petroleum", "Gulf Petroleum Services",
    or "gulf-petroleum" interchangeably. All map to the same record.
    """
    if not raw:
        return ""
    needle = raw.lower().strip()
    for c in load_customers():
        if needle == c["customer_id"]:
            return c["customer_id"]
        name_lc = c["name"].lower()
        if needle == name_lc or needle in name_lc or name_lc in needle:
            return c["customer_id"]
    return raw  # unknown — pass through so caller can fail explicitly


def get_customer(customer_id: str) -> dict | None:
    """Lookup a customer by id, accepting display names too."""
    return next(
        (c for c in load_customers() if c["customer_id"] == normalize_customer_id(customer_id)),
        None,
    )
