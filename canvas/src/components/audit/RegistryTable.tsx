"use client";

/**
 * Agent Registry table — 4 registered MCP servers with endpoint, status,
 * registration date, and tool count. Renders inside the Audit Mode page.
 *
 * Status pill: emerald for Healthy, amber for Degraded (Cloud Run health
 * probe state). Endpoints come from `infra/cloud_run/*.yaml` (for the three
 * synthetic servers) and the managed Dataplex MCP path (Knowledge Catalog).
 */

import { CheckCircle2, AlertTriangle } from "lucide-react";

import type {
  RegistryEntry,
  RegistryStatus,
} from "@/data/auditMockData";

interface RegistryTableProps {
  entries: ReadonlyArray<RegistryEntry>;
}

// DEMO NARRATION (Persona 6, Ayesha): "Here are the four MCP servers
// registered with Agent Registry. Default-deny is enabled at the Gateway —
// anything not in this list is unreachable to every agent in the system.
// SAP, Maximo, FDP run on Cloud Run. Knowledge Catalog is the managed
// Dataplex MCP. All four scanned by Model Armor at the boundary."
export function RegistryTable({ entries }: RegistryTableProps) {
  return (
    <div className="rounded-2xl border border-white/10 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-white/[0.04]">
          <tr>
            <Th>Server</Th>
            <Th>Endpoint</Th>
            <Th align="right">Tools</Th>
            <Th align="right">p50 latency</Th>
            <Th>Registered</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr
              key={e.serverId}
              className="border-t border-white/5 transition-colors hover:bg-white/[0.02]"
            >
              <td className="px-4 py-3.5">
                <div className="font-medium text-white">{e.displayName}</div>
                <div className="mt-0.5 text-[11px] text-white/45">
                  {e.source}
                </div>
              </td>
              <td className="px-4 py-3.5">
                <div
                  className="max-w-[360px] truncate font-mono text-[11px] text-white/55"
                  title={e.endpoint}
                >
                  {e.endpoint}
                </div>
                <div className="mt-0.5 font-mono text-[10px] text-white/30">
                  {e.serverId}
                </div>
              </td>
              <td className="px-4 py-3.5 text-right font-mono text-sm tabular-nums text-white/85">
                {e.toolCount}
              </td>
              <td className="px-4 py-3.5 text-right font-mono text-xs tabular-nums text-white/65">
                {e.latencyP50Ms} ms
              </td>
              <td className="px-4 py-3.5 font-mono text-[11px] text-white/55">
                {formatRegisteredAt(e.registeredAt)}
              </td>
              <td className="px-4 py-3.5">
                <StatusPill status={e.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------

interface ThProps {
  children: React.ReactNode;
  align?: "left" | "right";
}

function Th({ children, align = "left" }: ThProps) {
  return (
    <th
      className={`px-4 py-3 text-[10px] font-medium uppercase tracking-[0.14em] text-white/50 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function StatusPill({ status }: { status: RegistryStatus }) {
  const isHealthy = status === "Healthy";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${
        isHealthy
          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
          : "border-amber-400/30 bg-amber-400/10 text-amber-300"
      }`}
    >
      {isHealthy ? (
        <CheckCircle2 className="h-3 w-3" />
      ) : (
        <AlertTriangle className="h-3 w-3" />
      )}
      {status}
    </span>
  );
}

function formatRegisteredAt(iso: string): string {
  // Output: "2026-05-12 14:08 UTC" — stable across SSR/CSR (no toLocaleString
  // surprises on a dual-render mismatch). The page itself is client-only via
  // "use client" so this is belt-and-braces.
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mn = String(d.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mn} UTC`;
}
