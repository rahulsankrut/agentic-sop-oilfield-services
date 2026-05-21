"""Shared pytest fixtures + autouse offline mocks.

This conftest.py serves the whole ``agents/tests/`` tree, but its autouse
mocks intentionally only fire for **unit** tests (anything not under
``agents/tests/integration/``). The integration tests are skipped by
``pytest.mark.skipif`` when their respective resource-name env vars are
unset; when those env vars ARE set, the tests run against real Agent
Engine / Memory Bank / Sessions endpoints and must not be silently
short-circuited by mocks.

What gets mocked (unit-test scope only):

* ``vertexai.init`` — no-op; avoids ADC discovery during import.
* ``vertexai.Client.__init__`` — no-op; lets code construct the client
  without an authenticated session.
* ``google.genai.Client.__init__`` — no-op; same rationale for the
  ``GlobalGemini`` plumbing.
* ``google.adk.memory.VertexAiMemoryBankService`` methods
  (``add_memory``, ``add_session_to_memory``, ``search_memory``) return
  empty / no-op responses so units that touch the memory service don't
  block on network.
* ``google.adk.sessions.VertexAiSessionService`` methods
  (``create_session``, ``get_session``, ``list_sessions``,
  ``delete_session``) return synthetic-but-shape-correct values.

Anything else (Pydantic schemas, pure-Python skill tools, PromptBuilder,
GlobalGemini location plumbing, the deploy MessageToJson patch) stays
fully real — we want unit failures in those to surface.

Per-test overrides via ``unittest.mock.patch`` still take precedence
inside the patched scope because they patch the same symbol later in
test setup.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Repo root = parent of `agents/`. Exposed for tests that want to locate
# project resources (skill SKILL.md files, fixture data, etc.) without
# hard-coding traversal counts.
REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = Path(__file__).resolve().parent / "integration"


def _is_integration_test(request: pytest.FixtureRequest) -> bool:
    """True iff the test file lives under ``agents/tests/integration/``."""
    try:
        test_path = Path(str(request.node.fspath)).resolve()
    except Exception:
        return False
    try:
        test_path.relative_to(INTEGRATION_DIR)
        return True
    except ValueError:
        return False


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the repository root (parent of ``agents/``)."""
    return REPO_ROOT


# ---------------------------------------------------------------------------
# Autouse offline mocks — unit-test scope only.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_vertexai(request: pytest.FixtureRequest):
    """No-op ``vertexai.init`` + ``vertexai.Client.__init__`` for units.

    Skipped for integration tests so they hit the real Agent Engine.
    """
    if _is_integration_test(request):
        yield
        return

    patches: list[Any] = []
    try:
        import vertexai  # type: ignore[import-not-found]
    except ImportError:
        yield
        return

    init_p = patch.object(vertexai, "init", MagicMock(return_value=None))
    patches.append(init_p)
    init_p.start()

    # vertexai.Client is the modern entry point used by deploy scripts.
    client_cls = getattr(vertexai, "Client", None)
    if client_cls is not None:
        client_init_p = patch.object(client_cls, "__init__", MagicMock(return_value=None))
        patches.append(client_init_p)
        client_init_p.start()

    try:
        yield
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def _mock_genai_client(request: pytest.FixtureRequest):
    """No-op ``google.genai.Client.__init__`` for units.

    ``test_global_gemini`` patches the same symbol via ``unittest.mock.patch``
    as a context manager inside the test body — that nests over this autouse
    fixture cleanly.
    """
    if _is_integration_test(request):
        yield
        return

    try:
        from google import genai  # type: ignore[import-not-found]
    except ImportError:
        yield
        return

    p = patch.object(genai.Client, "__init__", MagicMock(return_value=None))
    p.start()
    try:
        yield
    finally:
        p.stop()


@pytest.fixture(autouse=True)
def _mock_memory_bank_service(request: pytest.FixtureRequest):
    """Stub VertexAiMemoryBankService methods so units don't call out.

    Returns shape-correct empty responses:

    * ``add_memory`` / ``add_session_to_memory`` → ``None``
    * ``search_memory`` → object with ``.memories == []`` (matches the
      ``SearchMemoryResponse`` contract used in
      ``test_memory_bank.py``).
    """
    if _is_integration_test(request):
        yield
        return

    try:
        from google.adk.memory import (  # type: ignore[import-not-found]
            VertexAiMemoryBankService,
        )
    except ImportError:
        yield
        return

    empty_search_response = SimpleNamespace(memories=[])

    patches = [
        patch.object(VertexAiMemoryBankService, "__init__", MagicMock(return_value=None)),
        patch.object(
            VertexAiMemoryBankService,
            "add_memory",
            AsyncMock(return_value=None),
        ),
        patch.object(
            VertexAiMemoryBankService,
            "add_session_to_memory",
            AsyncMock(return_value=None),
        ),
        patch.object(
            VertexAiMemoryBankService,
            "search_memory",
            AsyncMock(return_value=empty_search_response),
        ),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def _mock_session_service(request: pytest.FixtureRequest):
    """Stub VertexAiSessionService methods so units don't call out.

    Returns synthetic-but-shape-correct values:

    * ``create_session`` → fake Session with the requested id.
    * ``get_session`` → fake Session (callers asserting ``None`` for 404
      should override this within the test).
    * ``list_sessions`` → empty list.
    * ``delete_session`` → ``None``.
    """
    if _is_integration_test(request):
        yield
        return

    try:
        from google.adk.sessions import (  # type: ignore[import-not-found]
            VertexAiSessionService,
        )
    except ImportError:
        yield
        return

    def _fake_session(**kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            id=kwargs.get("session_id") or "synthetic-session-id",
            app_name=kwargs.get("app_name") or "synthetic-app",
            user_id=kwargs.get("user_id") or "synthetic-user",
            state={},
            events=[],
        )

    patches = [
        patch.object(VertexAiSessionService, "__init__", MagicMock(return_value=None)),
        patch.object(
            VertexAiSessionService,
            "create_session",
            AsyncMock(side_effect=_fake_session),
        ),
        patch.object(
            VertexAiSessionService,
            "get_session",
            AsyncMock(side_effect=_fake_session),
        ),
        patch.object(
            VertexAiSessionService,
            "list_sessions",
            AsyncMock(return_value=SimpleNamespace(sessions=[])),
        ),
        patch.object(
            VertexAiSessionService,
            "delete_session",
            AsyncMock(return_value=None),
        ),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


@pytest.fixture(autouse=True)
def _mock_mcp_http(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Route agents.utils.mcp_client HTTP calls through FastAPI TestClient.

    Skill tools migrated in TASK-16 Steps 8-11 use `agents.utils.mcp_client`
    helpers that hit the SAP / Maximo / FDP FastAPI backends over HTTP.
    For unit tests we don't want to spin up uvicorn servers; instead we
    monkey-patch the client's two underlying request functions
    (`_do_get`, `_do_post`) to dispatch through a per-backend
    `fastapi.testclient.TestClient` against the in-process app.

    Integration tests (`agents/tests/integration/`) are skipped — they
    hit real Cloud Run / Agent Engine over real HTTP.
    """
    if _is_integration_test(request):
        yield
        return

    # Lazy imports — these modules pull in the BQ client which the earlier
    # autouse fixtures have mocked, so they're cheap.
    try:
        from fastapi.testclient import TestClient  # type: ignore[import-not-found]

        from agents.utils import mcp_client  # noqa: PLC0415
        from mcp_servers.fdp.backend.main import app as fdp_app  # noqa: PLC0415
        from mcp_servers.maximo.backend.main import app as maximo_app  # noqa: PLC0415
        from mcp_servers.sap.backend.main import app as sap_app  # noqa: PLC0415
    except ImportError:
        yield
        return

    clients = {
        mcp_client.SAP_MCP_URL: TestClient(sap_app),
        mcp_client.MAXIMO_MCP_URL: TestClient(maximo_app),
        mcp_client.FDP_MCP_URL: TestClient(fdp_app),
    }

    def _fake_get(base_url: str, path: str, params: dict | None = None):
        client = clients.get(base_url)
        if client is None:
            return None
        resp = client.get(path, params=params or {})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def _fake_post(base_url: str, path: str, payload: dict | None = None):
        client = clients.get(base_url)
        if client is None:
            return None
        resp = client.post(path, json=payload or {})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    monkeypatch.setattr(mcp_client, "_do_get", _fake_get)
    monkeypatch.setattr(mcp_client, "_do_post", _fake_post)
    yield
