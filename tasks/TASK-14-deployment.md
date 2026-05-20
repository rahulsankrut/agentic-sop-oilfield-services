# TASK-14: End-to-end deployment (agents-cli evaluation + Terraform)

**Prerequisites:** TASK-13 complete. Customer skin system works; default and one alternate skin verified.

**Estimated effort:** 3-5 days for one engineer.

**Stream:** Backend

---

## Context

The build has accumulated a lot of moving parts: five agents on Agent Runtime, three custom MCP servers on Cloud Run, the Operations Canvas on Cloud Run, Knowledge Catalog content, Memory Bank profiles, Agent Identities, Agent Gateway policies, Model Armor floor settings, IAM bindings, BigQuery datasets, plus the `customer.yaml` skin system. None of it is reproducible from scratch yet. A new CE who wants their own demo environment needs a documented, automated path from a fresh GCP project to a running demo.

This task delivers that path. It opens with a **time-boxed evaluation of agents-cli** (`google.github.io/agents-cli`), the unified deployment CLI Google ships for the platform. agents-cli claims to cover pre-built templates, interactive playground, automated Terraform infrastructure, CI/CD pipelines via Cloud Build, and built-in Cloud Trace + Cloud Logging. If it covers what we need, adopting it shrinks this task dramatically. If it doesn't, we write Terraform.

The deliverable is **`make deploy-from-scratch PROJECT=<id>`** that takes a fresh GCP project and produces a working demo in under 90 minutes. Idempotent — running it again updates rather than duplicates. Tested by running it twice in two empty projects.

---

## Inputs

- TASK-13 complete (skin system working)
- agents-cli docs: `https://google.github.io/agents-cli/`
- The Reference Solution as it stands

---

## Deliverables

When this task is complete:

1. **agents-cli evaluation report** at `docs/adr/0002-agents-cli-evaluation.md` — what it covers, what gaps remain, decision to adopt or defer
2. **Either: agents-cli configuration** — `agents.yaml` or equivalent at the repo root, plus migration of what was previously manual
3. **Or: Terraform modules** — `infra/` complete with modules for every deployable resource (agents, MCP servers, canvas, governance, BigQuery, IAM)
4. **`make deploy-from-scratch`** — one command, ~90 minutes, fresh project to running demo
5. **Tested twice** — two fresh projects, both produce working demos
6. **Documentation** — `docs/deployment.md` for the team and partners adapting the Reference Solution

---

## Step-by-step instructions

### Step 1 — Time-box the agents-cli evaluation (Day 1)

Don't try to use agents-cli end-to-end on Day 1. Read the docs, install it locally, run the quickstart, and ask three specific questions:

**Question A: Coverage.** What does agents-cli deploy automatically?
- Agent Runtime deployments via `adk deploy` integration? ✓ likely
- Cloud Run for the MCP servers? ✓ possibly via templates
- Cloud Run for the canvas frontend? ✓ likely via templates
- Knowledge Catalog content ingestion? ✗ probably not
- Memory Bank profile setup? ✗ probably not
- Agent Identity provisioning? ✓ possibly
- Agent Gateway policies? ? unclear
- Model Armor floor settings? ✗ probably not (security tooling)
- BigQuery dataset creation? ? unclear

**Question B: Customization.** Can we plug in our `customer.yaml` skin system?

**Question C: CI/CD.** Does the built-in Cloud Build integration work with our test suite?

Approach:

```bash
# Install agents-cli
pip install agents-cli   # or whatever the official install path is

# Try the quickstart in a throwaway directory
mkdir /tmp/agents-cli-eval && cd /tmp/agents-cli-eval
agents init multi-agent-with-mcp   # or closest template to our system

# Inspect what it generated
ls -la
cat agents.yaml

# Try deploying to a throwaway project
gcloud config set project <eval-project>
agents deploy
```

Write down what works, what didn't, what's manual. Be specific.

### Step 2 — Write the evaluation ADR

`docs/adr/0002-agents-cli-evaluation.md`:

```markdown
# ADR 0002: agents-cli evaluation and adoption decision

## Status

[Accepted | Deferred] — based on findings below

## Context

The Reference Solution needs end-to-end reproducible deployment. Two paths:
1. Adopt agents-cli — Google's unified deployment CLI for the platform
2. Build Terraform modules from scratch

## Findings from time-boxed evaluation

### What agents-cli covers cleanly

- [list specifically what worked: agent deployment, Cloud Run, etc.]

### What agents-cli doesn't cover (gaps for our build)

- [list specifically what was missing: KC ingestion, Memory Bank, governance config, BigQuery, etc.]
- [for each: estimate effort to fill the gap manually]

### Compatibility with our customer skin system

- [does CUSTOMER_SKIN env var thread through? do skin-specific configs survive?]

### Compatibility with our CI/CD

- [does the built-in Cloud Build integration work? does it conflict with our existing tests?]

## Decision

[Pick one based on findings]:

**Option A: Adopt agents-cli as the deployment primitive.** Use it for the
80% it covers cleanly. Fill gaps with shell scripts called from agents-cli
hooks. Rationale: aligns with platform direction, less custom infrastructure
to maintain.

**Option B: Defer agents-cli; write Terraform.** agents-cli does not cover
enough of our build for the integration cost to be worth it. Use Terraform
as the deployment primitive. Revisit agents-cli when it matures.

**Option C: Hybrid.** Use agents-cli for agent deployments and Cloud Run.
Use Terraform for governance, Knowledge Catalog, Memory Bank, BigQuery.
Stitch with Makefile targets.

## Consequences

[List specific implications of the choice]
```

### Step 3a — If adopting agents-cli (Option A or C)

Configure `agents.yaml` at the repo root:

```yaml
# agents.yaml — agents-cli configuration
project:
  name: agentic-sop-oilfield-services
  description: "Reference Solution for oilfield services agentic S&OP"

agents:
  - name: capacity-orchestrator
    path: src/orchestrator_agent
    runtime: agent-platform
    streaming: true
    
  - name: plan-evaluator
    path: src/plan_evaluator
    runtime: agent-platform
    
  - name: procurement-approval
    path: src/procurement_approval
    runtime: agent-platform
    
  - name: forecast-review
    path: src/forecast_review
    runtime: agent-platform
    
  - name: capacity-planning
    path: src/capacity_planning
    runtime: agent-platform

cloud_run:
  - name: sap-mcp-server
    path: mcp_servers/sap
  - name: maximo-mcp-server
    path: mcp_servers/maximo
  - name: fdp-mcp-server
    path: mcp_servers/fdp
  - name: operations-canvas
    path: canvas

# Pre/post hooks for things agents-cli doesn't manage natively
hooks:
  pre_deploy:
    - cmd: make setup-knowledge-catalog
      description: "Populate Knowledge Catalog with canonical assets"
    - cmd: make setup-memory-bank
      description: "Create Memory Profiles for personas"
  
  post_deploy:
    - cmd: make register-mcp-servers
      description: "Register MCP servers with Agent Registry"
    - cmd: terraform apply -auto-approve -chdir=infra/governance
      description: "Apply governance config (IAM, Gateway policies, Model Armor)"
    - cmd: make seed-blocked-attack
      description: "Generate a recent Model Armor block for Persona 6"
    - cmd: make seed-demo-sessions
      description: "Pre-warm deterministic demo sessions"

observability:
  cloud_trace: enabled
  cloud_logging: enabled

ci:
  cloud_build:
    enabled: true
    test_command: make test
```

Customer skin selection threads through:

```bash
# agents-cli respects env vars; pass CUSTOMER_SKIN through
CUSTOMER_SKIN=halliburton-pattern agents deploy
```

### Step 3b — If deferring agents-cli (Option B)

Build Terraform modules. Folder structure:

```
infra/
├── main.tf                    # root, calls modules
├── variables.tf
├── providers.tf
├── modules/
│   ├── agents/                # Agent Runtime deployments
│   ├── mcp_servers/           # Cloud Run for SAP/Maximo/FDP
│   ├── canvas/                # Cloud Run for operations-canvas
│   ├── knowledge_catalog/     # Aspect types and Entry Group (custom resource calling Python script)
│   ├── memory_bank/           # Profile setup (custom resource)
│   ├── governance/            # Agent Identity, Gateway, Model Armor (from TASK-11)
│   ├── bigquery/              # datasets for synthetic data and forecasts
│   └── iam/                   # service accounts, role bindings
```

Each module is self-contained with `main.tf`, `variables.tf`, `outputs.tf`.

The root `main.tf` wires modules with dependencies:

```hcl
module "iam" {
  source     = "./modules/iam"
  project_id = var.project_id
}

module "bigquery" {
  source     = "./modules/bigquery"
  project_id = var.project_id
  depends_on = [module.iam]
}

module "mcp_servers" {
  source     = "./modules/mcp_servers"
  project_id = var.project_id
  region     = var.region
  service_account_emails = module.iam.mcp_service_accounts
  depends_on = [module.iam]
}

module "knowledge_catalog" {
  source     = "./modules/knowledge_catalog"
  project_id = var.project_id
  region     = var.region
  depends_on = [module.iam]
}

module "agents" {
  source     = "./modules/agents"
  project_id = var.project_id
  region     = var.region
  service_account_emails = module.iam.agent_service_accounts
  customer_skin = var.customer_skin
  depends_on = [module.knowledge_catalog, module.mcp_servers]
}

module "governance" {
  source     = "./modules/governance"
  project_id = var.project_id
  region     = var.region
  agent_identities = module.agents.identities
  mcp_servers = module.mcp_servers.registered_servers
  depends_on = [module.agents, module.mcp_servers]
}

module "memory_bank" {
  source     = "./modules/memory_bank"
  project_id = var.project_id
  customer_skin = var.customer_skin
  depends_on = [module.agents]
}

module "canvas" {
  source     = "./modules/canvas"
  project_id = var.project_id
  region     = var.region
  customer_skin = var.customer_skin
  agent_gateway_endpoint = module.governance.gateway_endpoint
  depends_on = [module.governance]
}
```

Custom resources (Knowledge Catalog, Memory Bank) use Terraform's `null_resource` with `local-exec` to invoke our setup scripts:

```hcl
# modules/knowledge_catalog/main.tf
resource "null_resource" "setup_knowledge_catalog" {
  triggers = {
    # Re-run if the canonical asset data changes
    data_hash = filemd5("${path.module}/../../../data/canonical_assets.json")
  }

  provisioner "local-exec" {
    command = "uv run python ${path.module}/../../../knowledge_catalog/setup.py"
    environment = {
      GOOGLE_CLOUD_PROJECT = var.project_id
      GOOGLE_CLOUD_LOCATION = var.region
      CUSTOMER_SKIN = var.customer_skin
    }
  }
}
```

### Step 4 — Build `make deploy-from-scratch`

Regardless of Option A or B, the outermost entry point is one Make target:

```makefile
.PHONY: deploy-from-scratch

# Usage: make deploy-from-scratch PROJECT=my-fresh-project CUSTOMER=default
deploy-from-scratch:
	@if [ -z "$(PROJECT)" ]; then echo "Usage: make deploy-from-scratch PROJECT=<id> [CUSTOMER=<skin>]"; exit 1; fi
	@echo "==> Deploying Agentic S&OP Reference Solution to $(PROJECT)"
	@echo "==> Customer skin: $(or $(CUSTOMER),default)"
	@echo ""
	@echo "==> Step 1/8: Enable required APIs"
	gcloud config set project $(PROJECT)
	gcloud services enable \
	    aiplatform.googleapis.com \
	    dataplex.googleapis.com \
	    run.googleapis.com \
	    cloudbuild.googleapis.com \
	    bigquery.googleapis.com \
	    secretmanager.googleapis.com \
	    modelarmor.googleapis.com \
	    iam.googleapis.com \
	    iamcredentials.googleapis.com
	@echo ""
	@echo "==> Step 2/8: Wait for API propagation (60s)"
	@sleep 60
	@echo ""
	@echo "==> Step 3/8: Bootstrap IAM service accounts"
	# Provisions agent service accounts and minimum IAM
	cd infra && terraform init && terraform apply -auto-approve \
	    -var="project_id=$(PROJECT)" -var="customer_skin=$(or $(CUSTOMER),default)" \
	    -target=module.iam
	@echo ""
	@echo "==> Step 4/8: Deploy MCP servers and BigQuery datasets"
	cd infra && terraform apply -auto-approve \
	    -var="project_id=$(PROJECT)" -var="customer_skin=$(or $(CUSTOMER),default)" \
	    -target=module.mcp_servers -target=module.bigquery
	@echo ""
	@echo "==> Step 5/8: Populate Knowledge Catalog"
	CUSTOMER_SKIN=$(or $(CUSTOMER),default) make setup-knowledge-catalog
	@echo ""
	@echo "==> Step 6/8: Deploy agents and configure governance"
	cd infra && terraform apply -auto-approve \
	    -var="project_id=$(PROJECT)" -var="customer_skin=$(or $(CUSTOMER),default)"
	@echo ""
	@echo "==> Step 7/8: Seed Memory Bank profiles and demo sessions"
	CUSTOMER_SKIN=$(or $(CUSTOMER),default) make setup-memory-bank
	CUSTOMER_SKIN=$(or $(CUSTOMER),default) make seed-demo-sessions
	CUSTOMER_SKIN=$(or $(CUSTOMER),default) make seed-blocked-attack
	@echo ""
	@echo "==> Step 8/8: Deploy canvas frontend"
	cd canvas && NEXT_PUBLIC_CUSTOMER_SKIN=$(or $(CUSTOMER),default) gcloud builds submit \
	    --tag gcr.io/$(PROJECT)/operations-canvas
	gcloud run deploy operations-canvas \
	    --image gcr.io/$(PROJECT)/operations-canvas \
	    --region us-central1 \
	    --allow-unauthenticated \
	    --project $(PROJECT)
	@echo ""
	@echo "==> Deployment complete. Run 'make demo-preflight' to verify."
	@echo "==> Canvas URL:"
	@gcloud run services describe operations-canvas --region us-central1 --project $(PROJECT) --format='value(status.url)'
```

### Step 5 — Test in two fresh projects

The deployment is only proven if it works twice. Create two fresh projects, run `make deploy-from-scratch` against each, run `make demo-preflight` on each, verify both pass.

```bash
PROJECT_1=agentic-sop-eval-001
PROJECT_2=agentic-sop-eval-002

gcloud projects create $PROJECT_1
gcloud projects create $PROJECT_2
# (link to billing account)

make deploy-from-scratch PROJECT=$PROJECT_1 CUSTOMER=default
make deploy-from-scratch PROJECT=$PROJECT_2 CUSTOMER=halliburton-pattern

# Verify both
GOOGLE_CLOUD_PROJECT=$PROJECT_1 make demo-preflight
GOOGLE_CLOUD_PROJECT=$PROJECT_2 make demo-preflight
```

Capture the actual end-to-end time. If under 90 minutes, you're at target. If over, identify the slow steps and parallelize or accept.

### Step 6 — Document for partners

`docs/deployment.md`:

```markdown
# Deployment guide

## What this deploys

[List every GCP resource: agents, Cloud Run services, IAM, Knowledge Catalog
content, Memory Bank profiles, Gateway policies, Model Armor floor settings,
BigQuery datasets, canvas frontend.]

## Prerequisites

- A GCP project with billing enabled
- `gcloud` CLI authenticated with project-level Owner permissions
- `terraform` >= 1.6 installed
- `uv` Python package manager installed
- `node` 20+ installed
- `make` (BSD or GNU)

## One-command deployment

```bash
make deploy-from-scratch PROJECT=<your-project-id> CUSTOMER=<skin-name>
```

Approximate timing:
- API enablement: 5 min
- IAM bootstrap: 2 min
- MCP servers + BigQuery: 15 min
- Knowledge Catalog population: 10 min
- Agent deployments: 15 min
- Governance config: 5 min
- Memory Bank + seed data: 5 min
- Canvas deployment: 15 min
- Total: ~75 min

## Verifying the deployment

```bash
make demo-preflight
```

All checks should pass. If any fail, see the troubleshooting section.

## Cost estimate

Approximate cost for a demo environment running 24/7:
- Agent Runtime: ~$X/month
- Cloud Run (4 services): ~$Y/month
- Knowledge Catalog: ~$Z/month
- BigQuery storage: minimal
- Model Armor: per-call pricing, demo volume is small
- Total: ~$N/month for an always-on demo environment

To reduce cost, scale Cloud Run services to zero when not demoing.

## Tearing down

```bash
make teardown PROJECT=<your-project-id>
```

This removes all resources. Cannot be undone.

## Troubleshooting

[Common issues from the two test deployments]
```

### Step 7 — Add the teardown target

```makefile
.PHONY: teardown

teardown:
	@if [ -z "$(PROJECT)" ]; then echo "Usage: make teardown PROJECT=<id>"; exit 1; fi
	@echo "==> Tearing down deployment in $(PROJECT)"
	@read -p "Are you sure? This will delete all resources. (yes/no) " confirm; \
	if [ "$$confirm" != "yes" ]; then echo "Aborted"; exit 1; fi
	cd infra && terraform destroy -auto-approve \
	    -var="project_id=$(PROJECT)"
	gcloud run services delete operations-canvas --region us-central1 --project $(PROJECT) --quiet
	@echo "Teardown complete. The GCP project itself is not deleted."
```

### Step 8 — Commit

```bash
git add infra/ agents.yaml docs/deployment.md docs/adr/0002-agents-cli-evaluation.md Makefile
git commit -m "feat: end-to-end deployment via $(option) (TASK-14)"
git push
```

---

## Acceptance criteria

- [ ] `docs/adr/0002-agents-cli-evaluation.md` written with specific findings and a clear decision
- [ ] Either: `agents.yaml` complete and tested deploy (if Option A)
- [ ] Or: Terraform modules complete for all deployable resources (if Option B)
- [ ] Or: hybrid configuration documented and tested (if Option C)
- [ ] `make deploy-from-scratch PROJECT=<id> CUSTOMER=<skin>` runs to completion in two fresh test projects
- [ ] Both fresh deployments pass `make demo-preflight`
- [ ] `make teardown PROJECT=<id>` cleanly removes everything
- [ ] `docs/deployment.md` written for partners
- [ ] Total deployment time documented (target: <90 minutes; record actual)
- [ ] Cost estimate documented
- [ ] Commit pushed

---

## Common pitfalls

**API enablement is async.** Enabling a service via `gcloud services enable` returns before the service is actually usable. Subsequent calls within ~30s often fail with permission errors. The 60s sleep in the Makefile is intentional. Don't remove it to "speed things up."

**Quota limits in fresh projects.** Cloud Run, Agent Runtime, BigQuery — all have default quotas. A fresh project may hit quota limits during the parallel agent deployments. If `make deploy-from-scratch` fails partway, check Cloud Console → IAM & Admin → Quotas before assuming the script is broken.

**Terraform state in a remote backend.** For a real customer engagement, store Terraform state in a GCS bucket, not locally. The default Makefile uses local state for simplicity; for production, configure a remote backend in `infra/providers.tf`.

**Service account propagation lag.** After creating service accounts in Step 3, the next steps may fail with "service account not found." IAM eventual consistency takes 30-60 seconds. The next step should sleep or retry.

**Agent deployment ordering.** Some agents call other agents via A2A; the called agent must be deployed first. The Capacity Orchestrator depends on Plan Evaluator and Procurement Approval. Topological deployment order is enforced via Terraform `depends_on` or `agents.yaml` ordering.

**MCP server URLs in agent prompts.** If agent prompts hardcode MCP URLs, redeploying with new URLs breaks the agents. Use environment variables or service discovery (the Agent Registry pattern); never hardcode.

**Knowledge Catalog quota for Entries.** Knowledge Catalog has limits on number of Entries per project. For 80-120 canonical assets we're well below; for a customer with 10K+ assets, consider partitioning.

**Two-project test catches stale state.** The test "run deploy twice in two fresh projects" reliably catches issues caused by stale state from earlier runs (cached IAM, leftover service accounts, etc.). Don't shortcut by re-running in the same project.

**Canvas build size.** Next.js production builds can be large. Cloud Build deployment takes ~10-15 minutes. If it's slower, check if the build is bundling unused dependencies (run `npm run analyze`).

**Mapbox token in deployed canvas.** `NEXT_PUBLIC_MAPBOX_TOKEN` must be set at build time, not runtime. The Cloud Build substitution `_MAPBOX_TOKEN` must be configured in the cloudbuild.yaml or the deployed canvas shows a blank map.

---

## References

- agents-cli: `https://google.github.io/agents-cli/`
- Terraform Google Cloud provider: `https://registry.terraform.io/providers/hashicorp/google/latest/docs`
- Cloud Run deployments: `https://cloud.google.com/run/docs/deploying`
- ADK deployment: `https://adk.dev/deploy/`

---

*When TASK-14 is complete, a new CE or partner can take a fresh GCP project and produce a working demo environment in ~75-90 minutes with one command. The Reference Solution is now genuinely re-deployable. Final task: polish, fail-safe, and the recorded fallback that protects the highest-stakes demos.*
