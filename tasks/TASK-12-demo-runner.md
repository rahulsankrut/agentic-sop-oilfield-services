# TASK-12: Demo storyboard wiring and rehearsal mode

**Prerequisites:** TASK-11 complete. Live WebSocket mode works, governance posture is demo-visible, all six persona scenarios have backend support.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Both (backend session orchestration + frontend control surface)

---

## Context

We have the pieces. We do not yet have a **demo we can run cold in front of a customer**. The difference is the connective tissue: how does the demoer move between personas without fumbling? How is the audience kept oriented on which persona they're seeing? What's the recovery path if a scenario fails mid-run? How does rehearsal work?

This task builds the demo runner — a thin layer on top of everything else — that turns "six working scenarios" into "one 18-minute presentation that lands every time."

Three things happen:

1. **Persona launcher** — a unified entry point that lets the demoer pick a persona and trigger their scenario. Lives in the canvas at `/demo` and inside the GE app as a small custom panel.

2. **Rehearsal mode** — full keyboard control surface: persona switch, beat-by-beat advance, mode toggle (live / static / replay), pause-and-explain at any beat, reset, and a backstage view that shows the demoer the next narration cue.

3. **Recovery patterns** — explicit handling for the three failure modes that matter: agent timeout (auto-fallback to replay mode for the current scenario), WebSocket disconnect (recovery banner with one-click reconnect), and customer interrupt during a scenario (clean pause-and-resume).

The goal: the demoer can present this to a customer without rehearsing the underlying technology each time. Same way a salesperson uses a deck — the structure is fixed, the delivery improves with reps, but the structure does not need to be reconstructed from scratch every demo.

---

## Inputs

- TASK-11 complete (governance demoable for Persona 6)
- TASK-10 complete (live mode working for Personas 2 and 3)
- Persona narratives from `agentic_sop_oilfield_services_brief.md`
- Operations Canvas storyboard for Persona 3 from `persona3_canvas_storyboard.md`

---

## Deliverables

When this task is complete:

1. **Persona launcher** at `/demo` in the canvas — six tiles, one per persona, with persona name, role, scenario one-liner, and the trigger button
2. **Rehearsal control surface** — keyboard shortcuts documented and reliable: `1-6` jumps to that persona, `Space` advances the beat, `Shift+Space` goes back a beat, `L` toggles live/static/replay, `P` pauses, `R` resets the current scenario, `\` opens the backstage panel
3. **Backstage panel** — overlay (toggle with `\`) showing: current beat, next beat preview, narration cue for the current beat, technical state (connection status, current event, last error), and quick-action buttons (skip to end, restart, switch mode)
4. **Persona session pre-warm** — when the demoer selects a persona, the right Memory Profile is loaded, the right deterministic session is selected, the canvas pre-renders Beat 0 — so when they hit Space, Beat 1 happens immediately
5. **Failure recovery** — agent timeout falls back to Replay mode for the current scenario with a small notice; WebSocket disconnect shows a reconnect banner; manual reset always works
6. **Demo timer** — small unobtrusive timer in the corner showing elapsed time per scenario, with the published target time (e.g., "3:12 / 5:00" for Persona 3)
7. **Pre-flight checklist** — `make demo-preflight` runs a quick verification: registered MCP servers respond, Knowledge Catalog query returns expected entry, Memory Profiles loaded, blocked-attack example recent enough, canvas builds clean
8. **Demo handbook** at `docs/demo-handbook.md` — the demoer's playbook: pre-flight steps, persona-by-persona walkthrough with narration cues, recovery scripts, what to do when things go wrong

---

## Step-by-step instructions

### Step 1 — Build the persona launcher

`canvas/app/demo/page.tsx`:

```tsx
"use client";

import Link from "next/link";

import { PERSONAS } from "@/data/personas";

// DEMO NARRATION (Pre-demo): "This is the persona launcher. Six tiles,
// six S&OP roles. We'll walk through them in cycle order: David sees the
// demand signal, Tomas plans the supply response, Maria handles the
# active gap, Priya gets the executive briefing, Rafael builds his own
# agent, Ayesha audits the whole thing."
export default function DemoLauncherPage() {
  return (
    <main className="min-h-screen p-12">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-wider text-white/40">Demo runner</div>
        <h1 className="text-3xl font-semibold mt-1">Agentic S&OP for Oilfield Services</h1>
        <p className="text-sm text-white/60 mt-2 max-w-2xl">
          Six personas, six scenarios, one S&OP cycle. Select a persona to begin, or press 1–6
          to jump directly. The full demo runs ~18 minutes; individual scenarios run 2-5 minutes.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-6xl">
        {PERSONAS.map((p, idx) => (
          <Link
            key={p.id}
            href={p.route}
            className="group rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10 transition-colors"
          >
            <div className="flex items-baseline justify-between mb-3">
              <div className="text-xs uppercase tracking-wider text-white/40">
                Persona {idx + 1}
              </div>
              <kbd className="text-xs text-white/50 bg-white/10 px-1.5 py-0.5 rounded">
                {idx + 1}
              </kbd>
            </div>
            <div className="text-xl font-medium">{p.displayName}</div>
            <div className="text-sm text-white/70 mt-1">{p.role}</div>
            <div className="text-sm text-white/60 mt-4 line-clamp-3">{p.scenario_oneliner}</div>
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-white/10">
              <div className="text-xs text-white/40">
                Target: {p.target_duration_min} min
              </div>
              <div className="text-xs text-white/40">
                S&OP stage: {p.sop_stage}
              </div>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-8 text-xs text-white/40 max-w-2xl">
        <p>
          Press <kbd className="bg-white/10 px-1 rounded">\</kbd> at any time to open the backstage
          panel. Press <kbd className="bg-white/10 px-1 rounded">?</kbd> for the full keyboard reference.
        </p>
      </div>
    </main>
  );
}
```

`canvas/data/personas.ts`:

```typescript
export interface Persona {
  id: string;
  number: number;
  displayName: string;
  role: string;
  sop_stage: string;
  scenario_oneliner: string;
  route: string;
  target_duration_min: number;
  memory_profile_user_id: string;
  session_id: string;
}

export const PERSONAS: Persona[] = [
  {
    id: "david",
    number: 1,
    displayName: "David Okeke",
    role: "Basin Leader — West Africa",
    sop_stage: "Demand sensing",
    scenario_oneliner: "Reviews Q4 ML forecast, overrides two basins with qualitative rationale that gets re-ingested into the model.",
    route: "/scenarios/forecast-review",
    target_duration_min: 3,
    memory_profile_user_id: "david-basin-leader-west-africa",
    session_id: "demo-david-forecast-review-v1",
  },
  {
    id: "tomas",
    number: 2,
    displayName: "Tomas Reyes",
    role: "Fleet Scheduler — Permian",
    sop_stage: "Demand-to-supply planning",
    scenario_oneliner: "Sets Q3 fleet buffer for ExxonMobil-Permian with probabilistic forecast and explicit risk-tolerance slider.",
    route: "/scenarios/buffer-planning",
    target_duration_min: 3,
    memory_profile_user_id: "tomas-fleet-scheduler-permian",
    session_id: "demo-tomas-buffer-planning-v1",
  },
  {
    id: "maria",
    number: 3,
    displayName: "Maria Adeyemi",
    role: "OCC Planner — West Africa",
    sop_stage: "Supply response",
    scenario_oneliner: "Pivots a $420K cargo plane charter to a $40K ground transit from Lagos via functional equivalence. $380K avoided.",
    route: "/scenarios/cargo-plane",
    target_duration_min: 5,
    memory_profile_user_id: "maria-occ-planner-west-africa",
    session_id: "demo-maria-cargo-plane-v1",
  },
  {
    id: "priya",
    number: 4,
    displayName: "Priya Krishnan",
    role: "Operations VP — Global",
    sop_stage: "Strategic review",
    scenario_oneliner: "Deep Research Agent answers 'what's my West African deepwater exposure?' with citation-grounded briefing.",
    route: "/scenarios/deep-research",
    target_duration_min: 2,
    memory_profile_user_id: "priya-operations-vp-global",
    session_id: "demo-priya-deep-research-v1",
  },
  {
    id: "rafael",
    number: 5,
    displayName: "Rafael Santos",
    role: "Citizen Developer — Permian",
    sop_stage: "Self-service automation",
    scenario_oneliner: "Builds a new 'rig-down notification' agent live in Agent Studio in under 60 seconds.",
    route: "/scenarios/agent-studio",
    target_duration_min: 2,
    memory_profile_user_id: "rafael-citizen-dev-permian",
    session_id: "demo-rafael-agent-studio-v1",
  },
  {
    id: "ayesha",
    number: 6,
    displayName: "Ayesha Khan",
    role: "Audit Director — Global",
    sop_stage: "Governance",
    scenario_oneliner: "Audits the agent ecosystem via Agent Registry, Gateway decisions, Model Armor blocks, Agent Identities.",
    route: "/audit",
    target_duration_min: 3,
    memory_profile_user_id: "ayesha-audit-director-global",
    session_id: "demo-ayesha-audit-v1",
  },
];
```

### Step 2 — Build the rehearsal control surface

A global keyboard handler that works across all scenario routes.

`canvas/components/demo/RehearsalControls.tsx`:

```tsx
"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";

import { PERSONAS } from "@/data/personas";
import { BackstagePanel } from "./BackstagePanel";
import { HelpOverlay } from "./HelpOverlay";

export function RehearsalControls() {
  const router = useRouter();
  const pathname = usePathname();
  const [backstageOpen, setBackstageOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      // Number keys 1-6 jump to persona
      if (/^[1-6]$/.test(e.key) && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        const p = PERSONAS[parseInt(e.key, 10) - 1];
        if (p) router.push(p.route);
        return;
      }

      // Backstage panel toggle
      if (e.key === "\\") {
        e.preventDefault();
        setBackstageOpen((b) => !b);
        return;
      }

      // Help overlay
      if (e.key === "?") {
        e.preventDefault();
        setHelpOpen((h) => !h);
        return;
      }

      // Home (back to demo launcher)
      if (e.key === "Home" || (e.key === "0" && !e.metaKey)) {
        e.preventDefault();
        router.push("/demo");
        return;
      }

      // Other shortcuts (Space, Shift+Space, L, P, R) are handled per-scenario
      // because the actions depend on the current scenario's state machine
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  return (
    <>
      {backstageOpen && <BackstagePanel onClose={() => setBackstageOpen(false)} pathname={pathname} />}
      {helpOpen && <HelpOverlay onClose={() => setHelpOpen(false)} />}
    </>
  );
}
```

Mount it in the root layout:

```tsx
// canvas/app/layout.tsx
import { RehearsalControls } from "@/components/demo/RehearsalControls";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="h-screen overflow-hidden">
        <RehearsalControls />
        {children}
      </body>
    </html>
  );
}
```

### Step 3 — Build the backstage panel

The backstage panel is the demoer's coach. It shows the next thing they should say, the current scenario state, the technical health of the connection, and quick-action buttons.

`canvas/components/demo/BackstagePanel.tsx`:

```tsx
"use client";

import { motion } from "framer-motion";
import { X, RotateCcw, FastForward, Pause, Play } from "lucide-react";

import { useDemoContext } from "@/hooks/useDemoContext";

interface BackstagePanelProps {
  onClose: () => void;
  pathname: string;
}

// DEMO NARRATION (off-screen — for the demoer): "This is the backstage
# panel. The audience doesn't see it. The demoer sees the current beat,
# the narration cue, technical state, and quick actions. If something
# goes wrong, recovery is one click away."
export function BackstagePanel({ onClose, pathname }: BackstagePanelProps) {
  const { currentScenario, currentBeat, totalBeats, narrationCue, connectionState, mode, lastError } = useDemoContext();

  return (
    <motion.div
      initial={{ x: 400, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 400, opacity: 0 }}
      className="fixed top-0 right-0 z-50 h-screen w-[400px] bg-bg-elevated border-l border-white/10 shadow-2xl overflow-y-auto"
    >
      <div className="sticky top-0 bg-bg-elevated border-b border-white/10 p-4 flex items-center justify-between">
        <h2 className="text-sm font-medium">Backstage</h2>
        <button onClick={onClose} className="text-white/60 hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4 space-y-6">
        {/* Current scenario */}
        <section>
          <div className="text-xs uppercase tracking-wider text-white/40 mb-2">Now playing</div>
          <div className="text-lg font-medium">{currentScenario?.displayName ?? "—"}</div>
          <div className="text-sm text-white/60">{currentScenario?.role}</div>
        </section>

        {/* Beat indicator */}
        <section>
          <div className="text-xs uppercase tracking-wider text-white/40 mb-2">
            Beat {currentBeat + 1} of {totalBeats}
          </div>
          <div className="flex gap-1">
            {Array.from({ length: totalBeats }).map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full ${
                  i < currentBeat ? "bg-white" : i === currentBeat ? "bg-amber-400" : "bg-white/20"
                }`}
              />
            ))}
          </div>
        </section>

        {/* Narration cue — the most important thing on this panel */}
        <section className="rounded-lg bg-amber-400/10 border border-amber-400/30 p-3">
          <div className="text-xs uppercase tracking-wider text-amber-400/80 mb-2">
            Say next
          </div>
          <div className="text-sm text-white/90 leading-relaxed">
            {narrationCue ?? "—"}
          </div>
        </section>

        {/* Technical state */}
        <section>
          <div className="text-xs uppercase tracking-wider text-white/40 mb-3">Technical</div>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-white/60">Mode</dt>
              <dd className="font-mono">{mode.toUpperCase()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-white/60">Connection</dt>
              <dd className={`font-mono ${
                connectionState === "open" ? "text-emerald-400" :
                connectionState === "error" ? "text-red-400" : "text-amber-400"
              }`}>{connectionState}</dd>
            </div>
            {lastError && (
              <div className="text-red-300 text-xs mt-2">Error: {lastError}</div>
            )}
          </dl>
        </section>

        {/* Quick actions */}
        <section>
          <div className="text-xs uppercase tracking-wider text-white/40 mb-3">Quick actions</div>
          <div className="grid grid-cols-2 gap-2">
            <ActionButton icon={<RotateCcw className="h-4 w-4" />} label="Restart" shortcut="R" onClick={() => {/* reset */}} />
            <ActionButton icon={<FastForward className="h-4 w-4" />} label="Skip to end" shortcut="" onClick={() => {/* jump */}} />
            <ActionButton icon={<Pause className="h-4 w-4" />} label="Pause" shortcut="P" onClick={() => {/* pause */}} />
            <ActionButton label="Switch mode" shortcut="L" onClick={() => {/* toggle */}} />
          </div>
        </section>
      </div>
    </motion.div>
  );
}


function ActionButton({ icon, label, shortcut, onClick }: any) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-between rounded-lg bg-white/5 hover:bg-white/10 p-2 text-sm transition-colors"
    >
      <span className="flex items-center gap-2">
        {icon}
        {label}
      </span>
      {shortcut && (
        <kbd className="text-xs bg-white/10 px-1 rounded">{shortcut}</kbd>
      )}
    </button>
  );
}
```

The `useDemoContext` hook reads scenario state from a React context provider that wraps the app.

### Step 4 — Pre-warm sessions on persona selection

When the demoer clicks (or hotkeys to) a persona, the backend should pre-load that persona's Memory Profile and seed the deterministic session, so Beat 1 is instant.

`canvas/lib/preWarmSession.ts`:

```typescript
import type { Persona } from "@/data/personas";

export async function preWarmSession(persona: Persona): Promise<void> {
  // Tell the orchestrator backend to:
  // 1. Load the Memory Profile for this user
  // 2. Activate the deterministic session
  // 3. Reset any in-flight state
  await fetch("/api/demo/pre-warm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: persona.memory_profile_user_id,
      session_id: persona.session_id,
    }),
  });
}
```

Call from the scenario page's mount effect:

```tsx
useEffect(() => {
  preWarmSession(currentPersona);
}, [currentPersona.id]);
```

### Step 5 — Build the demo timer

Unobtrusive elapsed-time display per scenario.

`canvas/components/demo/DemoTimer.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";

interface DemoTimerProps {
  targetMinutes: number;
  startedAt?: Date;
}

export function DemoTimer({ targetMinutes, startedAt }: DemoTimerProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startedAt) return;
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const overTarget = elapsed > targetMinutes * 60;

  return (
    <div className={`absolute bottom-6 right-6 rounded-full px-3 py-1 text-xs font-mono ${
      overTarget ? "bg-amber-400/20 text-amber-400" : "bg-white/5 text-white/60"
    }`}>
      {minutes}:{seconds.toString().padStart(2, "0")} / {targetMinutes}:00
    </div>
  );
}
```

### Step 6 — Build the failure recovery handlers

Three failure modes need explicit handling:

**Mode A: Agent timeout.** If a scenario's `workflow.completed` event doesn't arrive within 30 seconds of the trigger, auto-fall-back to Replay mode for the current scenario.

```typescript
// canvas/hooks/useScenarioWithFallback.ts
export function useScenarioWithFallback(persona: Persona) {
  const live = useLiveScenario({ /* ... */ });
  const replay = useReplayScenario({ recording: `cargo_plane_v1.json` });
  const [usingFallback, setUsingFallback] = useState(false);

  // If live mode but no workflow.completed within 30s, switch to replay
  useEffect(() => {
    if (live.connectionState !== "open" || live.workflowCompleted) return;
    const timeout = setTimeout(() => {
      console.warn("Workflow timeout — falling back to replay mode");
      setUsingFallback(true);
    }, 30_000);
    return () => clearTimeout(timeout);
  }, [live.connectionState, live.workflowCompleted]);

  const state = usingFallback ? replay.state : live.state;
  return { state, usingFallback };
}
```

**Mode B: WebSocket disconnect.** Show a small banner in the chat panel with a reconnect button. Don't auto-reconnect more than 3 times — surface the issue clearly.

**Mode C: Manual reset.** `R` key always works, even mid-scenario. Resets canvas state, re-pre-warms the session, lets the demoer try again.

### Step 7 — Build the pre-flight check script

```python
# scripts/demo_preflight.py
"""Pre-flight verification before a customer demo.

Run this 30-60 minutes before the demo. Catches anything that needs
fixing while there's time to fix it.
"""

import sys

CHECKS = []


def check(name: str):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


@check("MCP servers respond")
async def check_mcp_servers():
    """Each registered MCP server returns 200 from its health endpoint."""
    for server in ["sap-mcp-server", "maximo-mcp-server", "fdp-mcp-server"]:
        url = await get_mcp_server_url(server)
        response = await http_get(f"{url}/health")
        assert response.status == 200, f"{server} unhealthy"


@check("Knowledge Catalog query returns canonical Tool X")
async def check_kc_canonical_query():
    """The managed KC MCP returns Tool X entry with all expected aliases."""
    result = await call_kc_mcp_tool("lookup_entry", canonical_id="TX-001")
    assert result["aspects"]["cross_system_aliases"]["sap_material_number"] == "MAT-67890"
    assert result["aspects"]["functional_equivalence"]["equivalents"][0]["equivalent_canonical_id"] == "TX-007"


@check("Memory Profiles loaded for all six personas")
async def check_memory_profiles():
    """All six persona profiles exist in Memory Bank."""
    for persona in PERSONAS:
        profile = await fetch_memory_profile(persona["memory_profile_user_id"])
        assert profile is not None, f"Missing profile: {persona['id']}"
        assert profile["display_name"] == persona["display_name"]


@check("Blocked-attack example recent enough")
async def check_blocked_attack_logged():
    """Model Armor logs show a recent prompt-injection block (within 7 days)."""
    logs = await fetch_recent_model_armor_blocks(limit=10)
    recent = [l for l in logs if (datetime.utcnow() - l.timestamp).days < 7]
    if not recent:
        print("⚠️  No recent blocked attack in logs. Run: make seed-blocked-attack")
        return False


@check("Cargo-plane scenario produces correct output")
async def check_cargo_plane_scenario():
    """Run the cargo-plane scenario end-to-end; verify Lagos result and $380K avoided cost."""
    response = await run_orchestrator(
        user_input="I need a Tool X variant in Luanda by Friday",
        session_id="preflight-cargo-plane",
        user_id="maria-occ-planner-west-africa",
    )
    plan = response.output
    assert plan["primary_option"]["source_location"]["label"] == "Lagos, Nigeria"
    assert plan["avoided_cost_usd"] > 300_000


@check("Canvas builds clean")
def check_canvas_builds():
    """`npm run build` in canvas/ exits 0."""
    result = subprocess.run(["npm", "run", "build"], cwd="canvas/", capture_output=True)
    assert result.returncode == 0, f"Canvas build failed: {result.stderr.decode()}"


async def main():
    failures = []
    for name, fn in CHECKS:
        try:
            print(f"⏳ {name}...")
            result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
            if result is False:
                failures.append(name)
                print(f"⚠️  {name}: WARNING")
            else:
                print(f"✅ {name}")
        except Exception as e:
            failures.append(name)
            print(f"❌ {name}: {e}")

    if failures:
        print(f"\n{len(failures)} failure(s). Fix before demo.")
        sys.exit(1)
    print(f"\n✅ All {len(CHECKS)} checks passed. Demo ready.")


if __name__ == "__main__":
    asyncio.run(main())
```

Add to Makefile:

```makefile
demo-preflight:
	uv run python scripts/demo_preflight.py
```

### Step 8 — Write the demo handbook

`docs/demo-handbook.md`:

```markdown
# Demo handbook — Agentic S&OP for Oilfield Services

This is the demoer's playbook. Read it before your first demo. Keep it
open on a second monitor during the demo for narration cues.

## Pre-flight (45-60 min before demo)

1. Run `make demo-preflight` — fix anything that fails before continuing
2. Run `make seed-blocked-attack` if the preflight reports the blocked-attack
   example is older than a week
3. Open the canvas at `/demo` in Chrome at the demo display's native resolution
4. Test each scenario at least once. Watch the timer. Note any timing issues.
5. Identify your fallback strategy: if live mode breaks, you fall back to
   replay mode (press `Shift+L`). If the canvas breaks entirely, fall back
   to the recorded walkthrough video (URL: ...)

## The demo flow (target 18 minutes)

### 0:00 — Opening (1 min)
"Today I'm showing you Agentic S&OP. Six personas across the planning cycle,
six concrete scenarios. The agents are built on Gemini Enterprise Agent
Platform — ADK 2.0 workflows on Agent Runtime, governed by Agent Registry,
Agent Gateway, and Model Armor."

[Open /demo. Six tiles visible.]

### 1:00 — Persona 1: David (3 min)
[Press 1]

"David is the West Africa basin leader. He's reviewing the Q4 ML forecast..."

[See backstage panel for the full beat-by-beat narration cues.]

Key narration moments:
- Beat 1: "ML forecast loaded — but David has knowledge the model doesn't."
- Beat 2: "He overrides two basins with qualitative rationale."
- Beat 3: "Watch — the rationale is re-ingested into the model via Knowledge Catalog."

Target time: 3:00. Acceptable: 2:30-3:30.

### 4:00 — Persona 2: Tomas (3 min)
[Press 2]

[Full Tomas narration]

### 7:00 — Persona 3: Maria — CENTERPIECE (5 min)
[Press 3]

This is the cargo-plane scenario. Take your time. The avoided cost moment
is the demo's strongest beat — don't rush it.

[Full Maria beat-by-beat narration with explicit Agent Registry, Knowledge
Catalog, MCP, and avoided cost callouts. See persona3_canvas_storyboard.md
for the complete text.]

### 12:00 — Persona 4: Priya (2 min)
[Press 4]

[Priya narration]

### 14:00 — Persona 5: Rafael (2 min)
[Press 5]

[Rafael narration — live Agent Studio build]

### 16:00 — Persona 6: Ayesha (3 min)
[Press 6]

Audit Mode opens. Take the customer through the four tabs:
- Agent Registry: "Every registered MCP server, every tool, every agent. Default-deny."
- Gateway: "Every call, every authorization decision, in the log."
- Model Armor: "Recent blocks. Here's a prompt-injection attempt from yesterday."
- Identities: "Five agents, five cryptographic identities, mTLS by default."

### 19:00 — Wrap (2 min)
"Six personas. The full S&OP cycle. One platform. Questions?"

## Recovery scripts

**If live mode fails mid-scenario:**
"Let me switch to replay mode so I can finish telling this story."
[Press Shift+L until indicator shows REPLAY]

**If WebSocket disconnects:**
[Backstage panel shows the error]
"One second — let me reconnect."
[Click the reconnect button]

**If the canvas itself crashes:**
[Reload the tab]
[Press the number key for the persona you were on]
"Apologies — picking up where we left off."

**If the customer interrupts mid-scenario:**
[Press P to pause]
"Great question. Let me pause here and address it."
[Answer]
[Press P to resume, or press R to restart that scenario]

## Keyboard reference

| Key | Action |
|---|---|
| 1-6 | Jump to persona |
| 0 / Home | Back to launcher |
| Space | Advance beat |
| Shift+Space | Previous beat |
| L | Toggle Live / Static |
| Shift+L | Toggle Live / Static / Replay |
| P | Pause auto-advance |
| R | Reset current scenario |
| \\ | Open backstage panel |
| ? | Show help overlay |

## Common questions and answers

**"Is this running on real customer data?"**
"No — synthetic data with realistic shape. The platform integration patterns
(MCP, Agent Registry, Knowledge Catalog, governance) are real. In your
production deployment, your real SAP/Maximo/FDP plug into the same MCP
infrastructure."

**"What did you build vs. what's the platform?"**
"We built four things: the Capacity Orchestrator Workflow, the three custom
MCP servers (SAP/Maximo/FDP mocks — the real ones in your environment), the
Knowledge Catalog content (custom Aspect Types for oilfield assets), and
the Operations Canvas frontend. Everything else — Agent Runtime, Agent
Registry, Agent Gateway, Agent Identity, Memory Bank, Sessions, Model Armor,
the Knowledge Catalog managed MCP server, Cloud Trace — is platform."

**"How long would it take to deploy in our environment?"**
[Tailored to the customer's engagement stage — typically 7-9 weeks for
Gate 3 POC scope on synthetic data; longer for production integration]
```

### Step 9 — Commit

```bash
git add canvas/app/demo/ canvas/components/demo/ canvas/data/personas.ts \
        canvas/hooks/useDemoContext.ts canvas/lib/preWarmSession.ts \
        scripts/demo_preflight.py docs/demo-handbook.md
git commit -m "feat: demo runner with rehearsal controls and recovery (TASK-12)"
git push
```

---

## Acceptance criteria

- [ ] Persona launcher at `/demo` shows six tiles with all metadata
- [ ] Number keys 1-6 jump to each persona's scenario from anywhere
- [ ] Backstage panel (toggle with `\`) shows current beat, narration cue, technical state, quick actions
- [ ] Help overlay (toggle with `?`) lists all keyboard shortcuts
- [ ] Pre-warm session loads Memory Profile and seeds session before Beat 0 renders
- [ ] Demo timer shows elapsed time per scenario with target
- [ ] Live → Replay auto-fallback on agent timeout (30s)
- [ ] WebSocket disconnect shows reconnect banner with one-click reconnect
- [ ] Manual reset (`R`) works at any time
- [ ] `make demo-preflight` runs all checks and exits 0 if ready
- [ ] `docs/demo-handbook.md` is complete and usable by someone who didn't build the system
- [ ] All six personas have a working scenario path (even if Persona 4/5 are minimal — they have a route, a backstage cue, a target time)
- [ ] Commit pushed

---

## Common pitfalls

**Hotkey conflicts with browser shortcuts.** `Cmd+R` reloads. `Cmd+L` focuses URL bar. Avoid Cmd/Ctrl combinations for demo controls. Plain letters and digits work because the demoer's hands are off the keyboard during narration.

**Backstage panel showing stale narration cues.** The narration cue is keyed to the current beat. If the scenario state machine and the backstage state get out of sync, the demoer sees the wrong cue. Use a single source of truth (the scenario state) for both.

**Pre-warm taking longer than expected.** Memory Profile load + session seed can take 2-3 seconds. Show a small spinner during pre-warm; don't render Beat 0 until ready. Otherwise the demoer hits Space too early and beats run out of order.

**Demo timer showing red on first run.** If the timer goes amber/red the moment you hit the persona, it's because `startedAt` defaults to scenario load time instead of trigger time. Set `startedAt` when the first user action happens, not on mount.

**Recovery banner partially obscuring the canvas.** Position the reconnect banner at top center — not over the map area where the cargo-plane scenario plays. Test in actual scenario context.

**`make demo-preflight` failing on first run.** First run after a code change often has stale state. Run twice; if both fail consistently, the failure is real.

**Demo handbook getting out of sync with the implementation.** Every time a beat changes or a key shortcut is renamed, update the handbook. This is the single most likely doc to rot. Add a hash of the handbook to `make demo-preflight` and fail the check if it hasn't been touched in 30 days.

**Six personas, only three substantive.** Personas 1, 4, and 5 are lighter in this build. Make sure the demo handbook is honest about this — the demoer shouldn't oversell Persona 4 as the centerpiece if it's actually a 2-minute Deep Research Agent demo with less custom canvas.

**Recovery mode visible to audience.** The backstage panel is for the demoer. If the customer sees "live connection error" in big red text on the projector, that's the wrong story. Keep error messaging muted and recoverable. If something goes wrong, fall back silently.

---

## References

- Persona narratives: `agentic_sop_oilfield_services_brief.md`
- Cargo-plane storyboard: `persona3_canvas_storyboard.md`
- Recovery patterns: `https://www.nngroup.com/articles/error-recovery/`

---

*When TASK-12 is complete, the demo is a thing you can run end-to-end with one keystroke per persona. The next batch (TASK-13–15) packages it for customer-specific delivery: skinning, deployment, polish.*
