"""Build the `mcc_contracts/` corpus in
`gs://oilfield-services-unstructured/` from real SEC EDGAR filings.

TASK-17 — unstructured pillar, customer-contracts slice.

Source: SEC EDGAR Archives. Every file is a real Master Service
Agreement (MSA), Master Field Services Agreement (MFSA), or amendment
filed by an OFS-relevant SEC registrant — split roughly between:

  - Service-buying operators (Diamondback, SandRidge, Murphy, etc.) —
    the MSAs they sign with contractors. Lives in the contract from
    the operator's side.
  - OFS service vendors (Mammoth Energy, NOV / DNOW, Patterson UTI,
    Seventy Seven Energy, Hyperdynamics) — the MSA templates they
    propose to their customers.

The corpus seeds the `oilfield-mcc-contracts` Vertex AI Search data
store (TASK-17). When a customer substitutes their own contract corpus
they re-point the data store at their own GCS bucket; this seed gives
the demo something real to ground on out of the box.

URL pattern:
  https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_no_dashes}/{primaryDocument}

SEC fair-use requires a descriptive User-Agent. We sleep 1s between
fetches.

Run:
  venv-deploy-310/bin/python scripts/build_sec_edgar_corpus.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from google.cloud import storage

ROOT = Path(__file__).resolve().parent.parent
ANCHOR_OUT = ROOT / "data" / "anchors" / "sec_edgar_corpus.json"

GCS_PROJECT = "vertex-ai-demos-468803"
GCS_BUCKET = "oilfield-services-unstructured"
GCS_PREFIX = "mcc_contracts/"

SEC_UA = "agentic-sop-oilfield-services rahulsankrut@gmail.com"
SLEEP_BETWEEN_FETCHES_S = 1.0

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Curated corpus.
#
# Each entry is a real SEC EDGAR Archive URL pointing at a Master
# Service Agreement, Master Field Services Agreement, MSA letter, or
# MSA amendment. Curated 2026-05-20 from:
#   - EDGAR full-text search (efts.sec.gov), queries:
#       "Master Service Agreement" oilfield  forms=10-K,10-Q,8-K,S-1
#       "Master Field Services Agreement"     forms=10-K,10-Q,8-K,S-1
#       "Master Services Agreement" oilfield services
#   - Operators picked from the seven curated CIKs in
#     `data/anchors/sec_edgar_customers.json` plus public-record OFS
#     operators (SandRidge, Berry, Patterson UTI, Seventy Seven, etc.)
#     where they had filed an MSA exhibit directly.
#
# All URLs verified with HTTP 200 and a substantive content-length
# (≥10 KB) on 2026-05-20.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContractSource:
    """One contract filing to download + upload."""

    accession_number: str  # SEC accession (10-18 numeric, hyphenated)
    primary_document: str  # filename in the archive
    filer_cik: str  # 10-digit string for the API; converted to int for URL
    filer_name: str
    filing_year: int
    contract_title: str  # human-readable contract title
    contract_type: str  # "MSA" | "MFSA" | "MSA-amendment" | "MSA-letter"
    side: str  # "operator" (service buyer) | "vendor" (OFS service vendor)
    keywords: list[str]

    @property
    def url(self) -> str:
        cik_int = int(self.filer_cik)
        accession_nodash = self.accession_number.replace("-", "")
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_int}/{accession_nodash}/{self.primary_document}"
        )

    @property
    def filename(self) -> str:
        """Stable filename in GCS — derived from filer + accession."""
        safe_filer = (
            self.filer_name.lower()
            .replace(",", "")
            .replace(".", "")
            .replace("/", "-")
            .replace(" ", "-")
        )
        # primary_document already has an extension (.htm/.html/.pdf)
        ext = Path(self.primary_document).suffix.lower() or ".htm"
        if ext == ".htm":
            ext = ".html"  # Vertex AI Search prefers .html
        return f"{safe_filer}__{self.accession_number}__{self.contract_type}{ext}"

    @property
    def gcs_uri(self) -> str:
        return f"gs://{GCS_BUCKET}/{GCS_PREFIX}{self.filename}"


CORPUS: list[ContractSource] = [
    # ------------------------------------------------------------------
    # OPERATOR-SIDE MSAs (service buyers)
    # ------------------------------------------------------------------
    # 1. Diamondback Energy (FANG, CIK 1539838) — MFSA with Bison Drilling.
    #    Operator from `sec_edgar_customers.json` (permian-fields anchor).
    ContractSource(
        accession_number="0001193125-13-033148",
        primary_document="d466231dex102.htm",
        filer_cik="0001539838",
        filer_name="Diamondback Energy Inc",
        filing_year=2013,
        contract_title="Master Field Services Agreement between Diamondback E&P LLC and Bison Drilling and Field Services LLC",
        contract_type="MFSA",
        side="operator",
        keywords=["Permian", "drilling", "completions", "indemnity", "insurance", "WSIA"],
    ),
    # 2. Diamondback Energy — First Amendment to the MFSA (10-K exhibit).
    ContractSource(
        accession_number="0001539838-13-000004",
        primary_document="dbex10351stamendmenttomast.htm",
        filer_cik="0001539838",
        filer_name="Diamondback Energy Inc",
        filing_year=2013,
        contract_title="First Amendment to Master Field Services Agreement (Diamondback E&P LLC / Bison Drilling and Field Services LLC)",
        contract_type="MSA-amendment",
        side="operator",
        keywords=["Permian", "amendment", "drilling", "field services"],
    ),
    # 3. SandRidge Energy (CIK 1349436) — operator MSA template (S-1/A
    #    exhibit). SandRidge is a Mid-Continent / Permian operator;
    #    template form contract their contractors sign.
    ContractSource(
        accession_number="0001047469-11-006736",
        primary_document="a2205021zex-10_11.htm",
        filer_cik="0001349436",
        filer_name="SandRidge Energy Inc",
        filing_year=2011,
        contract_title="Master Services Agreement (SandRidge Energy template)",
        contract_type="MSA",
        side="operator",
        keywords=["Mid-Continent", "Permian", "template", "scope of work", "indemnity"],
    ),
    # 4. Bonanza Creek Energy (now Civitas Resources, CIK 1509589 —
    #    8-K/EX-99.1, the news release announces an MSA). Operator side.
    #    NOTE: this is a press release not the contract itself but
    #    contains MSA terms and is the only document from this filer.
    ContractSource(
        accession_number="0001104659-21-032885",
        primary_document="tm218011d3_ex99-1.htm",
        filer_cik="0001509589",
        filer_name="Bonanza Creek Energy Inc",
        filing_year=2021,
        contract_title="Bonanza Creek Energy press release referencing Master Services Agreement",
        contract_type="MSA-letter",
        side="operator",
        keywords=["DJ Basin", "Colorado", "merger", "Civitas"],
    ),
    # 5. Triangle Petroleum (CIK 1281922) — 8-K/EX-99.1 about an MSA.
    #    Bakken operator.
    ContractSource(
        accession_number="0001104659-14-061586",
        primary_document="a14-19182_1ex99d1.htm",
        filer_cik="0001281922",
        filer_name="Triangle Petroleum Corp",
        filing_year=2014,
        contract_title="Triangle Petroleum — disclosure referencing Master Service Agreement (Bakken oilfield services)",
        contract_type="MSA-letter",
        side="operator",
        keywords=["Bakken", "North Dakota", "completions", "press release"],
    ),
    # 6. Hyperdynamics Corp (CIK 937136) — 10-Q EX-10.3, full Master
    #    Service Agreement. International (Guinea-Conakry offshore).
    ContractSource(
        accession_number="0001104659-17-013824",
        primary_document="a16-23818_1ex10d3.htm",
        filer_cik="0000937136",
        filer_name="Hyperdynamics Corp",
        filing_year=2017,
        contract_title="Master Service Agreement — Hyperdynamics (Guinea offshore)",
        contract_type="MSA",
        side="operator",
        keywords=["West Africa", "Guinea", "offshore", "exploration"],
    ),
    # ------------------------------------------------------------------
    # VENDOR-SIDE MSAs (OFS service providers proposing template MSAs)
    # ------------------------------------------------------------------
    # 7. Mammoth Energy Services (TUSK, CIK 1679268) — S-1 EX-10.7,
    #    Master Field Services Agreement (vendor side).
    ContractSource(
        accession_number="0001193125-16-700981",
        primary_document="d222950dex107.htm",
        filer_cik="0001679268",
        filer_name="Mammoth Energy Services Inc",
        filing_year=2016,
        contract_title="Master Field Services Agreement (Mammoth Energy Partners / Gulfport Energy)",
        contract_type="MFSA",
        side="vendor",
        keywords=["pressure pumping", "completion", "Utica", "vendor template"],
    ),
    # 8. Mammoth Energy Services — S-1 EX-10.3, sister MSA.
    ContractSource(
        accession_number="0001193125-16-700981",
        primary_document="d222950dex103.htm",
        filer_cik="0001679268",
        filer_name="Mammoth Energy Services Inc",
        filing_year=2016,
        contract_title="Master Services Agreement (Mammoth Energy Services — Stingray Pressure Pumping)",
        contract_type="MSA",
        side="vendor",
        keywords=["pressure pumping", "Stingray", "completions", "vendor"],
    ),
    # 9. Mammoth Energy Partners LP (CIK 1599613) — S-1 EX-10.17,
    #    Master Field Services Agreement, predecessor entity.
    ContractSource(
        accession_number="0001193125-14-350455",
        primary_document="d753416dex1017.htm",
        filer_cik="0001599613",
        filer_name="Mammoth Energy Partners LP",
        filing_year=2014,
        contract_title="Master Field Services Agreement — Mammoth Energy Partners LP",
        contract_type="MFSA",
        side="vendor",
        keywords=["pressure pumping", "completions", "MLP", "vendor"],
    ),
    # 10. DNOW / National Oilwell Varco (CIK 1599617) — 8-K EX-10.5,
    #     Master Service Agreement between DNOW and NOV (parent–sub
    #     vendor template). NOV is the largest US oilfield equipment
    #     vendor; DNOW is its spinoff.
    ContractSource(
        accession_number="0001193125-14-220143",
        primary_document="d735822dex105.htm",
        filer_cik="0001599617",
        filer_name="DNOW Inc",
        filing_year=2014,
        contract_title="Master Service Agreement — DNOW L.P. / National Oilwell Varco L.P.",
        contract_type="MSA",
        side="vendor",
        keywords=["distribution", "NOV", "equipment", "vendor", "supply"],
    ),
    # 11. Seventy Seven Energy / Chesapeake Oilfield Operating — 10-Q
    #     EX-10.7 (MSA letter agreement with Chesapeake Operating).
    ContractSource(
        accession_number="0001532930-14-000028",
        primary_document="ex107.htm",
        filer_cik="0001532930",
        filer_name="Seventy Seven Energy Inc",
        filing_year=2014,
        contract_title="Master Services Agreement Letter — Seventy Seven Energy / Chesapeake Operating",
        contract_type="MSA-letter",
        side="vendor",
        keywords=["Chesapeake", "drilling", "vendor", "spinoff", "letter"],
    ),
    # 12. Great White Energy Services (CIK 1509696) — S-1/A EX-10.26,
    #     Master Services Agreement template.
    ContractSource(
        accession_number="0001193125-11-172128",
        primary_document="dex1026.htm",
        filer_cik="0001509696",
        filer_name="Great White Energy Services Inc",
        filing_year=2011,
        contract_title="Master Services Agreement — Great White Energy Services (vendor template)",
        contract_type="MSA",
        side="vendor",
        keywords=["pressure pumping", "completions", "vendor", "small-cap"],
    ),
]


# ---------------------------------------------------------------------------
# Fetch + upload
# ---------------------------------------------------------------------------


def _fetch_sec(url: str) -> bytes:
    """Fetch a URL from sec.gov with the required User-Agent."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_UA,
            "Accept": "text/html,application/pdf,*/*",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _upload_to_gcs(
    client: storage.Client,
    bucket: storage.Bucket,
    blob_name: str,
    payload: bytes,
    content_type: str,
) -> bool:
    """Upload payload to gs://bucket/blob_name. Returns True if newly
    uploaded, False if already present."""
    blob = bucket.blob(blob_name)
    if blob.exists(client):
        return False
    blob.upload_from_string(payload, content_type=content_type)
    return True


def _content_type_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


def main() -> int:
    log.info("SEC EDGAR contract corpus loader — %d sources", len(CORPUS))
    log.info("Destination: gs://%s/%s", GCS_BUCKET, GCS_PREFIX)

    client = storage.Client(project=GCS_PROJECT)
    bucket = client.bucket(GCS_BUCKET)
    if not bucket.exists():
        log.error("bucket gs://%s does not exist — aborting", GCS_BUCKET)
        return 1

    manifest: dict[str, dict] = {}
    if ANCHOR_OUT.exists():
        try:
            manifest = json.loads(ANCHOR_OUT.read_text())
            log.info("loaded existing manifest with %d entries", len(manifest))
        except json.JSONDecodeError:
            log.warning("existing manifest at %s is malformed — replacing", ANCHOR_OUT)
            manifest = {}

    uploaded_count = 0
    skipped_count = 0
    failed_count = 0
    total_bytes = 0
    failures: list[tuple[str, str]] = []

    for entry in CORPUS:
        key = entry.accession_number + ":" + entry.primary_document
        blob_name = f"{GCS_PREFIX}{entry.filename}"

        try:
            log.info("→ %s (%s)", entry.filer_name, entry.contract_type)
            log.info("   url: %s", entry.url)
            payload = _fetch_sec(entry.url)
            size = len(payload)
            content_type = _content_type_for(entry.filename)
            newly_uploaded = _upload_to_gcs(client, bucket, blob_name, payload, content_type)
            if newly_uploaded:
                uploaded_count += 1
                total_bytes += size
                log.info("   uploaded %s (%d bytes)", entry.gcs_uri, size)
            else:
                skipped_count += 1
                log.info(
                    "   already present at %s — skipped (%d bytes on remote)", entry.gcs_uri, size
                )
            manifest[key] = {
                "filename": entry.filename,
                "gcs_uri": entry.gcs_uri,
                "contract_title": entry.contract_title,
                "filer_cik": entry.filer_cik,
                "filer_name": entry.filer_name,
                "filing_year": entry.filing_year,
                "contract_type": entry.contract_type,
                "side": entry.side,
                "source_url": entry.url,
                "size_bytes": size,
                "content_type": content_type,
                "keywords": entry.keywords,
            }
        except urllib.error.HTTPError as exc:
            failed_count += 1
            failures.append((entry.url, f"HTTP {exc.code}"))
            log.warning("   FAILED HTTP %s — skipped: %s", exc.code, entry.url)
        except urllib.error.URLError as exc:
            failed_count += 1
            failures.append((entry.url, f"URL {exc.reason}"))
            log.warning("   FAILED URL %s — skipped: %s", exc.reason, entry.url)
        except Exception as exc:  # noqa: BLE001 — defensive: keep going
            failed_count += 1
            failures.append((entry.url, repr(exc)))
            log.warning("   FAILED %r — skipped: %s", exc, entry.url)

        time.sleep(SLEEP_BETWEEN_FETCHES_S)

    ANCHOR_OUT.parent.mkdir(parents=True, exist_ok=True)
    with ANCHOR_OUT.open("w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

    log.info("")
    log.info("=" * 60)
    log.info("Summary:")
    log.info("  uploaded:  %d files (%d bytes)", uploaded_count, total_bytes)
    log.info("  skipped:   %d files already present", skipped_count)
    log.info("  failed:    %d files", failed_count)
    log.info("  manifest:  %s (%d entries total)", ANCHOR_OUT, len(manifest))
    if failures:
        log.info("  failures:")
        for url, reason in failures:
            log.info("    %s — %s", url, reason)
    return 0 if failed_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
