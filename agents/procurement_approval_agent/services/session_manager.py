"""Session Manager for Procurement Approval Agent.

Manages session lifecycle with TTL-based caching for A2A context mapping.
"""

import os
import time
from typing import Any

from google.adk.sessions import InMemorySessionService, VertexAiSessionService


class TTLCache:
    """Simple TTL cache for mapping A2A context_id to Vertex AI session_id."""

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        if len(self._cache) >= self._maxsize:
            self._evict_oldest()
        self._cache[key] = (value, time.time())

    def _evict_oldest(self) -> None:
        if not self._cache:
            return
        sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])
        evict_count = max(1, len(sorted_keys) // 10)
        for key in sorted_keys[:evict_count]:
            del self._cache[key]

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self._cleanup_expired()
        return len(self._cache)

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items() if now - timestamp >= self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]


def create_session_service(
    project: str | None = None,
    location: str | None = None,
    agent_engine_id: str | None = None,
    use_vertex: bool | None = None,
) -> VertexAiSessionService | InMemorySessionService:
    """Create appropriate session service based on environment.

    Returns:
        VertexAiSessionService for production, InMemorySessionService for local dev.
    """
    project = project or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = location or (
        os.environ.get("AGENT_ENGINE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    agent_engine_id = agent_engine_id or os.environ.get("AGENT_ENGINE_ID")

    if use_vertex is None:
        use_vertex = agent_engine_id is not None

    if use_vertex:
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable required")
        return VertexAiSessionService(
            project=project,
            location=location,
            agent_engine_id=agent_engine_id,
        )
    else:
        return InMemorySessionService()


class SessionManager:
    """Manages sessions with A2A context mapping and TTL caching."""

    def __init__(
        self,
        session_service: VertexAiSessionService | InMemorySessionService | None = None,
        cache_maxsize: int = 1000,
        cache_ttl: int = 3600,
    ):
        self.session_service = session_service or create_session_service()
        self.session_cache = TTLCache(maxsize=cache_maxsize, ttl=cache_ttl)

    async def get_or_create_session(
        self,
        context_id: str,
        app_name: str,
        user_id: str,
    ) -> str:
        cached_session_id = self.session_cache.get(context_id)
        if cached_session_id:
            return cached_session_id

        session = await self.session_service.create_session(
            app_name=app_name,
            user_id=user_id,
        )
        self.session_cache.set(context_id, session.id)
        return session.id

    def get_session_id(self, context_id: str) -> str | None:
        return self.session_cache.get(context_id)

    def cache_session(self, context_id: str, session_id: str) -> None:
        self.session_cache.set(context_id, session_id)
