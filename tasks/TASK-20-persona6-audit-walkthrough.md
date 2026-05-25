# TASK-18: Persona 6 (Ayesha) — Audit walkthrough scenario

**Prerequisites:** TASK-11 complete (governance infrastructure: Agent Identity, Gateway policies, Model Armor floor settings, the `/audit` view with four tabs, blocked-attack seeding). TASK-12 complete (demo runner with Ayesha's launcher tile). TASK-17 complete (Rafael's agent appears in the registry — the hand-off into this scenario).

**Estimated effort:** 2 days for one engineer.

**Stream:** Both (light — mostly scenario choreography on existing infrastructure)

---

## Context

**This task depends heavily on TASK-11 and does not re-build it.** TASK-11 already provisioned the governance infrastructure and built the `/audit` view with its four tabs (Agent Registry, Gateway Decisions, Model Armor Blocks, Agent Identities). This task is the **scenario layer**: the choreographed three-minute walkthrough Ayesha performs, the live blocked-attack moment, the cross-persona connection that ties the whole demo together, and the demo-runner integration.

Ayesha Khan is the Audit Director, Global. Her segment closes the demo. Where the other five personas showed agents *doing* things, Ayesha shows that everything they did is *accountable*. This is the persona that converts a technical buyer's "this is impressive" into a security stakeholder's "and we can actually deploy it." For a tier-one oilfield services major — with procurement audit, regulatory exposure, and a safety culture — this is often the segment that unblocks the deal.

The arc of her three minutes: she arrives right after Rafael deployed an agent (Persona 5). Her first move is to find that brand-new agent in Agent Registry — demonstrating that self-service automation is immediately visible to audit. Then she walks the governance surface: what every agent can reach, every authorization decision, every security scan. She closes with a live blocked-attack: she triggers a prompt-injection attempt and watches Model Armor block it in real time. The demo's final image is a governance system that works, not a promise that it will.

---

## Inputs

- TASK-11 complete (governance infrastructure + `/audit` view)
- TASK-12 complete (demo runner; Ayesha's launcher tile routes to `/audit`)
- TASK-17 complete (Rafael's rig-down agent in the registry — Ayesha finds it)
- Ayesha's Memory Profile (TASK-07)

---

## Deliverables

When this task is complete:

1. **Audit walkthrough choreography** — 5-6 beats covering: find Rafael's new agent → registry overview → gateway decisions → identities → live blocked attack
2. **Live blocked-attack moment** — Ayesha triggers a prompt-injection attempt and the canvas shows Model Armor blocking it in real time (not just pointing at an old log)
3. **Cross-persona connection** — the audit view can surface activity from the *other* personas' scenarios (Maria's MCP calls, Tomas's queries, Rafael's deployment) so Ayesha's "everything is logged" claim is concrete and specific
4. **Demo-runner integration** — Ayesha's segment has a backstage narration script; the launcher tile pre-warms her view
5. **A "guided tour" mode** for the `/audit` view — optional beat-advancing highlights that walk the eye to the right tab/row as the demoer narrates
6. **Handbook section** — Ayesha's segment in the demo handbook, including the recovery path if the live attack doesn't block cleanly

---

## Step-by-step instructions

### Step 1 — Define the walkthrough beats

`canvas/data/auditWalkthroughBeats.ts`:

```typescript
export const auditWalkthroughBeats = [
  {
    beatNumber: 0,
    durationMs: 0,
    description: "Ayesha's view loads on the Agent Registry tab",
    state: {
      activeTab: "registry",
      highlight: null,
      chatNarration: "Ayesha @ Audit Director, Global",
    },
  },
  {
    beatNumber: 1,
    durationMs: 4000,
    description: "Find Rafael's just-deployed agent — self-service is immediately visible",
    state: {
      activeTab: "registry",
      highlight: "rig-down-notification-agent",   // the row Rafael just created
      chatNarration: "Rafael deployed his rig-down agent sixty seconds ago. It's already here in Agent Registry — with an identity, under policy. Self-service automation, immediately visible to audit.",
    },
  },
  {
    beatNumber: 2,
    durationMs: 4000,
    description: "Registry overview — every MCP server, agent, tool; default-deny",
    state: {
      activeTab: "registry",
      highlight: null,
      chatNarration: "Every MCP server, every agent, every tool — catalogued here. Default-deny: anything not in this registry is unreachable. Your audit team can answer 'what can our agents touch?' from one screen.",
    },
  },
  {
    beatNumber: 3,
    durationMs: 4000,
    description: "Gateway decisions — every call, every authorization, cross-referenced to the personas",
    state: {
      activeTab: "gateway",
      highlight: null,
      chatNarration: "Every call from every agent routes through Agent Gateway. Here are the decisions from this very demo — Maria's MCP calls, Tomas's queries, all authorized, all logged. Notice the Plan Evaluator was denied write access — least privilege, enforced.",
    },
  },
  {
    beatNumber: 4,
    durationMs: 3500,
    description: "Agent Identities — five (now six) cryptographic identities",
    state: {
      activeTab: "identities",
      highlight: null,
      chatNarration: "Each agent has a cryptographic identity. mTLS by default. When an agent calls a tool, the Gateway knows exactly which agent — not just 'some service'.",
    },
  },
  {
    beatNumber: 5,
    durationMs: 5000,
    description: "Live blocked attack — Ayesha triggers a prompt injection; Model Armor blocks it in real time",
    state: {
      activeTab: "model-armor",
      highlight: "live-block",
      triggerLiveAttack: true,
      chatNarration: "Let me show you it's not theatre. I'll send a prompt-injection attempt right now — asking an agent to dump customer pricing and exfiltrate it. Watch the Model Armor tab. Blocked. Logged. No agent ever reasoned over the malicious payload.",
    },
  },
];
```

### Step 2 — Build the live blocked-attack trigger

The strongest version of this beat isn't pointing at an old log — it's triggering an attack live and watching it get blocked. Wire a button (or beat trigger) that sends the attack and surfaces the block.

`canvas/components/audit/LiveAttackDemo.tsx`:

```tsx
"use client";

import { useState } from "react";
import { ShieldAlert, ShieldCheck, Loader2 } from "lucide-react";

// DEMO NARRATION (Beat 5): "This is live. I'm sending a real prompt-injection
// attempt through Agent Gateway right now — asking an agent to disclose
// customer pricing and email it out. Model Armor inspects it at the boundary..."
export function LiveAttackDemo() {
  const [status, setStatus] = useState<"idle" | "sending" | "blocked" | "error">("idle");
  const [blockDetail, setBlockDetail] = useState<any>(null);

  const triggerAttack = async () => {
    setStatus("sending");
    try {
      const res = await fetch("/api/audit/trigger-attack", { method: "POST" });
      const data = await res.json();
      if (data.blocked) {
        setStatus("blocked");
        setBlockDetail(data);
      } else {
        // This should never happen; if Model Armor doesn't block, that's a problem
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
      <h3 className="text-lg font-medium mb-2">Live attack simulation</h3>
      <p className="text-sm text-white/60 mb-4">
        Sends a prompt-injection attempt through Agent Gateway. Model Armor should block it.
      </p>

      <button
        onClick={triggerAttack}
        disabled={status === "sending"}
        className="rounded-lg bg-red-500/20 text-red-300 border border-red-500/40 px-4 py-2 text-sm font-medium hover:bg-red-500/30 disabled:opacity-50"
      >
        {status === "sending" ? (
          <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Sending attack...</span>
        ) : (
          <span className="flex items-center gap-2"><ShieldAlert className="h-4 w-4" /> Trigger prompt-injection attempt</span>
        )}
      </button>

      {status === "blocked" && (
        <div className="mt-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-4">
          <div className="flex items-center gap-2 text-emerald-400 font-medium">
            <ShieldCheck className="h-5 w-5" /> Blocked by Model Armor
          </div>
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-white/60">Filter triggered</dt>
              <dd className="font-mono">{blockDetail?.filter ?? "prompt_injection"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-white/60">Confidence</dt>
              <dd className="font-mono">{blockDetail?.confidence ?? "HIGH"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-white/60">Logged to</dt>
              <dd className="font-mono">Cloud Logging</dd>
            </div>
          </dl>
          <div className="mt-2 text-xs text-white/40">
            No agent reasoned over the malicious payload. The block happened at the MCP boundary.
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="mt-4 text-sm text-amber-400">
          Attack not blocked as expected — fall back to the pre-seeded log example below.
        </div>
      )}
    </div>
  );
}
```

`canvas/app/api/audit/trigger-attack/route.ts`:

```typescript
import { NextResponse } from "next/server";

// Reuses the seed_blocked_attack logic from TASK-11, but invoked live.
export async function POST() {
  try {
    const result = await sendPromptInjectionThroughGateway();
    // Expect a 403/block from Model Armor
    return NextResponse.json({
      blocked: result.blocked,
      filter: result.filter,
      confidence: result.confidence,
      timestamp: new Date().toISOString(),
    });
  } catch (e) {
    return NextResponse.json({ blocked: false, error: String(e) }, { status: 500 });
  }
}
```

### Step 3 — Make the cross-persona connection concrete

Ayesha's "everything is logged" claim lands harder if the Gateway Decisions tab shows activity from the *actual* personas the customer just watched. After running Maria's and Tomas's scenarios, their MCP calls should be visible in the gateway log.

Ensure the `GatewayDecisionsPanel` (from TASK-11) can filter/highlight by agent or by recent session, so Ayesha can say "here's Maria's session from five minutes ago" and point at the actual calls.

Add a filter to the panel:

```tsx
// Enhancement to TASK-11's GatewayDecisionsPanel
// Add a session filter so Ayesha can show "Maria's cargo-plane session"
<select onChange={(e) => setSessionFilter(e.target.value)}>
  <option value="">All recent activity</option>
  <option value="demo-maria-cargo-plane-v1">Maria — cargo-plane session</option>
  <option value="demo-tomas-buffer-planning-v1">Tomas — buffer-planning session</option>
</select>
```

This requires the demo to have been run for Personas 2/3 before Ayesha's segment — which is the natural demo order anyway (she's last).

### Step 4 — Build the guided-tour highlight mode

To keep the audience's eye where the narration is, add optional highlight overlays that the beat advancement drives — e.g., when Beat 1 fires, the Rafael agent row in the registry gets a brief highlight ring.

`canvas/components/audit/useAuditTour.ts`:

```typescript
// Drives highlight state from the audit walkthrough beats.
// When a beat specifies a `highlight` target, the corresponding
// row/tab gets a highlight ring for the beat's duration.
export function useAuditTour(beats: typeof auditWalkthroughBeats) {
  // Reuse the useScenario hook pattern from TASK-08
  // Expose: activeTab, highlightTarget, advance/back/reset
}
```

The highlight is subtle — a ring or a soft glow on the relevant element — enough to guide the eye without looking gimmicky.

### Step 5 — Demo runner integration

Ayesha's launcher tile (TASK-12) routes to `/audit`. Enhance the `/audit` page to accept the walkthrough beats and the backstage narration:
- On entering from the demo runner, start at Beat 0
- Space advances through the walkthrough beats (driving tab switches and highlights)
- The backstage panel shows Ayesha's narration cues
- The live-attack beat (Beat 5) arms the `LiveAttackDemo` trigger

### Step 6 — Handbook section

Add to `docs/demo-handbook.md`:

```markdown
## Persona 6: Ayesha (3 min) — Audit walkthrough — CLOSING

### Setup
- Personas 2, 3, and 5 should have run already (their activity populates the
  gateway log and registry that Ayesha points at)
- Confirm a recent blocked-attack example exists (run `make seed-blocked-attack`
  if the live trigger is risky in this environment)

### Script
[Press 6 — opens /audit on the Registry tab]

[0:00] "Everything you've seen — six personas, agents reasoning, building,
deciding. Ayesha's job is to make sure all of it is accountable."

[0:15 — Beat 1] "Rafael deployed his agent a minute ago. Here it is in Agent
Registry already. Self-service, immediately visible."

[0:40 — Beat 2] "Every MCP server, agent, tool — catalogued. Default-deny."

[1:10 — Beat 3, Gateway tab] "Every call routes through Agent Gateway. Here's
Maria's session from earlier — her MCP calls, all authorized, all logged.
Notice the Plan Evaluator was denied write access. Least privilege, enforced."

[1:45 — Beat 4, Identities tab] "Five — now six — cryptographic agent identities.
mTLS by default."

[2:10 — Beat 5, Model Armor tab — THE CLOSER] "Let me show you it's not theatre."
[Click 'Trigger prompt-injection attempt']
"I'm sending a real injection attempt — dump customer pricing, exfiltrate it.
Watch Model Armor." [block appears] "Blocked. Logged. No agent ever saw the
payload."

[2:45] "Six personas, the full planning cycle, one platform — and every action
accountable. That's Agentic S&OP."

### Recovery
- If the live attack doesn't block cleanly (Beat 5 shows error): "Let me show
  you a recent one from the log instead" — switch to the pre-seeded block in
  the Model Armor tab. Always have `make seed-blocked-attack` run beforehand
  as backup.
- If the gateway log doesn't show Maria's session: run Maria's scenario again
  quickly, or point at the aggregate activity instead of a specific session.
```

### Step 7 — Commit

```bash
git add canvas/data/auditWalkthroughBeats.ts canvas/components/audit/LiveAttackDemo.tsx \
        canvas/components/audit/useAuditTour.ts canvas/app/api/audit/trigger-attack/ \
        canvas/app/audit/ docs/demo-handbook.md
git commit -m "feat: Persona 6 (Ayesha) audit walkthrough scenario (TASK-18)"
git push
```

---

## Acceptance criteria

- [ ] Audit walkthrough has 5-6 beats driving tab switches and highlights
- [ ] Beat 1 highlights Rafael's just-deployed agent in the registry (depends on TASK-17)
- [ ] Live blocked-attack trigger works: sends injection, Model Armor blocks, canvas shows the block in real time
- [ ] Gateway Decisions tab can filter to show a specific persona's session (Maria's, Tomas's)
- [ ] Guided-tour highlights guide the eye without looking gimmicky
- [ ] Demo runner integration: launcher tile routes here, Space advances beats, backstage shows narration
- [ ] Handbook section complete with the closing script and recovery path
- [ ] Scenario fits in ~3 minutes and lands as the demo's closer
- [ ] Every demo-significant component has a `// DEMO NARRATION:` comment
- [ ] Does NOT duplicate TASK-11's infrastructure — builds on it
- [ ] Commit pushed

---

## Common pitfalls

**Live attack not blocking on demo day.** Model Armor thresholds can be tuned such that a specific phrasing slips through. Test the exact attack payload in rehearsal that same day. Always have the pre-seeded log block (`make seed-blocked-attack`) as the fallback. Never rely solely on the live trigger.

**Re-building TASK-11.** This task is the scenario layer. If you find yourself re-provisioning Agent Identities or re-writing Gateway policies, stop — that's TASK-11's job. This task choreographs the walkthrough on top of what TASK-11 built.

**Empty gateway log.** If Personas 2/3 haven't run in this session, the gateway decisions tab is empty and Ayesha's "here's Maria's session" falls flat. Enforce demo order (Ayesha last) or pre-seed representative gateway activity.

**The closer running long.** Ayesha is the closer; if she runs to 5 minutes, the demo overshoots. The live-attack beat is the moment — everything before it should be brisk. Rehearse to 3 minutes.

**Highlight overlays looking gimmicky.** A subtle ring guides the eye; a flashing animated arrow looks like a tutorial for children. Keep highlights restrained — these are security professionals, not a consumer app onboarding.

**Rafael's agent not yet propagated.** Beat 1 depends on Rafael's agent (TASK-17) being in the registry. If there's a propagation delay from his deployment, either wait or have it pre-deployed. Coordinate the Persona 5 → Persona 6 hand-off timing in rehearsal.

---

## References

- TASK-11 (the infrastructure this builds on): `claude_code_specs/tasks/TASK-11-governance.md`
- TASK-17 (Rafael's agent, the hand-off): `claude_code_specs/tasks/TASK-17-persona5-agent-studio.md`
- Model Armor: `https://docs.cloud.google.com/model-armor/configure-floor-settings`
- Agent Registry: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry`

---

*When TASK-18 is complete, all six personas are demoable end-to-end. Ayesha closes the demo by converting "impressive" into "deployable" — the governance posture is not a promise, it's a working system the customer watched block an attack in real time.*
