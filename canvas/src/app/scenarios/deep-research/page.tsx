"use client";

/**
 * Persona 4 (Priya, Operations VP) — deep research scenario stub.
 *
 * Full scenario lands in TASK-15. For now this is a routing placeholder.
 */

import { usePathname } from "next/navigation";

import { ScenarioStub } from "@/components/demo/ScenarioStub";

export default function DeepResearchScenarioPage() {
  const pathname = usePathname();
  return (
    <ScenarioStub
      pathname={pathname}
      comingInTask="TASK-15"
      scenarioSummary="Priya asks the Deep Research Agent: 'What's my West African deepwater exposure?' The agent produces a citation-grounded briefing with inline source links — Connected Sheets, BigQuery, internal docs, and public web — all anchored on canonical assets in Knowledge Catalog."
    />
  );
}
