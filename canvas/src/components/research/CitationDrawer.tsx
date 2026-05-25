"use client";

/**
 * CitationDrawer
 *
 * Side-drawer detail view for a clicked citation in Persona 4's
 * deep-research scenario. The exec clicks a chip in the synthesis;
 * this drawer renders the underlying record:
 *   - 1-2 sentence summary of what the source is
 *   - structured key/value facts the synthesis actually pulled
 *   - optional raw excerpt (e.g. a BQ row or weekly series snippet)
 *   - "View source" link out to the public URL when one exists
 *
 * The drawer is intentionally read-only and uniform across source types
 * — public web sources and internal SAP rows render with the same
 * structure so the auditor's "show me where this number came from" path
 * works identically regardless of provenance.
 */

import { ExternalLink, X } from "lucide-react";

import type { Citation } from "@/data/scenarios/deepResearch";

interface CitationDrawerProps {
  citation: Citation;
  onClose?: () => void;
}

// DEMO NARRATION: "Priya clicks the BLS chip. Drawer opens — the actual
// employment number, the NAICS code, the geography filter. Same shape
// for the internal SAP chip — the ZHR_WORKFORCE row, the WERKS plant.
// No hand-waving; the exec can audit her own briefing."
export function CitationDrawer({ citation, onClose }: CitationDrawerProps) {
  const isInternal = citation.kind === "internal";
  const accentText = isInternal ? "text-emerald-300" : "text-sky-300";
  const dotColor = isInternal ? "bg-emerald-400" : "bg-sky-400";
  const kindLabel = isInternal ? "Internal source" : "Public source";

  return (
    <div className="flex h-full flex-col p-6">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${dotColor}`} />
            <div
              className={`text-[10px] uppercase tracking-[0.18em] ${accentText}`}
            >
              {kindLabel}
            </div>
          </div>
          <h2 className="mt-2 text-lg font-semibold text-white">
            {citation.label}
          </h2>
          <div className="mt-0.5 text-xs text-white/55">{citation.source}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close source drawer"
            className="rounded-md p-1 text-white/40 hover:bg-white/10 hover:text-white/80"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </header>

      {citation.detail ? (
        <div className="flex flex-col gap-5 overflow-y-auto">
          <p className="text-sm leading-relaxed text-white/80">
            {citation.detail.summary}
          </p>

          <dl className="grid grid-cols-1 gap-y-2 rounded-lg border border-white/10 bg-white/[0.03] p-4">
            {citation.detail.facts.map((f) => (
              <div
                key={f.key}
                className="flex items-baseline justify-between gap-3 text-sm"
              >
                <dt className="text-white/55">{f.key}</dt>
                <dd className="text-right font-mono tabular-nums text-white/90">
                  {f.value}
                </dd>
              </div>
            ))}
          </dl>

          {citation.detail.excerpt && (
            <div>
              <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-white/40">
                Raw excerpt
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-white/80">
                {citation.detail.excerpt}
              </pre>
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.02] p-6 text-sm text-white/50">
          No structured detail attached to this citation.
        </div>
      )}

      {citation.href && (
        <a
          href={citation.href}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-6 inline-flex items-center gap-2 self-start rounded-lg border border-white/15 bg-white/[0.06] px-3 py-2 text-xs font-medium text-white/85 hover:bg-white/10"
        >
          View source <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}
