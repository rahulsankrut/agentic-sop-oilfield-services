"""Build the InTouch technical-specs corpus for TASK-17 (unstructured pillar).

Downloads real public OFS technical PDFs from three sources and uploads
them to `gs://oilfield-services-unstructured/intouch_specs/`:

  1. USPTO patents — uses ~10 entries from `data/anchors/uspto_patents.json`
     (built by TASK-16 step 4d.1 against the Google Patents Public BQ
     Dataset). For each picked patent the PDF is fetched from one of
     two endpoints:
       a) https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/<patno>
          works for granted patents (B1/B2) but NOT application
          publications (A1/A9).
       b) https://patents.google.com/patent/<canonical-pub>/en — scrape
          for the `patentimages.storage.googleapis.com/<hash>/<id>.pdf`
          URL. This covers BOTH granted patents and application
          publications, but requires HTML scraping.
     We try (a) first for B-kind, (b) for A-kind, then fall back to the
     other if the first 404s. Patents granted very recently (e.g. 2026
     publications) often have no PDF yet — skip and log.
  2. Equinor (real Volve dataset URLs are gone — `datasetdisko.equinor.com`
     no longer resolves. The only reliably-reachable Equinor PDF is the
     **Equinor open-data user guide**, which references Volve. We grab
     that as the canonical Equinor InTouch-style spec doc.)
  3. OSTI.GOV — DOE's scientific & technical reports repository. We pull
     2 carefully-picked DOE technical reports matching OFS asset
     categories (drilling / wellbore characterization / fracture
     imaging). Filtered by file size <25 MB to keep the upload sane.

Output: `data/anchors/intouch_corpus.json`. Each entry includes:
  - gcs_uri, pdf_filename
  - title, source ("uspto" | "equinor" | "osti")
  - assignee_or_publisher, year
  - applies_to_canonical_ids: which canonical_ids the doc is anchor for

Idempotent: skips uploads when the GCS object already exists.

Run with `venv-deploy-310/bin/python` (Python 3.10) per project env conventions.

DEMO NARRATION: "These ten USPTO patents plus the Equinor reference doc
become our customer's InTouch spec repository. In the demo, the
asset-equivalence skill RAG-queries this corpus to ground its
'is Tool X equivalent to Tool Y' rationale in real engineering text."
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests
from google.cloud import storage

ROOT = Path(__file__).resolve().parent.parent
ANCHORS_IN = ROOT / "data" / "anchors" / "uspto_patents.json"
CORPUS_OUT = ROOT / "data" / "anchors" / "intouch_corpus.json"
PROJECT = "vertex-ai-demos-468803"
BUCKET = "oilfield-services-unstructured"
GCS_PREFIX = "intouch_specs"

USER_AGENT = "agentic-sop-oilfield-services rahulsankrut@gmail.com"
HEADERS = {"User-Agent": USER_AGENT}
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB cap — OSTI returns some huge PDFs

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# Diverse spread across asset categories: drilling motors, MWD, LWD,
# wireline, completions (bridge plug + safety valve), ESP, sensing
# (DAS), cementing, frac, perforating. Skips the 2026-filed patents
# (CMP-510, PUMP-CMT-B) because PDFs are not yet posted by USPTO.
PATENT_PICKS_CANONICAL: list[str] = [
    "TX-001",  # drilling motor — SLB (inverted)
    "DM-805",  # drilling motor — Halliburton (electric gen in rotor)
    "MWD-300",  # MWD centralizer — Halliburton
    "LWD-420",  # LWD distributed logging — Baker Hughes
    "WIRE-100",  # wireline rope socket — SLB
    "CMP-500",  # completions — single-trip casing cutting + bridge plug — SLB
    "SAFE-VAL-1",  # subsea safety valve — SLB
    "ESP-450",  # ESP virtual sensor — Baker Hughes
    "PERF-GUN-2",  # perforating gun shock loads — SLB
    "FBG-DAS",  # distributed acoustic sensing — SLB
]

# Each canonical_id maps to which other canonical_ids the doc applies to
# (asset family / variant pairing). The patent text covers the entire
# family in most cases.
PATENT_APPLIES_TO: dict[str, list[str]] = {
    "TX-001": ["TX-001", "TX-007"],
    "DM-805": ["DM-805", "DM-810"],
    "MWD-300": ["MWD-300", "MWD-310"],
    "LWD-420": ["LWD-420", "BHA-DRL-3"],
    "WIRE-100": ["WIRE-100", "WIRE-120"],
    "CMP-500": ["CMP-500", "CMP-510"],
    "SAFE-VAL-1": ["SAFE-VAL-1", "SAFE-VAL-2"],
    "ESP-450": ["ESP-450", "ESP-460", "PCP-700"],
    "PERF-GUN-2": ["PERF-GUN-2", "PERF-GUN-4"],
    "FBG-DAS": ["FBG-DAS", "FBG-DTS"],
}


# --- Equinor: only the user guide PDF (volve raw is gone) ---
EQUINOR_DOCS: list[dict] = [
    {
        "key": "equinor-open-data-user-guide",
        "url": "https://equinoropendata.blob.core.windows.net/userguides/Equinor%20open%20data%20-%20User%20Guide.pdf",
        "title": "Equinor Open Data User Guide (Volve, Northern Lights, etc.)",
        "publisher": "Equinor ASA",
        "year": 2018,
        # Apply broadly to drilling / wireline / MWD assets that benefit
        # from real upstream documentation.
        "applies_to": ["TX-001", "TX-007", "WIRE-100", "WIRE-120", "MWD-300", "LWD-420"],
    },
]


# --- OSTI.GOV: hand-picked DOE technical reports relevant to OFS specs ---
# Picked via the OSTI search API; each URL resolves to a real PDF
# (verified with HEAD). osti_id 2562738 ("Wellbore Fracture Imaging
# Using Inflow Detection Measurements") is 34MB — exceeds the 25MB cap,
# so we use osti_id 2584141 ("Expedition UT-GOM2-2 Methods", 10MB)
# instead for the wireline/sensing fallback.
OSTI_DOCS: list[dict] = [
    {
        "key": "osti-2584141-utgom2-methods",
        "osti_id": 2584141,
        "title": "Expedition UT-GOM2-2 Methods (subsea coring + wireline log analysis)",
        "publisher": "U.S. Department of Energy / Univ. of Texas",
        "year": 2024,
        # Wireline + sensing reports apply to wireline/MWD/LWD assets.
        "applies_to": ["WIRE-100", "WIRE-120", "LWD-420", "MWD-310", "FBG-DAS", "FBG-DTS"],
    },
    {
        "key": "osti-3023057-dynamometer",
        "osti_id": 3023057,
        "title": "High-Temperature Dynamometer Test Stand Development (downhole motor testing)",
        "publisher": "U.S. Department of Energy",
        "year": 2024,
        # Dynamometer testing for downhole motors -> applies to drilling motors.
        "applies_to": ["TX-001", "TX-007", "DM-805", "DM-810"],
    },
]


def _pub_to_patent_id(pub: str) -> tuple[str, str]:
    """`US-10006249-B2` -> `('10006249', 'B2')`."""
    m = re.match(r"US-(\d+)-([AB]\d?)", pub)
    if not m:
        raise ValueError(f"can't parse publication_number: {pub}")
    return m.group(1), m.group(2)


def _google_patents_canonical(pub: str) -> str:
    """Build the canonical Google Patents URL slug.

    - Granted (Bx): drop dashes -> `US10006249B2`.
    - Application (Ax): year-based publications like `2021162896` need
      a zero inserted after the 4-digit year: `20210162896`. The full
      slug becomes `US20210162896A1`.
    """
    patno, kind = _pub_to_patent_id(pub)
    if kind.startswith("A") and len(patno) >= 10 and patno[:4].isdigit():
        # application publication: insert leading 0 between year and seq
        patno = f"{patno[:4]}0{patno[4:]}"
    return f"US{patno}{kind}"


def _try_uspto_direct(patno: str) -> str | None:
    """Return the USPTO direct-download URL if it 200s, else None."""
    url = f"https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/{patno}"
    try:
        r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code == 200 and "pdf" in (r.headers.get("content-type") or "").lower():
            return url
    except requests.RequestException as e:
        log.warning("    USPTO HEAD error: %s", e)
    return None


def _try_google_patents(pub: str) -> str | None:
    """Scrape patents.google.com for the `patentimages.storage.googleapis.com` PDF URL."""
    slug = _google_patents_canonical(pub)
    page_url = f"https://patents.google.com/patent/{slug}/en"
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            log.warning("    google patents page %s -> %d", slug, r.status_code)
            return None
        m = re.search(r"https://patentimages\.storage\.googleapis\.com/[\w./-]+\.pdf", r.text)
        if not m:
            log.warning("    google patents page %s: no PDF URL found", slug)
            return None
        return m.group(0)
    except requests.RequestException as e:
        log.warning("    google patents error: %s", e)
        return None


def _download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        if r.status_code != 200:
            log.warning("    download %s -> %d", url, r.status_code)
            return None
        ct = (r.headers.get("content-type") or "").lower()
        if "pdf" not in ct:
            log.warning("    download %s: not a PDF (ct=%s)", url, ct)
            return None
        cl = r.headers.get("content-length")
        if cl and int(cl) > MAX_PDF_BYTES:
            log.warning("    download %s: too large (%s bytes > %d cap)", url, cl, MAX_PDF_BYTES)
            return None
        # Stream into memory but cap to avoid runaway PDFs that lie about CL.
        buf = bytearray()
        for chunk in r.iter_content(chunk_size=1 << 16):
            buf.extend(chunk)
            if len(buf) > MAX_PDF_BYTES:
                log.warning("    download %s: exceeded cap mid-stream", url)
                return None
        return bytes(buf)
    except requests.RequestException as e:
        log.warning("    download error %s: %s", url, e)
        return None


def _ensure_uploaded(
    bucket: storage.Bucket, gcs_name: str, payload: bytes, content_type: str = "application/pdf"
) -> tuple[str, int, bool]:
    """Upload `payload` if `gcs_name` is missing. Return (gcs_uri, size, was_uploaded)."""
    blob = bucket.blob(gcs_name)
    if blob.exists():
        blob.reload()
        size = blob.size or len(payload)
        return f"gs://{bucket.name}/{gcs_name}", size, False
    blob.upload_from_string(payload, content_type=content_type)
    return f"gs://{bucket.name}/{gcs_name}", len(payload), True


def _process_patent(canonical_id: str, patent: dict, bucket: storage.Bucket) -> dict | None:
    pub = patent["publication_number"]
    patno, kind = _pub_to_patent_id(pub)
    log.info("  %s [%s] %s", canonical_id, pub, patent["title"][:60])

    # Choose download strategy by kind. Granted = USPTO direct first
    # (cleaner, no scrape). Application = Google Patents only (USPTO
    # direct doesn't serve A-kind publications).
    pdf_url: str | None = None
    if kind.startswith("B"):
        pdf_url = _try_uspto_direct(patno)
        if not pdf_url:
            pdf_url = _try_google_patents(pub)
    else:
        pdf_url = _try_google_patents(pub)
        if not pdf_url:
            pdf_url = _try_uspto_direct(patno)

    if not pdf_url:
        log.warning("    %s: no PDF source available — skipping", pub)
        return None

    payload = _download_pdf(pdf_url)
    if payload is None:
        log.warning("    %s: download failed — skipping", pub)
        return None

    filename = f"uspto-{patno}-{kind}.pdf"
    gcs_name = f"{GCS_PREFIX}/{filename}"
    gcs_uri, size, was_uploaded = _ensure_uploaded(bucket, gcs_name, payload)
    log.info("    %s  %s  (%d bytes)", "UPLOADED" if was_uploaded else "EXISTS", gcs_uri, size)

    return {
        "gcs_uri": gcs_uri,
        "pdf_filename": filename,
        "title": patent["title"],
        "source": "uspto",
        "publication_number": pub,
        "assignee_or_publisher": patent.get("assignee", "UNKNOWN"),
        "year": patent.get("filing_year"),
        "applies_to_canonical_ids": PATENT_APPLIES_TO.get(canonical_id, [canonical_id]),
        "source_url": pdf_url,
        "size_bytes": size,
    }


def _process_equinor(doc: dict, bucket: storage.Bucket) -> dict | None:
    log.info("  EQUINOR %s", doc["title"][:60])
    payload = _download_pdf(doc["url"])
    if payload is None:
        log.warning("    %s: download failed — skipping", doc["url"])
        return None
    filename = f"{doc['key']}.pdf"
    gcs_name = f"{GCS_PREFIX}/{filename}"
    gcs_uri, size, was_uploaded = _ensure_uploaded(bucket, gcs_name, payload)
    log.info("    %s  %s  (%d bytes)", "UPLOADED" if was_uploaded else "EXISTS", gcs_uri, size)
    return {
        "gcs_uri": gcs_uri,
        "pdf_filename": filename,
        "title": doc["title"],
        "source": "equinor",
        "assignee_or_publisher": doc["publisher"],
        "year": doc["year"],
        "applies_to_canonical_ids": doc["applies_to"],
        "source_url": doc["url"],
        "size_bytes": size,
    }


def _process_osti(doc: dict, bucket: storage.Bucket) -> dict | None:
    log.info("  OSTI %s", doc["title"][:60])
    url = f"https://www.osti.gov/servlets/purl/{doc['osti_id']}"
    payload = _download_pdf(url)
    if payload is None:
        log.warning("    osti %s: download failed — skipping", doc["osti_id"])
        return None
    filename = f"{doc['key']}.pdf"
    gcs_name = f"{GCS_PREFIX}/{filename}"
    gcs_uri, size, was_uploaded = _ensure_uploaded(bucket, gcs_name, payload)
    log.info("    %s  %s  (%d bytes)", "UPLOADED" if was_uploaded else "EXISTS", gcs_uri, size)
    return {
        "gcs_uri": gcs_uri,
        "pdf_filename": filename,
        "title": doc["title"],
        "source": "osti",
        "osti_id": doc["osti_id"],
        "assignee_or_publisher": doc["publisher"],
        "year": doc["year"],
        "applies_to_canonical_ids": doc["applies_to"],
        "source_url": url,
        "size_bytes": size,
    }


def main() -> int:
    with ANCHORS_IN.open() as f:
        patents = json.load(f)

    client = storage.Client(project=PROJECT)
    bucket = client.bucket(BUCKET)
    if not bucket.exists():
        log.error("bucket gs://%s does not exist — create it first", BUCKET)
        return 2

    manifest: dict[str, dict] = {}
    uploaded_count = 0
    total_bytes = 0

    log.info("=== USPTO patents ===")
    for i, canonical_id in enumerate(PATENT_PICKS_CANONICAL):
        if canonical_id not in patents:
            log.warning("  %s: not in uspto_patents.json — skipping", canonical_id)
            continue
        entry = _process_patent(canonical_id, patents[canonical_id], bucket)
        if entry:
            manifest[canonical_id] = entry
            uploaded_count += 1
            total_bytes += entry["size_bytes"]
        # Respect USPTO/Google's rate limits between patent fetches.
        if i < len(PATENT_PICKS_CANONICAL) - 1:
            time.sleep(1.0)

    log.info("\n=== Equinor docs ===")
    for doc in EQUINOR_DOCS:
        entry = _process_equinor(doc, bucket)
        if entry:
            manifest[doc["key"]] = entry
            uploaded_count += 1
            total_bytes += entry["size_bytes"]
        time.sleep(1.0)

    log.info("\n=== OSTI.GOV docs ===")
    for doc in OSTI_DOCS:
        entry = _process_osti(doc, bucket)
        if entry:
            manifest[doc["key"]] = entry
            uploaded_count += 1
            total_bytes += entry["size_bytes"]
        time.sleep(1.0)

    CORPUS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_OUT.open("w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info("\n=== summary ===")
    log.info(
        "uploaded/processed %d PDFs, total %d bytes (%.1f MB)",
        uploaded_count,
        total_bytes,
        total_bytes / (1024 * 1024),
    )
    log.info("wrote manifest -> %s", CORPUS_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
