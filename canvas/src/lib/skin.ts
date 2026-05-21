/**
 * skin.ts — Library helpers for reading the active customer skin.
 *
 * The skin itself is compiled at build time by `scripts/compile_skin.py`
 * from `skins/<slug>/customer.yaml` and emitted to
 * `canvas/src/data/skin.generated.ts`. This module re-exports the const
 * plus a few typed lookup helpers so consumers never need to import the
 * generated file directly.
 *
 * To swap skins, run:
 *
 *     make use-skin SKIN=halliburton
 *
 * which regenerates `skin.generated.ts` and the canvas picks up the new
 * data on the next build.
 */

import {
  ACTIVE_SKIN,
  ACTIVE_SKIN_SLUG,
} from "@/data/skin.generated";
import type {
  CustomerSkin,
  PersonaId,
  ScenarioConfig,
  SkinPersona,
} from "@/types/skin";

/** Synchronous accessor — the skin is build-time-bundled, no async needed. */
export function getActiveSkin(): CustomerSkin {
  return ACTIVE_SKIN;
}

/** Currently-active skin slug (e.g. "default", "halliburton"). */
export function getActiveSkinSlug(): string {
  return ACTIVE_SKIN_SLUG;
}

/**
 * Look up a persona by stable id. Throws on miss because callers using
 * known persona ids (one of the six fixed slugs) should never hit that
 * case — it indicates the skin YAML is malformed.
 */
export function getPersona(id: PersonaId): SkinPersona {
  const p = ACTIVE_SKIN.personas.find((p) => p.id === id);
  if (!p) {
    throw new Error(
      `Active skin '${ACTIVE_SKIN_SLUG}' has no persona with id '${id}'`,
    );
  }
  return p;
}

/** Look up a persona by 1..6 ordinal. Throws on miss for the same reason. */
export function getPersonaByNumber(n: number): SkinPersona {
  const p = ACTIVE_SKIN.personas.find((p) => p.number === n);
  if (!p) {
    throw new Error(
      `Active skin '${ACTIVE_SKIN_SLUG}' has no persona with number ${n}`,
    );
  }
  return p;
}

/**
 * Look up a scenario config by slug (e.g. "cargo-plane", "buffer-planning").
 * Returns `null` for slugs the active skin doesn't define — let the caller
 * decide whether that's a soft miss (placeholder route) or hard error.
 */
export function getScenario(slug: string): ScenarioConfig | null {
  return ACTIVE_SKIN.scenarios[slug] ?? null;
}

export { ACTIVE_SKIN, ACTIVE_SKIN_SLUG };
