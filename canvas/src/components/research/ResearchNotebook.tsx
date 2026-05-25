"use client";

/**
 * ResearchNotebook
 *
 * The canvas surface for Persona 4 (Priya, EVP). A notebook-style layout
 * with the question at top, a row of citation chips, a synthesis block,
 * and a recommended-action card. Built as a single component so the
 * scenario page is just wiring.
 *
 * Markdown rendering: there is no ``react-markdown`` in package.json
 * (see ``canvas/package.json``), so we ship a small hand-rolled renderer
 * that handles the two patterns the storyboard uses — bold spans inside
 * paragraphs, and ordered/unordered lists. That's enough for the
 * synthesis content; adding a real Markdown library is a future task if
 * the demo expands.
 */

import type {
  Citation,
  Recommendation,
} from "@/data/scenarios/deepResearch";
import { CitationChip } from "./CitationChip";

interface ResearchNotebookProps {
  question: string;
  citations: Citation[];
  synthesisMarkdown: string;
  recommendation: Recommendation | null;
  saveToast: string | null;
  /** Callback when an exec clicks a citation chip to drill into the source. */
  onCitationOpen?: (citation: Citation) => void;
}

export function ResearchNotebook({
  question,
  citations,
  synthesisMarkdown,
  recommendation,
  saveToast,
  onCitationOpen,
}: ResearchNotebookProps) {
  return (
    <div className="relative flex h-full flex-col overflow-y-auto px-10 py-8">
      <NotebookHeader question={question} />

      <SectionLabel label="Sources" muted={citations.length === 0} />
      {citations.length === 0 ? (
        <EmptyChips />
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
          {citations.map((c) => (
            <CitationChip key={c.id} citation={c} onOpen={onCitationOpen} />
          ))}
        </div>
      )}

      <SectionLabel label="Synthesis" muted={!synthesisMarkdown} />
      {synthesisMarkdown ? (
        <SynthesisBlock markdown={synthesisMarkdown} />
      ) : (
        <EmptyBlock label="Awaiting cross-source synthesis…" />
      )}

      <SectionLabel label="Recommendation" muted={!recommendation} />
      {recommendation ? (
        <RecommendationCard recommendation={recommendation} />
      ) : (
        <EmptyBlock label="Recommendation will surface after synthesis." />
      )}

      <SaveToast toast={saveToast} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function NotebookHeader({ question }: { question: string }) {
  return (
    <header className="mb-6 border-b border-white/10 pb-6">
      <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
        Deep Research · Strategic synthesis
      </div>
      <h1 className="mt-2 text-2xl font-semibold leading-snug text-white">
        {question}
      </h1>
    </header>
  );
}

function SectionLabel({ label, muted }: { label: string; muted: boolean }) {
  return (
    <div
      className={`mt-8 text-[10px] uppercase tracking-[0.18em] ${
        muted ? "text-white/25" : "text-white/55"
      }`}
    >
      {label}
    </div>
  );
}

function EmptyChips() {
  return (
    <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-[58px] rounded-lg border border-dashed border-white/10 bg-white/[0.02]"
        />
      ))}
    </div>
  );
}

function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="mt-3 rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-8 text-center text-xs text-white/30">
      {label}
    </div>
  );
}

function SynthesisBlock({ markdown }: { markdown: string }) {
  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.04] p-6">
      <SimpleMarkdown source={markdown} />
    </div>
  );
}

function RecommendationCard({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-sky-400/40 bg-gradient-to-br from-sky-500/20 to-blue-500/10 p-6 shadow-lg shadow-sky-500/10">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-sky-400" />
        <div className="text-[10px] uppercase tracking-[0.18em] text-sky-200">
          {recommendation.title}
        </div>
      </div>
      <div className="mt-3 text-base leading-relaxed text-white/95">
        {recommendation.body}
      </div>
    </div>
  );
}

function SaveToast({ toast }: { toast: string | null }) {
  if (!toast) return null;
  return (
    <div className="pointer-events-none fixed bottom-8 left-1/2 z-50 -translate-x-1/2">
      <div className="flex items-center gap-3 rounded-full border border-emerald-400/40 bg-emerald-500/20 px-5 py-2.5 backdrop-blur-md">
        <div className="h-2 w-2 rounded-full bg-emerald-400" />
        <div className="text-sm text-white/95">{toast}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tiny Markdown renderer
//
// Handles:
//   - ordered lists ("1. …")
//   - paragraph breaks (blank line)
//   - inline **bold** spans
//
// Anything else is rendered as plain text. This is intentional — the
// synthesis content is curated, so we don't need a full parser. If the
// scenarios grow, swap to react-markdown.
// ---------------------------------------------------------------------------

function SimpleMarkdown({ source }: { source: string }) {
  const blocks = source.split(/\n\n+/);
  return (
    <div className="space-y-4 text-sm leading-relaxed text-white/85">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        const isList = lines.every((l) => /^\s*\d+\.\s/.test(l));
        if (isList) {
          return (
            <ol key={i} className="ml-4 list-decimal space-y-2">
              {lines.map((line, j) => {
                const text = line.replace(/^\s*\d+\.\s/, "");
                return (
                  <li key={j} className="pl-1">
                    <InlineBold text={text} />
                  </li>
                );
              })}
            </ol>
          );
        }
        return (
          <p key={i}>
            <InlineBold text={block} />
          </p>
        );
      })}
    </div>
  );
}

function InlineBold({ text }: { text: string }) {
  // Split on **bold** markers — odd-indexed chunks are the bolded spans.
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-semibold text-white">
            {part}
          </strong>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
