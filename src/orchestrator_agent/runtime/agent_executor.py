"""A2A Agent Executor for the Capacity Orchestrator Agent.

Bridges the A2A ``message:stream`` SSE endpoint to the underlying ADK 2.0
Workflow. Translates each Workflow ADK ``Event`` into one or more A2A
``Message`` events on the SSE stream so the canvas (and any other A2A
peer) can render the live execution.

Pattern is modeled on ``src/procurement_approval_agent/runtime/agent_
executor.py`` — same lazy Runner init, same session_manager wiring — with
an additional canvas-event drain on the ``state_delta`` stream.

Canvas-event protocol contract:
- Workflow nodes append to ``ctx.state['canvas_events']`` via
  :func:`src.orchestrator_agent.events.emit.emit`.
- On each ADK ``Event`` emitted by ``Runner.run_async``, we look at
  ``event.actions.state_delta['canvas_events']`` for new entries beyond
  the last index we forwarded, and push each new entry as a
  ``new_agent_text_message(json.dumps(...))`` to the A2A event queue.
- On the final ADK event, we emit a completion text message + complete
  the A2A task with the final artifact.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import vertexai
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from google.adk import Runner
from google.genai import types

from ..events.canvas_events import WorkflowStartedEvent
from ..services.memory_manager import create_memory_service
from ..services.session_manager import SessionManager, create_session_service

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """ISO-8601 UTC timestamp matching ``BaseEvent.timestamp`` formatting."""
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class CapacityOrchestratorExecutor(AgentExecutor):
    """Execute orchestrator requests via A2A protocol, streaming canvas events.

    Features:
    - VertexAI Session Service for persistent conversation history
    - Memory Bank integration for cross-session learning
    - TTL-based session caching to map A2A context_id → Vertex AI session_id
    - Per-Workflow-event canvas-event drain that pushes the queued canvas
      events out as A2A Messages on the SSE stream
    """

    def __init__(self):
        self.agent = None
        self.runner = None
        self.session_manager: SessionManager | None = None

    def _init_agent(self) -> None:
        """Lazy initialization of the agent and ADK Runner."""
        if self.agent is None:
            try:
                from orchestrator_agent.agent import root_agent
            except ImportError:
                from ..core.agent import root_agent

            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
                "GOOGLE_CLOUD_LOCATION", "us-central1"
            )

            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT environment variable required")

            vertexai.init(project=project_id, location=location)
            self.agent = root_agent

        if self.runner is None:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
            location = os.environ.get("AGENT_ENGINE_LOCATION") or os.environ.get(
                "GOOGLE_CLOUD_LOCATION", "us-central1"
            )
            agent_engine_id = os.environ.get("AGENT_ENGINE_ID")

            logger.debug(
                "Initializing runner project=%s location=%s agent_engine_id=%s",
                project_id,
                location,
                agent_engine_id,
            )

            session_service = create_session_service(
                project=project_id,
                location=location,
            )

            memory_service = create_memory_service(
                project=project_id,
                location=location,
            )

            from google.adk.agents.context_cache_config import ContextCacheConfig
            from google.adk.apps import App

            app = App(
                name=self.agent.name,
                root_agent=self.agent,
                context_cache_config=ContextCacheConfig(
                    cache_intervals=10,
                    ttl_seconds=3600,
                    min_tokens=4096,
                ),
            )

            self.runner = Runner(
                app=app,
                session_service=session_service,
                memory_service=memory_service,
            )

        if self.session_manager is None:
            self.session_manager = SessionManager(
                session_service=self.runner.session_service,
                cache_maxsize=1000,
                cache_ttl=3600,
            )

    async def _drain_canvas_events(
        self,
        adk_event: Any,
        event_queue: EventQueue,
        last_emitted: int,
    ) -> int:
        """Forward newly-appended canvas events to the A2A event queue.

        Returns the new value of ``last_emitted`` (i.e., total events seen).
        """
        try:
            actions = getattr(adk_event, "actions", None)
            state_delta = getattr(actions, "state_delta", None) if actions else None
        except Exception:
            state_delta = None

        if not state_delta:
            return last_emitted

        canvas_events = state_delta.get("canvas_events") if isinstance(state_delta, dict) else None
        if not canvas_events:
            return last_emitted

        for evt in canvas_events[last_emitted:]:
            try:
                payload = json.dumps(evt, default=str)
            except Exception as exc:
                logger.warning("Failed to JSON-encode canvas event: %s", exc)
                continue
            try:
                await event_queue.enqueue_event(new_agent_text_message(text=payload))
            except Exception as exc:
                logger.warning("Failed to enqueue canvas event: %s", exc)
        return len(canvas_events)

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute an orchestrator request via A2A protocol.

        Streams canvas events as they're emitted by the underlying Workflow,
        then completes the A2A task with the final sourcing-plan artifact.
        """
        if self.agent is None:
            self._init_agent()

        user_id = (
            context.message.metadata.get("user_id")
            if context.message and context.message.metadata
            else "orchestrator_user"
        )

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not hasattr(context, "current_task") or not context.current_task:
            await updater.submit()

        await updater.start_work()

        request_data = context.get_user_input()

        if not request_data:
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message("No request data provided"),
                final=True,
            )
            return

        try:
            from google.adk.agents.run_config import ToolThreadPoolConfig
            from google.adk.runners import RunConfig
            from google.genai.types import ContextWindowCompressionConfig

            await updater.update_status(
                TaskState.working,
                message=new_agent_text_message("Resolving capacity gap..."),
            )

            app_name = getattr(self.runner, "app_name", "capacity_orchestrator_agent")
            session_id = await self.session_manager.get_or_create_session(
                context_id=context.context_id,
                app_name=app_name,
                user_id=user_id,
            )

            # Seed the session with workflow_id / session_id / start time so
            # canvas events can carry consistent identifiers and finalize()
            # can compute duration. We do this by pushing an initial state
            # delta carrying a WorkflowStartedEvent — the executor's drain
            # picks it up and forwards on the SSE stream just like any
            # other canvas event.
            workflow_id = uuid.uuid4().hex
            started_at = datetime.utcnow()
            workflow_started = WorkflowStartedEvent(
                workflow_id=workflow_id,
                session_id=session_id,
                # The canvas dispatches on scenario; the orchestrator only
                # serves the cargo-plane scenario today. Buffer-planning is
                # owned by the capacity_planning_agent.
                scenario="cargo-plane",
                user_id=user_id,
                initial_context={"request_excerpt": request_data[:512]},
            )

            # Push the WorkflowStartedEvent and seed-state to session state
            # by directly appending via the session service so the first
            # Workflow node sees them on ctx.state.
            try:
                session = await self.runner.session_service.get_session(
                    app_name=app_name,
                    user_id=user_id,
                    session_id=session_id,
                )
                if session is not None:
                    seed_state = dict(getattr(session, "state", {}) or {})
                    existing_events = list(seed_state.get("canvas_events", []) or [])
                    seed_state["workflow_id"] = workflow_id
                    seed_state["session_id"] = session_id
                    seed_state["workflow_started_at"] = started_at.isoformat()
                    seed_state["canvas_events"] = [
                        *existing_events,
                        workflow_started.model_dump(mode="json"),
                    ]
                    try:
                        # Best-effort write — sessions services vary in API.
                        # If direct mutation isn't supported the state delta
                        # from the first node will still seed the chain via
                        # state_delta merging.
                        session.state.update(seed_state)
                    except Exception:
                        pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to seed session state for canvas events: %s", exc)

            # Surface the WorkflowStartedEvent immediately so the canvas
            # gets a clear start signal regardless of session-service quirks.
            try:
                await event_queue.enqueue_event(
                    new_agent_text_message(
                        text=json.dumps(workflow_started.model_dump(mode="json"), default=str)
                    )
                )
            except Exception as exc:
                logger.warning("Failed to enqueue WorkflowStartedEvent: %s", exc)

            content = types.Content(role="user", parts=[types.Part(text=request_data)])

            final_event = None
            # The seeded WorkflowStartedEvent is index 0; downstream nodes
            # append after it. last_emitted=1 means "the first event the
            # workflow emits goes out next".
            last_emitted = 1
            async for event in self.runner.run_async(
                session_id=session_id,
                user_id=user_id,
                new_message=content,
                run_config=RunConfig(
                    tool_thread_pool_config=ToolThreadPoolConfig(max_workers=4),
                    max_llm_calls=15,
                    context_window_compression=ContextWindowCompressionConfig(),
                ),
            ):
                last_emitted = await self._drain_canvas_events(
                    event, event_queue, last_emitted
                )
                if event.is_final_response():
                    final_event = event

            if final_event and final_event.content and final_event.content.parts:
                response_text = "".join(
                    part.text
                    for part in final_event.content.parts
                    if hasattr(part, "text") and part.text
                )

                if response_text:
                    await updater.add_artifact(
                        [TextPart(text=response_text)],
                        name="sourcing_plan",
                    )
                    await updater.complete()
                    return

            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message("Failed to generate sourcing plan"),
                final=True,
            )

        except Exception as e:  # noqa: BLE001
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(f"Resolution failed: {e!s}"),
                final=True,
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel is not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())


# Backwards-compat alias — local_server.py / test_client.py / other
# integrations may still import the old name. New code (deploy.py) uses
# the canonical ``CapacityOrchestratorExecutor`` per the TASK-10 spec.
OrchestratorExecutor = CapacityOrchestratorExecutor
