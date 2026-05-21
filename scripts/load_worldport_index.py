"""Load NGA World Port Index (Pub 150) into BigQuery.

TASK-16 Step 4b.

The NGA WPI is the authoritative public dataset of world ports — 3,800+
entries with location, harbor characteristics, and vessel-handling
capabilities. US Government public domain. Refreshed by NGA on an
irregular cadence; downloaded directly each run.

Source: https://msi.nga.mil/Publications/WPI
Direct CSV: https://msi.nga.mil/api/publications/download?type=view&key=16920959/SFH00000/UpdatedPub150.csv

What we project to BQ (per spec §3 — 11 columns of the 109 in the source):

  WORLD_PORT_INDEX_NUMBER  ← "World Port Index Number"
  MAIN_PORT_NAME           ← "Main Port Name"
  UN_LOCODE                ← "UN/LOCODE" (e.g. "NG LOS")
  COUNTRY_CODE             ← derived from first 2 chars of UN/LOCODE
                              (the CSV's "Country Code" column is actually
                              the country *name*, not the ISO code)
  LATITUDE / LONGITUDE     ← "Latitude" / "Longitude" (decimal degrees)
  HARBOR_TYPE              ← "Harbor Type"
  HARBOR_SIZE              ← "Harbor Size"
  OCEAN_BASIN              ← derived from "World Water Body" (last
                              semicolon-segment, typically the encompassing
                              ocean: "...; North Atlantic Ocean")
  MAX_VESSEL_LENGTH_M      ← "Maximum Vessel Length (m)"
  MAX_VESSEL_DRAFT_M       ← "Maximum Vessel Draft (m)"

Substitution path: this dataset is the same for everyone (US Govt public
domain). Customer doesn't need to substitute. Refresh via re-running
this script.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import urllib.request
from collections.abc import Iterable
from datetime import UTC, datetime

UTC = UTC  # Python 3.10 compat (datetime.UTC is 3.11+)

from google.cloud import bigquery

PROJECT = "vertex-ai-demos-468803"
TABLE = "worldport_index.ports"
AUDIT_TABLE = "bakerhughes_rig_count.dataset_loads"  # shared audit table per Step 2 DDL

WPI_URL = (
    "https://msi.nga.mil/api/publications/download"
    "?type=view&key=16920959/SFH00000/UpdatedPub150.csv"
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def _coalesce_num(s: str | None) -> float | None:
    if s is None or s.strip() in ("", "None"):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _coalesce_int(s: str | None) -> int | None:
    n = _coalesce_num(s)
    return int(n) if n is not None else None


def _truncate(s: str | None, maxlen: int) -> str | None:
    if s is None:
        return None
    s = s.strip()
    return s[:maxlen] if s else None


def _country_code(unlocode: str | None) -> str | None:
    """ISO-2 country code from a UN/LOCODE like 'NG LOS' (first 2 chars)."""
    if not unlocode:
        return None
    unlocode = unlocode.strip()
    if len(unlocode) < 2:
        return None
    return unlocode[:2].upper()


def _ocean_basin(world_water_body: str | None) -> str | None:
    """Derive the encompassing ocean from a 'A; B; C' chain.

    WPI's `World Water Body` lists progressively-encompassing water bodies
    separated by `; ` — last segment is the ocean / sea region. Cap at 20
    chars to match the DDL constraint.
    """
    if not world_water_body:
        return None
    parts = [p.strip() for p in world_water_body.split(";") if p.strip()]
    if not parts:
        return None
    return parts[-1][:20]


def _fetch_csv(url: str) -> str:
    log.info("downloading WPI CSV from %s ...", url)
    req = urllib.request.Request(url, headers={"User-Agent": "oilfield-services-task16/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    log.info("downloaded %.2f MiB", len(data) / 1024 / 1024)
    # WPI ships UTF-8 with a BOM.
    return data.decode("utf-8-sig")


def _build_rows(csv_text: str) -> Iterable[dict]:
    reader = csv.DictReader(io.StringIO(csv_text))
    n = 0
    for r in reader:
        wpi = _coalesce_int(r.get("World Port Index Number"))
        if wpi is None:
            continue
        unlocode = r.get("UN/LOCODE") or None
        yield {
            "WORLD_PORT_INDEX_NUMBER": wpi,
            "MAIN_PORT_NAME": _truncate(r.get("Main Port Name"), 80),
            "UN_LOCODE": _truncate(unlocode, 10),
            "COUNTRY_CODE": _country_code(unlocode),
            "LATITUDE": _coalesce_num(r.get("Latitude")),
            "LONGITUDE": _coalesce_num(r.get("Longitude")),
            "HARBOR_TYPE": _truncate(r.get("Harbor Type"), 20),
            "HARBOR_SIZE": _truncate(r.get("Harbor Size"), 10),
            "OCEAN_BASIN": _ocean_basin(r.get("World Water Body")),
            "MAX_VESSEL_LENGTH_M": _coalesce_num(r.get("Maximum Vessel Length (m)")),
            "MAX_VESSEL_DRAFT_M": _coalesce_num(r.get("Maximum Vessel Draft (m)")),
        }
        n += 1
    log.info("parsed %d WPI rows", n)


def _audit_row(source: str, row_count: int, started: datetime, ended: datetime) -> dict:
    return {
        "dataset": "worldport_index.ports",
        "source_url": source,
        "row_count": row_count,
        "load_started_at": started.isoformat(),
        "load_completed_at": ended.isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--file",
        help="Path to a local UpdatedPub150.csv (skips the NGA download).",
    )
    p.add_argument(
        "--url",
        default=WPI_URL,
        help="Override the NGA download URL.",
    )
    args = p.parse_args()

    started = datetime.now(tz=UTC)

    if args.file:
        with open(args.file, encoding="utf-8-sig") as f:
            csv_text = f.read()
        source = args.file
    else:
        csv_text = _fetch_csv(args.url)
        source = args.url

    rows = list(_build_rows(csv_text))
    if not rows:
        log.error("no rows parsed from WPI CSV")
        return 2

    client = bigquery.Client(project=PROJECT)
    job = client.load_table_from_json(
        rows,
        f"{PROJECT}.{TABLE}",
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        ),
    )
    job.result()
    ended = datetime.now(tz=UTC)
    log.info("loaded %d rows into %s", job.output_rows or 0, TABLE)

    audit_job = client.load_table_from_json(
        [_audit_row(source, job.output_rows or 0, started, ended)],
        f"{PROJECT}.{AUDIT_TABLE}",
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        ),
    )
    audit_job.result()
    log.info("audit row appended to %s", AUDIT_TABLE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
