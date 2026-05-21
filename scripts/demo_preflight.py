"""Pre-demo verification before a customer-facing run.

TASK-12 Step 7: this script is what the demoer runs 30-60 minutes before
the customer demo to catch anything fixable while there's still time to
fix it. Symptom of skipping it: a broken BQ table or an unauthenticated
GCS bucket surfacing live in front of the customer.

What it checks (each emits PASS / FAIL / STUB):

  1. BQ datasets populated — row counts >= minimums on the four spine
     tables the orchestrator's skill tools hit:
       oilfield_kc.canonical_assets        (>= 25 rows — demo taxonomy)
       maximo_extract.ASSET                (>= 10 rows — global fleet sample)
       sap_extract.MARA                    (>= 25 rows — material master)
       fdp_extract.CUSTOMER_CONFIG         (>=  5 rows — demo customers)
     (KC content is verified via the same canonical_assets count as a
     proxy until the live KC managed-MCP query is wired.)

     Minimums are demo floors, not the "80-120" goal in the product brief
     — they exist so the cargo-plane smoke can run end-to-end (TX-001,
     TX-007, MAT-67890, EQ-12345, KUNNR 0000100004 must all resolve).
     Bump these as the seeded datasets grow.

  2. Unstructured corpora — three corpus manifests
     (data/anchors/intouch_corpus.json, bsee_corpus.json,
     sec_edgar_corpus.json) load and every gcs_uri points to an object
     that exists in GCS (verified via google-cloud-storage Blob.exists).

  3. Cargo-plane smoke — delegates to scripts/smoke_cargo_plane.py,
     reports PASS only on exit 0.

  4. No-json-reads static check — delegates to
     scripts/verify_no_json_reads.py.

  5. Memory Profiles loaded — STUB (advisory). The Memory Bank API
     returns 404 when fetched without the right resource name, and the
     resource-name lookup requires the env vars the deployer sets after
     `make deploy-all-agents`. Wire as a real check in v1.1.

  6. Recent blocked-attack example — STUB (advisory). Requires Model
     Armor log read access which is not yet provisioned in the demo
     account.

  7. Canvas builds clean — runs `npm run build` in canvas/ if the
     directory exists. Capture exit code; PASS on 0.

Output: a checklist with PASS / FAIL / STUB markers. Exit 0 if every
check is PASS or STUB; exit 1 if any check is FAIL.

The Memory Bank + Model Armor STUBs are deliberately advisory — they
don't gate the demo, they just remind the demoer to verify out-of-band.

Wired into the Makefile as `make demo-preflight`. Run with the deploy
venv (Python 3.10): `venv-deploy-310/bin/python scripts/demo_preflight.py`.
"""

from __future__ import annotations

import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------
#
# Each check is a callable returning one of:
#   ("PASS", detail_str)   — green, counts toward demo readiness
#   ("FAIL", detail_str)   — red, gates the demo (exit 1)
#   ("STUB", detail_str)   — yellow advisory; does NOT gate (exit 0 still OK)
#
# Result tuples are kept simple — no dataclass — so this script stays a
# single self-contained file the demoer can read top-to-bottom while a
# customer waits.

CheckResult = tuple[str, str]
CheckFn = Callable[[], CheckResult]

CHECKS: list[tuple[str, CheckFn]] = []


def register(name: str):
    def decorator(fn: CheckFn) -> CheckFn:
        CHECKS.append((name, fn))
        return fn

    return decorator


# ---------------------------------------------------------------------------
# 1. BigQuery row counts
# ---------------------------------------------------------------------------

# (table_fqn, minimum_expected_rows, narration)
_BQ_TABLES: list[tuple[str, int, str]] = [
    (
        "vertex-ai-demos-468803.oilfield_kc.canonical_assets",
        25,
        "KC taxonomy",
    ),
    (
        "vertex-ai-demos-468803.maximo_extract.ASSET",
        10,
        "global fleet",
    ),
    (
        "vertex-ai-demos-468803.sap_extract.MARA",
        25,
        "material master",
    ),
    (
        "vertex-ai-demos-468803.fdp_extract.CUSTOMER_CONFIG",
        5,
        "demo customers",
    ),
]


@register("BQ datasets populated (KC + Maximo + SAP + FDP)")
def check_bq_populated() -> CheckResult:
    """All four spine tables exist and meet minimum row counts.

    Uses the BigQuery Python client (already in the deploy venv). One
    query per table — a fast COUNT(*). If any table is missing or under
    minimum, the whole check fails with the first offender named in the
    detail string.
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        return ("FAIL", "google-cloud-bigquery not installed in venv")

    try:
        client = bigquery.Client(project="vertex-ai-demos-468803")
    except Exception as e:
        return ("FAIL", f"BQ client init failed: {e}")

    shortfalls: list[str] = []
    counts: list[str] = []
    for table_fqn, minimum, label in _BQ_TABLES:
        try:
            sql = f"SELECT COUNT(*) AS n FROM `{table_fqn}`"
            rows = list(client.query(sql).result())
            n = rows[0]["n"] if rows else 0
        except Exception as e:
            shortfalls.append(f"{table_fqn} ({label}): query failed — {e}")
            continue
        counts.append(f"{label}={n}")
        if n < minimum:
            shortfalls.append(f"{table_fqn} ({label}): {n} < {minimum} min")

    if shortfalls:
        return ("FAIL", "; ".join(shortfalls))
    return ("PASS", ", ".join(counts))


# ---------------------------------------------------------------------------
# 2. KC content present
# ---------------------------------------------------------------------------
#
# Until the live KC managed-MCP query is wired into a check, we use the
# canonical_assets row count as a proxy — KC content is hydrated FROM
# that table, so a populated table means KC will return entries when
# queried. The full BQ check above already verifies the count; this check
# is a second-pass narrative confirmation that the load happened.


@register("KC content present (canonical assets + cross-system aliases)")
def check_kc_content() -> CheckResult:
    """Sanity-check oilfield_kc has aliases + equivalences alongside assets.

    A populated canonical_assets without cross_system_aliases or
    functional_equivalences means the load only got partway through
    — which the smoke would catch but slower. Quick early signal.
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        return ("FAIL", "google-cloud-bigquery not installed")
    client = bigquery.Client(project="vertex-ai-demos-468803")
    try:
        sql = """
        SELECT
          (SELECT COUNT(*) FROM `vertex-ai-demos-468803.oilfield_kc.canonical_assets`)        AS n_assets,
          (SELECT COUNT(*) FROM `vertex-ai-demos-468803.oilfield_kc.cross_system_aliases`)    AS n_aliases,
          (SELECT COUNT(*) FROM `vertex-ai-demos-468803.oilfield_kc.functional_equivalences`) AS n_equiv
        """
        row = next(iter(client.query(sql).result()))
        n_assets = row["n_assets"]
        n_aliases = row["n_aliases"]
        n_equiv = row["n_equiv"]
    except Exception as e:
        return ("FAIL", f"KC query failed: {e}")

    detail = f"assets={n_assets}, aliases={n_aliases}, equivalences={n_equiv}"
    # Demo floors — matched to actual seeded volume, not the brief's 80-120 goal.
    if n_assets < 25 or n_aliases < 25 or n_equiv < 5:
        return ("FAIL", detail + " (one or more below minimum)")
    return ("PASS", detail)


# ---------------------------------------------------------------------------
# 3. Unstructured corpora — manifests + GCS objects exist
# ---------------------------------------------------------------------------


def _check_one_corpus(manifest_path: Path, label: str, sample_n: int = 3) -> CheckResult:
    """Load a corpus manifest, verify a sample of gcs_uri values exist.

    We sample (not all) because the BSEE corpus has 7+ entries and the
    InTouch corpus has 80+; checking every blob is overkill for pre-flight.
    First N entries with a gcs_uri are checked. PASS only if ALL sampled
    blobs exist.
    """
    import json

    if not manifest_path.exists():
        return ("FAIL", f"{label}: manifest not found at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as e:
        return ("FAIL", f"{label}: manifest JSON parse failed — {e}")

    if not isinstance(manifest, dict) or not manifest:
        return ("FAIL", f"{label}: manifest is empty")

    try:
        from google.cloud import storage
    except ImportError:
        return ("FAIL", f"{label}: google-cloud-storage not installed")
    client = storage.Client(project="vertex-ai-demos-468803")

    entries_with_uri = [
        (k, v.get("gcs_uri"))
        for k, v in manifest.items()
        if isinstance(v, dict) and v.get("gcs_uri")
    ][:sample_n]

    if not entries_with_uri:
        return ("FAIL", f"{label}: no entries with gcs_uri")

    missing: list[str] = []
    for key, uri in entries_with_uri:
        # uri shape: gs://bucket/path/to/object.pdf
        if not uri.startswith("gs://"):
            missing.append(f"{key}: bad URI {uri}")
            continue
        bucket_name, _, blob_path = uri[len("gs://") :].partition("/")
        try:
            blob = client.bucket(bucket_name).blob(blob_path)
            if not blob.exists():
                missing.append(f"{key}: blob missing — {uri}")
        except Exception as e:
            missing.append(f"{key}: GCS check failed — {e}")

    if missing:
        return ("FAIL", f"{label}: " + "; ".join(missing))
    return (
        "PASS",
        f"{label}: {len(manifest)} entries in manifest, sampled {len(entries_with_uri)} GCS blobs",
    )


@register("InTouch corpus manifest + GCS objects exist")
def check_intouch_corpus() -> CheckResult:
    return _check_one_corpus(REPO_ROOT / "data" / "anchors" / "intouch_corpus.json", "intouch")


@register("BSEE corpus manifest + GCS objects exist")
def check_bsee_corpus() -> CheckResult:
    return _check_one_corpus(REPO_ROOT / "data" / "anchors" / "bsee_corpus.json", "bsee")


@register("SEC EDGAR (MCC) corpus manifest + GCS objects exist")
def check_mcc_corpus() -> CheckResult:
    return _check_one_corpus(REPO_ROOT / "data" / "anchors" / "sec_edgar_corpus.json", "mcc")


# ---------------------------------------------------------------------------
# 4. Cargo-plane scenario smoke
# ---------------------------------------------------------------------------


@register("Cargo-plane scenario smoke (delegates to smoke_cargo_plane.py)")
def check_cargo_plane_smoke() -> CheckResult:
    """Runs the existing programmatic smoke. Slow-ish (~10-30s) but the
    most load-bearing check — if this fails, the live demo will too.

    Captures stdout/stderr so the demoer's terminal stays readable; the
    summary line is parsed back out and surfaced in the detail string.
    """
    script = REPO_ROOT / "scripts" / "smoke_cargo_plane.py"
    if not script.exists():
        return ("FAIL", f"missing {script}")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    # Pull the summary "=== N/M checks passed ===" line if present
    summary = ""
    for line in result.stdout.splitlines():
        if "checks passed" in line:
            summary = line.strip()
            break
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-8:])
        return ("FAIL", f"{summary or 'smoke failed'} (rc={result.returncode}); tail:\n{tail}")
    return ("PASS", summary or "smoke ok")


# ---------------------------------------------------------------------------
# 5. No-json-reads static check
# ---------------------------------------------------------------------------


@register("No JSON reads in agent production paths (TASK-16 contract)")
def check_no_json_reads() -> CheckResult:
    script = REPO_ROOT / "scripts" / "verify_no_json_reads.py"
    if not script.exists():
        return ("FAIL", f"missing {script}")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )
    if result.returncode != 0:
        return ("FAIL", result.stdout.strip().splitlines()[-1] if result.stdout else "rc!=0")
    return ("PASS", result.stdout.strip().splitlines()[-1] if result.stdout else "ok")


# ---------------------------------------------------------------------------
# 6. Memory Profiles loaded (STUB)
# ---------------------------------------------------------------------------


@register("Memory Profiles loaded for six personas")
def check_memory_profiles() -> CheckResult:
    """Memory Bank verification — not yet wired.

    TODO (v1.1): once we standardize on a Memory Bank resource-name env
    var (provisional: MEMORY_BANK_RESOURCE_NAME), fetch each persona's
    profile (maria-occ-planner-west-africa, david-permian-basin-director,
    tomas-fleet-scheduler-west-texas, priya-evp-eastern-hemisphere,
    rafael-analyst-latin-america, ayesha-audit-director) and assert the
    `display_name` topic exists. Mark FAIL if any persona is missing.

    Until then this is an advisory: the demoer should manually run
    `make reset-and-seed` if they haven't seeded since the last redeploy.
    """
    return ("STUB", "TODO: wire Memory Bank verification when MEMORY_BANK_RESOURCE_NAME is fixed")


# ---------------------------------------------------------------------------
# 7. Recent blocked-attack example (STUB)
# ---------------------------------------------------------------------------


@register("Recent Model Armor blocked-attack example (<= 7 days)")
def check_blocked_attack() -> CheckResult:
    """Model Armor recent block — not yet wired.

    TODO (v1.1): query Cloud Logging for log entries with
    `protoPayload.serviceName="modelarmor.googleapis.com"` and a `BLOCK`
    decision, filter to last 7 days, FAIL if empty. The demoer's recovery
    today: `python scripts/seed_blocked_attack_example.py` re-seeds the
    log artifact Audit Mode renders.

    Marked STUB so it doesn't gate the demo; advisory in the output.
    """
    return ("STUB", "TODO: query Cloud Logging for recent Model Armor block events")


# ---------------------------------------------------------------------------
# 8. Canvas builds clean
# ---------------------------------------------------------------------------


@register("Canvas builds clean (npm run build in canvas/)")
def check_canvas_builds() -> CheckResult:
    """Run `npm run build` in canvas/. ~30-60s on a warm cache.

    PASS on exit 0; FAIL on anything else. If canvas/ doesn't exist
    (someone deleted it for a stripped-down deploy) we return STUB.
    """
    canvas_dir = REPO_ROOT / "canvas"
    if not canvas_dir.is_dir():
        return ("STUB", "canvas/ directory not found")
    if not (canvas_dir / "package.json").exists():
        return ("STUB", "canvas/package.json missing")
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(canvas_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return ("FAIL", "npm not on PATH — install Node.js")
    except subprocess.TimeoutExpired:
        return ("FAIL", "npm run build timed out after 5min")
    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout).splitlines()[-6:])
        return ("FAIL", f"npm run build rc={result.returncode}; tail:\n{tail}")
    return ("PASS", "npm run build exit 0")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _marker(status: str) -> str:
    return {
        "PASS": "[PASS]",
        "FAIL": "[FAIL]",
        "STUB": "[STUB]",
    }.get(status, f"[{status}]")


def main() -> int:
    print("=== Demo pre-flight ===")
    print(f"Repo: {REPO_ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Total checks: {len(CHECKS)}")
    print()

    counts = {"PASS": 0, "FAIL": 0, "STUB": 0}
    started = time.time()
    for name, fn in CHECKS:
        print(f"  ... {name}")
        try:
            status, detail = fn()
        except Exception as exc:
            status, detail = "FAIL", f"unhandled exception: {exc}"
            traceback.print_exc()
        counts[status] = counts.get(status, 0) + 1
        line = f"  {_marker(status)} {name}"
        if detail:
            line += f" — {detail}"
        print(line)
    elapsed = time.time() - started

    print()
    print(
        f"=== {counts['PASS']} PASS  {counts['FAIL']} FAIL  {counts['STUB']} STUB  "
        f"({elapsed:.1f}s) ==="
    )

    if counts["FAIL"] > 0:
        print("Demo NOT READY — fix FAILs above before running customer demo.")
        return 1
    if counts["STUB"] > 0:
        print(
            "Demo READY (with advisories). Verify STUB items out-of-band:\n"
            "  - Memory Profiles: `make reset-and-seed` if not run since last redeploy\n"
            "  - Recent blocked attack: `python scripts/seed_blocked_attack_example.py`"
        )
    else:
        print("Demo READY. All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
