"use client";

/**
 * Persona 5 (Rafael, Citizen Developer) — Agent Studio launchpad.
 *
 * Per TASK-19: Agent Studio is a real Gemini Enterprise feature. We do
 * not build it, and we do not simulate it. This page is the launchpad
 * into the real product — Rafael's actual experience in production
 * starts by opening Agent Studio in a browser tab.
 *
 * Two honest paths the demoer picks at run-time:
 *
 *  1. LIVE BUILD — click "Open Agent Studio" → does the live build in a
 *     separate tab against the pre-staged "Rig-Down Notification Agent"
 *     project. This is the persona's strongest demo moment per the spec.
 *     Requires NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL.
 *  2. RECORDED FALLBACK — click "Recorded fallback" → plays a clean
 *     60-second recording of the full build. Use when live is risky
 *     (slow network, untrusted environment). Requires
 *     NEXT_PUBLIC_AGENT_STUDIO_RECORDING_URL.
 *
 * If neither env var is set the corresponding button renders disabled
 * with a tooltip explaining what's missing. There is intentionally no
 * "scripted preview" of Agent Studio on this canvas — that was a
 * simulation of the product, which is exactly what the spec warns
 * against in §1.
 *
 * Below the launchpad: the rehearsal script the demoer narrates from
 * (per TASK-19 Step 4), so the script is at hand on the demo monitor.
 */

import { useEffect, useMemo } from "react";
import { usePathname } from "next/navigation";
import { ExternalLink, PlayCircle, Sparkles } from "lucide-react";

import { DemoTimer } from "@/components/demo/DemoTimer";
import { personaForPathname } from "@/data/personas";
import { publishDemoState } from "@/hooks/useDemoContext";
import { getPersona } from "@/lib/skin";
import { preWarmSession } from "@/lib/preWarmSession";

const RAFAEL = getPersona("rafael");
const RAFAEL_PROMPT =
  "I want to add a quick custom check: alert me when any Permian crew has been deployed > 21 days continuously.";

const AGENT_STUDIO_PROJECT_URL =
  process.env.NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL ?? "";
const AGENT_STUDIO_RECORDING_URL =
  process.env.NEXT_PUBLIC_AGENT_STUDIO_RECORDING_URL ?? "";

// Rehearsal script — verbatim from TASK-19 Step 4. Times are wall-clock
// targets in seconds from the start of Rafael's segment. The demoer reads
// or improvises from these as the live build progresses in the other tab.
const REHEARSAL_BEATS: Array<{ at: string; cue: string; action?: string }> = [
  {
    at: "0:00",
    cue: "Rafael's a field operations engineer in the Permian. Not a software developer. He keeps running into the same problem: when a rig goes down, the right people don't find out fast enough. Today he's going to fix that himself — in Agent Studio.",
  },
  {
    at: "0:15",
    cue: "He describes what he wants in plain language. No code.",
    action: "Type the last sentence of the agent's instruction",
  },
  {
    at: "0:30",
    cue: "He picks the tools — these are the same Maximo, SAP, and Knowledge Catalog tools the other agents use. Already registered, already governed. He's composing, not integrating.",
    action: "Pick three tools from the palette",
  },
  {
    at: "0:50",
    cue: "Who gets notified — the crew lead, Maria at the OCC, the basin scheduler.",
    action: "Set notification recipients",
  },
  {
    at: "1:05",
    cue: "He tests it. Agent Studio runs a sample rig-down on PX-114. It identifies the equipment, the crew, the customer commitment at risk, and drafts the notifications.",
    action: "Click Test",
  },
  {
    at: "1:30",
    cue: "He deploys. Sixty seconds, no code, a working agent.",
    action: "Click Deploy",
  },
  {
    at: "1:40",
    cue: "And here's the part that matters for IT: the moment Rafael deployed, his agent showed up in Agent Registry. Cryptographic identity. Subject to Agent Gateway policies and Model Armor — exactly like every other agent. Self-service doesn't mean ungoverned. Which is exactly what Ayesha cares about.",
    action: "Switch to Agent Registry (Persona 6 hand-off)",
  },
];

export default function AgentStudioScenarioPage() {
  const pathname = usePathname();
  const persona = useMemo(() => personaForPathname(pathname), [pathname]);

  // Pre-warm on mount so the persona's Memory Bank context is loaded when
  // the demoer switches into Agent Studio.
  useEffect(() => {
    if (!persona) return;
    void preWarmSession(persona);
  }, [persona]);

  // Publish minimal demo context (no beats — this page is event-driven via
  // the demoer's actual clicks into Agent Studio in another tab).
  useEffect(() => {
    if (!persona) return;
    const cleanup = publishDemoState({
      persona,
      currentBeatIndex: 0,
      totalBeats: 1,
      currentBeatId: "agent-studio-launchpad",
      narrationCue: REHEARSAL_BEATS[0].cue,
      nextBeatId: null,
      nextNarrationCue: null,
      mode: "live",
      connectionState: "idle",
      lastError: null,
      startedAt: null,
      onReset: null,
      onToggleMode: null,
      onPause: null,
      onSkipToEnd: null,
    });
    return cleanup;
  }, [persona]);

  return (
    <div
      className="min-h-screen overflow-y-auto"
      style={{ background: "var(--color-bg-base)" }}
    >
      <div className="mx-auto max-w-3xl px-8 py-12">
        <header className="border-b border-white/10 pb-6">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/40">
            {RAFAEL.name.split(" ")[0]} · {RAFAEL.role}
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-white">
            Agent Studio · live build
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-white/55">
            Rafael builds his agent in real Agent Studio — a Gemini Enterprise
            feature. The build doesn&apos;t happen on this canvas; it happens
            in the product, in a separate tab. This page is the launchpad
            plus the rehearsal script.
          </p>
        </header>

        <section className="mt-8">
          <div className="text-[10px] uppercase tracking-[0.18em] text-amber-200">
            Rafael&apos;s request
          </div>
          <div className="mt-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] p-4">
            <div className="text-sm leading-relaxed text-white/90">
              {RAFAEL_PROMPT}
            </div>
          </div>
        </section>

        <section className="mt-8">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/55">
            Two paths
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
            <LaunchpadAction
              icon={<ExternalLink className="h-5 w-5" />}
              label="Open Agent Studio"
              sub={
                AGENT_STUDIO_PROJECT_URL
                  ? "Pre-staged 'Rig-Down Notification Agent' project — opens in new tab"
                  : "NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL not configured"
              }
              href={AGENT_STUDIO_PROJECT_URL}
              accent="amber"
            />
            <LaunchpadAction
              icon={<PlayCircle className="h-5 w-5" />}
              label="Recorded fallback"
              sub={
                AGENT_STUDIO_RECORDING_URL
                  ? "Clean 60-second recording of the full build"
                  : "NEXT_PUBLIC_AGENT_STUDIO_RECORDING_URL not configured"
              }
              href={AGENT_STUDIO_RECORDING_URL}
              accent="sky"
            />
          </div>
          <div className="mt-3 flex items-start gap-2 text-[11px] text-white/45">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 text-amber-300" />
            <span>
              Pick before the demo, not during. If neither button is enabled,
              the only path is to narrate over the rehearsal script below —
              this is the weakest version of the persona and worth
              re-staging Agent Studio for.
            </span>
          </div>
        </section>

        <section className="mt-10">
          <div className="text-[10px] uppercase tracking-[0.18em] text-white/55">
            Rehearsal script · ~2 minutes
          </div>
          <ol className="mt-3 space-y-3">
            {REHEARSAL_BEATS.map((b, i) => (
              <li
                key={i}
                className="rounded-lg border border-white/10 bg-white/[0.03] p-4"
              >
                <div className="mb-1 flex items-center gap-3">
                  <span className="font-mono text-[10px] text-white/40">
                    {b.at}
                  </span>
                  {b.action && (
                    <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-emerald-200">
                      action · {b.action}
                    </span>
                  )}
                </div>
                <div className="text-sm leading-relaxed text-white/85">
                  {b.cue}
                </div>
              </li>
            ))}
          </ol>
        </section>

        {persona && (
          <DemoTimer
            targetMinutes={persona.targetDurationMin}
            startedAt={null}
          />
        )}
      </div>
    </div>
  );
}

function LaunchpadAction({
  icon,
  label,
  sub,
  href,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  sub: string;
  href: string;
  accent: "amber" | "sky";
}) {
  const accentBorder =
    accent === "amber" ? "border-amber-400/40" : "border-sky-400/40";
  const accentText = accent === "amber" ? "text-amber-200" : "text-sky-200";
  if (!href) {
    return (
      <div
        className={`flex items-start gap-3 rounded-lg border ${accentBorder} border-dashed bg-white/[0.02] p-4 opacity-60`}
        title={sub}
      >
        <div className={`mt-0.5 ${accentText}`}>{icon}</div>
        <div>
          <div className="text-sm font-medium text-white/70">
            {label}{" "}
            <span className="text-[10px] text-white/40">· disabled</span>
          </div>
          <div className="mt-0.5 text-[11px] text-white/45">{sub}</div>
        </div>
      </div>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`group flex items-start gap-3 rounded-lg border ${accentBorder} bg-white/[0.04] p-4 hover:bg-white/[0.08]`}
    >
      <div className={`mt-0.5 ${accentText}`}>{icon}</div>
      <div className="flex-1">
        <div className="text-sm font-medium text-white/90 group-hover:text-white">
          {label}
        </div>
        <div className="mt-0.5 text-[11px] text-white/55">{sub}</div>
      </div>
    </a>
  );
}
