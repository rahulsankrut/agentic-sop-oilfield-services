# Governance posture — operator runbook (TASK-11)

This is the **source of truth** for landing the governance layer (Agent
Identity, Agent Gateway policies, Model Armor) on top of the deployed
agents. The Python scripts and YAML in this repo cover the verifiable
parts; this document covers the manual gcloud / Console steps that must
be executed by an operator with project IAM.

> Most platform CLI surfaces here (`gcloud agent-platform`,
> `gcloud model-armor`, `gcloud ai agent-identities`) are **Preview** as
> of 2026-05-20. Verbs may have moved; whenever a `gcloud` command in
> this runbook errors with `unknown command`, fall back to the REST
> endpoint or the Console path noted alongside it.

---

## 1. Overview

Three independent controls layered into one defensive posture:

- **Agent Identity** binds each deployed agent to a dedicated GCP
  service account. The agent's SPIFFE ID becomes the principal in every
  Gateway IAM check and audit-log line — so "what can this agent
  reach?" has a precise, queryable answer.
- **Agent Gateway policies** enforce default-deny across MCP tool calls
  and A2A handshakes. Per-tool granularity (e.g. Plan Evaluator may
  call only `lookup_context` + `search_entries` on Knowledge Catalog,
  nothing on SAP/Maximo/FDP).
- **Model Armor** scans every prompt and response at the MCP boundary
  for prompt-injection, sensitive data leakage, responsible-AI
  violations, and malicious URLs. INSPECT_AND_BLOCK at MEDIUM+ confidence.

Persona 6 (Ayesha, audit director) points at the artifacts these three
controls produce: the Agent Registry list, the Gateway policy bundle,
the Model Armor block log.

---

## 2. Prerequisites

Before running anything in this runbook:

1. **Agents are deployed.** All four reasoning engines exist and their
   resource names are in `.env`:
   ```
   PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...
   FORECAST_REVIEW_AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...
   CAPACITY_PLANNING_AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...
   ORCHESTRATOR_AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...
   ```
2. **MCP servers are registered** with Agent Registry (`make register-mcp-servers`).
3. **gcloud is authenticated**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project $GOOGLE_CLOUD_PROJECT
   ```
4. **`venv-deploy-310/`** exists with `poetry install` complete (for the
   Python scripts).
5. **Per-agent service accounts exist** (one-time bootstrap — see §3.0).

The runbook helper script wraps the verifiable bits with interactive
confirmation:

```bash
chmod +x infra/governance_runbook.sh
./infra/governance_runbook.sh --dry-run   # preview all commands
./infra/governance_runbook.sh             # interactive, confirms each step
```

You can also scope it to a single step: `identity` | `gateway` | `armor` | `attack`.

---

## 3. Step-by-step instructions

### 3.0 — Create the per-agent service accounts (one-time)

Four dedicated SAs, one per deployed agent. Run once per project:

```bash
PROJECT=$GOOGLE_CLOUD_PROJECT
for AGENT in orchestrator procurement-approval forecast-review capacity-planning; do
  gcloud iam service-accounts create "${AGENT}-agent-sa" \
    --display-name="Service account for ${AGENT} agent" \
    --project="$PROJECT"
done
```

Verify:

```bash
gcloud iam service-accounts list --project=$PROJECT \
  --filter='email:*-agent-sa@*'
```

Expect four rows.

> **Why only four (not five)?** The Plan Evaluator currently runs
> in-process inside the Capacity Orchestrator deploy (see
> `src/orchestrator_agent/core/agent.py`). When it splits into its own
> reasoning engine, add `plan-evaluator-agent-sa` here and a 5th binding
> in step 3.1.

### 3.1 — Configure Agent Identity for each deployed agent

The script `scripts/configure_agent_identity.py` reads the four
`*_AGENT_RESOURCE_NAME` env vars and creates / updates one Agent Identity
binding per agent against `agentplatform.googleapis.com`.

**Preferred path — REST via the script:**

```bash
source venv-deploy-310/bin/activate

# Preview the requests first
AGENT_IDENTITY_DRY_RUN=1 python scripts/configure_agent_identity.py

# Live reconcile
python scripts/configure_agent_identity.py
```

The script is idempotent (GET → PATCH-or-POST) and prints a gcloud
fallback to stderr if the REST endpoint is unreachable.

**Fallback A — gcloud CLI (Preview verb; may not exist yet):**

```bash
gcloud ai agent-identities create procurement-approval-identity \
  --service-account="procurement-approval-agent-sa@${PROJECT}.iam.gserviceaccount.com" \
  --bound-agent="${PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME}" \
  --display-name="Procurement Approval Agent" \
  --project="$PROJECT" --location="$GOOGLE_CLOUD_LOCATION"
# Repeat for forecast-review, capacity-planning, orchestrator.
```

If `gcloud ai agent-identities` returns `unknown command`, try the
alternative root: `gcloud agent-platform identities create …` (same
flags). The current verb structure is in flux per CLAUDE.md.

**Fallback B — Console:**

1. Open https://console.cloud.google.com/agent-platform/identities (Preview
   surface — may live under "Vertex AI → Agent Engine → Identities" until
   GA).
2. Click **Create identity** for each of the four agents.
3. Set: name = `<slug>-identity`, bound agent = the
   `reasoningEngines/<id>` resource path, service account = the
   matching `<slug>-agent-sa@…`.
4. Save.

### 3.2 — Grant least-privilege IAM to each service account

Per the TASK-11 spec's IAM table. Adjust to the customer's actual MCP
tool catalog at deal time.

```bash
PROJECT=$GOOGLE_CLOUD_PROJECT

# Orchestrator — full MCP tool user + Memory Bank + KC viewer
for ROLE in roles/mcp.toolUser roles/aiplatform.memoryBankUser roles/dataplex.catalogViewer; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:orchestrator-agent-sa@${PROJECT}.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Procurement Approval — MCP tool user only
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:procurement-approval-agent-sa@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/mcp.toolUser"

# Forecast Review — BigQuery viewer
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:forecast-review-agent-sa@${PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

# Capacity Planning — BigQuery viewer + MCP tool user (read-only enforced by Gateway policy)
for ROLE in roles/bigquery.dataViewer roles/mcp.toolUser; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:capacity-planning-agent-sa@${PROJECT}.iam.gserviceaccount.com" \
    --role="$ROLE"
done
```

> **Preview role name:** `roles/mcp.toolUser` is the documented role per
> `https://docs.cloud.google.com/mcp/control-mcp-use-iam` but may rename
> to `roles/agentplatform.mcpToolUser` at GA. If `add-iam-policy-binding`
> rejects the role, run `gcloud iam roles list --filter='mcp'` to find
> the live name.

### 3.3 — Apply Agent Gateway policies

The bundle in `infra/gateway_policies.yaml` defines three explicit ALLOW
policies on top of a default-DENY:

1. `orchestrator_full_mcp_access` — Orchestrator → all 4 MCP servers
2. `plan_evaluator_readonly_kc` — Plan Evaluator → KC `lookup_context` + `search_entries` only
3. `orchestrator_a2a_procurement_approval` — Orchestrator → Procurement
   Approval agent over A2A (`agents.invoke`)

**Preferred path — Makefile target:**

```bash
make apply-gateway-policies
```

This runs `envsubst` against `infra/gateway_policies.yaml` then calls
`gcloud agent-platform gateway-policies apply --policy-file=…`.

**Fallback A — REST API:**

If the gcloud verb is missing, post the resolved YAML directly to
`https://agentplatform.googleapis.com/v1beta1/projects/{p}/locations/{l}/gatewayPolicies`.
The reference endpoint shape is in
`~/.claude/references/gemini-enterprise-agent-platform.md` §REST API
patterns. Same idempotent GET → PATCH-or-POST pattern as the agent
identity script — the policy bundle has a stable name
(`oilfield-services-mcp-policies`) so PATCH with `updateMask=spec` is
the update verb.

**Fallback B — Console:**

1. Open https://console.cloud.google.com/agent-platform/gateway-policies
   (or "Vertex AI → Agent Gateway → Policies" until GA).
2. Click **Import policy bundle**.
3. Upload `infra/gateway_policies.yaml` (with `${PROJECT}` / `${LOCATION}`
   resolved — easiest with `envsubst < infra/gateway_policies.yaml > /tmp/resolved.yaml`).
4. Confirm the default-DENY is enabled at the bundle level.

### 3.4 — Import + attach the Model Armor template

The template in `infra/model_armor.yaml` carries all four filter
categories per the Model Armor docs:

1. **Responsible AI Safety** (`responsibleAi`) — INSPECT_AND_BLOCK on
   responses; HATE_SPEECH, HARASSMENT, DANGEROUS_CONTENT, SEXUALLY_EXPLICIT.
2. **Prompt Injection & Jailbreak** (`promptInjectionAndJailbreak`) —
   INSPECT_AND_BLOCK on BOTH directions; HIGH and MEDIUM confidence.
3. **Sensitive Data Protection** (`sensitiveDataProtection`) — DLP basic
   profile on responses.
4. **Malicious URL Detection** (`maliciousUriFilterSettings`) — on responses.

**Preferred path — Makefile target:**

```bash
make enable-model-armor
```

This runs `envsubst` then calls `gcloud model-armor templates import …`.

**Fallback A — REST:**

`POST https://modelarmor.googleapis.com/v1/projects/{p}/locations/{l}/templates?templateId=oilfield-services-mcp-template`
with the body translated from the YAML (the JSON shape matches the
spec verbatim). To attach project-wide, `PATCH` the floor settings:
`https://modelarmor.googleapis.com/v1/projects/{p}/floorSettings` with
`{"mcpArmorTemplate": "projects/{p}/locations/{l}/templates/oilfield-services-mcp-template"}`.

**Fallback B — Console:**

1. Open https://console.cloud.google.com/security/model-armor.
2. **Templates** → **Create template** → switch to YAML editor → paste
   the resolved `infra/model_armor.yaml`.
3. **Floor settings** → **Project floor** → set MCP Armor template to
   the new template; enable **Enforcement** and **Cloud Logging**.

### 3.5 — Seed a blocked-attack example

For Persona 6's demo: a recent block entry must exist in Cloud Logging.
Run the seed script before each rehearsal / customer demo.

```bash
source venv/bin/activate
# Preview first — synthetic payload only, placeholders, no real names
BLOCKED_ATTACK_DRY_RUN=1 python scripts/seed_blocked_attack_example.py

# Live — expect HTTP 4xx with Model Armor block reason
python scripts/seed_blocked_attack_example.py
```

The script refuses to run if `AGENT_GATEWAY_ENDPOINT` is unset (a
"successful" attack that bypassed Gateway is a worse audit story than
no log at all). If the script returns HTTP 200/201, Model Armor did
NOT block — investigate via `gcloud model-armor floorsettings describe`
to confirm the template is attached.

---

## 4. Verification

After all four steps land, verify each piece:

### 4.1 — Agent Identity

```bash
gcloud ai agent-identities list \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --location="$GOOGLE_CLOUD_LOCATION"
# Expect 4 rows, one per deployed agent, each with a bound service account.
```

Console alternative: https://console.cloud.google.com/agent-platform/identities

### 4.2 — Gateway policies

```bash
gcloud agent-platform gateway-policies list \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --location="$GOOGLE_CLOUD_LOCATION"
# Expect the oilfield-services-mcp-policies bundle with 3 named policies.

gcloud agent-platform gateway-policies describe oilfield-services-mcp-policies \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --location="$GOOGLE_CLOUD_LOCATION"
# Confirm defaultBehavior=DENY and audit.logAllToolCalls=true.
```

### 4.3 — Model Armor

```bash
gcloud model-armor templates describe oilfield-services-mcp-template \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --location="$GOOGLE_CLOUD_LOCATION"

gcloud model-armor floorsettings describe \
  --project="$GOOGLE_CLOUD_PROJECT"
# Confirm mcpArmorTemplate points at the imported template.
```

### 4.4 — Blocked attack log entry

```bash
gcloud logging read 'jsonPayload.modelArmor.blocked=true' \
  --project="$GOOGLE_CLOUD_PROJECT" \
  --limit=5 --freshness=24h
# Expect at least one entry from the seed script run.
```

Console alternative: Logs Explorer with the filter
`jsonPayload.modelArmor.blocked=true`.

### 4.5 — End-to-end smoke

Run any agent that calls an MCP tool (e.g. `make demo-cargo-plane`) and
inspect Cloud Trace for the `agent_gateway` and `model_armor` spans.
Both should be present on every tool call; their absence means the
agent is bypassing Gateway (check `AGENT_GATEWAY_ENDPOINT` is set in
the agent's runtime env).

---

## 5. Common pitfalls

- **Preview gcloud verbs may not exist.** `gcloud agent-platform`,
  `gcloud model-armor`, `gcloud ai agent-identities` are all Preview
  as of 2026-05-20. If any verb errors with `unknown command`, fall
  back to REST (verified endpoint shapes in
  `~/.claude/references/gemini-enterprise-agent-platform.md` §REST API
  patterns) or to the Console paths listed inline above.
- **Region mixing.** Gateway in `us-central1`, Identity record in
  another region → "resource not found." Pick one region (we use
  `us-central1` everywhere — see CLAUDE.md).
- **`lookup_entry` vs `lookup_context`.** The managed Knowledge Catalog
  MCP server exposes `lookup_context`, NOT `lookup_entry` (some early
  doc drafts had the wrong name). The gateway policy in
  `infra/gateway_policies.yaml` was already correct as of 2026-05-19;
  re-verify if you regenerate it from a template.
- **Default-deny breaking dev loops.** Before the policies land, agents
  can still call MCP servers (the gateway's default state is permissive
  until a policy bundle is applied). The instant `make apply-gateway-policies`
  runs, the policy bundle's default-DENY takes effect — every unlisted
  agent / tool combination 403s. Apply policies AFTER all agents have
  the right service accounts wired.
- **Model Armor false positives during demos.** Aggressive thresholds
  (HIGH only) under-detect; LOW thresholds over-block. MEDIUM is the
  rehearsal-tested setting. If a demo rehearsal trips a block on a
  legitimate call, capture the prompt + raise the confidence threshold
  on `promptInjectionAndJailbreak` to `[HIGH]` only for that demo.
- **Blocked-attack log ages out.** Cloud Logging retains entries for
  ~30 days by default. The seed script should run within 7 days of
  any demo. Add it to the rehearsal checklist.
- **Token expiry mid-session.** ADC tokens are valid ~1 hour. Long
  rehearsal sessions need `gcloud auth application-default login`
  re-run; the agent runtimes refresh automatically.
- **MCP server URL mismatch.** Gateway routes by the registered MCP
  server id (URL path-prefix or `X-Agent-Mcp-Server` header). If the
  policies reference `sap-mcp-server` but the registration used a
  different id, every call 404s at the gateway. Cross-check
  `scripts/register_mcp_servers.py:_registrations()` against
  `infra/gateway_policies.yaml` resources.

---

## 6. Manual Console steps (explicit URLs)

When the gcloud CLI is unavailable or the Preview surface errors:

| Step | Console path |
|---|---|
| Service accounts | https://console.cloud.google.com/iam-admin/serviceaccounts |
| IAM bindings | https://console.cloud.google.com/iam-admin/iam |
| Agent Registry | https://console.cloud.google.com/agent-platform/registry |
| Agent Identities | https://console.cloud.google.com/agent-platform/identities |
| Gateway policies | https://console.cloud.google.com/agent-platform/gateway-policies |
| Model Armor templates | https://console.cloud.google.com/security/model-armor/templates |
| Model Armor floor settings | https://console.cloud.google.com/security/model-armor/floor-settings |
| Cloud Logging — Model Armor blocks | https://console.cloud.google.com/logs/query;query=jsonPayload.modelArmor.blocked%3Dtrue |
| Cloud Trace — Gateway spans | https://console.cloud.google.com/traces/list?filter=service%3Aagent_gateway |

Each path may be behind a "Switch to preview" toggle while the surfaces
are pre-GA.

---

## 7. Compliance considerations

(Customer-engagement section — fill in at deal stage.)

- **Data residency** — every governance component is regional. Pin
  `GOOGLE_CLOUD_LOCATION` to the customer's data-residency region (we
  use `us-central1` in this build).
- **VPC Service Controls** — supported on Agent Runtime, Knowledge
  Catalog, Model Armor templates.
- **CMEK** — supported on Knowledge Catalog entries; not yet on Agent
  Identity / Gateway policy stores as of 2026-05.
- **Audit-log retention** — Cloud Logging default is project-level. Add
  a log sink to BigQuery (or GCS) for retention beyond default.
- **Cross-project deploys** — if the customer's SAP / FDP lives in a
  different project than the orchestrator, the Gateway needs cross-project
  service-account impersonation configured. Document at deal time.
