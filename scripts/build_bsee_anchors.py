"""Build `data/anchors/bsee_workorders.json` — real BSEE incident
investigation records paired to our synthetic WORKORDERs (TASK-16
Step 4d.5, Mode C).

For every open WORKORDER in the seeder (one per maximo_inventory asset
with non-zero `certification_hours_remaining` or a non-trivial status),
we pick a real BSEE Incident Investigation record whose accident type
plausibly explains why a recert / repair work-order would be scheduled.
Then the seeder uses:

  - BSEE LEASE_NUMBER  → WORKORDER.BSEE_LEASE_REF       (real lease ID)
  - BSEE DATE_OCCURRED → WORKORDER.BSEE_INCIDENT_DATE   (real date)
                       → WORKORDER.REPORTDATE          (anchored to incident)

This grounds each WO in a real publicly-investigated incident. Source:
BSEE Incident Investigations raw data, ZIP file updated daily at
https://www.data.bsee.gov/Other/Files/IncInvRawData.zip — US Govt
public domain.

Substitution: a customer with their own Maximo WO data already has real
WOs; this anchor is only needed for the demo dataset.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

ANCHOR_OUT = Path(__file__).resolve().parent.parent / "data" / "anchors" / "bsee_workorders.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

BSEE_ZIP_URL = "https://www.data.bsee.gov/Other/Files/IncInvRawData.zip"


def _fetch_bsee_incidents() -> list[dict]:
    log.info("downloading BSEE Incident Investigations raw data from %s", BSEE_ZIP_URL)
    req = urllib.request.Request(
        BSEE_ZIP_URL, headers={"User-Agent": "agentic-sop-oilfield-services rahulsankrut@gmail.com"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        zipped = resp.read()
    log.info("downloaded %.1f KiB", len(zipped) / 1024)
    with zipfile.ZipFile(io.BytesIO(zipped)) as zf:
        with zf.open("IncInvRawData/mv_acc_investigations.txt") as raw:
            text = raw.read().decode("latin-1")
    rows = list(csv.DictReader(io.StringIO(text)))
    log.info("parsed %d BSEE incident records", len(rows))
    return rows


def _to_iso_date(s: str) -> str | None:
    """BSEE date format is M/D/YYYY. Return ISO YYYY-MM-DD or None."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _pick(rows: list[dict], match_substrings: list[str], year_min: int = 2018) -> dict | None:
    """Pick the most-recent BSEE incident whose accident_type contains
    any of the given substrings (case-insensitive)."""
    candidates = []
    for r in rows:
        at = (r.get("ACCIDENT_TYPE") or "").lower()
        if not any(s.lower() in at for s in match_substrings):
            continue
        iso = _to_iso_date(r.get("DATE_OCCURRED", ""))
        if not iso or int(iso[:4]) < year_min:
            continue
        candidates.append((iso, r))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    _iso, picked = candidates[0]
    return picked


def main() -> int:
    rows = _fetch_bsee_incidents()

    # Map equipment_instance_id → match terms. Each open WO in the seeder
    # corresponds to one entry. For TX-007-LGS-001 (Tool X recert in
    # Lagos), the underlying assumption is "Tool X tripped a safety
    # event triggering recert" — match Required Evacuation or Equipment
    # Damage incidents.
    anchors: dict[str, dict] = {}

    # 1) TX-007-LGS-001 — RECERT workflow after a safety event.
    pick = _pick(rows, ["required evacuation", "equipment damage", "damaged/disabled"])
    if pick:
        anchors["TX-007-LGS-001"] = {
            "lease_number": pick["LEASE_NUMBER"].strip(),
            "area_block": pick["AREA_BLOCK"].strip(),
            "incident_date": _to_iso_date(pick["DATE_OCCURRED"]),
            "accident_type": pick["ACCIDENT_TYPE"].strip()[:200],
            "panel_district": pick["PANEL_DISTRICT"].strip(),
        }
        log.info(
            "  TX-007-LGS-001 → BSEE lease %s on %s (%s)",
            pick["LEASE_NUMBER"].strip(),
            _to_iso_date(pick["DATE_OCCURRED"]),
            pick["ACCIDENT_TYPE"][:60],
        )

    # 2) Any other "in_repair" asset — REPAIR workflow after a crane/lift event.
    pick = _pick(rows, ["crane", "lifting"])
    if pick:
        # The seeder will fall back to this anchor for any non-TX asset
        # with WORKTYPE='REPAIR'. Keyed by a sentinel.
        anchors["__repair_default__"] = {
            "lease_number": pick["LEASE_NUMBER"].strip(),
            "area_block": pick["AREA_BLOCK"].strip(),
            "incident_date": _to_iso_date(pick["DATE_OCCURRED"]),
            "accident_type": pick["ACCIDENT_TYPE"].strip()[:200],
            "panel_district": pick["PANEL_DISTRICT"].strip(),
        }
        log.info(
            "  __repair_default__ → BSEE lease %s on %s (%s)",
            pick["LEASE_NUMBER"].strip(),
            _to_iso_date(pick["DATE_OCCURRED"]),
            pick["ACCIDENT_TYPE"][:60],
        )

    ANCHOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ANCHOR_OUT.open("w") as f:
        json.dump(anchors, f, indent=2, ensure_ascii=False)
    log.info("wrote %s", ANCHOR_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
