"""Idempotent Knowledge Catalog (Dataplex Universal Catalog) setup.

Builds the catalog content that grounds Issue 4 of the demo — the resolution
of taxonomic chaos across SAP, Maximo, FDP, and InTouch into a single
canonical asset model.

What this script does (idempotently):

1. Ensures one custom Entry Group `oilfield-canonical-assets` exists.
2. Ensures three custom Aspect Types exist, with schemas loaded from
   ``knowledge_catalog/aspect_types/*.yaml``:
       - oilfield-asset-specification
       - oilfield-cross-system-aliases
       - oilfield-functional-equivalence
3. Ensures one custom Entry Type `oilfield-canonical-asset` exists that
   requires the three Aspect Types above (so every canonical Entry is
   fully shaped).
4. For each row in ``data/canonical_assets.json`` upserts an Entry in the
   Entry Group with the three Aspects populated from
   ``cross_system_aliases.json`` and ``functional_equivalences.json``.
5. Prints a single summary block (created / updated / unchanged counts,
   per resource type, plus runtime).

Idempotency: every step performs a ``get_*`` first. If the resource exists,
``update_*`` is called with an explicit ``update_mask``. If it doesn't,
``create_*`` is called. Re-running the script converges the catalog state
to match the source JSON without duplicating anything.

Logging: deliberately uses ``print`` (not ``logging``) so that ``make
setup-knowledge-catalog`` produces a clean, ordered stream of progress
the operator can read directly.

Run:

    KNOWLEDGE_CATALOG_PROJECT=vertex-ai-demos-468803 \
    KNOWLEDGE_CATALOG_LOCATION=us-central1 \
    python knowledge_catalog/setup.py

Required env vars:
    KNOWLEDGE_CATALOG_PROJECT  GCP project id (required)
    KNOWLEDGE_CATALOG_LOCATION GCP region (default: us-central1)

Requirements:
    google-cloud-dataplex >= 2.0.0  (Aspect Types / Entries API)
    google-auth                     (ADC for API auth)
    pyyaml                          (parse aspect_types/*.yaml)

If the installed ``google-cloud-dataplex`` SDK predates the Aspect Types
API and does not expose ``CatalogServiceClient``, this script fails fast
with a clear remediation message. A REST fallback over ``httpx`` +
``google-auth`` would be the next escalation, but is intentionally not
implemented here — the project's pyproject pins a recent enough SDK.

# DEMO NARRATION: "Run this script once and the entire canonical asset
# model lives in Knowledge Catalog. Every canonical Tool X entry carries
# its SAP material number, Maximo equipment id, FDP config id, and
# InTouch spec references — unified in one Entry with structured Aspects.
# When the orchestrator asks 'what's an equivalent of TX-001?', it
# queries this catalog through the prebuilt MCP tool. No reasoning over
# system-specific identifiers. Issue 4 dissolves at setup time, not at
# runtime."
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from google.api_core.exceptions import AlreadyExists, NotFound
    from google.cloud import dataplex_v1
    from google.cloud.dataplex_v1.types import (
        Aspect,
        AspectType,
        Entry,
        EntryGroup,
        EntryType,
    )
except ImportError as exc:  # pragma: no cover - explicit fail-fast for setup tooling.
    print(
        "ERROR: google-cloud-dataplex is required. Install with "
        "'poetry install' (it is pinned in pyproject.toml) or "
        "'pip install \"google-cloud-dataplex>=2.0.0\"'.",
        file=sys.stderr,
    )
    print(f"Underlying ImportError: {exc}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
ASPECT_TYPE_DIR = Path(__file__).resolve().parent / "aspect_types"

ENTRY_GROUP_ID = "oilfield-canonical-assets"
ENTRY_TYPE_ID = "oilfield-canonical-asset"

ASPECT_TYPE_FILES: list[tuple[str, str]] = [
    # (yaml filename, Aspect Type id used in the catalog)
    ("asset_specification.yaml", "oilfield-asset-specification"),
    ("cross_system_aliases.yaml", "oilfield-cross-system-aliases"),
    ("functional_equivalence.yaml", "oilfield-functional-equivalence"),
]


@dataclass
class RunStats:
    """Counters printed in the final summary."""

    aspect_types_created: int = 0
    aspect_types_updated: int = 0
    aspect_types_unchanged: int = 0
    entry_group_action: str = "unchanged"  # one of: created / updated / unchanged
    entry_type_action: str = "unchanged"
    entries_created: int = 0
    entries_updated: int = 0
    entries_failed: int = 0
    started_at: float = field(default_factory=time.monotonic)

    @property
    def runtime_s(self) -> float:
        return time.monotonic() - self.started_at


# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------


def load_env() -> tuple[str, str]:
    """Return (project, location) from environment, exiting on missing project."""
    project = os.environ.get("KNOWLEDGE_CATALOG_PROJECT")
    if not project:
        print(
            "ERROR: KNOWLEDGE_CATALOG_PROJECT env var is required.",
            file=sys.stderr,
        )
        sys.exit(2)
    location = os.environ.get("KNOWLEDGE_CATALOG_LOCATION", "us-central1")
    return project, location


# ---------------------------------------------------------------------------
# YAML -> MetadataTemplate
# ---------------------------------------------------------------------------


def load_aspect_type_yaml(filename: str) -> dict[str, Any]:
    """Read one Aspect Type YAML file once and return the parsed dict."""
    path = ASPECT_TYPE_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_metadata_template(node: dict[str, Any]) -> AspectType.MetadataTemplate:
    """Recursively convert a YAML node into a Dataplex MetadataTemplate proto.

    Supports the type names documented for Dataplex Aspect Types:
    ``record``, ``enum``, ``string``, ``integer``, ``double``, ``boolean``,
    ``array``. Arrays carry ``array_items`` (another template). Records carry
    ``record_fields`` (a list of templates). Enums carry ``enum_values``.
    """
    kwargs: dict[str, Any] = {}
    if "name" in node:
        kwargs["name"] = node["name"]
    if "type" in node:
        kwargs["type_"] = node["type"]
    if ann := node.get("annotations"):
        kwargs["annotations"] = AspectType.MetadataTemplate.Annotations(
            description=ann.get("description")
        )

    if (fields := node.get("record_fields")) is not None:
        kwargs["record_fields"] = [_build_metadata_template(f) for f in fields]

    if (items := node.get("array_items")) is not None:
        kwargs["array_items"] = _build_metadata_template(items)

    if (enum_values := node.get("enum_values")) is not None:
        kwargs["enum_values"] = [
            AspectType.MetadataTemplate.EnumValue(name=ev["name"]) for ev in enum_values
        ]

    return AspectType.MetadataTemplate(**kwargs)


def build_aspect_type_proto(yaml_doc: dict[str, Any]) -> AspectType:
    """Build the AspectType proto for the create/update call."""
    return AspectType(
        display_name=yaml_doc.get("display_name", yaml_doc["name"]),
        description=yaml_doc.get("description", ""),
        metadata_template=_build_metadata_template(yaml_doc["metadata_template"]),
    )


# ---------------------------------------------------------------------------
# Data loading (read each JSON file exactly once and cache)
# ---------------------------------------------------------------------------


def load_canonical_data() -> tuple[list[dict], dict[str, dict], list[dict]]:
    """Load the three source JSON files. Each is read exactly once."""
    with (DATA_DIR / "canonical_assets.json").open("r", encoding="utf-8") as f:
        canonical_assets = json.load(f)
    with (DATA_DIR / "cross_system_aliases.json").open("r", encoding="utf-8") as f:
        cross_system_aliases = json.load(f)
    with (DATA_DIR / "functional_equivalences.json").open("r", encoding="utf-8") as f:
        functional_equivalences = json.load(f)
    return canonical_assets, cross_system_aliases, functional_equivalences


def index_equivalences(equivalences: list[dict]) -> dict[str, list[dict]]:
    """Index equivalence pairs by canonical_id from BOTH sides.

    Each row in ``functional_equivalences.json`` describes a symmetric
    relationship between canonical_id_a and canonical_id_b. We unfold it
    into two entries (one per perspective) so a lookup on either id finds
    the relationship without the caller having to know which side was
    listed first.
    """
    indexed: dict[str, list[dict]] = {}
    for eq in equivalences:
        a, b = eq["canonical_id_a"], eq["canonical_id_b"]
        for canonical_id, equivalent_id in ((a, b), (b, a)):
            indexed.setdefault(canonical_id, []).append(
                {
                    "canonical_id": equivalent_id,
                    "confidence": eq["confidence"],
                    "rationale_source": eq["rationale_source"],
                    "customer_overrides": eq.get(
                        "customer_compatibility_overrides", []
                    ),
                }
            )
    return indexed


# ---------------------------------------------------------------------------
# Resource ensure helpers
# ---------------------------------------------------------------------------


def parent_path(project: str, location: str) -> str:
    return f"projects/{project}/locations/{location}"


def aspect_type_name(project: str, location: str, aspect_type_id: str) -> str:
    return f"{parent_path(project, location)}/aspectTypes/{aspect_type_id}"


def ensure_entry_group(
    client: dataplex_v1.CatalogServiceClient,
    project: str,
    location: str,
    stats: RunStats,
) -> str:
    """Create the Entry Group if absent. Return its full resource name."""
    parent = parent_path(project, location)
    name = f"{parent}/entryGroups/{ENTRY_GROUP_ID}"

    # DEMO NARRATION: "Everything canonical about the oilfield business lives
    # under one Entry Group. Centralized governance, one IAM boundary, one
    # place the demo screen can drill into."
    try:
        client.get_entry_group(name=name)
        print(f"  entry_group  unchanged  {ENTRY_GROUP_ID}")
        stats.entry_group_action = "unchanged"
        return name
    except NotFound:
        pass

    proto = EntryGroup(
        display_name="Oilfield Canonical Assets",
        description="Canonical entity model for oilfield service assets",
    )
    try:
        op = client.create_entry_group(
            parent=parent,
            entry_group=proto,
            entry_group_id=ENTRY_GROUP_ID,
        )
        op.result(timeout=120)
        print(f"  entry_group  created    {ENTRY_GROUP_ID}")
        stats.entry_group_action = "created"
    except AlreadyExists:
        print(f"  entry_group  unchanged  {ENTRY_GROUP_ID} (raced)")
        stats.entry_group_action = "unchanged"
    return name


def ensure_aspect_types(
    client: dataplex_v1.CatalogServiceClient,
    project: str,
    location: str,
    stats: RunStats,
) -> list[str]:
    """Create or update each Aspect Type. Return list of full resource names."""
    parent = parent_path(project, location)
    names: list[str] = []
    for filename, aspect_type_id in ASPECT_TYPE_FILES:
        yaml_doc = load_aspect_type_yaml(filename)
        proto = build_aspect_type_proto(yaml_doc)
        name = aspect_type_name(project, location, aspect_type_id)
        proto.name = name

        try:
            existing = client.get_aspect_type(name=name)
        except NotFound:
            existing = None

        if existing is None:
            try:
                op = client.create_aspect_type(
                    parent=parent,
                    aspect_type=proto,
                    aspect_type_id=aspect_type_id,
                )
                op.result(timeout=180)
                print(f"  aspect_type  created    {aspect_type_id}")
                stats.aspect_types_created += 1
            except AlreadyExists:
                # Raced; fall through to update so re-runs converge.
                op = client.update_aspect_type(
                    aspect_type=proto,
                    update_mask={"paths": ["description", "display_name", "metadata_template"]},
                )
                op.result(timeout=180)
                print(f"  aspect_type  updated    {aspect_type_id} (raced)")
                stats.aspect_types_updated += 1
        else:
            # Compare description / display_name / template. If unchanged, skip
            # the API call — keeps re-runs quiet and avoids unnecessary writes.
            unchanged = (
                existing.description == proto.description
                and existing.display_name == proto.display_name
                and existing.metadata_template == proto.metadata_template
            )
            if unchanged:
                print(f"  aspect_type  unchanged  {aspect_type_id}")
                stats.aspect_types_unchanged += 1
            else:
                op = client.update_aspect_type(
                    aspect_type=proto,
                    update_mask={
                        "paths": ["description", "display_name", "metadata_template"]
                    },
                )
                op.result(timeout=180)
                print(f"  aspect_type  updated    {aspect_type_id}")
                stats.aspect_types_updated += 1

        names.append(name)
    return names


def ensure_entry_type(
    client: dataplex_v1.CatalogServiceClient,
    project: str,
    location: str,
    aspect_type_names: list[str],
    stats: RunStats,
) -> str:
    """Create the Entry Type bound to our three Aspect Types."""
    parent = parent_path(project, location)
    name = f"{parent}/entryTypes/{ENTRY_TYPE_ID}"

    required = [EntryType.AspectInfo(type_=atn) for atn in aspect_type_names]
    proto = EntryType(
        display_name="Oilfield Canonical Asset",
        description=(
            "Canonical oilfield asset Entry Type. Every Entry of this type "
            "carries asset_specification, cross_system_aliases, and "
            "functional_equivalence Aspects."
        ),
        required_aspects=required,
    )

    try:
        existing = client.get_entry_type(name=name)
    except NotFound:
        existing = None

    if existing is None:
        try:
            op = client.create_entry_type(
                parent=parent,
                entry_type=proto,
                entry_type_id=ENTRY_TYPE_ID,
            )
            op.result(timeout=180)
            print(f"  entry_type   created    {ENTRY_TYPE_ID}")
            stats.entry_type_action = "created"
        except AlreadyExists:
            proto.name = name
            op = client.update_entry_type(
                entry_type=proto,
                update_mask={
                    "paths": ["description", "display_name", "required_aspects"]
                },
            )
            op.result(timeout=180)
            print(f"  entry_type   updated    {ENTRY_TYPE_ID} (raced)")
            stats.entry_type_action = "updated"
    else:
        proto.name = name
        op = client.update_entry_type(
            entry_type=proto,
            update_mask={"paths": ["description", "display_name", "required_aspects"]},
        )
        op.result(timeout=180)
        print(f"  entry_type   updated    {ENTRY_TYPE_ID}")
        stats.entry_type_action = "updated"

    return name


# ---------------------------------------------------------------------------
# Entry building / upsert
# ---------------------------------------------------------------------------


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop None-valued keys so we don't write empty fields into Aspects."""
    return {k: v for k, v in payload.items() if v is not None}


def build_aspect_specification(asset: dict) -> dict[str, Any]:
    """Build the asset_specification Aspect data dict for one canonical asset."""
    spec = asset.get("specifications", {}) or {}
    return _strip_none(
        {
            "category": asset.get("category"),
            "subcategory": asset.get("subcategory"),
            "operating_temp_max_c": spec.get("operating_temp_max_c"),
            "operating_pressure_max_psi": spec.get("operating_pressure_max_psi"),
            "outer_diameter_in": spec.get("outer_diameter_in"),
            "horsepower": spec.get("horsepower"),
            "max_pressure_psi": spec.get("max_pressure_psi"),
            "manufacturer": asset.get("manufacturer"),
            "introduced_year": asset.get("introduced_year"),
        }
    )


def build_aspect_aliases(aliases_for_asset: dict | None) -> dict[str, Any]:
    """Build the cross_system_aliases Aspect data dict."""
    a = aliases_for_asset or {}
    return _strip_none(
        {
            "sap_material_number": a.get("sap_material_number"),
            "maximo_equipment_id": a.get("maximo_equipment_id"),
            "fdp_config_id": a.get("fdp_config_id"),
            "intouch_spec_refs": a.get("intouch_spec_refs", []) or [],
        }
    )


def build_aspect_equivalence(equivalents: list[dict]) -> dict[str, Any]:
    """Build the functional_equivalence Aspect data dict."""
    return {"equivalent_canonical_ids": equivalents}


def build_entry_proto(
    project: str,
    location: str,
    entry_group: str,
    entry_type: str,
    asset: dict,
    aliases_for_asset: dict | None,
    equivalents: list[dict],
) -> Entry:
    """Build the Entry proto with three Aspects attached."""
    canonical_id = asset["canonical_id"]
    aspect_keys = {
        "spec": f"{aspect_type_name(project, location, 'oilfield-asset-specification')}",
        "alias": f"{aspect_type_name(project, location, 'oilfield-cross-system-aliases')}",
        "equiv": f"{aspect_type_name(project, location, 'oilfield-functional-equivalence')}",
    }

    aspects: dict[str, Aspect] = {
        # Map keys are "<aspect_type_resource_name>" for singleton aspects on an
        # Entry. See dataplex_v1.types.Entry.aspects.
        aspect_keys["spec"]: Aspect(
            aspect_type=aspect_keys["spec"],
            data=build_aspect_specification(asset),
        ),
        aspect_keys["alias"]: Aspect(
            aspect_type=aspect_keys["alias"],
            data=build_aspect_aliases(aliases_for_asset),
        ),
        aspect_keys["equiv"]: Aspect(
            aspect_type=aspect_keys["equiv"],
            data=build_aspect_equivalence(equivalents),
        ),
    }

    entry_name = f"{entry_group}/entries/{canonical_id}"
    return Entry(
        name=entry_name,
        entry_type=entry_type,
        aspects=aspects,
        entry_source=Entry.EntrySource(
            display_name=asset["canonical_label"],
            description=(
                f"Canonical {asset.get('category', 'asset')}: "
                f"{asset['canonical_label']}"
            ),
            resource=canonical_id,
            labels={"category": asset.get("category", "unknown")},
        ),
    )


def upsert_entry(
    client: dataplex_v1.CatalogServiceClient,
    entry_proto: Entry,
    entry_group: str,
    canonical_id: str,
    stats: RunStats,
) -> None:
    """Create or update a single Entry. Updates re-write all three Aspects."""
    aspect_keys = list(entry_proto.aspects.keys())
    update_mask_paths = ["aspects", "entry_source"]

    try:
        client.get_entry(name=entry_proto.name)
        client.update_entry(
            entry=entry_proto,
            update_mask={"paths": update_mask_paths},
            aspect_keys=aspect_keys,
        )
        print(f"    entry  updated  {canonical_id}")
        stats.entries_updated += 1
    except NotFound:
        try:
            client.create_entry(
                parent=entry_group,
                entry=entry_proto,
                entry_id=canonical_id,
            )
            print(f"    entry  created  {canonical_id}")
            stats.entries_created += 1
        except AlreadyExists:
            client.update_entry(
                entry=entry_proto,
                update_mask={"paths": update_mask_paths},
                aspect_keys=aspect_keys,
            )
            print(f"    entry  updated  {canonical_id} (raced)")
            stats.entries_updated += 1


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    stats = RunStats()
    project, location = load_env()
    print(f"Knowledge Catalog setup: project={project} location={location}")
    print("-" * 64)

    client = dataplex_v1.CatalogServiceClient()

    print("Phase 1: Entry Group / Aspect Types / Entry Type")
    entry_group = ensure_entry_group(client, project, location, stats)
    aspect_type_names = ensure_aspect_types(client, project, location, stats)
    entry_type = ensure_entry_type(client, project, location, aspect_type_names, stats)

    print()
    print("Phase 2: Canonical Entries")
    canonical_assets, cross_system_aliases, functional_equivalences = (
        load_canonical_data()
    )
    equivalences_by_id = index_equivalences(functional_equivalences)
    print(f"  loaded {len(canonical_assets)} canonical assets")

    for asset in canonical_assets:
        canonical_id = asset["canonical_id"]
        try:
            entry_proto = build_entry_proto(
                project=project,
                location=location,
                entry_group=entry_group,
                entry_type=entry_type,
                asset=asset,
                aliases_for_asset=cross_system_aliases.get(canonical_id),
                equivalents=equivalences_by_id.get(canonical_id, []),
            )
            upsert_entry(client, entry_proto, entry_group, canonical_id, stats)
        except Exception as exc:  # noqa: BLE001 - surface failures, keep going.
            stats.entries_failed += 1
            print(f"    entry  FAILED   {canonical_id}: {exc}")

    print()
    print("-" * 64)
    print("Summary")
    print(
        f"  entry_group         {stats.entry_group_action}"
    )
    print(
        f"  entry_type          {stats.entry_type_action}"
    )
    print(
        "  aspect_types        "
        f"{stats.aspect_types_created} created, "
        f"{stats.aspect_types_updated} updated, "
        f"{stats.aspect_types_unchanged} unchanged"
    )
    print(
        "  entries             "
        f"{stats.entries_created} created, "
        f"{stats.entries_updated} updated, "
        f"{stats.entries_failed} failed"
    )
    print(f"  runtime             {stats.runtime_s:.1f}s")
    return 0 if stats.entries_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
