# TASK-15: Internal review, polish, fail-safe modes

**Prerequisites:** TASK-14 complete. End-to-end deployment proven in two fresh projects. Demo runs through all six personas.

**Estimated effort:** 5-7 days for one engineer (across both streams)

**Stream:** Both

---

## Context

We have a demo we can deploy and run. We do not yet have a demo we can confidently put in front of a tier-one major's executive team on a fixed date. The gap is everything that isn't a feature: error paths nobody intended to exercise, latency we haven't measured, dependencies on stable WiFi, the recorded fallback for when nothing else works, the second pair of eyes that catches the thing we missed.

This is the final pass. It is mostly checklist work, but each check matters because customers notice. A cold start that takes 8 seconds when the demoer hits the trigger. A blocked attack example that's 32 days old (Cloud Logging retention limit). A canvas that doesn't render at the customer's projector's aspect ratio. A persona's narration that mentions "Halliburton-pattern" out loud and creates an awkward moment.

The task organizes into seven areas: **internal review pass**, **recorded fallback for live-demo safety**, **error handling pass**, **performance pass**, **demo room testing**, **security review**, and **documentation completeness**. None individually is a feature; together they're the difference between "works on the engineer's laptop" and "lands in a customer meeting."

---

## Inputs

- TASK-14 complete (working deployment in two test projects)
- The full set of demo handbooks, runbooks, and ADRs accumulated through TASK-01–14
- Two internal review slots scheduled — one mid-task, one before sign-off

---

## Deliverables

When this task is complete:

1. **Internal review pass** — two structured reviews against the demo handbook; all flagged issues either fixed or explicitly accepted with rationale
2. **Recorded fallback video** — a clean recording of the full 18-minute demo, hosted somewhere accessible from the demo machine, with a one-keystroke fallback path from the canvas
3. **Error handling pass** — every place where the agent or canvas could throw an error has graceful degradation; no raw error stacks visible to the customer
4. **Performance baseline** — measured cold-start latencies, animation FPS, end-to-end scenario time; documented targets; warm-up procedure if needed
5. **Demo room test** — at least one full run-through on a real projector at 1920×1080 and 2560×1440, with WiFi degradation simulated
6. **Security review** — secret hygiene check, IAM least-privilege verification, OAuth scope audit, no test credentials in committed code
7. **Documentation completeness** — README, contributing guide, architecture doc, deployment guide, demo handbook, customer skinning guide, governance doc — all current, all reviewed
8. **Sign-off checklist** — `docs/demo-ready-checklist.md` with all items checked and dated

---

## Step-by-step instructions

### Step 1 — Schedule the internal reviews

Two slots:
- **Review 1 (mid-task):** ~halfway through TASK-15, with two senior CEs who haven't seen the build. Goal: identify the worst issues before fixing time runs out.
- **Review 2 (sign-off):** end of TASK-15, with the team plus one Industry Solutions rep and one engineer who doesn't know the build. Goal: confirm demo-readiness.

Send the demo handbook ahead so reviewers know what they're seeing. Reviews are scripted: demoer runs through the full 18 minutes, reviewers heckle as if they were customers, scribe captures everything.

### Step 2 — Internal review pass

For each persona, watch carefully for:

**Narration smoothness.** Does the demoer stumble? Are the cue cards from the backstage panel useful or distracting? Does anything mentioned in narration not actually happen on screen?

**Visual clarity.** Can a reviewer 10 feet from the monitor read the cost banner, the marker labels, the canvas chat panel? Does anything flash, jitter, or distract?

**Story coherence.** Does each persona's segment have a clear arc? Is the S&OP cycle visible across the six personas? Does Persona 6 (Ayesha) close the story cleanly?

**Customer skepticism stress tests.** Reviewers should try:
- "What did you build vs. the platform?" → demoer points to the documented split
- "Is this on real data?" → demoer clearly states synthetic, points to the canonical asset taxonomy
- "What happens if X fails?" → demoer demonstrates fallback (or hand-waves; if they hand-wave, it's a gap)
- "How long to deploy in our environment?" → demoer cites the deployment runbook timing
- "What's the cost?" → demoer cites the cost estimate from the deployment doc

For each issue raised: log to `docs/review-findings.md` with severity (P0/P1/P2) and decide fix-vs-accept. P0s block sign-off; P1s ideally fixed; P2s noted for v2.

### Step 3 — Build the recorded fallback

The recorded fallback is the safety net. If the live demo breaks in a way that recovery mode can't handle, the demoer says "let me show you the recording" and plays a clean, edited version of the full demo. Customer gets the story; demo continues.

Record the cleanest possible run:

```bash
make demo-preflight
# Verify all green

# Run the demo end-to-end at a quiet time when no one else is touching the env
# Record screen at 1920×1080 with system audio (the demoer narrating)
# Use OBS or QuickTime — full-screen capture of the canvas
```

Edit (or have someone edit) the recording for:
- Trim dead time between persona transitions
- Crop to just the canvas region (no browser chrome visible)
- Add chapter markers at each persona's start
- Verify audio is clear and at consistent levels

Host the recording in a place accessible from the demo machine without internet:
- Copy to the demo laptop's local storage
- Optionally also upload to internal storage as backup

Wire a fallback from the canvas. Add to the rehearsal controls:

```typescript
// canvas/components/demo/RehearsalControls.tsx
// Shift+Backspace opens the recorded fallback in a new tab/window
if (e.key === "Backspace" && e.shiftKey) {
  window.open("/recordings/full-demo.mp4", "_blank");
}
```

The recorded video lives at `/recordings/full-demo.mp4` (served from the canvas's Next.js public directory).

### Step 4 — Error handling pass

Sweep every code path where errors could surface to the customer:

**Backend agent errors.** Workflow nodes can fail (MCP timeout, KC unreachable, LLM error). Every Workflow node needs a `try`/`except` that emits a `node.failed` event and either:
- Recovers (retries the call, falls back to a default value)
- Degrades gracefully (proceeds with partial data, flags the gap in the output)
- Halts cleanly (emits `workflow.failed` with a customer-friendly message)

Never: raise the raw exception, surface a Python traceback, hang forever.

```python
# Pattern for every Workflow node
async def parallel_system_queries(node_input: dict, context) -> Event:
    try:
        # ... actual work ...
    except MCPTimeoutError as e:
        await context.emit(NodeFailedEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            workflow_id=context.workflow_id,
            session_id=context.session_id,
            node_name="parallel_system_queries",
            failure_kind="mcp_timeout",
            recovery_strategy="proceed_with_partial",
            customer_message="One of the source systems is slow today. Proceeding with what we have.",
        ))
        # Continue with degraded data
        return Event(payload={"sap": None, "maximo": maximo_result, "fdp": fdp_result})
```

**Canvas runtime errors.** Wrap every component tree in an ErrorBoundary that shows a friendly message and a "switch to recorded fallback" button.

```tsx
// canvas/components/ErrorBoundary.tsx
export class DemoErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean; error?: Error}> {
  state = { hasError: false };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Canvas error caught by boundary", error, info);
    // Optionally log to Cloud Logging
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center p-8 text-center">
          <div className="max-w-md">
            <h2 className="text-xl font-medium">Canvas hit an unexpected error</h2>
            <p className="mt-2 text-white/60">Don't worry — we have you covered. Switch to the recorded demo.</p>
            <a href="/recordings/full-demo.mp4" target="_blank" className="mt-4 inline-block rounded-lg bg-white/10 px-4 py-2">
              Open recorded demo →
            </a>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**WebSocket errors.** Already handled in TASK-10; verify the auto-fallback to replay mode works.

**MCP server cold starts.** If a Cloud Run MCP server is cold, the first call can take 5-8 seconds. Configure minimum instances on each MCP server:

```bash
gcloud run services update sap-mcp-server --min-instances=1 --region us-central1
gcloud run services update maximo-mcp-server --min-instances=1 --region us-central1
gcloud run services update fdp-mcp-server --min-instances=1 --region us-central1
```

The cost is small; the demo benefit is real.

### Step 5 — Performance pass

Measure, don't guess:

```bash
# Cold start: time from clicking "Run Cargo Plane" to first canvas event
make benchmark-cold-start

# Warm path: same, after warm-up
make benchmark-warm-path

# Animation FPS: Chrome DevTools Performance tab during the cargo-plane scenario
# (manual: record a 60-second profile while running the scenario; look for sustained 60fps)
```

Capture in `docs/performance-baseline.md`:

```markdown
# Performance baseline

Measured on: [date]
Demo machine: [model and specs]
Network: [type, bandwidth]

## Backend

| Metric | Cold | Warm |
|---|---|---|
| Cargo-plane scenario end-to-end | 12.4s | 6.8s |
| MCP call latency (median) | 800ms | 80ms |
| Knowledge Catalog lookup | 450ms | 90ms |
| LLM node (equivalence_lookup) | 1.8s | 1.6s |

## Frontend

| Metric | Value |
|---|---|
| Canvas first contentful paint | 1.2s |
| Mapbox dark style load | 2.1s |
| Cargo-plane scenario animation FPS | 58fps (target 60) |
| Drawer expand/collapse | 60fps |

## Demo machine warm-up procedure

To avoid cold-start latency during the demo, run this 10 minutes before:
1. Open the canvas at /demo
2. Click through all six personas to warm up the routes
3. Trigger the cargo-plane scenario once (it'll be slow; that's fine, you're warming up)
4. Wait 30 seconds
5. Demo is now warm
```

### Step 6 — Demo room testing

Real demos happen on screens that aren't your engineering laptop. Test:

**Aspect ratios:**
- 16:9 at 1920×1080 (standard projector) — primary target
- 16:9 at 2560×1440 (modern projector) — verify nothing breaks
- 16:10 at 1680×1050 (older projectors) — verify layout doesn't break
- Ultrawide 21:9 — won't be the customer's display but might be your own laptop

For each aspect ratio, run through all six scenarios. Note any layout breaks.

**WiFi degradation:**
- Disable WiFi for 5 seconds mid-scenario; verify WebSocket reconnect logic
- Throttle to 3G speed in Chrome DevTools; verify replay mode still works
- Completely offline; verify recorded fallback is accessible

**Projector color reproduction.** Projectors tend to wash out colors. The dark theme is mostly fine, but:
- Verify the red marker (capacity gap) is clearly red, not faded brown
- Verify the green marker (recommended) is clearly green, not yellow-green
- Verify the cost banner amber stands out from the background

**Audio:** if the demo includes any sound (it shouldn't, but verify), test conference room speakers.

### Step 7 — Security review

A quick audit before sign-off:

**Secret hygiene:**
```bash
# Check for committed secrets
git secrets --scan
# Or use truffleHog or similar

# Check .env files are gitignored
grep -r "^\.env" .gitignore

# Check Mapbox token is URL-restricted (Mapbox dashboard)
# Check any other API keys are scoped to minimum permissions
```

**IAM audit:**
```bash
# Each service account: what roles does it have?
for SA in orchestrator plan-evaluator procurement-approval forecast-review capacity-planning; do
  echo "=== $SA ==="
  gcloud projects get-iam-policy $PROJECT --filter="bindings.members:${SA}-agent-sa" --format='value(bindings.role)'
done

# Verify Plan Evaluator does NOT have BigQuery write or Memory Bank write
```

**OAuth scopes:**
- Verify the Orchestrator's Agent Identity has `dataplex.readonly` for Knowledge Catalog (not read-write, unless we explicitly need write)
- Verify the canvas backend service account has minimal IAM (just `roles/aiplatform.user` and `roles/run.invoker`)

**Test credentials:**
- Verify no developer's credentials are in the repo
- Verify the deploy uses Application Default Credentials or a workload-specific service account

**Customer data:**
- Verify all synthetic data is clearly marked as such
- Verify no production customer names appear in committed code (only in skin files, with pattern suffix)

Document findings in `docs/security-review.md`. Anything that's not least-privilege gets a justification or gets tightened.

### Step 8 — Documentation pass

Walk through every doc and verify it's:
1. **Current** — references match the actual code
2. **Complete** — no `TODO` or `TBD` markers in customer-facing docs
3. **Accurate** — claims about platform components match what's actually deployed

Docs to review:

- `README.md` — repo-level overview, quickstart
- `docs/architecture.md` — MCP architecture diagram, agent topology, data flow
- `docs/deployment.md` — from TASK-14
- `docs/demo-handbook.md` — from TASK-12
- `docs/customer-skinning.md` — from TASK-13
- `docs/governance.md` — from TASK-11
- `docs/performance-baseline.md` — from this task
- `docs/review-findings.md` — from this task
- `docs/security-review.md` — from this task
- `docs/adr/0001-adopt-adk-2-workflow.md` — from TASK-04
- `docs/adr/0002-agents-cli-evaluation.md` — from TASK-14

Add a `docs/README.md` (or `docs/index.md`) that lists all docs with a one-line description, sorted by audience (engineering / sales engineering / customer security).

### Step 9 — Sign-off checklist

`docs/demo-ready-checklist.md`:

```markdown
# Demo-readiness checklist

This list must be all-green before scheduling a customer demo.

## Functional

- [ ] All six personas run end-to-end in live mode (date verified, by whom)
- [ ] Replay mode works for all six personas
- [ ] Static mode works for all six personas
- [ ] Persona-to-persona transition is clean (no awkward state leakage)
- [ ] Backstage panel shows correct narration cues for all beats
- [ ] Recovery from WebSocket disconnect works (date tested)
- [ ] Recovery from agent timeout works (date tested)
- [ ] Recorded fallback video is accessible from demo machine

## Performance

- [ ] Cold-start path < 15s for cargo-plane scenario
- [ ] Warm path < 8s for cargo-plane scenario
- [ ] Animations sustained 60fps on demo machine
- [ ] MCP servers configured with min-instances=1 (no cold starts during demo)

## Visual

- [ ] All scenarios render cleanly at 1920×1080
- [ ] All scenarios render cleanly at 2560×1440
- [ ] No layout breaks at 16:10
- [ ] Color contrast verified at projector brightness

## Demo logistics

- [ ] Pre-flight script (`make demo-preflight`) all green within 30 minutes of demo
- [ ] Demo machine warmed up (run through all six personas, wait 30s)
- [ ] Recent blocked-attack example in Cloud Logging (run `make seed-blocked-attack` if needed)
- [ ] Memory Profiles current for the active customer skin
- [ ] Demo handbook printed and on the lectern (or open on second monitor)
- [ ] Backup demo machine on standby (if a high-stakes meeting)

## Documentation

- [ ] README current
- [ ] Demo handbook current
- [ ] Customer skinning guide current
- [ ] Deployment guide current
- [ ] Governance doc current and reviewed by [name]
- [ ] Architecture doc current

## Security

- [ ] No secrets in committed code
- [ ] IAM bindings reviewed; least-privilege confirmed
- [ ] OAuth scopes minimal
- [ ] Customer-data classification complete (synthetic everywhere, pattern-suffix on customer skins)

## Reviews

- [ ] Internal review #1 complete; P0 findings fixed
- [ ] Internal review #2 (sign-off) complete; all findings either fixed or accepted with rationale

## Sign-off

Signed off by: ____________________ Date: __________
```

The checklist gets reviewed and signed before any external demo. If any item is unchecked, the demo doesn't go.

### Step 10 — Commit

```bash
git add docs/ canvas/components/ErrorBoundary.tsx \
        src/orchestrator_agent/core/nodes/  # error handling updates
git commit -m "feat: polish, fail-safe modes, demo-readiness checklist (TASK-15)"
git push
```

---

## Acceptance criteria

- [ ] Two internal reviews completed and documented
- [ ] All P0 findings fixed; P1 findings addressed or accepted; P2 findings logged for v2
- [ ] Recorded fallback video produced and accessible from canvas via Shift+Backspace
- [ ] Every Workflow node has a try/except with graceful degradation
- [ ] Canvas has a top-level ErrorBoundary that surfaces the recorded fallback
- [ ] MCP servers configured with min-instances=1
- [ ] Performance baseline measured and documented
- [ ] Demo room tested at 1920×1080 and 2560×1440
- [ ] WiFi degradation tested; replay mode confirmed working
- [ ] Security review complete; documented findings and tightening applied
- [ ] All docs current and reviewed
- [ ] Demo-readiness checklist exists and is sign-off-ready
- [ ] Commit pushed

---

## Common pitfalls

**The "internal review" that's just colleagues being polite.** Invite people who'll actually be critical. Brief them: "your job today is to ruin this demo. Find the weakness." Reviews where everyone nods are wasted.

**The recorded fallback that's months old.** Every time the demo changes substantially, the recording needs to be re-shot. Add a check: if the recording is older than 30 days and the demo has changed, re-shoot.

**Error handling that just swallows errors silently.** "Graceful degradation" means the demoer can recover. If an error fails silently, the demoer doesn't know to switch modes; the customer sees the canvas stuck on a beat. Always emit an event (or surface a small indicator) so the demoer knows what happened.

**Min-instances cost.** Setting `min-instances=1` on four MCP servers costs ~$50-100/month for a demo environment. Worth it. Don't try to save the cost by living with cold starts — they will burn you in a demo.

**Demo room WiFi that's actually fine 99% of the time.** Don't trust that. Test with WiFi off, with WiFi degraded, with WiFi suddenly disconnecting mid-scenario. All three failure modes happen in practice.

**Security review that's a checkbox.** Have someone who didn't build the system do the security review. Their fresh eyes find things you've stopped seeing.

**Documentation that drifts during this task.** This task is the time to bring docs current. If TASK-04–14 introduced features that didn't get documented as they were built, do that catch-up here. Don't push it to "next iteration" — there is no next iteration unless v1 lands.

**Sign-off without the checklist.** The checklist isn't ceremonial. If you skip it once, you'll skip it always, and eventually you'll demo to a customer with an out-of-date recorded fallback or stale blocked-attack example. Run the checklist every time.

---

## References

- Demo handbook: `docs/demo-handbook.md` (from TASK-12)
- Performance baseline template: `https://web.dev/measure/`
- Cloud Run cold start optimization: `https://cloud.google.com/run/docs/tips/general`

---

*When TASK-15 is complete, the Reference Solution is ready for its first customer demo. The build crossed from "works" to "ships." Phase 1 closes.*
