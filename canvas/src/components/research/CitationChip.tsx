"use client";

/**
 * CitationChip
 *
 * Compact source pill rendered above the research-notebook synthesis.
 * Public sources (BLS, Baker Hughes, etc.) render in slate; internal
 * sources (SAP, ZHR_WORKFORCE) render in emerald to distinguish "your
 * data" from "the world's data" at a glance.
 *
 * v1 is purely visual — no click handler. The ``href`` is captured in
 * the data layer for the day we wire the chips to a side-panel
 * provenance viewer.
 */

import type { Citation } from "@/data/scenarios/deepResearch";

interface CitationChipProps {
  citation: Citation;
}

export function CitationChip({ citation }: CitationChipProps) {
  const isInternal = citation.kind === "internal";
  const borderColor = isInternal
    ? "border-emerald-400/40"
    : "border-sky-400/40";
  const dotColor = isInternal ? "bg-emerald-400" : "bg-sky-400";
  const tagText = isInternal ? "Internal" : "Public";
  const tagColor = isInternal ? "text-emerald-300" : "text-sky-300";

  return (
    <div
      className={`group flex items-start gap-3 rounded-lg border ${borderColor} bg-white/[0.04] p-3 transition-colors hover:bg-white/[0.07]`}
    >
      <div className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dotColor}`} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <div className="text-sm font-semibold text-white/90">
            {citation.label}
          </div>
          <div
            className={`rounded-full border border-white/10 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider ${tagColor}`}
          >
            {tagText}
          </div>
        </div>
        <div className="mt-0.5 text-xs text-white/50">{citation.source}</div>
      </div>
    </div>
  );
}
