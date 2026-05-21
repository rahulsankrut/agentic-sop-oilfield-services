"use client";

/**
 * Model Armor recent blocks — last ~5 INSPECT_AND_BLOCK hits. Mirrors the
 * four filter categories in `infra/model_armor.yaml`:
 *
 *   - promptInjectionAndJailbreak  (prompt-injection / jailbreak)
 *   - sensitiveDataProtection      (sensitive-data)
 *   - responsibleAi                (dangerous-content)
 *   - maliciousUriFilterSettings   (malicious-uri)
 *
 * The seed script in `scripts/seed_blocked_attack_example.py` produces the
 * first entry; the rest are drawn from prior demo rehearsals.
 */

import { ShieldAlert } from "lucide-react";

import type {
  ArmorBlockEntry,
  ArmorConfidence,
  ArmorTechnique,
} from "@/data/auditMockData";

interface ModelArmorBlocksListProps {
  entries: ReadonlyArray<ArmorBlockEntry>;
}

// DEMO NARRATION (Persona 6, Ayesha): "Show me an example of Model Armor
// working. — Here are the last five blocks. Yesterday at 14:32 UTC, a
// prompt-injection attempt was caught on the request leg before the SAP
// MCP server ever saw it. The detected technique, the confidence level,
// the truncated payload — all in Cloud Logging. No agent reasoned over
// the malicious payload. This is the floor setting acting."
export function ModelArmorBlocksList({ entries }: ModelArmorBlocksListProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-rose-300/90">
        <ShieldAlert className="h-3.5 w-3.5" />
        {entries.length} blocked attempt{entries.length === 1 ? "" : "s"} (last 7 days)
      </div>

      <ul className="space-y-3">
        {entries.map((entry, idx) => (
          <BlockCard key={`${entry.timestamp}-${idx}`} entry={entry} />
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------

function BlockCard({ entry }: { entry: ArmorBlockEntry }) {
  return (
    <li className="rounded-2xl border border-rose-400/15 bg-rose-400/[0.03] p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <TechniqueBadge technique={entry.technique} />
        <ConfidenceBadge confidence={entry.confidence} />
        <DirectionBadge direction={entry.direction} />
        <span className="ml-auto font-mono text-[10px] text-white/40">
          {formatTimestamp(entry.timestamp)}
        </span>
      </div>

      <div className="mb-2 flex items-baseline gap-2 text-[11px]">
        <span className="font-medium text-white/80">{entry.sourceAgent}</span>
        <span className="font-mono text-[10px] text-white/30">→</span>
        <span
          className="truncate font-mono text-white/70"
          title={entry.targetTool}
        >
          {entry.targetTool}
        </span>
      </div>

      <div className="rounded-lg border border-white/5 bg-black/30 p-3">
        <div className="mb-1 text-[10px] uppercase tracking-wider text-white/35">
          Payload (truncated · sensitive values redacted)
        </div>
        <div className="font-mono text-[11px] leading-relaxed text-white/70">
          {entry.payloadSnippet}
        </div>
      </div>
    </li>
  );
}

function TechniqueBadge({ technique }: { technique: ArmorTechnique }) {
  const label = TECHNIQUE_LABELS[technique];
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-rose-400/30 bg-rose-400/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-rose-200">
      {label}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: ArmorConfidence }) {
  const tone =
    confidence === "HIGH"
      ? "border-rose-400/30 bg-rose-400/10 text-rose-200"
      : confidence === "MEDIUM"
        ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
        : "border-white/15 bg-white/5 text-white/60";
  return (
    <span
      className={`inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider ${tone}`}
    >
      {confidence}
    </span>
  );
}

function DirectionBadge({
  direction,
}: {
  direction: ArmorBlockEntry["direction"];
}) {
  return (
    <span className="inline-flex items-center rounded-md border border-white/15 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white/55">
      {direction}
    </span>
  );
}

const TECHNIQUE_LABELS: Record<ArmorTechnique, string> = {
  "prompt-injection": "Prompt injection",
  jailbreak: "Jailbreak",
  "sensitive-data": "Sensitive data",
  "dangerous-content": "Dangerous content",
  "malicious-uri": "Malicious URI",
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mn = String(d.getUTCMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mn} UTC`;
}
