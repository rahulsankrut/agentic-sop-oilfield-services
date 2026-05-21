"""A2A Agent Executor for Procurement Approval Agent.

Handles A2A protocol execution for the Procurement Approval Agent.
"""

import logging
import os

import vertexai
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message
from a2a.utils.errors import ServerError
from google.adk import Runner
from google.genai import types

from .services.memory_manager import create_memory_service
from .services.session_manager import SessionManager, create_session_service

logger = logging.getLogger(__name__)


class ProcurementApprovalExecutor(AgentExecutor):
    """Execute procurement-approval review requests via A2A protocol."""

    def __init__(self):
        self.agent = None
        self.runner = None
        self.session_manager: SessionManager | None = None

    def _init_agent(self) -> None:
        """Lazy initialization of the agent and ADK Runner."""
        if self.agent is None:
            try:
                from procurement_approval_agent.agent import root_agent
            except ImportError:
                from .agent import root_agent

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

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a procurement-approval review request via A2A protocol."""
        if self.agent is None:
            self._init_agent()

        user_id = (
            context.message.metadata.get("user_id")
            if context.message and context.message.metadata
            else "planner_agent"
        )

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not hasattr(context, "current_task") or not context.current_task:
            await updater.submit()

        await updater.start_work()

        plan_data = context.get_user_input()

        if not plan_data:
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message("No plan data provided for review"),
                final=True,
            )
            return

        try:
            await updater.update_status(
                TaskState.working,
                message=new_agent_text_message("Reviewing plan for procurement readiness..."),
            )

            session_id = await self.session_manager.get_or_create_session(
                context_id=context.context_id,
                app_name=getattr(self.runner, "app_name", "procurement_approval_agent"),
                user_id=user_id,
            )

            content = types.Content(role="user", parts=[types.Part(text=plan_data)])

            final_event = None
            async for event in self.runner.run_async(
                session_id=session_id, user_id=user_id, new_message=content
            ):
                if event.is_final_response():
                    final_event = event

            if final_event and final_event.content and final_event.content.parts:
                response_text = ""
                for part in final_event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text
                    # Also check for thought/other attributes if they exist
                    elif hasattr(part, "thought") and part.thought:
                        response_text += part.thought

                if response_text:
                    logger.debug("Captured response text (len=%d)", len(response_text))
                    await updater.add_artifact(
                        [TextPart(text=response_text)],
                        name="result",  # Use 'result' for standard tool satisfaction
                    )
                    await updater.complete()
                    return

            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message("Failed to generate procurement approval"),
                final=True,
            )

        except Exception:
            # Log the full exception + traceback server-side for triage,
            # surface only a sanitized error code to the A2A caller. Raw
            # `str(e)` can include DB query fragments, file paths, or
            # downstream API response bodies. (Code-review HIGH #10.)
            logger.exception("Procurement Approval review failed")
            await updater.update_status(
                TaskState.failed,
                message=new_agent_text_message(
                    "Review failed — check the agent's Cloud Logs for the "
                    f"invocation id ({context.context_id}) for details."
                ),
                final=True,
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel is not supported for this agent."""
        raise ServerError(error=UnsupportedOperationError())
