/**
 * personas.ts
 *
 * Canonical persona registry for the demo runner (TASK-12).
 *
 * As of TASK-13, the persona list is derived from the active customer skin
 * (`skins/<slug>/customer.yaml` → `canvas/src/data/skin.generated.ts`). The
 * launcher at `/demo`, the global rehearsal hotkey handler (`1`..`6`), and
 * the Backstage panel all read this list as the single source of truth.
 * Switching skins re-skins every persona display string here for free.
 *
 * Routing + implementation-status flags stay hardcoded — those are
 * structural facts about the canvas itself (which scenario pages exist),
 * not customer-specific data.
 */

import { getActiveSkin } from "@/lib/skin";
import type { PersonaId } from "@/types/skin";

export type ImplementationStatus =
  | "ready" // full scenario page, live-mode-capable
  | "ready-static" // full scenario page, static beats only
  | "stub"; // route exists but renders a placeholder

export interface Persona {
  /** Stable slug; never displayed. Used for routing fallbacks and analytics. */
  id: PersonaId;
  /** 1-based ordinal — drives the `1`..`6` hotkeys. */
  number: 1 | 2 | 3 | 4 | 5 | 6;
  /** Human-readable name. Skinned per-customer via `customer.yaml`. */
  displayName: string;
  /** Job title with region suffix. Skinned per-customer. */
  role: string;
  /** S&OP stage label — kept short for the tile footer. */
  sopStage: string;
  /** One-sentence scenario summary for the launcher tile. */
  scenarioOneLiner: string;
  /** Route to navigate to when the tile is clicked / hotkeyed. */
  route: string;
  /** Target wall-clock duration for this persona's scenario, in minutes. */
  targetDurationMin: number;
  /** Memory Bank user_id for pre-warm — skinned per-customer. */
  memoryProfileUserId: string;
  /** Pre-seeded Sessions session_id — skinned per-customer. */
  sessionId: string;
  /** Build status — surfaces a small badge on stub tiles. */
  implementationStatus: ImplementationStatus;
}

/**
 * Per-persona routing + implementation-status table. These are structural
 * facts about which scenario pages exist in the canvas, kept here rather
 * than in `customer.yaml` because they describe code, not configuration.
 *
 * When a new scenario page lands, flip the `implementationStatus` and
 * trim the `?status=stub` from the route.
 */
const ROUTING_BY_PERSONA: Record<
  PersonaId,
  { route: string; implementationStatus: ImplementationStatus }
> = {
  david: {
    route: "/scenarios/forecast-review",
    implementationStatus: "ready-static",
  },
  tomas: {
    route: "/scenarios/buffer-planning",
    implementationStatus: "ready-static",
  },
  maria: {
    route: "/scenarios/cargo-plane",
    implementationStatus: "ready",
  },
  priya: {
    route: "/scenarios/deep-research?status=stub",
    implementationStatus: "stub",
  },
  rafael: {
    route: "/scenarios/agent-studio?status=stub",
    implementationStatus: "stub",
  },
  ayesha: {
    route: "/audit/registry",
    implementationStatus: "ready",
  },
};

function buildPersonas(): readonly Persona[] {
  const skin = getActiveSkin();
  return skin.personas.map((p) => {
    const routing = ROUTING_BY_PERSONA[p.id];
    return {
      id: p.id,
      number: p.number,
      displayName: p.name,
      role: `${p.role} — ${p.region}`,
      sopStage: p.sop_stage,
      scenarioOneLiner: p.opening_line,
      route: routing.route,
      targetDurationMin: p.target_time_minutes,
      memoryProfileUserId: p.memory_profile_user_id,
      sessionId: p.session_id,
      implementationStatus: routing.implementationStatus,
    } satisfies Persona;
  });
}

export const PERSONAS: readonly Persona[] = buildPersonas();

/**
 * Lookup by route prefix — used by the Backstage panel and the RehearsalControls
 * hook to figure out which persona is currently on screen. Returns `null` for
 * routes that aren't owned by a persona (e.g. `/demo` itself).
 */
export function personaForPathname(pathname: string): Persona | null {
  // Strip query string if present.
  const path = pathname.split("?")[0];
  for (const p of PERSONAS) {
    const baseRoute = p.route.split("?")[0];
    if (path === baseRoute || path.startsWith(baseRoute + "/")) {
      return p;
    }
  }
  return null;
}

/** Lookup by 1-based ordinal — used by the `1..6` hotkeys. */
export function personaByNumber(n: number): Persona | null {
  return PERSONAS.find((p) => p.number === n) ?? null;
}
