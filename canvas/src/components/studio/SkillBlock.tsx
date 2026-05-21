"use client";

/**
 * SkillBlock
 *
 * A single visual block in the Agent Studio canvas (Persona 5, Rafael).
 * Blocks chain top-to-bottom with arrow connectors drawn by the parent
 * SkillBuilder — each block is just one card.
 *
 * Kind-specific color is the cheap visual cue: input (sky), query
 * (violet), filter (amber), output (emerald). The ``bound`` flag
 * upgrades the input block in Beat 2 once Rafael wires it to
 * ZHR_WORKFORCE.BASIN.
 */

import type { SkillBlock as SkillBlockData } from "@/data/scenarios/agentStudio";

const KIND_STYLES: Record<
  SkillBlockData["kind"],
  { border: string; tag: string; dot: string; label: string }
> = {
  input: {
    border: "border-sky-400/40",
    tag: "text-sky-200",
    dot: "bg-sky-400",
    label: "Input",
  },
  query: {
    border: "border-violet-400/40",
    tag: "text-violet-200",
    dot: "bg-violet-400",
    label: "Query",
  },
  filter: {
    border: "border-amber-400/40",
    tag: "text-amber-200",
    dot: "bg-amber-400",
    label: "Filter",
  },
  output: {
    border: "border-emerald-400/40",
    tag: "text-emerald-200",
    dot: "bg-emerald-400",
    label: "Output",
  },
};

interface SkillBlockProps {
  block: SkillBlockData;
}

export function SkillBlock({ block }: SkillBlockProps) {
  const style = KIND_STYLES[block.kind];
  return (
    <div
      className={`rounded-xl border ${style.border} bg-white/[0.04] p-4 transition-shadow hover:shadow-lg hover:shadow-white/5`}
    >
      <div className="flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${style.dot}`} />
        <div
          className={`text-[10px] uppercase tracking-[0.18em] ${style.tag}`}
        >
          {style.label}
        </div>
        {block.bound && (
          <div className="ml-auto rounded-full border border-emerald-400/40 bg-emerald-500/15 px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-emerald-200">
            Bound
          </div>
        )}
      </div>
      <div className="mt-2 text-sm font-semibold text-white/95">
        {block.title}
      </div>
      <div className="mt-1 text-xs text-white/55">{block.detail}</div>
      {block.parameterValue && (
        <div className="mt-3 inline-flex items-center gap-2 rounded-md border border-white/10 bg-black/40 px-2.5 py-1">
          <span className="text-[10px] uppercase tracking-wider text-white/40">
            Param
          </span>
          <span className="text-xs font-medium text-white/90">
            {block.parameterValue}
          </span>
        </div>
      )}
    </div>
  );
}
