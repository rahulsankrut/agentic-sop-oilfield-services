"""Build the BSEE incident-reports corpus for TASK-17 (unstructured data pillar).

Downloads a representative set of real BSEE Investigation Report PDFs
(mix of Panel + District reports), uploads them to GCS at
`gs://oilfield-services-unstructured/bsee_incidents/<filename>.pdf`,
and writes a manifest JSON at `data/anchors/bsee_corpus.json` keyed by
a stable incident_id.

Idempotent: skips uploads if the object already exists in GCS, but
still rewrites the manifest from the curated source list.

The curated list was assembled by parsing
https://www.bsee.gov/what-we-do/incident-investigations/offshore-incident-investigations/district-investigation-reports
(public BSEE table — Date / Lease / Area-Block / Accident Type / PDF link) on
2026-05-20, plus two panel reports whose direct URLs were verified via the
prompt's WebSearch hints. Picks are representative of the corpus, not
necessarily the most recent.

Substitution: a customer with their own incident-report corpus dumps it
to a GCS bucket of their choosing and repoints
`INCIDENTS_SEARCH_DATASTORE_ID`. This script is only needed for the
demo dataset.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from google.cloud import storage

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_OUT = REPO_ROOT / "data" / "anchors" / "bsee_corpus.json"

GCS_PROJECT = "vertex-ai-demos-468803"
GCS_BUCKET = "oilfield-services-unstructured"
GCS_PREFIX = "bsee_incidents"

USER_AGENT = "agentic-sop-oilfield-services rahulsankrut@gmail.com"
FETCH_SLEEP_SEC = 1.0

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# Curated list of BSEE investigation reports.
#
# Each entry's `incident_id` is stable (district reports use the BSEE
# DISTRICT-<area>-<block>-<yyyymmdd> convention; panel reports use
# PANEL-<area>-<block>-<yyyymmdd>). This is the key the Knowledge
# Catalog will use to link a WORKORDER to an incident-report citation.
#
# `pdf_url` is the canonical BSEE source URL.
# `pdf_filename` is the slugified name we store the blob under (avoids
# url-encoded spaces in GCS object names).
# `report_type` is "panel" | "district".
# `lease_number`, `area_block`, `incident_date` come from the BSEE table.
# `title` and `accident_type` are short labels.
# `keywords` are vector-search tags (used at indexing time later).
CURATED_REPORTS: list[dict] = [
    # --- Required Evacuation (matches TX-007-LGS-001 anchor — Tool X recert WO) ---
    {
        "incident_id": "DISTRICT-GB-783-20260307",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-04/W%26T%207Mar2026%20GB%20783_Redacted.pdf",
        "pdf_filename": "gb-783-wt-offshore-07-mar-2026.pdf",
        "report_type": "district",
        "title": "W&T Offshore — GB 783 — Required Evacuation / LTA",
        "lease_number": "G11573",
        "area_block": "GB 783",
        "incident_date": "2026-03-07",
        "incident_year": 2026,
        "accident_type": "Required Evacuation, LTA (>3 days)",
        "keywords": ["required evacuation", "lta", "injury", "offshore"],
    },
    {
        "incident_id": "DISTRICT-GB-959-20251014",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-03/GB%20959%20Shell%2014-Oct-2025.pdf",
        "pdf_filename": "gb-959-shell-14-oct-2025.pdf",
        "report_type": "district",
        "title": "Shell — GB 959 — Required Evacuation / Lifting",
        "lease_number": "G30876",
        "area_block": "GB 959",
        "incident_date": "2025-10-14",
        "incident_year": 2025,
        "accident_type": "Required Evacuation, LTA (>3 days), Other Lifting Device, Injury",
        "keywords": ["required evacuation", "lifting", "lta", "injury"],
    },
    # --- Crane / lifting (matches __repair_default__ anchor) ---
    {
        "incident_id": "DISTRICT-KC-785-20251123",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-03/KC%20785%20LLOG%2023-Nov-2025.pdf",
        "pdf_filename": "kc-785-llog-23-nov-2025.pdf",
        "report_type": "district",
        "title": "LLOG — KC 785 — Other Lifting",
        "lease_number": "G25806",
        "area_block": "KC 785",
        "incident_date": "2025-11-23",
        "incident_year": 2025,
        "accident_type": "Other Lifting",
        "keywords": ["crane", "lifting", "rigging"],
    },
    {
        "incident_id": "DISTRICT-WD-152-20250827",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2025-12/WD%20152%20Renaissance%2027-Aug-2025.pdf",
        "pdf_filename": "wd-152-renaissance-27-aug-2025.pdf",
        "report_type": "district",
        "title": "Renaissance — WD 152 — Crane / Incident >$25k",
        "lease_number": "G37455",
        "area_block": "WD 152",
        "incident_date": "2025-08-27",
        "incident_year": 2025,
        "accident_type": "Crane, Incident > $25k",
        "keywords": ["crane", "equipment damage", "rigging"],
    },
    # --- Fire ---
    {
        "incident_id": "DISTRICT-VK-989-20260108",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-03/VK%20989%20Talos%20Energy%2008-Jan-2026_0.pdf",
        "pdf_filename": "vk-989-talos-energy-08-jan-2026.pdf",
        "report_type": "district",
        "title": "Talos Energy — VK 989 — Fire",
        "lease_number": "G06898",
        "area_block": "VK 989",
        "incident_date": "2026-01-08",
        "incident_year": 2026,
        "accident_type": "Fire",
        "keywords": ["fire", "hot work", "ignition"],
    },
    {
        "incident_id": "DISTRICT-MP-300B-20251126",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-03/MP%20300-B%20Cantium%2026-NOV-2025.pdf",
        "pdf_filename": "mp-300b-cantium-26-nov-2025.pdf",
        "report_type": "district",
        "title": "Cantium — MP 300-B — Fire",
        "lease_number": "G01317",
        "area_block": "MP 300-B",
        "incident_date": "2025-11-26",
        "incident_year": 2025,
        "accident_type": "Fire",
        "keywords": ["fire", "platform fire"],
    },
    # --- Pollution / Spill ---
    {
        "incident_id": "DISTRICT-MC-300-20250529",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-01/MC%20300%20Murphy%20Exploration%2029-May-2025.pdf",
        "pdf_filename": "mc-300-murphy-exploration-29-may-2025.pdf",
        "report_type": "district",
        "title": "Murphy Exploration — MC 300 — Pollution / EDS",
        "lease_number": "G22868",
        "area_block": "MC 300",
        "incident_date": "2025-05-29",
        "incident_year": 2025,
        "accident_type": "Pollution - Emergency Disconnect Sequence",
        "keywords": ["pollution", "spill", "emergency disconnect"],
    },
    # --- Well control / Gas release ---
    {
        "incident_id": "DISTRICT-SP-62C-20251103",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-01/SP%2062-C%20GOM%20Shelf%20%2003-Nov-2025.pdf",
        "pdf_filename": "sp-62c-gom-shelf-03-nov-2025.pdf",
        "report_type": "district",
        "title": "GOM Shelf — SP 62-C — Shutdown from Gas Release",
        "lease_number": "G01294",
        "area_block": "SP 62-C",
        "incident_date": "2025-11-03",
        "incident_year": 2025,
        "accident_type": "Shutdown from Gas Release - Incident >$25K",
        "keywords": ["gas release", "well control", "shutdown"],
    },
    # --- Explosion ---
    {
        "incident_id": "DISTRICT-WR-249-20250428",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2025-11/EV2010R%20-%20WR%20249.pdf",
        "pdf_filename": "wr-249-ev2010r-28-apr-2025.pdf",
        "report_type": "district",
        "title": "WR 249 — Injury, Explosion, Incident >$25k",
        "lease_number": "G30369",
        "area_block": "WR 249",
        "incident_date": "2025-04-28",
        "incident_year": 2025,
        "accident_type": "Injury, Explosion, Incident > $25k",
        "keywords": ["explosion", "injury", "equipment damage"],
    },
    # --- Injury / LTA ---
    {
        "incident_id": "DISTRICT-EI-259C-20251003",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/2026-01/EI%20259%20White%20Fleet%2003_OCT_2025.pdf",
        "pdf_filename": "ei-259-white-fleet-03-oct-2025.pdf",
        "report_type": "district",
        "title": "White Fleet — EI 259 C — Required Evacuation / LTA",
        "lease_number": "G00985",
        "area_block": "EI 259 C",
        "incident_date": "2025-10-03",
        "incident_year": 2025,
        "accident_type": "Required Evacuation, LTA (>3 days)",
        "keywords": ["injury", "lta", "evacuation"],
    },
    # --- Panel reports (verified via prompt hints) ---
    {
        "incident_id": "PANEL-GB-426-20210403",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/gb-426-shell-03-apr-2021.pdf",
        "pdf_filename": "gb-426-shell-03-apr-2021.pdf",
        "report_type": "panel",
        "title": "Shell — GB 426 — Panel Investigation Report",
        "lease_number": "",
        "area_block": "GB 426",
        "incident_date": "2021-04-03",
        "incident_year": 2021,
        "accident_type": "Panel investigation (offshore incident)",
        "keywords": ["panel", "shell", "offshore", "investigation"],
    },
    {
        "incident_id": "PANEL-HIA-379B-20150420",
        "pdf_url": "https://www.bsee.gov/sites/bsee.gov/files/reports/incident-and-investigations/hi-a-379-b-w-and-t-offshore-20-apr-2015.pdf",
        "pdf_filename": "hi-a-379-b-wt-offshore-20-apr-2015.pdf",
        "report_type": "panel",
        "title": "W&T Offshore — HI A 379 B — Panel Investigation Report",
        "lease_number": "",
        "area_block": "HI A 379 B",
        "incident_date": "2015-04-20",
        "incident_year": 2015,
        "accident_type": "Panel investigation (offshore incident)",
        "keywords": ["panel", "wt-offshore", "offshore", "investigation"],
    },
]


def _download_pdf(url: str) -> bytes:
    """Download a PDF from a URL. Returns the raw bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _gcs_uri(filename: str) -> str:
    return f"gs://{GCS_BUCKET}/{GCS_PREFIX}/{filename}"


def main() -> int:
    storage_client = storage.Client(project=GCS_PROJECT)
    bucket = storage_client.bucket(GCS_BUCKET)
    if not bucket.exists():
        log.error("GCS bucket %s does not exist", GCS_BUCKET)
        return 2

    manifest: dict[str, dict] = {}
    uploaded = 0
    skipped = 0
    failed: list[str] = []
    total_bytes = 0

    for rec in CURATED_REPORTS:
        incident_id = rec["incident_id"]
        filename = rec["pdf_filename"]
        url = rec["pdf_url"]
        gcs_uri = _gcs_uri(filename)
        blob = bucket.blob(f"{GCS_PREFIX}/{filename}")

        if blob.exists():
            blob.reload()
            size = blob.size or 0
            log.info("[skip] %s already in GCS (%d bytes)", gcs_uri, size)
            skipped += 1
            total_bytes += size
        else:
            log.info("[fetch] %s", url)
            try:
                data = _download_pdf(url)
            except Exception as e:  # noqa: BLE001
                log.warning("  -> FAILED (%s): %s", type(e).__name__, e)
                failed.append(url)
                time.sleep(FETCH_SLEEP_SEC)
                continue
            log.info("  -> %d bytes; uploading to %s", len(data), gcs_uri)
            blob.upload_from_string(data, content_type="application/pdf")
            uploaded += 1
            total_bytes += len(data)
            time.sleep(FETCH_SLEEP_SEC)

        manifest[incident_id] = {
            "pdf_filename": filename,
            "gcs_uri": gcs_uri,
            "source_url": url,
            "title": rec["title"],
            "report_type": rec["report_type"],
            "lease_number": rec["lease_number"],
            "area_block": rec["area_block"],
            "incident_date": rec["incident_date"],
            "incident_year": rec["incident_year"],
            "accident_type": rec["accident_type"],
            "keywords": rec["keywords"],
        }

    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_OUT.open("w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    log.info("wrote %s (%d entries)", MANIFEST_OUT, len(manifest))

    log.info("")
    log.info("=" * 60)
    log.info("BSEE corpus build summary")
    log.info("=" * 60)
    log.info("  curated:    %d", len(CURATED_REPORTS))
    log.info("  uploaded:   %d", uploaded)
    log.info("  skipped:    %d (already in GCS)", skipped)
    log.info("  failed:     %d", len(failed))
    log.info("  manifest:   %d entries", len(manifest))
    log.info("  total size: %d bytes (%.2f MiB)", total_bytes, total_bytes / (1024 * 1024))
    if failed:
        log.info("  failed urls:")
        for u in failed:
            log.info("    %s", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
