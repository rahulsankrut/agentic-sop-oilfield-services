"""Unit tests for `agents.utils.vertex_ai_search` (TASK-16 Phase 3).

Mocks the Discovery Engine SearchServiceClient so the tests are hermetic
(no live API calls). The real-API smoke test was done at module-write time
and lives in the deploy verification script, not the unit suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.utils import vertex_ai_search


@pytest.fixture(autouse=True)
def _reset_client_cache():
    """Each test starts with an empty SearchServiceClient cache."""
    vertex_ai_search._client.cache_clear()
    yield
    vertex_ai_search._client.cache_clear()


@pytest.fixture
def _engine_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DISCOVERY_ENGINE_PROJECT", "test-project")
    monkeypatch.setenv("DISCOVERY_ENGINE_LOCATION", "global")
    monkeypatch.setenv("BSEE_ENGINE_ID", "bsee-engine")
    monkeypatch.setenv("MCC_ENGINE_ID", "mcc-engine")
    monkeypatch.setenv("INTOUCH_ENGINE_ID", "intouch-engine")


def _make_fake_result(
    *,
    doc_id: str,
    title: str,
    uri: str,
    snippet: str | None = None,
    segment: str | None = None,
):
    """Build a mock SearchResult matching the proto-plus shape we read."""
    doc = MagicMock()
    doc.name = f"projects/x/locations/global/dataStores/y/branches/0/documents/{doc_id}"
    derived: dict = {"title": title, "link": uri}
    if snippet is not None:
        snippet_map = MagicMock()
        snippet_map.get = lambda k, default=None: {
            "snippet": snippet, "snippet_status": "SUCCESS"
        }.get(k, default)
        derived["snippets"] = [snippet_map]
    if segment is not None:
        seg_map = MagicMock()
        seg_map.get = lambda k, default=None: {"content": segment}.get(k, default)
        derived["extractive_segments"] = [seg_map]
    doc.derived_struct_data = derived
    result = MagicMock()
    result.document = doc
    return result


def test_serving_config_format(_engine_env):
    """Serving config resource name must match Discovery Engine convention."""
    name = vertex_ai_search._serving_config("my-engine")
    assert name == (
        "projects/test-project/locations/global/collections/default_collection/"
        "engines/my-engine/servingConfigs/default_search"
    )


def test_serving_config_missing_project_raises(monkeypatch):
    """No project env → explicit ValueError, not a confusing API error."""
    monkeypatch.delenv("DISCOVERY_ENGINE_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError, match="DISCOVERY_ENGINE_PROJECT"):
        vertex_ai_search._serving_config("eid")


def test_serving_config_falls_back_to_gcp_project(monkeypatch):
    """DISCOVERY_ENGINE_PROJECT unset → use GOOGLE_CLOUD_PROJECT."""
    monkeypatch.delenv("DISCOVERY_ENGINE_PROJECT", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fallback-project")
    monkeypatch.setenv("DISCOVERY_ENGINE_LOCATION", "global")
    name = vertex_ai_search._serving_config("eid")
    assert "fallback-project" in name


def test_clean_strips_b_tags_and_entities():
    assert vertex_ai_search._clean("a <b>WORD</b> b") == "a WORD b"
    assert vertex_ai_search._clean("a&nbsp;b") == "a\xa0b"
    assert vertex_ai_search._clean("&gt;$25K") == ">$25K"
    assert vertex_ai_search._clean("  spaced  ") == "spaced"


def test_search_engine_returns_normalized_list(_engine_env):
    """Happy path: API returns 1 doc with snippet+segment, we normalize it."""
    fake_response = MagicMock()
    fake_response.results = [
        _make_fake_result(
            doc_id="abc123",
            title="Accident Investigation Report",
            uri="gs://bucket/doc.pdf",
            snippet="... <b>BLOWOUT</b> at depth ...",
            segment="UNITED STATES DEPARTMENT OF THE INTERIOR.",
        )
    ]
    with patch.object(vertex_ai_search, "_client") as mock_client_factory:
        mock_client_factory.return_value.search.return_value = fake_response
        out = vertex_ai_search.search_engine("bsee-engine", "blowout")
    assert len(out) == 1
    hit = out[0]
    assert hit["document_id"] == "abc123"
    assert hit["title"] == "Accident Investigation Report"
    assert hit["uri"] == "gs://bucket/doc.pdf"
    assert "BLOWOUT" in hit["snippet"]
    assert "<b>" not in hit["snippet"]  # tags stripped
    assert hit["extractive_segment"].startswith("UNITED STATES")


def test_search_engine_handles_missing_snippets(_engine_env):
    """Docs without snippet/segment should still come back with empty strings."""
    fake_response = MagicMock()
    fake_response.results = [
        _make_fake_result(
            doc_id="xyz", title="Bare doc", uri="gs://b/d.pdf",
        )
    ]
    with patch.object(vertex_ai_search, "_client") as mock_client_factory:
        mock_client_factory.return_value.search.return_value = fake_response
        out = vertex_ai_search.search_engine("any-engine", "q")
    assert out == [
        {
            "document_id": "xyz",
            "title": "Bare doc",
            "uri": "gs://b/d.pdf",
            "snippet": "",
            "extractive_segment": "",
        }
    ]


def test_search_engine_empty_engine_id_returns_empty(_engine_env):
    """Empty engine_id → empty list, no API call."""
    with patch.object(vertex_ai_search, "_client") as mock_client_factory:
        out = vertex_ai_search.search_engine("", "q")
    assert out == []
    mock_client_factory.return_value.search.assert_not_called()


def test_search_engine_empty_query_returns_empty(_engine_env):
    """Empty query → empty list, no API call (don't waste a search call)."""
    with patch.object(vertex_ai_search, "_client") as mock_client_factory:
        out = vertex_ai_search.search_engine("e", "   ")
    assert out == []
    mock_client_factory.return_value.search.assert_not_called()


def test_search_engine_api_error_returns_empty(_engine_env, caplog):
    """Transient API errors → log + return []; workflow degrades gracefully."""
    with patch.object(vertex_ai_search, "_client") as mock_client_factory:
        mock_client_factory.return_value.search.side_effect = RuntimeError("503")
        out = vertex_ai_search.search_engine("eid", "q")
    assert out == []
    assert any("503" in r.message for r in caplog.records)


def test_named_wrappers_route_to_correct_engine(_engine_env):
    """Each wrapper passes its env-var-resolved engine ID through to search_engine."""
    captured: list[str] = []

    def fake_search_engine(engine_id, query, page_size=5):
        captured.append(engine_id)
        return []

    with patch.object(vertex_ai_search, "search_engine", side_effect=fake_search_engine):
        vertex_ai_search.search_bsee_incidents("q")
        vertex_ai_search.search_mcc_contracts("q")
        vertex_ai_search.search_intouch_specs("q")

    assert captured == ["bsee-engine", "mcc-engine", "intouch-engine"]


def test_wrapper_with_unset_engine_id_returns_empty(monkeypatch):
    """If the env var isn't set, the wrapper degrades to empty (no crash)."""
    monkeypatch.delenv("BSEE_ENGINE_ID", raising=False)
    # Don't set DISCOVERY_ENGINE_PROJECT either — should still no-op
    monkeypatch.delenv("DISCOVERY_ENGINE_PROJECT", raising=False)
    assert vertex_ai_search.search_bsee_incidents("q") == []
