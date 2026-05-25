# TASK-17: Persona 5 (Rafael) — Agent Studio live build scenario

**Prerequisites:** TASK-11 complete (governance — so the agent Rafael builds is immediately governable), TASK-12 complete (demo runner with Rafael's launcher tile).

**Estimated effort:** 2-3 days for one engineer (mostly scripting + staging, minimal custom code).

**Stream:** Demo engineering (light)

---

## Context

Rafael Santos is a Digital Operations Engineer in the Permian — a **citizen developer**, not a software engineer. His scenario is the platform's no-code/low-code story: *"watch a non-developer build a useful, governed agent in under 60 seconds."*

This is the **lightest task in the build** because we are not building software. **Agent Studio** is a real Gemini Enterprise feature — a visual, low-code agent builder. Rafael's scenario is a *scripted live demonstration* of Agent Studio, not custom development. The deliverables are a rehearsal script, a pre-staged starting state in Agent Studio (so the live build is fast and reliable), the specific agent to build, and a recorded fallback for when live demos go sideways.

The strategic point this persona makes: agentic AI on this platform is not locked behind the engineering team. A field-adjacent engineer like Rafael can build an agent that solves a real local problem — and the moment he does, that agent is automatically subject to the same governance as everything else (Agent Registry, Agent Gateway, Agent Identity, Model Armor). Self-service does not mean ungoverned. That's the closing beat, and it hands off naturally to Ayesha (Persona 6).

The agent Rafael builds: a **"rig-down notification agent"** that watches for rig-down events, identifies the affected crew and equipment, and notifies the right people through the right channels. It's small, it's recognizable to anyone in the field, and it's the kind of thing that today requires a ticket to IT and a three-week wait.

---

## Inputs

- TASK-11 complete (governance — Agent Registry, Gateway, Identity, Model Armor)
- TASK-12 complete (demo runner; Rafael's launcher tile exists)
- Rafael's Memory Profile (TASK-07)
- Agent Studio docs: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/agent-studio` (verify exact URL)
- Agent Garden templates: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/agent-garden`

---

## Deliverables

When this task is complete:

1. **Pre-staged Agent Studio starting state** — a saved Agent Studio project, partially configured, so the live build is fast and low-risk
2. **The "rig-down notification agent" definition** — what it does, its trigger, its tools, its notification logic — buildable in Agent Studio in <60 seconds from the staged state
3. **Rehearsal script** — the exact click/type sequence, in order, with what appears on screen at each step
4. **Governance hand-off moment** — after building, show the new agent appearing in Agent Registry (the bridge to Persona 6)
5. **Recorded fallback** — a clean screen recording of the full Agent Studio build, accessible if the live build fails
6. **Demo runner integration** — Rafael's launcher tile opens Agent Studio (or the recorded fallback) and the rehearsal script appears in the backstage panel
7. **Handbook section** — Rafael's segment in the demo handbook, with the live-vs-recorded decision criteria

---

## Step-by-step instructions

### Step 1 — Understand Agent Studio as a platform feature

Agent Studio is Gemini Enterprise's visual agent builder. It is a platform feature; we do not build it. It lets a non-developer:
- Start from a template (Agent Garden) or scratch
- Define the agent's purpose in natural language
- Attach tools (MCP tools, built-in tools, connectors)
- Configure triggers and outputs
- Test in an interactive playground
- Deploy — and the agent is immediately registered and governed

Read the Agent Studio docs to understand the build flow and the exact UI steps. The rehearsal script depends on knowing the real click sequence.

### Step 2 — Design the rig-down notification agent

Keep it small enough to build in 60 seconds but real enough to be credible.

```
Agent: Rig-Down Notification Agent
Purpose: When a rig-down event is detected, identify the affected crew,
         equipment, and customer commitment, then notify the relevant
         people through their preferred channels.

Trigger: rig-down event (from the operational data store / event stream)

Tools (all already registered, so they're available to pick in Agent Studio):
  - maximo_get_equipment (existing Maximo MCP tool) — identify affected equipment
  - sap_get_workforce_availability (existing SAP MCP tool) — identify affected crew
  - knowledge_catalog lookup — identify the customer commitment at risk
  - notify (a simple notification tool — Agent Inbox + email)

Output: a structured notification to the crew lead, the OCC planner (Maria),
        and the basin scheduler, with the rig ID, the affected commitment,
        and recommended next action.
```

The agent reuses tools that already exist from earlier tasks (Maximo MCP, SAP MCP, Knowledge Catalog) — which reinforces the platform story: Rafael isn't building integrations, he's composing existing, governed tools.

### Step 3 — Pre-stage the Agent Studio starting state

A 60-second live build only works if most of the setup is already done. Pre-stage:
- The Agent Studio project created, named "Rig-Down Notification Agent"
- The purpose/instruction partially filled (Rafael completes the last sentence live)
- The tool palette showing the available registered tools (so Rafael just picks them)
- The trigger pre-configured (rig-down event)

What Rafael does *live* (the visible 60 seconds):
1. Finish the agent's purpose statement (type one sentence)
2. Pick three tools from the palette (three clicks)
3. Set the notification recipients (pick from a list)
4. Click "Test" — playground runs a sample rig-down event
5. Click "Deploy"

That's it. Everything before step 1 is pre-staged.

Document the staging in `demo_staging/agent_studio_setup.md`:

```markdown
# Agent Studio pre-staging for Rafael's scenario

Run this setup before the demo (or restore from the saved project).

## Pre-staged state
1. Agent Studio project: "Rig-Down Notification Agent" (created, not deployed)
2. Instruction field, pre-filled except the last sentence:
   "You are a rig-down notification assistant. When a rig-down event occurs,
    identify the affected equipment, crew, and customer commitment.
    [LIVE: Rafael types] Then notify the crew lead, OCC planner, and basin
    scheduler with the rig ID and recommended next action."
3. Tool palette: maximo_get_equipment, sap_get_workforce_availability,
   knowledge_catalog_lookup, notify — all visible, none yet attached
4. Trigger: rig-down event, pre-configured
5. Test event: a sample rig-down on Rig PX-114 (Permian), pre-loaded

## Restoring the staged state between rehearsals
Agent Studio projects can be duplicated. Keep a pristine
"Rig-Down Notification Agent — TEMPLATE" and duplicate it before each demo
so the live build always starts from the same clean state.
```

### Step 4 — Write the rehearsal script

`docs/demo-handbook.md` gets a Rafael section. Also surface it in the backstage panel.

```markdown
## Persona 5: Rafael (2 min) — Agent Studio live build

### Setup (before this segment)
- Agent Studio open to the pre-staged "Rig-Down Notification Agent" project
- (Fallback ready: recorded build at /recordings/rafael-agent-studio.mp4)

### Script

[0:00] "Rafael's a field operations engineer in the Permian. Not a software
developer. He keeps running into the same problem: when a rig goes down, the
right people don't find out fast enough. Today he's going to fix that himself
— in Agent Studio."

[0:15] [Type the last sentence of the instruction]
"He describes what he wants in plain language. No code."

[0:30] [Pick the three tools from the palette]
"He picks the tools — these are the same Maximo, SAP, and Knowledge Catalog
tools the other agents use. Already registered, already governed. He's
composing, not integrating."

[0:50] [Set notification recipients]
"Who gets notified — the crew lead, Maria at the OCC, the basin scheduler."

[1:05] [Click Test]
"He tests it. Agent Studio runs a sample rig-down on Rig PX-114. Watch — it
identifies the equipment, the crew, the customer commitment at risk, and
drafts the notifications."

[1:30] [Click Deploy]
"He deploys. Sixty seconds, no code, a working agent."

[1:40] [Switch to Agent Registry — the governance hand-off]
"And here's the part that matters for IT: the moment Rafael deployed, his
agent showed up in Agent Registry. It has an Agent Identity. It's subject to
Agent Gateway policies and Model Armor, exactly like every other agent.
Self-service doesn't mean ungoverned. Which is exactly what Ayesha cares
about — let's go see her."

[2:00] [Transition to Persona 6]

### Live vs. recorded decision
- Default: LIVE. The live build is the whole point of this persona.
- Switch to recorded IF: Agent Studio is slow to load, the network is
  unreliable, or you're short on time. Press Shift+Backspace, jump to
  Rafael's chapter.
- Never attempt the live build without having run it successfully in
  rehearsal that same day.
```

### Step 5 — Build the governance hand-off

After Rafael deploys, the demo should show the new agent in Agent Registry — the bridge to Persona 6. This reuses the `AgentRegistryPanel` from TASK-11. Ensure the newly-deployed Rig-Down agent appears in the registry list (it will, automatically, because deploying through Agent Studio registers it).

If running in a controlled demo environment, verify the timing: the registry list should reflect the new agent within seconds of deployment. If there's a propagation delay, the demoer either waits or uses the pre-deployed version that's already in the registry.

### Step 6 — Record the fallback

Record a clean run of the full Agent Studio build:

```bash
# In a stable environment, run the build start to finish
# Screen capture at 1920×1080, with narration
# Save to canvas/public/recordings/rafael-agent-studio.mp4
# Add a chapter marker so the full-demo fallback can jump here
```

### Step 7 — Demo runner integration

Rafael's launcher tile (from TASK-12) currently routes to `/scenarios/agent-studio`. Since the live build happens in actual Agent Studio (not our canvas), this route should:
- Show a "launch Agent Studio" instruction screen with the staged project link
- Surface the rehearsal script
- Offer the recorded fallback button prominently

`canvas/app/scenarios/agent-studio/page.tsx`:

```tsx
"use client";

// DEMO NARRATION: This route is a launchpad, not the scenario itself —
// the live build happens in actual Agent Studio. This page gives the
// demoer the staged-project link, the script, and the fallback.
export default function AgentStudioLaunchpad() {
  return (
    <div className="min-h-screen p-12 max-w-2xl mx-auto">
      <div className="text-xs uppercase tracking-wider text-white/40">Persona 5 — Rafael</div>
      <h1 className="text-3xl font-semibold mt-1">Agent Studio live build</h1>
      <p className="text-sm text-white/60 mt-2">
        This scenario runs in Agent Studio, not the canvas. Launch the staged project below.
      </p>

      <div className="mt-8 space-y-4">
        <a href={process.env.NEXT_PUBLIC_AGENT_STUDIO_PROJECT_URL} target="_blank"
           className="block rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10">
          <div className="text-lg font-medium">Launch Agent Studio →</div>
          <div className="text-sm text-white/60 mt-1">Opens the pre-staged "Rig-Down Notification Agent" project</div>
        </a>

        <a href="/recordings/rafael-agent-studio.mp4" target="_blank"
           className="block rounded-2xl border border-white/10 bg-white/5 p-6 hover:bg-white/10">
          <div className="text-lg font-medium">Recorded fallback ▶</div>
          <div className="text-sm text-white/60 mt-1">Clean recording of the full build — use if live is risky</div>
        </a>
      </div>
    </div>
  );
}
```

### Step 8 — Commit

```bash
git add demo_staging/ docs/demo-handbook.md canvas/app/scenarios/agent-studio/ \
        canvas/public/recordings/rafael-agent-studio.mp4
git commit -m "feat: Persona 5 (Rafael) Agent Studio live build scenario (TASK-17)"
git push
```

---

## Acceptance criteria

- [ ] Pre-staged Agent Studio project exists and is duplicable for repeat rehearsals
- [ ] The rig-down notification agent is buildable from the staged state in <60 seconds
- [ ] Rehearsal script documented with exact click/type sequence and timing
- [ ] Governance hand-off works: the deployed agent appears in Agent Registry
- [ ] Recorded fallback exists and is accessible via the launchpad and the full-demo fallback
- [ ] Demo runner launcher tile routes to the launchpad
- [ ] Handbook section complete with live-vs-recorded decision criteria
- [ ] The scenario fits in ~2 minutes
- [ ] Commit pushed

---

## Common pitfalls

**Attempting the live build cold.** The single biggest risk. Never do the live Agent Studio build in front of a customer without having run it successfully in rehearsal *that same day*. Platform UI changes, session timeouts, and network issues all break live builds. Rehearse same-day or go recorded.

**Staged state drifting.** Agent Studio projects can be modified accidentally. Keep a pristine TEMPLATE project and duplicate it before each demo. Never demo from the working copy.

**The 60 seconds becoming 4 minutes.** Without tight staging, a "live build" sprawls. Pre-stage aggressively — the only live actions should be one sentence of typing, three tool picks, recipient selection, test, deploy. If it takes longer than 90 seconds in rehearsal, stage more.

**Governance hand-off propagation delay.** The newly-deployed agent may take a few seconds to appear in Agent Registry. If the demoer switches to the registry too fast, it's not there yet — which undercuts the "instantly governed" point. Either wait, or have a pre-deployed instance already in the registry to point at.

**Over-claiming.** Agent Studio is the platform. Rafael's build uses existing registered tools. The narration must not imply we built Agent Studio or that Rafael wrote integration code. The whole point is that he didn't.

**Recorded fallback out of date.** If Agent Studio's UI changes, the recording looks dated. Re-record when the UI changes materially. Add to the 30-day recording-age check from TASK-15.

---

## References

- Agent Studio: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/agent-studio`
- Agent Garden: `https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/agent-garden`
- Agent Registry (for the governance hand-off): `https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry`

---

*When TASK-17 is complete, Persona 5 demonstrates governed self-service — a non-developer builds a real agent in under a minute, and it's immediately subject to the full governance posture. The segment hands off naturally to Ayesha. Next: the audit walkthrough that closes the demo.*
