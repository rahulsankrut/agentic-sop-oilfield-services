# Testing guide

End-to-end checklist for verifying every piece of the Agentic S&OP for
Oilfield Services build. Designed for a fresh clone on a machine that
already has GCP ADC. Each section ends with a ✅ pass criterion.

> If you only have 5 minutes, jump to [§13 Minimum viable smoke](#13-minimum-viable-smoke).

---

## 1. Environment

```bash
# venv is named `venv/` (NOT `.venv/` — see CLAUDE.md)
source venv/bin/activate

# Verify Poetry is installed inside venv, not globally
which poetry              # → .../venv/bin/poetry
python --version          # 3.11+ for local dev
```

```bash
# Sibling deploy venv (Python 3.10 to match Reasoning Engine runtime)
venv-deploy-310/bin/python --version    # → Python 3.10.x
```

```bash
# ADC + project
gcloud auth application-default print-access-token | head -c 20; echo
gcloud config get-value project          # → vertex-ai-demos-468803
```

✅ **Pass:** venv activates, both Python versions report correctly, ADC token prints.

---

## 2. Lint

```bash
poetry run ruff check agents/ scripts/
poetry run ruff format --check agents/
```

✅ **Pass:** `All checks passed!` on both.

---

## 3. Unit tests

```bash
poetry run pytest agents/tests/unit/ -q --tb=line
```

✅ **Pass:** `121 passed` (count may grow over time). Tests cover schemas,
prompt builder, deploy patch, global Gemini, skill toolset, skin loader,
skin splice (cross-skin behavior), vertex AI search, A2UI v0.8 catalog.

---

## 4. BigQuery data layer

```bash
# Datasets that should exist in vertex-ai-demos-468803:
bq ls --project_id=vertex-ai-demos-468803 \
  | grep -E "oilfield_kc|sap_extract|maximo_extract|fdp_extract"
# expect 4 lines: oilfield_kc, sap_extract, maximo_extract, fdp_extract

# Row-count sanity (one per dataset):
bq query --use_legacy_sql=false --project_id=vertex-ai-demos-468803 \
"SELECT COUNT(*) AS n FROM \`vertex-ai-demos-468803.oilfield_kc.canonical_assets\`"
# expect n > 0
```

✅ **Pass:** all 4 datasets present, `canonical_assets` has rows. The
deterministic data-flow smoke (§5) covers the rest of the BQ surface.

---

## 5. Data-flow smoke (no LLM in the path)

```bash
make smoke-cargo-plane
```

This runs `scripts/smoke_cargo_plane.py` — 11 assertions against the
KC + SAP + Maximo + FDP backends via the skill tool API, no LLM
involved.

✅ **Pass:** `=== 11/11 checks passed ===`.

---

## 6. MCP servers (Cloud Run)

```bash
# All 3 services up
gcloud run services list --region=us-central1 \
  --project=vertex-ai-demos-468803 \
  --format="value(metadata.name,status.url)" \
  | grep mcp
# expect 3 lines: sap-mcp-server, maximo-mcp-server, fdp-mcp-server
```

```bash
# tools/list via JSON-RPC (canonical MCP)
curl -s -X POST "https://sap-mcp-server-5udif2v3cq-uc.a.run.app/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json,text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['result']['tools']), 'tools')"
# expect: "9 tools"
```

```bash
# End-to-end MCP call via ADK McpToolset (path + auth + backend reach):
source venv/bin/activate
python3 - <<'PY'
import asyncio, os
for ln in open(".env"):
    if "=" in ln and not ln.startswith("#"):
        k, _, v = ln.partition("="); os.environ.setdefault(k, v.strip().strip('"'))
async def main():
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
    for env_key, tool, args in [
        ("SAP_MCP_URL", "sap_get_workforce_by_basin", {"basin": "Permian"}),
        ("MAXIMO_MCP_URL", "maximo_query_assets_by_region",
         {"itemnum": "EQ-12399", "region": "west_africa"}),
        ("FDP_MCP_URL", "fdp_get_customer_config",
         {"customer_id": "gulf-petroleum", "matnr": "MAT-67890"}),
    ]:
        ts = McpToolset(connection_params=StreamableHTTPConnectionParams(
            url=os.environ[env_key] + "/mcp"))
        tools = await ts.get_tools()
        t = next(t for t in tools if t.name == tool)
        res = await t.run_async(args=args, tool_context=None)
        text = (res.get("content") or [{}])[0].get("text", "")
        status = "ERROR" if res.get("isError") else "OK"
        print(f"  {env_key} {tool}: [{status}] {text[:80]}")
asyncio.run(main())
PY
```

✅ **Pass:** all 3 print `[OK]` with the expected SAP / Maximo / FDP
JSON shapes (not the literal `{basin}` / connection-refused strings
that earlier broke states produced).

---

## 7. Vertex AI Search (Discovery Engine)

```bash
# 3 data stores ingested
for DS in oilfield-bsee-incidents oilfield-mcc-contracts oilfield-intouch-specs; do
  N=$(gcloud discovery-engine documents list \
        --location=global --collection=default_collection \
        --data-store=$DS --branch=default_branch \
        --project=vertex-ai-demos-468803 \
        --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
  echo "$DS: $N docs"
done
# expect 12 / 12 / 13
```

```bash
# Search smoke via the agents/utils/vertex_ai_search helper
source venv/bin/activate
python3 - <<'PY'
import os
for ln in open(".env"):
    if "=" in ln and not ln.startswith("#"):
        k,_,v = ln.partition("="); os.environ.setdefault(k, v.strip().strip('"'))
from agents.utils.vertex_ai_search import (
    search_bsee_incidents, search_mcc_contracts, search_intouch_specs)
for fn, q in [
    (search_bsee_incidents, "kick well control"),
    (search_mcc_contracts, "indemnification clause"),
    (search_intouch_specs, "measurement while drilling")]:
    hits = fn(q, page_size=2)
    print(f"  {fn.__name__}({q!r}): {len(hits)} hits — first: {hits[0]['title'][:60]}")
PY
```

✅ **Pass:** each search returns ≥1 hit with a real document title.

---

## 8. Deployed agents (Reasoning Engine)

```bash
# All 4 reachable
TOKEN=$(gcloud auth application-default print-access-token)
for VAR in ORCHESTRATOR_AGENT_RESOURCE_NAME \
           PROCUREMENT_APPROVAL_AGENT_RESOURCE_NAME \
           FORECAST_REVIEW_AGENT_RESOURCE_NAME \
           CAPACITY_PLANNING_AGENT_RESOURCE_NAME; do
  RN=$(grep "^$VAR=" .env | sed -E 's/^[^=]+=//; s/^"(.*)"$/\1/')
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "https://us-central1-aiplatform.googleapis.com/v1beta1/$RN")
  echo "  $VAR: HTTP $HTTP"
done
# expect: HTTP 200 × 4
```

```bash
# Quick probe — Forecast Review returns ForecastOverride JSON
source venv/bin/activate
TOKEN=$(gcloud auth application-default print-access-token)
RN=$(grep '^FORECAST_REVIEW_AGENT_RESOURCE_NAME=' .env | sed -E 's/^[^=]+=//; s/^"(.*)"$/\1/')
python3 - <<PY
import json, urllib.request
token = "$TOKEN"
url = "https://us-central1-aiplatform.googleapis.com/v1beta1/$RN:streamQuery?alt=sse"
body = {"class_method":"async_stream_query","input":{
    "message":{"role":"user","parts":[{"text":"Show me Q4 forecast for west_africa basin."}]},
    "user_id":"smoke"}}
req = urllib.request.Request(url, method="POST",
    headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
    data=json.dumps(body).encode())
with urllib.request.urlopen(req, timeout=120) as r:
    for raw in r:
        line = raw.decode().strip()
        if line.startswith("data:"): line = line[5:].strip()
        if not line: continue
        try: evt = json.loads(line)
        except: continue
        for p in (evt.get("content") or {}).get("parts", []):
            if p.get("text"):
                print(p["text"][:200]); break
PY
```

✅ **Pass:** all 4 agents `HTTP 200`. Forecast Review's response prints a
`ForecastOverride`-shaped JSON object.

---

## 9. End-to-end cargo-plane Live smoke

The headline test — Persona 3, Maria, deployed Orchestrator Workflow,
14 nodes, 6 LLM calls, MCP + skill composers + memory + finalize.

```bash
source venv/bin/activate
TOKEN=$(gcloud auth application-default print-access-token)
RN=$(grep '^ORCHESTRATOR_AGENT_RESOURCE_NAME=' .env | sed -E 's/^[^=]+=//; s/^"(.*)"$/\1/')
python3 - <<PY
import json, time, urllib.request
token = "$TOKEN"
url = "https://us-central1-aiplatform.googleapis.com/v1beta1/$RN:streamQuery?alt=sse"
body = {"class_method":"async_stream_query","input":{
    "message":{"role":"user","parts":[{"text":
        "I need a Tool X variant in Luanda by Friday — what are my options?"}]},
    "user_id":"smoke-cargo"}}
req = urllib.request.Request(url, method="POST",
    headers={"Content-Type":"application/json","Authorization":f"Bearer {token}"},
    data=json.dumps(body).encode())
all_ce, t0 = [], time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    for raw in r:
        line = raw.decode().strip()
        if line.startswith("data:"): line = line[5:].strip()
        if not line: continue
        try: evt = json.loads(line)
        except: continue
        for c in (((evt.get("actions") or {}).get("state_delta") or {}).get("canvas_events") or []):
            if c not in all_ce: all_ce.append(c)
last = next((c for c in reversed(all_ce) if c.get("type")=="workflow.completed"), None)
print(f"events: {len(all_ce)}  duration: {time.time()-t0:.1f}s")
if last:
    plan = (last.get("final_output") or {}).get("plan")
    if plan:
        p = plan.get("primary_option", {})
        print(f"  asset:   {p.get('asset',{}).get('canonical_label')}")
        print(f"  source:  {p.get('source_location',{}).get('label')}")
        print(f"  cost:    \${p.get('estimated_cost_usd',0):,}")
        print(f"  avoided: \${plan.get('avoided_cost_usd',0):,}")
PY
```

✅ **Pass:** workflow completes in ~90-150s, ~16 canvas events,
SourcingPlan shows:
- asset: **Tool X-V7** (TX-007)
- source: **Lagos repair shop, Nigeria**
- cost: ~**$162K**
- avoided: ~**$474K**

---

## 10. Canvas

```bash
cd canvas
npm install                # idempotent
npm run build              # → "Compiled successfully"
npm run dev &              # background, listens on :3000
sleep 5
curl -s http://localhost:3000/scenarios/cargo-plane | grep -oE "<title>[^<]+" | head -1
kill %1 2>/dev/null
cd ..
```

✅ **Pass:** `npm run build` reports `Compiled successfully`; the
cargo-plane page returns HTTP 200 with a `<title>` element.

### Manual A2UI surface checks
With `cd canvas && npm run dev` running:

- `http://localhost:3000/scenarios/cargo-plane` — press `Space` to step through static beats; press `L` to engage Live mode against the deployed Orchestrator (you should see the same SourcingPlan from §9 painted onto the map)
- `http://localhost:3000/audit/registry` — Ayesha's audit panels (Registry / Gateway / Model Armor) render via A2UI v0.8

---

## 11. Skin system

```bash
# Snapshot current active skin
cat canvas/src/data/skin.generated.ts | grep "customer_slug" | head -1
# Swap to halliburton
make use-skin SKIN=halliburton
cat canvas/src/data/skin.generated.ts | grep "customer_slug" | head -1
# expect: "customer_slug": "halliburton"
# Restore
make use-skin SKIN=default
```

```bash
# Cross-skin behavioral tests
poetry run pytest agents/tests/unit/test_skin_splice.py -v
# expect: 5 passed (default→Luanda/Darwin, halliburton→Búzios/Singapore)
```

✅ **Pass:** skin swap toggles `customer_slug` cleanly; 5 cross-skin
tests pass.

---

## 12. Demo runner (TASK-12)

```bash
# Each target should: set skin, verify agent, print URLs, then start canvas.
# Use SKIP_CANVAS=1 for preflight-only validation.
for T in demo-cargo-plane demo-forecast demo-fleet-buffer \
         demo-deep-research demo-agent-studio demo-audit; do
  echo "=== $T ==="
  SKIP_CANVAS=1 make $T 2>&1 | grep -E "✓|⚠|target session|Canvas \(A2UI"
done
```

✅ **Pass:** each persona prints its agent's resource id (or
"static A2UI demo only" for rafael/ayesha), the seed session id, and
the canvas URL.

---

## 13. Minimum viable smoke

If you only have 5 minutes (e.g., the morning of a demo):

```bash
# 1. Unit tests pass
poetry run pytest agents/tests/unit/ -q

# 2. Data-flow smoke
make smoke-cargo-plane

# 3. Live cargo-plane workflow
# (copy the §9 python heredoc — produces SourcingPlan in ~90-150s)

# 4. Canvas builds clean
cd canvas && npm run build && cd ..

# 5. Demo runner sanity check
SKIP_CANVAS=1 make demo-cargo-plane | tail -20
```

If all 5 pass, the demo will run.

---

## Known footguns

- **ADC expires every hour** — re-run `gcloud auth application-default login`
  before a fresh smoke; the canvas API proxy refreshes its own token but
  curl-based smokes don't.
- **`venv/`, not `.venv/`** — every Python command needs the right venv
  active. Deploy scripts must use `venv-deploy-310/`.
- **Cargo-plane is the only Live mode wired persona** — David / Tomas /
  Priya / Rafael / Ayesha canvas pages are static A2UI showcases. The
  agents themselves respond to streamQuery but don't emit canvas events
  per-persona. Documented in `docs/persona-live-mode-status.md`.
- **`make deploy` / `make teardown` are stubs** — TASK-14 (reproducibility)
  is the only deliberately-unfinished SPECS acceptance item.
- **Stale Reasoning Engines accumulate** — each redeploy creates a new
  engine. Run the prune step from `docs/persona-live-mode-status.md` if
  the registry gets cluttered.

---

## Reference

- ADRs: `docs/adr/`
- Persona Live mode coverage: `docs/persona-live-mode-status.md`
- Demo storyboard: `docs/demo_storyboard.md`
- SPECS deviations: `SPECS.md` §Architectural deviations
- CLAUDE.md "Known gotchas" — the long list of land mines
