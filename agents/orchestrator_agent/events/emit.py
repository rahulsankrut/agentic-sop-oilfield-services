"""Helper to append canvas events to Workflow session state.

Workflow nodes call :func:`emit` to record a canvas event. The function
returns a ``state_delta`` dict shaped for ADK 2.0's ``Event(state=...)``
kwarg, which the framework merges into ``ctx.actions.state_delta``.

The canvas consumes the Orchestrator's deployed ``streamQuery`` REST
endpoint (driven by ``AdkApp.async_stream_query``). Each ADK ``Event``
yielded by the Runner carries ``event.actions.state_delta`` —
``canvas_events`` lives there, and the canvas SSE client
(``canvas/src/lib/agent-stream.ts``) drains new entries off each chunk.

Usage (function node)::

    async def my_node(node_input: dict, ctx: Context) -> Event:
        evt = NodeStartedEvent(workflow_id=..., session_id=..., ...)
        return Event(
            output=...,
            state=emit(ctx, evt),
            message="Starting my_node",
        )

For nodes that emit multiple events, accumulate by merging::

    state = emit(ctx, start_evt)
    state = {**state, **emit(ctx, mcp_started_evt)}
    # The second call reads ctx.state which is now stale relative to the
    # in-flight node, so we additionally splice in the prior canvas_events
    # list manually — see parallel_queries.py for the pattern.
"""

from __future__ import annotations

from typing import Any

from google.adk import Context

from .canvas_events import CanvasEvent


def emit(ctx: Context, event: CanvasEvent) -> dict[str, Any]:
    """Append a canvas event to session state. Returns a state delta.

    The returned dict is suitable for ``Event(state=...)``. The framework
    merges it into the session's state delta; the A2A executor then
    picks up new entries and forwards them on the SSE stream.
    """
    existing: list[Any] = []
    if hasattr(ctx, "state"):
        try:
            existing = list(ctx.state.get("canvas_events", []) or [])
        except Exception:
            existing = []
    return {"canvas_events": [*existing, event.model_dump(mode="json")]}


def emit_a2ui(ctx: Context, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Append an A2UI v0.8 ServerToClientMessage batch to session state.

    TASK-45 Phase 2 — agent-emitted A2UI surfaces (KC drawer, cost rollup,
    audit panels). The canvas SSE client drains ``a2ui_envelopes`` from
    each ``state_delta`` and hands the messages to ``A2UIProvider.
    processMessages()`` so the right surface renders client-side.

    ``messages`` is what ``agents/utils/a2ui.message_batch(...)`` returns
    (a list of ``surfaceUpdate`` + ``beginRendering`` envelopes per the
    v0.8 schema).
    """
    existing: list[Any] = []
    if hasattr(ctx, "state"):
        try:
            existing = list(ctx.state.get("a2ui_envelopes", []) or [])
        except Exception:
            existing = []
    return {"a2ui_envelopes": [*existing, *messages]}
