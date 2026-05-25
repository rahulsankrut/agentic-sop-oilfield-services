"use client";

/**
 * Persona 6 (Ayesha, Audit Director) — Audit Mode canvas view.
 *
 * Route: /audit/registry
 *
 * Read-only governance dashboard. Three stacked panels:
 *   1. Agent Registry        — 4 registered MCP servers, endpoints, status.
 *   2. Gateway decisions     — last ~20 authz checks, ALLOW / DENY mix.
 *   3. Model Armor blocks    — last 5 blocked prompt-injection / DLP hits.
 *
 * Data is mock for v1 (TASK-11). The `data: mock` indicator in the top-right
 * makes the source visible. The live wiring (Cloud Logging tail + Agent
 * Registry list) is a TASK-13 deploy concern.
 *
 * The page deliberately does NOT use `CanvasShell` — Ayesha's view is a
 * standalone document-style dashboard, not a map-centric scenario page.
 */

import { useEffect, useState } from "react";

import { A2UIPanel } from "@/components/a2ui/A2UIPanel";
import {
  AUDIT_GATEWAY_DECISIONS,
  AUDIT_GATEWAY_DECISIONS_SURFACE_ID,
  AUDIT_MODEL_ARMOR_BLOCKS,
  AUDIT_MODEL_ARMOR_SURFACE_ID,
  AUDIT_REGISTRY_SURFACE_ID,
  AUDIT_REGISTRY_TABLE,
} from "@/data/a2uiSamples";
import { getPersona } from "@/lib/skin";

// Persona 6 (Audit Director) display name + role come from the active
// customer skin. The structural facts of this page (Agent Registry,
// Gateway, Model Armor) don't vary across skins; only her name + title do.
const AYESHA = getPersona("ayesha");

type DataMode = "mock" | "live";

// DEMO NARRATION (Persona 6, Ayesha — entry): "This is the governance
// surface. Three panels: registered MCP servers, recent Gateway decisions,
// recent Model Armor blocks. Every claim here is platform-native — Agent
// Registry, Agent Gateway audit log, Model Armor Cloud Logging. Mock data
// for the v1 demo; the live wiring is the deploy step."
export default function AuditRegistryPage() {
  // For TASK-11 v1 this is always "mock" — TASK-13 flips it to "live" via
  // env-driven feature flag once the Cloud Logging tail is wired. Plain
  // `const` (not useState — there's no setter wired). Code-review LOW #26.
  const dataMode: DataMode = "mock";

  // R reloads the data — for v1 this is just a no-op flash that re-renders
  // (mock data doesn't change). Wired now so the rehearsal muscle-memory is
  // identical to the live build.
  const [refreshTick, setRefreshTick] = useState(0);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "r" && e.key !== "R") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      setRefreshTick((t) => t + 1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div
      className="min-h-screen overflow-y-auto"
      style={{ background: "var(--color-bg-base)" }}
    >
      <div className="mx-auto max-w-[1280px] px-8 py-10">
        <Header dataMode={dataMode} refreshTick={refreshTick} />

        <div className="mt-10 space-y-10">
          <Section
            eyebrow="Section 1 of 3"
            title="Agent Registry"
            subtitle="Four MCP servers registered. Default-deny is enforced at Agent Gateway — anything not in this table is unreachable to every agent in the system."
          >
            {/* DEMO NARRATION (Persona 6, Ayesha — TASK-45 Phase 2): "These
                audit panels were hand-coded React in v1. In v2 they're A2UI
                — the agent emits JSON describing the table, the gateway
                decisions list, and the Model Armor blocks. If the catalog
                of policies grew tomorrow, the agent emits more rows and
                the canvas updates without a code deploy." */}
            <A2UIPanel
              messages={AUDIT_REGISTRY_TABLE}
              surfaceId={AUDIT_REGISTRY_SURFACE_ID}
            />
          </Section>

          <Section
            eyebrow="Section 2 of 3"
            title="Agent Gateway — recent decisions"
            subtitle="Every MCP tool call and every A2A handshake passes through Agent Gateway. ALLOWED rows cite the policy that approved them; DENIED rows show what default-deny rejected (e.g. Plan Evaluator writing to SAP — least-privilege at the tool level)."
          >
            <A2UIPanel
              messages={AUDIT_GATEWAY_DECISIONS}
              surfaceId={AUDIT_GATEWAY_DECISIONS_SURFACE_ID}
            />
          </Section>

          <Section
            eyebrow="Section 3 of 3"
            title="Model Armor — recent blocks"
            subtitle="INSPECT_AND_BLOCK at MEDIUM+ confidence across prompt-injection, sensitive-data, dangerous-content, and malicious-URI filter categories. Blocks fire at the MCP boundary, before any agent reasons over the payload."
          >
            {/* DEMO NARRATION (Persona 6, Ayesha — closing): "Here's what was blocked. Real attacks land in production constantly; this view is what an auditor opens to see they were caught. The most recent one was [point at top row] — prompt injection at HIGH confidence, blocked at the MCP boundary before any agent reasoned over it." Ayesha narrates over what's on screen; she doesn't trigger anything. */}
            <A2UIPanel
              messages={AUDIT_MODEL_ARMOR_BLOCKS}
              surfaceId={AUDIT_MODEL_ARMOR_SURFACE_ID}
            />
          </Section>
        </div>

        <Footer />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layout primitives — kept inline so this route owns its document chrome
// without dragging in CanvasShell (which is map-centric).
// ---------------------------------------------------------------------------

interface HeaderProps {
  dataMode: DataMode;
  refreshTick: number;
}

function Header({ dataMode, refreshTick }: HeaderProps) {
  return (
    <header className="flex items-start justify-between gap-8">
      <div>
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">
          {AYESHA.name.split(" ")[0]} · {AYESHA.role}
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-white">
          Governance posture
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/55">
          Read-only view of Agent Registry, Agent Gateway authz decisions, and
          Model Armor blocks. Every artifact is platform-native — Agent
          Identity binds each agent to a service account; Gateway enforces
          default-deny on a per-tool grain; Model Armor scans every prompt
          and response at the MCP boundary.
        </p>
      </div>
      <DataModeIndicator dataMode={dataMode} refreshTick={refreshTick} />
    </header>
  );
}

function DataModeIndicator({ dataMode, refreshTick }: HeaderProps) {
  const isLive = dataMode === "live";
  return (
    <div className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 backdrop-blur-md">
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            isLive ? "bg-emerald-400" : "bg-white/40"
          }`}
        />
        <span className="text-[10px] uppercase tracking-[0.18em] text-white/70">
          data: {dataMode}
        </span>
        {!isLive && (
          <span
            className="font-mono text-[10px] text-white/35"
            // The tick number is harmless metadata for rehearsal — confirms
            // the R-key reload fires without distracting the room.
          >
            · #{refreshTick}
          </span>
        )}
      </div>
    </div>
  );
}

interface SectionProps {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

function Section({ eyebrow, title, subtitle, children }: SectionProps) {
  return (
    <section>
      <div className="mb-4">
        <div className="text-[10px] uppercase tracking-[0.2em] text-white/35">
          {eyebrow}
        </div>
        <h2 className="mt-1.5 text-xl font-semibold text-white">{title}</h2>
        <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-white/50">
          {subtitle}
        </p>
      </div>
      {children}
    </section>
  );
}

function Footer() {
  return (
    <footer className="mt-12 border-t border-white/5 pt-6">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[10px] uppercase tracking-wider text-white/35">
        <span>TASK-11 · Governance posture · v1</span>
        <span>Source contracts: infra/gateway_policies.yaml · infra/model_armor.yaml</span>
        <span className="ml-auto">R · refresh</span>
      </div>
    </footer>
  );
}
