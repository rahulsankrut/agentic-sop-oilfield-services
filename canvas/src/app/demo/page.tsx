"use client";

/**
 * Demo launcher (TASK-12 Step 1).
 *
 * Six tiles, one per persona, walking the S&OP cycle in order. Click a
 * tile (or press 1..6) to route to that persona's scenario. Tiles flag
 * `ready` / `ready-static` / `stub` status so the demoer can see at a
 * glance which scenarios have full canvas implementations vs. which are
 * routing-only placeholders for TASK-13.
 *
 * Layout mirrors the Audit Mode page's typography (tracking-[0.18em]
 * eyebrows, font-mono numerics, dark gradient background) — same visual
 * language across every page in the canvas.
 */

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { PERSONAS, type Persona } from "@/data/personas";
import { preWarmSession } from "@/lib/preWarmSession";

// DEMO NARRATION (Pre-demo): "This is the persona launcher. Six tiles,
// six S&OP roles. We'll walk through them in cycle order — demand
// sensing, demand-to-supply planning, supply response, strategic review,
// citizen development, and governance. Number keys jump directly to any
// persona. Backslash opens the rehearsal backstage panel at any time."
export default function DemoLauncherPage() {
  const router = useRouter();

  function launch(persona: Persona) {
    // Fire-and-forget pre-warm; navigation does not wait. The scenario
    // page also issues its own pre-warm on mount as a belt-and-braces.
    void preWarmSession(persona);
    router.push(persona.route);
  }

  return (
    <main
      className="min-h-screen overflow-y-auto"
      style={{ background: "var(--color-bg-base)" }}
    >
      <div className="mx-auto max-w-[1280px] px-8 py-10">
        <Header />

        <div className="mt-10 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PERSONAS.map((p) => (
            <PersonaTile key={p.id} persona={p} onLaunch={launch} />
          ))}
        </div>

        <Footer />
      </div>
    </main>
  );
}

function Header() {
  return (
    <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div className="max-w-2xl">
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/40">
          Demo runner
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-white">
          Agentic S&OP for Oilfield Services
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-white/55">
          Six personas, six scenarios, one S&OP cycle. Select a persona to
          begin, or press <Kbd>1</Kbd>–<Kbd>6</Kbd> to jump directly. Full
          demo runs ~18 minutes; individual scenarios run 2–5 minutes.
        </p>
      </div>
      <div className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 backdrop-blur-md">
        <span className="text-[10px] uppercase tracking-[0.18em] text-white/70">
          rehearsal · v1
        </span>
      </div>
    </header>
  );
}

interface PersonaTileProps {
  persona: Persona;
  onLaunch: (p: Persona) => void;
}

function PersonaTile({ persona, onLaunch }: PersonaTileProps) {
  const statusLabel =
    persona.implementationStatus === "ready"
      ? "ready"
      : persona.implementationStatus === "ready-static"
        ? "static"
        : "stub";

  const statusDot =
    persona.implementationStatus === "ready"
      ? "bg-emerald-400"
      : persona.implementationStatus === "ready-static"
        ? "bg-sky-400"
        : "bg-white/30";

  return (
    <button
      type="button"
      onClick={() => onLaunch(persona)}
      className="group flex h-full flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-6 text-left transition-colors hover:border-white/20 hover:bg-white/[0.07]"
    >
      <div className="flex items-start justify-between">
        <div className="text-[10px] uppercase tracking-[0.2em] text-white/40">
          Persona {persona.number}
        </div>
        <Kbd>{persona.number}</Kbd>
      </div>

      <div className="mt-3 text-lg font-medium text-white">
        {persona.displayName}
      </div>
      <div className="text-sm text-white/60">{persona.role}</div>

      <p className="mt-4 line-clamp-3 text-sm leading-relaxed text-white/65">
        {persona.scenarioOneLiner}
      </p>

      <div className="mt-6 flex items-center justify-between border-t border-white/10 pt-4">
        <div className="flex flex-col gap-1">
          <div className="text-[10px] uppercase tracking-wider text-white/35">
            S&OP · {persona.sopStage}
          </div>
          <div className="font-mono text-[11px] text-white/55">
            target {persona.targetDurationMin}:00
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${statusDot}`} />
            <span className="text-[10px] uppercase tracking-[0.18em] text-white/45">
              {statusLabel}
            </span>
          </span>
          <ArrowRight className="h-4 w-4 text-white/40 transition-transform group-hover:translate-x-0.5 group-hover:text-white/70" />
        </div>
      </div>
    </button>
  );
}

function Footer() {
  return (
    <footer className="mt-10 border-t border-white/5 pt-6">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[10px] uppercase tracking-wider text-white/35">
        <span>
          <Kbd>\</Kbd> backstage panel
        </span>
        <span>
          <Kbd>?</Kbd> all shortcuts
        </span>
        <span>
          <Kbd>0</Kbd> back to launcher
        </span>
        <span className="ml-auto">
          <Link
            href="/audit/registry"
            className="text-white/45 hover:text-white/75"
          >
            audit mode →
          </Link>
        </span>
      </div>
    </footer>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-block rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-white/70">
      {children}
    </kbd>
  );
}
