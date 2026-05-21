import { redirect } from "next/navigation";

/**
 * Root route. TASK-12 lands the persona launcher at /demo — that's the
 * canonical entry point for the demo runner, so the root redirects there.
 *
 * Deep-link routes (`/scenarios/cargo-plane`, `/audit/registry`, etc.)
 * still work — the launcher is just the front door.
 */
export default function Home() {
  redirect("/demo");
}
