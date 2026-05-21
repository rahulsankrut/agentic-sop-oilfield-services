"use client";

/**
 * Agent Gateway recent decisions — last ~20 authz checks, mixed
 * ALLOWED / DENIED. Default-DENY is on at the bundle level
 * (`infra/gateway_policies.yaml`), so DENY rows are the "audit happy path":
 * the system refused something it didn't have an explicit ALLOW for.
 */

import { Check, X } from "lucide-react";

import type {
  GatewayDecision,
  GatewayDecisionEntry,
} from "@/data/auditMockData";

interface GatewayDecisionsListProps {
  entries: ReadonlyArray<GatewayDecisionEntry>;
}

// DEMO NARRATION (Persona 6, Ayesha): "Every MCP tool call and every A2A
// handshake passes through Agent Gateway. Here are the last twenty
// decisions — ALLOWED ones cite the policy that approved them, DENIED ones
// show what the default-deny floor rejected. Notice the Plan Evaluator
// trying to write to SAP — denied. That's least-privilege at the tool level,
// not the service level."
export function GatewayDecisionsList({ entries }: GatewayDecisionsListProps) {
  const allowed = entries.filter((e) => e.decision === "ALLOWED").length;
  const denied = entries.length - allowed;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 text-[11px] uppercase tracking-wider">
        <div className="flex items-center gap-1.5 text-emerald-300/90">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          {allowed} allowed
        </div>
        <div className="flex items-center gap-1.5 text-rose-300/90">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
          {denied} denied
        </div>
        <div className="ml-auto text-white/35">
          last {entries.length} decisions
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10">
        <ul className="divide-y divide-white/5">
          {entries.map((e, idx) => (
            <DecisionRow key={`${e.timestamp}-${idx}`} entry={e} />
          ))}
        </ul>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function DecisionRow({ entry }: { entry: GatewayDecisionEntry }) {
  const allowed = entry.decision === "ALLOWED";
  return (
    <li className="grid grid-cols-[88px_1fr_auto] items-start gap-3 px-4 py-3 transition-colors hover:bg-white/[0.02]">
      {/* Timestamp + decision icon column */}
      <div className="flex flex-col items-start gap-1.5">
        <DecisionBadge decision={entry.decision} />
        <span className="font-mono text-[10px] text-white/35">
          {formatTime(entry.timestamp)}
        </span>
      </div>

      {/* Detail column */}
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium text-white/85">
            {entry.sourceAgent}
          </span>
          <span className="font-mono text-[10px] text-white/30">→</span>
          <span
            className="truncate font-mono text-[11px] text-white/75"
            title={entry.toolPath}
          >
            {entry.toolPath}
          </span>
        </div>
        <div className="mt-1 font-mono text-[10px] text-white/40">
          principal: {entry.principal}@…iam.gserviceaccount.com
        </div>
        <div
          className={`mt-1 text-[11px] ${
            allowed ? "text-white/55" : "text-rose-200/80"
          }`}
        >
          {entry.reason}
        </div>
      </div>

      {/* Latency column */}
      <div className="flex flex-col items-end gap-0.5 pt-0.5">
        <span className="font-mono text-xs tabular-nums text-white/65">
          {entry.latencyMs}
          <span className="ml-0.5 text-[10px] text-white/35">ms</span>
        </span>
      </div>
    </li>
  );
}

function DecisionBadge({ decision }: { decision: GatewayDecision }) {
  const allowed = decision === "ALLOWED";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider ${
        allowed
          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
          : "border-rose-400/30 bg-rose-400/10 text-rose-300"
      }`}
    >
      {allowed ? <Check className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
      {decision}
    </span>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mn = String(d.getUTCMinutes()).padStart(2, "0");
  const ss = String(d.getUTCSeconds()).padStart(2, "0");
  return `${hh}:${mn}:${ss}`;
}
