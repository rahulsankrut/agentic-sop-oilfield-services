/**
 * Stub server route for Persona 4's "Run Live" path.
 *
 * Deep Research Agent is a Gemini Enterprise feature. When it's provisioned
 * in the project's tenant the implementation here replaces the 501 with a
 * real call (see `tasks/TASK-18-persona4-deep-research.md` §1-2). Until
 * then, the route returns a structured 501 so the canvas can surface an
 * honest "not provisioned in this tenant" message rather than simulating a
 * fake research run.
 *
 * Gap-fix locus: this single file. When DRA is reachable:
 *   - Replace the body with a call to the real research endpoint (likely
 *     Gemini Enterprise API or Vertex AI Search Conversation API, depending
 *     on the DRA surface chosen by the tenant)
 *   - Stream the research plan + section assembly events back as NDJSON
 *   - Resolve `parsed` on the client to a structured briefing payload
 *
 * Until then, the front-end falls back to the pre-authored seeded briefing.
 */

import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(): Promise<Response> {
  // Honest 501: no fake research output. The front-end interprets this
  // status as "not provisioned" and keeps the seeded briefing visible.
  return NextResponse.json(
    {
      ok: false,
      provisioned: false,
      reason:
        "Deep Research Agent is not wired in this tenant. The scenario is rendering the pre-authored briefing seeded from real source data; the structured shape is identical to what a live run would return.",
      hint: "Set DEEP_RESEARCH_AGENT_URL + matching credentials in .env, then implement the live call in canvas/src/app/api/deep-research/run/route.ts.",
    },
    { status: 501 },
  );
}
