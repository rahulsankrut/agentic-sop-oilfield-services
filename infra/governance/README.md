# `infra/governance/` — Terraform module

End-to-end IaC for the governance layer described in `tasks/TASK-11-governance.md`
Steps 1, 2, 3, 4. Wraps the existing source-of-truth artifacts at
`infra/gateway_policies.yaml` and `infra/model_armor.yaml` — does **not**
duplicate them.

> **Status (2026-05-20):** Several resources used here (Agent Identity,
> Agent Gateway authorization policies, Model Armor templates) are Preview
> on Google Cloud and do **not** yet have typed Terraform resources in
> `hashicorp/google` or `hashicorp/google-beta`. Those pieces are wrapped
> via `null_resource` + `local-exec` against the documented Preview
> `gcloud` verbs, with `# TODO: replace with typed resource when GA`
> markers throughout. See [Preview API fallbacks](#preview-api-fallbacks)
> below.

---

## What this module creates

| Resource | Count | Type |
|---|---|---|
| `google_service_account.agent` | 5 | Typed (`google` provider) |
| Agent Identity bindings | 5 | `null_resource` → `gcloud ai agent-identities create …` |
| `google_project_iam_member.*` | 9 | Typed (per-agent least-privilege bindings) |
| Gateway policy bundle (3 ALLOW policies + default-DENY) | 1 | `null_resource` → `gcloud agent-platform gateway-policies apply …` |
| Model Armor template (4 filter categories) | 1 | `null_resource` → `gcloud model-armor templates import …` |
| Model Armor floor settings | 1 | `null_resource` → `gcloud model-armor floorsettings update` + REST PATCH for agentplatform |

The five agent slugs:

```
orchestrator
plan-evaluator
procurement-approval
forecast-review
capacity-planning
```

Each slug gets:
- A service account: `<slug>-agent-sa@<project>.iam.gserviceaccount.com`
- An Agent Identity: `<slug>-identity`
- The IAM bindings called out in TASK-11 Step 2

The Plan Evaluator currently runs in-process inside the Orchestrator (see
`docs/governance.md` §3.0); the module provisions its SA + Identity anyway
so the `plan_evaluator_readonly_kc` policy in
`infra/gateway_policies.yaml` has a real principal to bind to. When Plan
Evaluator splits into its own Reasoning Engine deploy, no IaC change is
needed.

---

## File layout

```
infra/governance/
├── README.md             this file
├── versions.tf           provider pins (google, google-beta, null, local)
├── variables.tf          project_id, region, agent_engine_ids, …
├── service_accounts.tf   5 google_service_account resources
├── agent_identities.tf   5 null_resource shims (Preview API)
├── iam_bindings.tf       9 google_project_iam_member bindings (TASK-11 §2)
├── gateway_policies.tf   wraps ../gateway_policies.yaml (Preview API shim)
├── model_armor.tf        wraps ../model_armor.yaml (Preview API shim)
├── outputs.tf            SA emails, identity paths, policy resource paths
└── .gitignore            terraform state + .terraform_render/
```

---

## Prerequisites

Before `terraform apply`:

1. **gcloud installed and authenticated.** The Preview verbs (
   `gcloud ai agent-identities`, `gcloud agent-platform gateway-policies`,
   `gcloud model-armor`) live in the alpha/beta CLI surface. Run
   `gcloud components update` if any verb returns `unknown command`.
   ```bash
   gcloud auth login
   gcloud auth application-default login
   gcloud config set project vertex-ai-demos-468803
   ```
2. **APIs enabled** on the target project:
   - `iam.googleapis.com`
   - `aiplatform.googleapis.com`
   - `agentplatform.googleapis.com` (Preview)
   - `modelarmor.googleapis.com`
   - `dataplex.googleapis.com` (for the Knowledge Catalog viewer role binding)
   - `bigquery.googleapis.com`
   ```bash
   gcloud services enable \
     iam.googleapis.com aiplatform.googleapis.com agentplatform.googleapis.com \
     modelarmor.googleapis.com dataplex.googleapis.com bigquery.googleapis.com \
     --project=vertex-ai-demos-468803
   ```
3. **Operator IAM** — the applying principal needs at minimum:
   - `roles/iam.serviceAccountAdmin` (create the 5 SAs)
   - `roles/resourcemanager.projectIamAdmin` (grant per-agent project bindings)
   - `roles/aiplatform.admin` or the equivalent for Agent Identity / Agent
     Gateway management
   - `roles/modelarmor.admin`
4. **TASK-05 done.** MCP servers are registered with Agent Registry and
   the Cloud Run services exist. Without registered MCP servers, the
   gateway policies still apply but have nothing to authorize against.

---

## Apply sequence

```bash
cd infra/governance

# 1. Initialize providers + null/local plugins. No remote backend is
#    configured — state lives locally. Add a `backend "gcs" { … }` block
#    in versions.tf if you need shared state.
terraform init

# 2. Optional sanity check.
terraform validate

# 3. Preview. Read carefully — the null_resource shims show as "will be
#    created" each time the source YAMLs change, which is intended.
terraform plan -var "project_id=vertex-ai-demos-468803" -var "region=us-central1"

# 4. Apply. Bind Agent Identities to deployed Reasoning Engines by
#    passing -var 'agent_engine_ids={ orchestrator = "1234567890", … }'
#    once those resources exist (see docs/governance.md §3.1).
terraform apply -auto-approve \
  -var "project_id=vertex-ai-demos-468803" \
  -var "region=us-central1"
```

Override defaults with a `terraform.tfvars` (gitignored by default):

```hcl
project_id = "your-project"
region     = "us-central1"

agent_engine_ids = {
  orchestrator         = "1234567890"
  procurement-approval = "2345678901"
  forecast-review      = "3456789012"
  capacity-planning    = "4567890123"
  # plan-evaluator binding intentionally omitted — runs in-process today.
}
```

### Apply order (handled automatically)

Terraform's dependency graph already linearizes correctly via the
`depends_on` declarations:

```
google_service_account.agent           (5x, parallel)
  └─> null_resource.agent_identity     (5x, parallel)
  └─> google_project_iam_member.*      (9x, parallel)
  └─> local_file.gateway_policies_resolved
        └─> null_resource.gateway_policies_apply
  └─> local_file.model_armor_resolved
        └─> null_resource.model_armor_template
              └─> null_resource.model_armor_floor_settings
```

Service accounts and IAM bindings run first; Agent Identity creation
depends on the SAs; Gateway policy application depends on both SAs and
Identities (the policies reference SA emails); Model Armor floor settings
depend on the template being importable.

---

## Verification

```bash
# Service accounts
gcloud iam service-accounts list --project=vertex-ai-demos-468803 \
  --filter='email:*-agent-sa@*'
# Expect 5 rows.

# IAM bindings on each SA
for SLUG in orchestrator plan-evaluator procurement-approval forecast-review capacity-planning; do
  echo "--- $SLUG ---"
  gcloud projects get-iam-policy vertex-ai-demos-468803 \
    --flatten='bindings[].members' \
    --filter="bindings.members:serviceAccount:${SLUG}-agent-sa@*" \
    --format='value(bindings.role)'
done

# Agent Identities
gcloud ai agent-identities list \
  --project=vertex-ai-demos-468803 --location=us-central1
# (or: gcloud agent-platform identities list)

# Gateway policies
gcloud agent-platform gateway-policies describe oilfield-services-mcp-policies \
  --project=vertex-ai-demos-468803 --location=us-central1

# Model Armor template
gcloud model-armor templates describe oilfield-services-mcp-template \
  --project=vertex-ai-demos-468803 --location=us-central1

# Module outputs
terraform output -raw policy_summary
```

---

## Preview API fallbacks

Three components have `# TODO: replace with typed resource when GA` markers:

| Component | Today (Preview) | When GA |
|---|---|---|
| Agent Identity | `null_resource` → `gcloud ai agent-identities create` (with `gcloud agent-platform identities create` fallback) in `agent_identities.tf` | `google_ai_platform_agent_identity` (provisional name) typed resource — direct port of the `service_account` / `bound_agent` / `display_name` shape already in the null_resource block |
| Agent Gateway policies | `null_resource` → `gcloud agent-platform gateway-policies apply --policy-file=$RESOLVED` in `gateway_policies.tf` | `google_gateway_authorization_policy` (provisional name) — one resource per policy in the bundle, sourced from `yamldecode(file("../gateway_policies.yaml"))` |
| Model Armor template | `null_resource` → `gcloud model-armor templates import` in `model_armor.tf` | `google_model_armor_template` (already exists in google-beta but schema needs parity with the four-filter YAML — re-evaluate quarterly) |

All three shims:
- Re-run only when their inputs change (source YAML hash, SA email, project,
  region) — so steady-state `terraform plan` shows no diff.
- Try the alternative gcloud verb tree on `unknown command` (Agent Platform
  CLI surface has moved at least once during Preview).
- Emit a REST endpoint hint to stderr on failure, pointing at the matching
  section of `docs/governance.md`.
- Treat `ALREADY_EXISTS` as success (idempotent re-applies).
- Have a `destroy`-time provisioner that best-effort deletes the resource;
  failure during destroy is non-fatal.

---

## Source-of-truth YAMLs

This module reads but does **not** modify two existing files:

- `infra/gateway_policies.yaml` — the 3 gateway authorization policies +
  default-DENY (verbatim from TASK-05). The module resolves `${PROJECT}`
  and `${LOCATION}` placeholders and applies via gcloud.
- `infra/model_armor.yaml` — the Model Armor template definition with all
  four filter categories. Same placeholder-resolution flow.

To change policy content, edit the YAML — then `terraform apply` picks up
the change via the `sha256(content)` trigger and re-runs the apply step.

---

## Common pitfalls

- **`local-exec` runs on the operator's machine.** That means the operator
  must have `gcloud`, network access to the Preview APIs, and the right
  IAM. CI/CD pipelines need a service account with the prereq roles and
  `gcloud` installed in the runner.
- **State drift on Preview verbs.** If someone deletes a policy via the
  Console, Terraform doesn't know. Re-run `terraform apply` to reconcile,
  or `terraform taint null_resource.gateway_policies_apply` to force a
  re-apply on the next run.
- **`roles/mcp.toolUser` is the documented Preview role name.** If
  `terraform apply` errors with "role does not exist", run
  `gcloud iam roles list --filter='mcp'` to find the current name and
  update `iam_bindings.tf` in one place.
- **`agent_engine_ids` map is optional.** Omitting it creates unbound
  Agent Identities, which is fine for bring-up. Add the engine ids and
  re-apply once `make deploy-*` has produced the Reasoning Engine
  numeric ids — see `docs/governance.md` §3.1.
- **`.terraform_render/` is gitignored.** The resolved YAMLs are derived
  artifacts. If you need to see exactly what was applied, check the file
  in that directory after `terraform apply`, or copy from
  `terraform output gateway_policies_rendered_path`.
- **Floor settings are global.** The Model Armor floor setting URI is
  `projects/<p>/locations/global/floorSetting` (note: `global`, not
  `us-central1`). Other Model Armor resources are regional. This is
  intentional per the GCP Model Armor docs.

---

## Reference

- TASK spec: `tasks/TASK-11-governance.md`
- Operator runbook: `docs/governance.md`
- Source YAMLs: `infra/gateway_policies.yaml`, `infra/model_armor.yaml`
- Platform reference: `~/.claude/references/gemini-enterprise-agent-platform.md`
- Existing scripts that share the REST fallback patterns:
  - `scripts/configure_agent_identity.py`
  - `scripts/register_mcp_servers.py`
  - `scripts/seed_blocked_attack_example.py`
