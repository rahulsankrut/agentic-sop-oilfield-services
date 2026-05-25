"use client";

/**
 * CitationChip
 *
 * Compact source pill rendered above the research-notebook synthesis.
 * Public sources (BLS, Baker Hughes, etc.) render in slate; internal
 * sources (SAP, ZHR_WORKFORCE) render in emerald to distinguish "your
 * data" from "the world's data" at a glance.
 *
 * Clicking the chip opens `CitationDrawer` (via the `onOpen` callback
 * the parent supplies) so an exec can drill from a synthesis claim back
 * into the underlying record — the spec calls this out as the moment
 * that earns auditor trust.
 */

import type { Citation } from "@/data/scenarios/deepResearch";

interface CitationChipProps {
  citation: Citation;
  onOpen?: (citation: Citation) => void;
}

// DEMO NARRATION: "Every chip is groundable — click it and the exec sees
// the actual record. Public sources keep their URL; internal sources
// drill into the SAP/Maximo row the synthesis pulled."
export function CitationChip({ citation, onOpen }: CitationChipProps) {
  const isInternal = citation.kind === "internal";
  const borderColor = isInternal
    ? "border-emerald-400/40"
    : "border-sky-400/40";
  const dotColor = isInternal ? "bg-emerald-400" : "bg-sky-400";
  const tagText = isInternal ? "Internal" : "Public";
  const tagColor = isInternal ? "text-emerald-300" : "text-sky-300";

  const handleClick = () => {
    if (onOpen) onOpen(citation);
  };
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!onOpen) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpen(citation);
    }
  };

  return (
    <div
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      onClick={onOpen ? handleClick : undefined}
      onKeyDown={onOpen ? handleKeyDown : undefined}
      className={`group flex items-start gap-3 rounded-lg border ${borderColor} bg-white/[0.04] p-3 transition-colors hover:bg-white/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 ${
        onOpen ? "cursor-pointer" : ""
      }`}
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
          {onOpen && citation.detail && (
            <div className="ml-auto text-[10px] uppercase tracking-wider text-white/30 group-hover:text-white/60">
              drill ↗
            </div>
          )}
        </div>
        <div className="mt-0.5 text-xs text-white/50">{citation.source}</div>
      </div>
    </div>
  );
}
