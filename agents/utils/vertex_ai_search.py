"""Vertex AI Search (Discovery Engine) retrieval helper — TASK-16 Phase 3.

Thin wrapper around ``discoveryengine_v1.SearchServiceClient`` that returns
LLM-friendly citation dicts. Used by the Orchestrator's `deep-research`
skill and the Procurement Approval agent's `regulatory-precedents` skill.

The deployed Reasoning Engine inherits the engine IDs via env vars
(plumbed by every ``deploy.py`` since commit cf50a3c):

    DISCOVERY_ENGINE_PROJECT, DISCOVERY_ENGINE_LOCATION,
    BSEE_ENGINE_ID, MCC_ENGINE_ID, INTOUCH_ENGINE_ID

Returns ``list[dict]`` (not Pydantic) so the values pass cleanly through
ADK's ``FunctionTool`` JSON-schema layer without forcing the LLM through
a Pydantic round-trip.
"""

from __future__ import annotations

import html
import logging
import os
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Strip the <b>...</b> highlight tags Discovery Engine wraps query terms
# in — the LLM doesn't need HTML, and they make snippets harder to parse.
_HIGHLIGHT_RE = re.compile(r"</?b>", re.IGNORECASE)


@lru_cache(maxsize=1)
def _client() -> Any:
    """Lazily construct and cache the SearchServiceClient.

    Lazy because the import drags in the full discoveryengine_v1 client
    surface; we don't want it loaded at agent-module-import time.
    """
    from google.cloud import discoveryengine_v1  # noqa: PLC0415

    return discoveryengine_v1.SearchServiceClient()


def _serving_config(engine_id: str) -> str:
    """Build the fully-qualified serving-config resource name."""
    project = os.environ.get("DISCOVERY_ENGINE_PROJECT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    location = os.environ.get("DISCOVERY_ENGINE_LOCATION", "global")
    if not project:
        raise ValueError(
            "DISCOVERY_ENGINE_PROJECT (or GOOGLE_CLOUD_PROJECT) must be set"
        )
    return (
        f"projects/{project}/locations/{location}/collections/default_collection/"
        f"engines/{engine_id}/servingConfigs/default_search"
    )


def _clean(text: str) -> str:
    """Strip <b> highlight tags + decode HTML entities (&nbsp;, &gt;, …)."""
    return html.unescape(_HIGHLIGHT_RE.sub("", text)).strip()


def _normalize_result(raw: Any) -> dict[str, Any]:
    """Project a `SearchResponse.SearchResult` into an LLM-friendly dict.

    Pulls out the fields the calling LLM actually needs to cite:
    document_id, title, uri, snippet (best 1), extractive_segment (best 1).

    ``derived_struct_data`` arrives as a ``proto.marshal.collections.MapComposite``
    (not a ``dict``), and each element of the snippets/segments lists is the
    same MapComposite type. Both expose ``.get()`` so we use duck-typing
    rather than ``isinstance(_, dict)`` (which would fail).
    """
    doc = raw.document
    derived = doc.derived_struct_data or {}
    snippets: list[str] = []
    for s in derived.get("snippets") or []:
        text = (s.get("snippet", "") or "") if hasattr(s, "get") else ""
        if text:
            snippets.append(_clean(text))
    segments: list[str] = []
    for s in derived.get("extractive_segments") or []:
        text = (s.get("content", "") or "") if hasattr(s, "get") else ""
        if text:
            segments.append(_clean(text))
    return {
        "document_id": doc.name.rsplit("/", 1)[-1],
        "title": derived.get("title") or "",
        "uri": derived.get("link") or "",
        "snippet": snippets[0] if snippets else "",
        "extractive_segment": segments[0] if segments else "",
    }


def search_engine(
    engine_id: str,
    query: str,
    page_size: int = 5,
) -> list[dict[str, Any]]:
    """Query a Discovery Engine search app and return normalized citations.

    Returns a list of dicts shaped::

        {
            "document_id": "<hash>",
            "title": "Accident Investigation Report",
            "uri": "gs://.../path.pdf",
            "snippet": "... query terms in context ...",
            "extractive_segment": "First clean paragraph from the doc.",
        }

    On API errors the function logs and returns ``[]`` rather than
    raising — the LLM gets "no results" and can degrade gracefully rather
    than blowing up the workflow.
    """
    if not engine_id:
        logger.warning("vertex_ai_search.search_engine called with empty engine_id")
        return []
    if not query or not query.strip():
        return []

    from google.cloud import discoveryengine_v1 as de  # noqa: PLC0415

    request = de.SearchRequest(
        serving_config=_serving_config(engine_id),
        query=query.strip(),
        page_size=page_size,
        content_search_spec=de.SearchRequest.ContentSearchSpec(
            snippet_spec=de.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True,
            ),
            extractive_content_spec=de.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_segment_count=1,
            ),
        ),
    )
    try:
        response = _client().search(request)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "vertex_ai_search: engine=%s query=%r failed: %s", engine_id, query, e
        )
        return []
    return [_normalize_result(r) for r in response.results]


# Convenience wrappers — every skill calls these by name rather than
# threading engine IDs through the LLM. The engine env var lookup happens
# at call time so a missing var produces an empty-result no-op rather than
# an import-time crash.


def search_bsee_incidents(query: str, page_size: int = 5) -> list[dict[str, Any]]:
    """Search BSEE offshore incident investigations (safety + regulatory)."""
    return search_engine(os.environ.get("BSEE_ENGINE_ID", ""), query, page_size)


def search_mcc_contracts(query: str, page_size: int = 5) -> list[dict[str, Any]]:
    """Search OFS Master Service Agreements (SEC EDGAR filings)."""
    return search_engine(os.environ.get("MCC_ENGINE_ID", ""), query, page_size)


def search_intouch_specs(query: str, page_size: int = 5) -> list[dict[str, Any]]:
    """Search OFS technical specs (USPTO patents + Volve + OSTI reports)."""
    return search_engine(os.environ.get("INTOUCH_ENGINE_ID", ""), query, page_size)


__all__ = [
    "search_engine",
    "search_bsee_incidents",
    "search_mcc_contracts",
    "search_intouch_specs",
]
