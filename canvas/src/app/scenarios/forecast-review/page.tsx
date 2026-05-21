"use client";

/**
 * Persona 1 (David, Basin Leader) — forecast review scenario stub.
 *
 * Full scenario lands in TASK-14. For now this is a routing placeholder
 * that keeps the demo runner's rehearsal flow honest.
 */

import { usePathname } from "next/navigation";

import { ScenarioStub } from "@/components/demo/ScenarioStub";

export default function ForecastReviewScenarioPage() {
  const pathname = usePathname();
  return (
    <ScenarioStub
      pathname={pathname}
      comingInTask="TASK-14"
      scenarioSummary="David reviews the Q4 ML forecast in Connected Sheets. Overrides two basins with structured rationale that gets re-ingested into the model via Knowledge Catalog. The 'model improving' indicator shows override magnitude shrinking quarter over quarter."
    />
  );
}
