/**
 * useSkin — React hook returning the active customer skin.
 *
 * The skin is bundled at build time (see `scripts/compile_skin.py`), so the
 * hook doesn't actually need to be a hook — it always returns the same
 * object. We expose it as a hook anyway so the calling convention matches
 * what consumers expect, and so we can later swap to a runtime-fetched
 * skin (TASK-13 follow-up, if needed) without touching call sites.
 */

import { getActiveSkin, getActiveSkinSlug } from "@/lib/skin";
import type { CustomerSkin } from "@/types/skin";

export function useSkin(): CustomerSkin {
  return getActiveSkin();
}

export function useSkinSlug(): string {
  return getActiveSkinSlug();
}
