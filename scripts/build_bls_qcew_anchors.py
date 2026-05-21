"""Build `data/anchors/bls_qcew_workforce.json` — real BLS QCEW NAICS 211
(Oil & Gas Extraction) state employment, rolled up to basin (TASK-16
Step 4d.3, Mode C).

For each US basin we sum the BLS state employment numbers via a curated
state-share map (a basin doesn't align cleanly to a state; Texas spans
Permian + Eagle Ford + Anadarko + GoM, etc.). For foreign basins
(west_africa, north_sea, bohai, south_china_sea, asia_pacific) BLS
QCEW is irrelevant — set to NULL in the seeder.

Source: BLS QCEW (Quarterly Census of Employment and Wages), annual
file for NAICS 211. Direct CSV, no API key:
  https://data.bls.gov/cew/data/api/{year}/a/industry/211.csv

The BLS CSV filter:
  agglvl_code = '55'  (statewide industry)
  own_code    = '5'   (private ownership)
  industry_code = '211' (NAICS 211 — Oil & Gas Extraction)

Substitution: a customer with their own HR roster sub the JSON kernel +
this anchor with whatever BLS-equivalent extract they have.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sys
import urllib.request
from pathlib import Path

ANCHOR_OUT = Path(__file__).resolve().parent.parent / "data" / "anchors" / "bls_qcew_workforce.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# Curated basin → {state FIPS: share-of-state-employment-attributable-to-basin}
# Shares are coarse industry-knowledge estimates; the goal is "the right
# order of magnitude with real BLS denominators behind it", not census-
# grade accuracy. State FIPS codes are 5-char zero-padded ("48000" etc.).
BASIN_SHARES: dict[str, dict[str, float]] = {
    # Permian Basin sits across W Texas + SE New Mexico
    "permian": {
        "48000": 0.55,   # Texas — Permian is roughly half of TX O&G employment
        "35000": 0.85,   # New Mexico — overwhelmingly Permian Delaware Basin
    },
    # Gulf of Mexico = TX + LA offshore + ports; LA is much smaller HQ-wise
    "gulf_of_mexico": {
        "48000": 0.10,   # Texas — small offshore-attributable share
        "22000": 0.65,   # Louisiana — most of state O&G is GoM-adjacent
    },
}

# Foreign basins don't have a US-public-data equivalent. The seeder
# leaves NAICS_211_STATE_EMPLOYMENT NULL for these. List included here
# so the anchor's `coverage` field is explicit.
FOREIGN_BASINS = ["west_africa", "north_sea", "bohai", "south_china_sea", "asia_pacific"]

YEAR = 2024
BLS_URL = f"https://data.bls.gov/cew/data/api/{YEAR}/a/industry/211.csv"


def _fetch_bls() -> dict[str, int]:
    """Return {area_fips: annual_avg_emplvl} for state-level private O&G ext."""
    log.info("downloading BLS QCEW NAICS 211 (annual %d) from %s", YEAR, BLS_URL)
    req = urllib.request.Request(BLS_URL, headers={"User-Agent": "agentic-sop-oilfield-services rahulsankrut@gmail.com"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    out: dict[str, int] = {}
    for r in csv.DictReader(io.StringIO(text)):
        if r["agglvl_code"] != "55" or r["own_code"] != "5":
            continue
        out[r["area_fips"]] = int(r["annual_avg_emplvl"] or 0)
    log.info("parsed %d US state rows", len(out))
    return out


def main() -> int:
    state_emp = _fetch_bls()
    anchors: dict[str, dict] = {}
    for basin, shares in BASIN_SHARES.items():
        employed = sum(
            int(state_emp.get(fips, 0) * share)
            for fips, share in shares.items()
        )
        components = {fips: state_emp.get(fips, 0) for fips in shares}
        anchors[basin] = {
            "naics_211_state_employment": employed,
            "components_by_fips": components,
            "shares_by_fips": shares,
            "data_source": f"BLS QCEW {YEAR} NAICS 211 (Oil & Gas Extraction)",
        }
        log.info("  %-15s  → %d employees  (from %s)",
                 basin, employed,
                 ", ".join(f"{fips}:{state_emp.get(fips,0)}*{share}" for fips, share in shares.items()))
    for basin in FOREIGN_BASINS:
        anchors[basin] = {
            "naics_211_state_employment": None,
            "components_by_fips": {},
            "shares_by_fips": {},
            "data_source": "Synthesized — BLS QCEW covers US states only; foreign basin workforce stays demo-synthesized",
        }
        log.info("  %-15s  → NULL (foreign basin, no BLS data)", basin)

    ANCHOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ANCHOR_OUT.open("w") as f:
        json.dump(anchors, f, indent=2)
    log.info("wrote %s", ANCHOR_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
