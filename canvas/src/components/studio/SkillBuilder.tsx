"use client";

/**
 * SkillBuilder
 *
 * Two-column canvas surface for Persona 5 (Rafael, Citizen Developer):
 *   - Left:  visual skill-block stack (drag-and-drop in the real
 *            product; static and ordered for the demo).
 *   - Right: live code preview that updates as the blocks evolve.
 *
 * The bottom row carries the test-results list and the publish
 * confirmation card. Both panels are always mounted to avoid layout
 * shift between beats — they just render empty states when the
 * scenario hasn't populated them yet.
 */

import type {
  SkillBlock as SkillBlockData,
} from "@/data/scenarios/agentStudio";
import { SkillBlock } from "./SkillBlock";

interface SkillBuilderProps {
  skillName: string;
  blocks: SkillBlockData[];
  testResults: string[];
  publishStatus: string | null;
  codePreview: string;
}

export function SkillBuilder({
  skillName,
  blocks,
  testResults,
  publishStatus,
  codePreview,
}: SkillBuilderProps) {
  return (
    <div className="relative flex h-full flex-col overflow-y-auto px-8 py-6">
      <StudioHeader skillName={skillName} />

      <div className="mt-6 grid flex-1 grid-cols-1 gap-5 lg:grid-cols-2">
        <BuilderColumn blocks={blocks} />
        <PreviewColumn codePreview={codePreview} />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <TestResultsPanel results={testResults} />
        <PublishPanel status={publishStatus} skillName={skillName} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function StudioHeader({ skillName }: { skillName: string }) {
  return (
    <header className="flex items-center justify-between border-b border-white/10 pb-4">
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
          Agent Studio · low-code builder
        </div>
        <h1 className="mt-1 font-mono text-xl font-semibold text-white">
          {skillName || "untitled_skill"}
        </h1>
      </div>
      <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5">
        <div
          className={`h-2 w-2 rounded-full ${
            skillName ? "bg-emerald-400" : "bg-white/30"
          }`}
        />
        <span className="text-[10px] uppercase tracking-[0.18em] text-white/60">
          {skillName ? "Draft" : "Empty"}
        </span>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Left column — visual block stack
// ---------------------------------------------------------------------------

function BuilderColumn({ blocks }: { blocks: SkillBlockData[] }) {
  return (
    <section>
      <SectionLabel label="Skill blocks" />
      {blocks.length === 0 ? (
        <EmptyBlock label="Drop or generate blocks to start." />
      ) : (
        <div className="mt-3 space-y-3">
          {blocks.map((block, i) => (
            <div key={block.id}>
              <SkillBlock block={block} />
              {i < blocks.length - 1 && <Connector />}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Connector() {
  return (
    <div className="flex justify-center py-1">
      <div className="flex flex-col items-center">
        <div className="h-3 w-px bg-white/20" />
        <div className="h-0 w-0 border-x-4 border-t-4 border-x-transparent border-t-white/40" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column — code preview
// ---------------------------------------------------------------------------

function PreviewColumn({ codePreview }: { codePreview: string }) {
  return (
    <section>
      <SectionLabel label="Code preview" />
      <div className="mt-3 overflow-hidden rounded-xl border border-white/10 bg-black/40">
        <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
          <div className="flex gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-rose-400/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-amber-400/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-400/60" />
          </div>
          <div className="text-[10px] uppercase tracking-wider text-white/40">
            skill.yaml
          </div>
        </div>
        {codePreview ? (
          <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-white/85">
            {codePreview}
          </pre>
        ) : (
          <div className="p-8 text-center text-xs text-white/30">
            Preview will appear once blocks are added.
          </div>
        )}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Bottom row — test results + publish card
// ---------------------------------------------------------------------------

function TestResultsPanel({ results }: { results: string[] }) {
  return (
    <section>
      <SectionLabel label="Test run" />
      {results.length === 0 ? (
        <EmptyBlock label="Run the skill to see results." />
      ) : (
        <div className="mt-3 overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
            <div className="text-[10px] uppercase tracking-wider text-emerald-200">
              {results.length} hit{results.length === 1 ? "" : "s"}
            </div>
          </div>
          <ul className="divide-y divide-white/5">
            {results.map((line, i) => (
              <li
                key={i}
                className="px-4 py-2.5 font-mono text-xs text-white/85"
              >
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function PublishPanel({
  status,
  skillName,
}: {
  status: string | null;
  skillName: string;
}) {
  return (
    <section>
      <SectionLabel label="Publish" />
      {status ? (
        <div className="mt-3 overflow-hidden rounded-xl border border-emerald-400/40 bg-gradient-to-br from-emerald-500/20 to-teal-500/10 p-5 shadow-lg shadow-emerald-500/10">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
            <div className="text-[10px] uppercase tracking-[0.18em] text-emerald-200">
              Published
            </div>
          </div>
          <div className="mt-2 text-sm leading-relaxed text-white/90">
            {renderInlineCode(status)}
          </div>
        </div>
      ) : (
        <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-5">
          <div className="text-xs text-white/55">
            {skillName
              ? "Skill is in draft. Click Publish once the test run looks right."
              : "Awaiting skill scaffold."}
          </div>
          <button
            type="button"
            disabled
            className="mt-3 cursor-not-allowed rounded-md border border-white/10 bg-white/[0.05] px-4 py-2 text-xs font-medium uppercase tracking-wider text-white/40"
          >
            Publish to my team
          </button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function SectionLabel({ label }: { label: string }) {
  return (
    <div className="text-[10px] uppercase tracking-[0.18em] text-white/55">
      {label}
    </div>
  );
}

function EmptyBlock({ label }: { label: string }) {
  return (
    <div className="mt-3 rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center text-xs text-white/30">
      {label}
    </div>
  );
}

/**
 * Tiny inline-code renderer — wraps `\`backtick\`` spans in styled <code>.
 * Used by the publish confirmation so the skill version string gets the
 * monospace treatment without requiring a Markdown library.
 */
function renderInlineCode(text: string) {
  const parts = text.split(/`([^`]+)`/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <code
        key={i}
        className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-xs text-emerald-200"
      >
        {part}
      </code>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
