"""Load + index the TASK-17 unstructured-corpus manifests.

For each of the three corpora (BSEE incidents / SEC MCC contracts /
InTouch specs) this module loads the JSON manifest (committed under
`data/anchors/*_corpus.json`) and exposes lookup helpers the skill
tools call when attaching citations to their structured outputs.

These helpers are deliberately decoupled from Vertex AI Search — they
return the GCS URI + a one-line metadata snippet from the manifest. If
Vertex AI Search is set up + the agent has the right IAM, a higher
layer (Vertex AI Search MCP) can run a semantic query over the PDFs
themselves and return richer snippets. The skill-tool citation always
works regardless.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ANCHORS = _REPO_ROOT / "data" / "anchors"


@lru_cache(maxsize=1)
def _bsee_manifest() -> dict:
    p = _ANCHORS / "bsee_corpus.json"
    return json.loads(p.read_text()) if p.exists() else {}


@lru_cache(maxsize=1)
def _mcc_manifest() -> dict:
    p = _ANCHORS / "sec_edgar_corpus.json"
    return json.loads(p.read_text()) if p.exists() else {}


@lru_cache(maxsize=1)
def _intouch_manifest() -> dict:
    p = _ANCHORS / "intouch_corpus.json"
    return json.loads(p.read_text()) if p.exists() else {}


def intouch_citation_for(canonical_id: str) -> dict | None:
    """Return one matching intouch_corpus entry for a canonical_id, or None.

    The intouch_corpus manifest entries have either a canonical_id as their
    key (USPTO patent-anchored docs) or a freeform key (Equinor / OSTI
    docs) with an `applies_to_canonical_ids` list. Prefer the direct-keyed
    entry; fall back to the first freeform entry that lists the canonical_id.
    """
    manifest = _intouch_manifest()
    direct = manifest.get(canonical_id)
    if direct:
        return _format_citation("intouch", canonical_id, direct)
    for key, entry in manifest.items():
        if canonical_id in (entry.get("applies_to_canonical_ids") or []):
            return _format_citation("intouch", key, entry)
    return None


def bsee_citation_for_keyword(keyword: str) -> dict | None:
    """Return one BSEE incident citation matching a keyword (case-insensitive).

    Used by the plan_evaluator's safety_compliance criterion to ground in a
    real near-miss / safety incident matching the asset class or scenario
    keyword (e.g. "crane" → crane-incident report).
    """
    needle = keyword.lower()
    for incident_id, entry in _bsee_manifest().items():
        haystack = " ".join(str(v) for v in (entry.get("keywords") or [])).lower()
        title = (entry.get("title") or "").lower()
        accident_type = (entry.get("accident_type") or "").lower()
        if needle in haystack or needle in title or needle in accident_type:
            return _format_citation("bsee", incident_id, entry)
    return None


def bsee_citation_for_lease(lease_number: str) -> dict | None:
    """Exact lease-number match (best-effort; many incident-WO anchors
    don't share leases with our 12 corpus PDFs — falls through to None)."""
    if not lease_number:
        return None
    for incident_id, entry in _bsee_manifest().items():
        if (entry.get("lease_number") or "").strip() == lease_number.strip():
            return _format_citation("bsee", incident_id, entry)
    return None


def mcc_citation_for_customer(
    customer_cik: str | None, contract_type_pref: str | None = None
) -> dict | None:
    """Return one MCC contract citation matching a customer's CIK if
    available; else fall back to a representative MSA from the manifest."""
    manifest = _mcc_manifest()
    cik = (customer_cik or "").lstrip("0") or None
    pref = (contract_type_pref or "").upper()
    if cik:
        for key, entry in manifest.items():
            if (entry.get("filer_cik") or "").lstrip("0") == cik:
                return _format_citation("mcc", key, entry)
    # Fallback by contract type preference
    for key, entry in manifest.items():
        if pref and (entry.get("contract_type") or "").upper() == pref:
            return _format_citation("mcc", key, entry)
    # Final fallback — any entry
    if manifest:
        first_key = next(iter(manifest))
        return _format_citation("mcc", first_key, manifest[first_key])
    return None


def _format_citation(corpus: str, key: str, entry: dict) -> dict:
    """Normalize a manifest entry into the shape consumed by the Citation
    Pydantic schema and the canvas citation chips."""
    title = entry.get("title") or entry.get("contract_title") or entry.get("pdf_filename") or key
    return {
        "corpus": corpus,
        "doc_id": key,
        "doc_uri": entry.get("gcs_uri"),
        "title": title,
        "publisher": (
            entry.get("assignee_or_publisher")
            or entry.get("filer_name")
            or entry.get("panel_district")
            or entry.get("source")
            or ""
        ),
        "year": entry.get("year") or entry.get("filing_year") or entry.get("incident_year") or 0,
    }
