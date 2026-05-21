"""Build `data/anchors/sec_edgar_customers.json` — real SEC EDGAR
filings matched to each customer for the Mode C "real fields, kept IDs"
enrichment (TASK-16 Step 4d.2).

For every customer_id in `data/customers.json`, this script picks a real
public OFS-services BUYER (an operator that purchases oilfield services)
whose business footprint matches the customer's regions in our kernel.
SEC submission metadata then provides real values for:

  - `sap_extract.KNA1.LAND1`     ← addresses[0].country (ISO code)
  - `sap_extract.KNA1.ORT01`     ← addresses[0].city
  - `sap_extract.KNA1.STRAS`     ← addresses[0].street1 (truncated)
  - (cache) CIK, ticker, SIC, fiscal year end, official name — useful narration

Output: JSON keyed by customer_id. The seeder reads this when building
KNA1/KNVV rows. Mode C preserves `customer_id` slug + `name1` from the
JSON kernel (scenario references stay intact); only the auxiliary fields
become real.

SEC EDGAR JSON API: https://data.sec.gov/submissions/CIK{cik}.json
- Free, no auth.
- Requires a descriptive User-Agent per SEC fair-use policy.
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path

ANCHOR_OUT = (
    Path(__file__).resolve().parent.parent / "data" / "anchors" / "sec_edgar_customers.json"
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# Curated customer_id → (CIK, ISO-2 country, justification). The CIK is
# the SEC EDGAR registrant ID for a real public OFS-operator whose
# regional footprint matches the customer's regions field in
# data/customers.json. ISO country is overlaid because SEC's
# state_or_country field uses nonstandard codes (F4/Q8/C3 etc.).
CUSTOMER_TO_CIK: dict[str, tuple[str, str, str]] = {
    # gulf-petroleum (West Africa + Gulf of Mexico)
    #   → Murphy Oil Corp (NYSE:MUR) — GoM + historical West Africa
    "gulf-petroleum": (
        "0000717423",
        "US",
        "Murphy Oil — GoM + Eagle Ford + historical West Africa",
    ),
    # north-atlantic-resources (North Sea)
    #   → Hess Corp (NYSE:HES) — Bakken/GoM + historical North Sea
    "north-atlantic-resources": (
        "0000004447",
        "US",
        "Hess Corp — Bakken/GoM + historical North Sea",
    ),
    # bohai-energy (Bohai + South China Sea)
    #   → CNOOC Limited (NYSE:CEO; delisted 2021 but filings remain)
    "bohai-energy": ("0001095595", "HK", "CNOOC Limited — Bohai + South China Sea offshore"),
    # permian-fields (Permian + Midland)
    #   → Diamondback Energy (NASDAQ:FANG) — pure-play Permian
    "permian-fields": ("0001539838", "US", "Diamondback Energy — pure-play Permian"),
    # north-shelf-energy (North Sea + Barents Sea)
    #   → Equinor ASA (NYSE:EQNR) — Norwegian state operator
    "north-shelf-energy": ("0001140625", "NO", "Equinor ASA — North Sea + Barents Sea"),
    # deepwater-ventures (GoM + West Africa + Brazil)
    #   → Petrobras (NYSE:PBR) — Brazilian deepwater operator
    "deepwater-ventures": ("0001119639", "BR", "Petrobras — Brazil pre-salt + GoM + W. Africa"),
    # asia-pacific-ops (SCS + Timor + Australia NW Shelf)
    #   → Woodside Energy Group (NYSE:WDS) — Australia NW Shelf operator
    "asia-pacific-ops": ("0000844551", "AU", "Woodside Energy — Australia NW Shelf + Timor"),
}

# SEC requires a descriptive User-Agent identifying the requester.
# Format per their fair-use guidance: "<name> <admin email>".
SEC_UA = "agentic-sop-oilfield-services rahulsankrut@gmail.com"


def _fetch_submission(cik: str) -> dict:
    """Pull the SEC EDGAR submission JSON for a given CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def _pick_address(addresses: dict) -> dict:
    """SEC submissions have 'mailing' + 'business' addresses; prefer mailing."""
    if not isinstance(addresses, dict):
        return {}
    return addresses.get("business") or addresses.get("mailing") or {}


def main() -> int:
    anchors: dict[str, dict] = {}
    log.info("fetching SEC EDGAR submissions for %d customers...", len(CUSTOMER_TO_CIK))

    for customer_id, (cik, iso_country, why) in CUSTOMER_TO_CIK.items():
        try:
            sub = _fetch_submission(cik)
        except Exception as exc:  # noqa: BLE001
            log.warning("  %s (CIK %s): fetch failed — %s", customer_id, cik, exc)
            continue

        addr = _pick_address(sub.get("addresses", {}))
        anchors[customer_id] = {
            "cik": cik,
            "name": sub.get("name"),
            "ticker": (sub.get("tickers") or [None])[0],
            "exchange": (sub.get("exchanges") or [None])[0],
            "sic": sub.get("sic"),
            "sic_description": sub.get("sicDescription"),
            "iso_country": iso_country,  # curated — SEC's stateOrCountry is nonstandard
            "city": addr.get("city"),
            "state_or_country": addr.get("stateOrCountry"),
            "street1": addr.get("street1"),
            "street2": addr.get("street2"),
            "zip_code": addr.get("zipCode"),
            "fiscal_year_end": sub.get("fiscalYearEnd"),
            "justification": why,
        }
        log.info(
            "  %-30s → %s (CIK %s, ISO=%s) %s",
            customer_id,
            anchors[customer_id]["name"],
            cik,
            iso_country,
            anchors[customer_id]["sic_description"] or "",
        )

    ANCHOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ANCHOR_OUT.open("w") as f:
        json.dump(anchors, f, indent=2, ensure_ascii=False)
    log.info("wrote %s with %d anchors", ANCHOR_OUT, len(anchors))

    missing = set(CUSTOMER_TO_CIK) - set(anchors)
    if missing:
        log.warning("MISSING ANCHORS for: %s", sorted(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
