"""Run the Orchestrator locally via InMemoryRunner — no Agent Engine deploy.

Usage:
    poetry run python -u scripts/local_run_orchestrator.py
    poetry run python -u scripts/local_run_orchestrator.py "custom prompt"
    LOCAL_MODEL=gemini-3.1-pro-preview LOCAL_MODEL_LOCATION=global \\
        poetry run python -u scripts/local_run_orchestrator.py

Why a separate test model: production is gemini-3.1-pro-preview on the
'global' endpoint, but `global` returns intermittent 502s during this
iteration session. For prompt engineering, gemini-2.5-pro on us-central1
is more stable; instruction-following behaviour transfers.

What's exercised locally:
- LlmAgent + skills (asset-equivalence, sourcing-logistics, enterprise-systems)
  via SkillToolset
- In-process Plan Evaluator AgentTool
- output_schema=SourcingPlan validation
- Whichever model is selected via LOCAL_MODEL / LOCAL_MODEL_LOCATION

Stubbed out locally:
- Procurement Approval A2A (env unset → tools.py skips it)
- Memory Bank (AGENT_ENGINE_ID unset → auto_save_memories no-ops)
- Sessions are in-memory only
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

os.environ.pop("PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME", None)
os.environ.pop("AGENT_ENGINE_ID", None)


DEFAULT_PROMPT = (
    "I need a Tool X variant on site in Luanda, Angola by Friday. "
    "Customer: Gulf Petroleum. Authorization tier: standard. "
    "What are my options?"
)


def _patch_orchestrator_model() -> None:
    """Re-bind ``root_agent.model`` to a regional model for stable iteration."""
    test_model = os.environ.get("LOCAL_MODEL", "gemini-2.5-pro")
    test_location = os.environ.get("LOCAL_MODEL_LOCATION", "us-central1")
    from src.orchestrator_agent.core.agent import root_agent
    from src.utils.global_gemini import GlobalGemini

    root_agent.model = GlobalGemini(model=test_model, location=test_location)
    print(f"[local-test] model={test_model} location={test_location}", flush=True)


async def main(prompt: str) -> None:
    _patch_orchestrator_model()

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from src.orchestrator_agent import root_agent
    from src.schemas import SourcingPlan

    runner = InMemoryRunner(agent=root_agent, app_name="local-orchestrator")
    session = runner.session_service.create_session_sync(
        app_name="local-orchestrator", user_id="local-test"
    )

    print("=" * 70, flush=True)
    print(f"Prompt: {prompt}", flush=True)
    print("=" * 70, flush=True)

    final_text_parts: list[str] = []
    n_calls = 0
    n_resps = 0

    try:
        async for event in runner.run_async(
            user_id="local-test",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        ):
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    args = dict(fc.args or {})
                    print(f"  [CALL] {fc.name}({args})", flush=True)
                    n_calls += 1
                if getattr(part, "function_response", None):
                    fr = part.function_response
                    resp = str(fr.response)[:200]
                    print(f"  [RESP] {fr.name} -> {resp}", flush=True)
                    n_resps += 1
                if getattr(part, "text", None):
                    final_text_parts.append(part.text)
    except Exception as exc:
        print(
            f"\n!! Exception during run: {type(exc).__name__}: {str(exc)[:200]}",
            flush=True,
        )

    full_text = "".join(final_text_parts)
    print(
        f"\nSummary: {n_calls} tool calls, {n_resps} responses, "
        f"final text {len(full_text)} chars",
        flush=True,
    )
    print(f"\nFinal output:\n{full_text[:2500]}", flush=True)

    if full_text.strip().startswith("{"):
        try:
            plan = SourcingPlan.model_validate_json(full_text)
            print("\n✓ Parses as SourcingPlan")
            print(f"  canonical_id: {plan.primary_option.asset.canonical_id}")
            print(f"  source: {plan.primary_option.source_location.label}")
            print(f"  transit_mode: {plan.primary_option.transit_mode}")
            print(f"  cost: ${plan.primary_option.estimated_cost_usd:,}")
            if plan.naive_baseline:
                print(f"  baseline mode: {plan.naive_baseline.transit_mode}")
                print(f"  baseline cost: ${plan.naive_baseline.estimated_cost_usd:,}")
            print(f"  avoided_cost_usd: ${plan.avoided_cost_usd:,}")
        except Exception as exc:
            print(f"\n✗ Failed to parse as SourcingPlan: {exc}")


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    asyncio.run(main(prompt))
