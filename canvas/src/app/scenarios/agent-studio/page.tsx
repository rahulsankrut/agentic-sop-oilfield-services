"use client";

/**
 * Persona 5 (Rafael, Citizen Developer) — agent studio scenario stub.
 *
 * Full scenario lands in TASK-16. For now this is a routing placeholder.
 */

import { usePathname } from "next/navigation";

import { ScenarioStub } from "@/components/demo/ScenarioStub";

export default function AgentStudioScenarioPage() {
  const pathname = usePathname();
  return (
    <ScenarioStub
      pathname={pathname}
      comingInTask="TASK-16"
      scenarioSummary="Rafael builds a new 'rig-down notification' agent live in Agent Studio in under 60 seconds. Draws from registered MCP tools, drops in a skill, deploys to Agent Runtime, and tests it on a synthetic rig-down event — all without writing code."
    />
  );
}
