"""Build `data/anchors/uspto_patents.json` — real USPTO patents matched to
each canonical asset for the Mode C "real fields, kept IDs" enrichment
(TASK-16 Step 4d.1).

For every canonical_id in `data/canonical_assets.json`, this script picks
a real OFS-relevant US patent via Google Patents Public BQ Dataset
(`patents-public-data.patents.publications`). The picked patent provides
real values for:

  - `oilfield_kc.canonical_assets.MANUFACTURER`      ← assignee_harmonized
  - `oilfield_kc.canonical_assets.INTRODUCED_YEAR`   ← filing_date year
  - `sap_extract.MAKT.MAKTX`                         ← patent title (truncated)
  - `maximo_extract.ITEM.DESCRIPTION`                ← patent title
  - (cache) abstract — useful narration material

Output: JSON keyed by canonical_id. The seeder reads this file when
constructing rows; falls back to the data/*.json kernel for IDs and
display names (Mode C: scenario narrative unchanged).

This is a one-shot anchor builder. Re-run if we add/remove canonical
assets. The output JSON is committed.

Query strategy: each canonical_id has a tailored `(assignee_pattern,
keyword, year_window)` triplet so we get a real flagship product patent
from the right manufacturer for that asset class. Variants (TX-001 vs
TX-007) get patents at different filing years to reflect generations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from google.cloud import bigquery

PROJECT = "vertex-ai-demos-468803"
ANCHOR_OUT = Path(__file__).resolve().parent.parent / "data" / "anchors" / "uspto_patents.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# Curated query criteria per canonical_id. Each value is a *list* of
# (assignee_substr, keyword, year_min, year_max) fallbacks tried in
# order — first hit wins. The fallback list lets us start narrow ("real
# Halliburton frac-pump patent") and widen progressively ("any OFS major
# with frac-related patent") rather than silently NULLing the row.
ASSET_QUERIES: dict[str, list[tuple[str, str, int, int]]] = {
    # downhole_tool / drilling_motor
    "TX-001":    [("SCHLUMBERGER", "drilling motor",     2014, 2018)],
    "TX-007":    [("SCHLUMBERGER", "drilling motor",     2019, 2024)],
    "DM-805":    [("HALLIBURTON",  "drilling motor",     2014, 2018)],
    "DM-810":    [("HALLIBURTON",  "drilling motor",     2019, 2025),
                  ("HALLIBURTON",  "directional drilling", 2019, 2025)],
    # downhole_tool / mwd_lwd
    "MWD-300":   [("HALLIBURTON",  "measurement while drilling", 2014, 2020)],
    "MWD-310":   [("HALLIBURTON",  "measurement while drilling", 2021, 2025),
                  ("HALLIBURTON",  "downhole telemetry",         2021, 2025),
                  ("HALLIBURTON",  "mwd",                        2021, 2025)],
    "LWD-420":   [("BAKER HUGHES", "logging",                    2017, 2022)],
    # downhole_tool / bha
    "BHA-DRL-3": [("SCHLUMBERGER", "bottom hole assembly",       2017, 2022)],
    # wireline_tool / logging
    "WIRE-100":  [("SCHLUMBERGER", "wireline logging",  2011, 2017)],
    "WIRE-120":  [("SCHLUMBERGER", "wireline logging",  2018, 2023)],
    # completions / flow_control (bridge plugs + safety valves)
    "CMP-500":   [("SCHLUMBERGER", "bridge plug",        2015, 2020)],
    "CMP-510":   [("SCHLUMBERGER", "bridge plug",        2021, 2025),
                  ("HALLIBURTON",  "bridge plug",        2021, 2025)],
    "SAFE-VAL-1":[("BAKER HUGHES", "subsurface safety valve", 2014, 2019),
                  ("SCHLUMBERGER", "safety valve",            2014, 2019)],
    "SAFE-VAL-2":[("SCHLUMBERGER", "subsurface safety valve", 2020, 2024)],
    # completions / isolation
    "PKR-220":   [("BAKER HUGHES", "production packer",  2014, 2019)],
    # completions / perforating
    "PERF-GUN-2":[("SCHLUMBERGER", "perforating gun",    2015, 2020)],
    "PERF-GUN-4":[("HALLIBURTON",  "perforating gun",    2015, 2020)],
    # artificial_lift / esp
    "ESP-450":   [("BAKER HUGHES", "electric submersible pump", 2012, 2017)],
    "ESP-460":   [("BAKER HUGHES", "electric submersible pump", 2018, 2023)],
    # artificial_lift / pcp
    "PCP-700":   [("HALLIBURTON",  "progressive cavity",  2013, 2024),
                  ("BAKER HUGHES", "cavity pump",         2013, 2024),
                  ("SCHLUMBERGER", "progressive cavity",  2013, 2024)],
    # surface_equipment / cementing
    "PUMP-CMT-A":[("HALLIBURTON",  "cementing",          2014, 2020),
                  ("SCHLUMBERGER", "cementing pump",     2014, 2020)],
    "PUMP-CMT-B":[("HALLIBURTON",  "cementing pump",     2020, 2025),
                  ("HALLIBURTON",  "cementing",          2020, 2025)],
    # surface_equipment / coiled_tubing
    "CT-500":    [("SCHLUMBERGER", "coiled tubing",      2014, 2020),
                  ("HALLIBURTON",  "coiled tubing",      2014, 2020),
                  ("BAKER HUGHES", "coiled tubing",      2014, 2020)],
    "CT-520":    [("SCHLUMBERGER", "coiled tubing",      2020, 2025),
                  ("HALLIBURTON",  "coiled tubing",      2020, 2025)],
    # surface_equipment / hydraulic_fracturing
    "FRAC-PUMP-A":[("HALLIBURTON", "hydraulic fracturing pump", 2015, 2020),
                   ("HALLIBURTON", "frac pump",                 2015, 2020),
                   ("HALLIBURTON", "fracturing",                2015, 2020)],
    "FRAC-PUMP-B":[("HALLIBURTON", "fracturing pump",    2021, 2025)],
    # surface_equipment / workover
    "RIG-LWP-A": [("SCHLUMBERGER", "workover rig",       2014, 2020),
                  ("HALLIBURTON",  "workover",           2014, 2020),
                  ("BAKER HUGHES", "well intervention",  2014, 2020)],
    "RIG-LWP-B": [("SCHLUMBERGER", "workover",           2020, 2025),
                  ("HALLIBURTON",  "well intervention",  2020, 2025)],
    # sensing / distributed_acoustic
    "FBG-DAS":   [("SCHLUMBERGER", "distributed acoustic sensing", 2016, 2024),
                  ("SCHLUMBERGER", "fiber optic acoustic",         2016, 2024),
                  ("HALLIBURTON",  "distributed acoustic",         2016, 2024)],
    # sensing / distributed_temperature
    "FBG-DTS":   [("SCHLUMBERGER", "distributed temperature sensing", 2014, 2024),
                  ("SCHLUMBERGER", "fiber optic temperature",         2014, 2024),
                  ("HALLIBURTON",  "distributed temperature",         2014, 2024)],
}


PATENT_QUERY = """
SELECT
  publication_number,
  (SELECT text FROM UNNEST(title_localized) WHERE language = 'en' LIMIT 1) AS title,
  (SELECT text FROM UNNEST(abstract_localized) WHERE language = 'en' LIMIT 1) AS abstract,
  assignee_harmonized[SAFE_OFFSET(0)].name AS assignee,
  CAST(SUBSTR(CAST(filing_date AS STRING), 1, 4) AS INT64) AS filing_year,
  filing_date,
  ARRAY(SELECT code FROM UNNEST(cpc) LIMIT 5) AS cpc_codes
FROM `patents-public-data.patents.publications`
WHERE country_code = 'US'
  AND filing_date BETWEEN @ymin AND @ymax
  AND assignee_harmonized[SAFE_OFFSET(0)].name LIKE @assignee_pat
  AND LOWER(
        ARRAY_TO_STRING(ARRAY(SELECT text FROM UNNEST(title_localized)), ' ')
      ) LIKE @kw_pat
ORDER BY ARRAY_LENGTH(citation) DESC, filing_date DESC
LIMIT 1
"""


def _fetch_patent(client: bigquery.Client, canonical_id: str,
                  assignee: str, keyword: str, year_min: int, year_max: int) -> dict | None:
    """Return one real patent matching the criteria, or None if no match."""
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ymin", "INT64", int(f"{year_min}0101")),
            bigquery.ScalarQueryParameter("ymax", "INT64", int(f"{year_max}1231")),
            bigquery.ScalarQueryParameter("assignee_pat", "STRING", f"%{assignee}%"),
            bigquery.ScalarQueryParameter("kw_pat",       "STRING", f"%{keyword.lower()}%"),
        ],
    )
    rows = list(client.query(PATENT_QUERY, job_config=job_config).result())
    if not rows:
        log.warning("  %s: no match for (%s, %s, %d-%d)", canonical_id, assignee, keyword, year_min, year_max)
        return None
    r = rows[0]
    return {
        "publication_number": r["publication_number"],
        "title": r["title"],
        "abstract": (r["abstract"] or "")[:1000],
        "assignee": r["assignee"],
        "filing_year": int(r["filing_year"]),
        "cpc_codes": list(r["cpc_codes"]) if r["cpc_codes"] else [],
    }


def main() -> int:
    client = bigquery.Client(project=PROJECT)
    anchors: dict[str, dict] = {}
    log.info("querying Google Patents Public BQ Dataset for %d assets...", len(ASSET_QUERIES))
    for canonical_id, fallbacks in ASSET_QUERIES.items():
        patent: dict | None = None
        for assignee, kw, ymin, ymax in fallbacks:
            patent = _fetch_patent(client, canonical_id, assignee, kw, ymin, ymax)
            if patent:
                break
        if patent:
            anchors[canonical_id] = patent
            log.info("  %-12s → %s (%d) — %s", canonical_id, patent["publication_number"],
                     patent["filing_year"], patent["title"][:60])

    ANCHOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ANCHOR_OUT.open("w") as f:
        json.dump(anchors, f, indent=2, ensure_ascii=False)
    log.info("wrote %s with %d anchors", ANCHOR_OUT, len(anchors))

    missing = set(ASSET_QUERIES) - set(anchors)
    if missing:
        log.warning("MISSING ANCHORS for: %s", sorted(missing))
        log.warning("  (these assets will fall back to JSON-derived values in the seeder)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
