"""A2UI v0.9 emitter helpers (TASK-45).

A2UI ("Agent to UI") is Google's open declarative-UI protocol for
agent-driven interfaces. Agents emit JSON messages describing component
trees; the client (canvas) renders them via @a2ui/react's <A2UIRenderer>.

We use A2UI for the **non-spatial** canvas surfaces (knowledge-catalog
drawer, cost rollup banner, audit panels). The spatial map (GlobalMap,
AssetMarker, LogisticsArc) stays bespoke — TASK-45 explicitly scopes
the swap to non-spatial UI.

This module exports a thin set of builders for the v0.8 standard catalog:
  surface_update(...)     → surfaceUpdate envelope
  begin_rendering(...)    → beginRendering envelope
  card / row / column / text / divider / button / list / icon / image
  message_batch(...)      → ServerToClientMessage[] ready for processMessages

Output shape matches the v0.8 schema at
node_modules/@a2ui/web_core/src/v0_8/schemas/server_to_client_with_standard_catalog.json
which is what @a2ui/react's default-export <A2UIRenderer> consumes.

Substitution: when an agent (e.g. equivalence_lookup) wants to emit a
KC-drawer surface to the canvas, it calls these builders and writes the
resulting list onto ``ctx.state['a2ui_envelopes']``. The canvas SSE
client (canvas/src/lib/agent-stream.ts) drains those envelopes and
hands them to A2UIProvider.processMessages().
"""

from __future__ import annotations

from typing import Any

V0_8 = "v0.8"
DEFAULT_CATALOG = "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"


# ---------------------------------------------------------------------------
# Envelope builders — v0.8 protocol (what @a2ui/react default-export consumes)
# ---------------------------------------------------------------------------


def surface_update(surface_id: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a ``surfaceUpdate`` envelope.

    ``components`` is the list of typed component nodes (Card/Row/Text/etc.).
    """
    return {
        "surfaceUpdate": {
            "surfaceId": surface_id,
            "components": components,
        },
    }


def begin_rendering(
    surface_id: str, root_id: str, *, catalog_id: str | None = None
) -> dict[str, Any]:
    """Build a ``beginRendering`` envelope.

    A surface is a named tree root; multiple surfaces can coexist
    (one for the KC drawer, one for the cost banner). The root_id
    selects which component to treat as the surface root.
    """
    msg: dict[str, Any] = {
        "beginRendering": {"surfaceId": surface_id, "root": root_id},
    }
    if catalog_id:
        msg["beginRendering"]["catalogId"] = catalog_id
    return msg


def message_batch(
    surface_id: str,
    root_id: str,
    components: list[dict[str, Any]],
    *,
    catalog_id: str | None = None,
) -> list[dict[str, Any]]:
    """The canonical 2-message bundle: surfaceUpdate (populate) + beginRendering.

    ``root_id`` should match the id of one of the supplied components; the
    renderer will treat it as the surface root.
    """
    return [
        surface_update(surface_id, components),
        begin_rendering(surface_id, root_id, catalog_id=catalog_id),
    ]


# ---------------------------------------------------------------------------
# Component builders — v0.9 catalog. Property names match the JSON schema.
# ---------------------------------------------------------------------------


def text(id_: str, value: str, *, variant: str | None = None) -> dict[str, Any]:
    """Display text. v0.8 wraps the literal in a StringValue object."""
    props: dict[str, Any] = {"text": {"literalString": value}}
    if variant:
        props["variant"] = variant
    return {"id": id_, "component": {"Text": props}}


def divider(id_: str, *, axis: str = "horizontal") -> dict[str, Any]:
    return {"id": id_, "component": {"Divider": {"axis": axis}}}


def icon(id_: str, name: str) -> dict[str, Any]:
    """Icon from the catalog's basic icon set."""
    return {"id": id_, "component": {"Icon": {"name": name}}}


def image(id_: str, url: str, *, fit: str = "cover", variant: str = "default") -> dict[str, Any]:
    return {"id": id_, "component": {"Image": {"url": url, "fit": fit, "variant": variant}}}


def card(id_: str, child_id: str) -> dict[str, Any]:
    """Container with elevation/border + padding."""
    return {"id": id_, "component": {"Card": {"child": child_id}}}


def row(
    id_: str, child_ids: list[str], *, distribution: str = "start", alignment: str = "stretch"
) -> dict[str, Any]:
    return {
        "id": id_,
        "component": {
            "Row": {
                "children": {"explicitList": list(child_ids)},
                "distribution": distribution,
                "alignment": alignment,
            }
        },
    }


def column(
    id_: str, child_ids: list[str], *, distribution: str = "start", alignment: str = "stretch"
) -> dict[str, Any]:
    return {
        "id": id_,
        "component": {
            "Column": {
                "children": {"explicitList": list(child_ids)},
                "distribution": distribution,
                "alignment": alignment,
            }
        },
    }


def list_(id_: str, child_ids: list[str], *, direction: str = "vertical") -> dict[str, Any]:
    """Scrollable list of children. Renamed with trailing underscore to avoid
    the Python builtin."""
    return {
        "id": id_,
        "component": {
            "List": {
                "children": {"explicitList": list(child_ids)},
                "direction": direction,
            }
        },
    }


def button(
    id_: str, child_id: str, *, action_name: str, variant: str = "primary"
) -> dict[str, Any]:
    return {
        "id": id_,
        "component": {
            "Button": {
                "child": child_id,
                "variant": variant,
                "action": {"name": action_name},
            }
        },
    }


# ---------------------------------------------------------------------------
# Convenience composites for the cargo-plane scenario
# ---------------------------------------------------------------------------


def kc_drawer(
    canonical_id: str, canonical_label: str, *, aspects: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build the KC drawer surface for an asset.

    Mirrors the structure of canvas/src/components/canvas/KnowledgeCatalogDrawer.tsx
    (which is the bespoke version we're replacing). Produces:
      Card containing a Column of: title + divider + aliases + equivalents + specs

    Returns the ServerToClientMessage list to be passed to
    A2UIProvider.processMessages() on the canvas.
    """
    cs = aspects.get("cross_system_aliases", {}) or {}
    eqs = aspects.get("functional_equivalences", []) or []
    spec = aspects.get("asset_specification", {}) or {}

    comps: list[dict[str, Any]] = [
        text("title", f"{canonical_label}  ({canonical_id})", variant="h2"),
        text("title-eyebrow", "Knowledge Catalog · canonical asset", variant="caption"),
        divider("d1"),
        text("aliases-h", "Cross-system aliases", variant="h3"),
        text("alias-sap", f"SAP MATNR · {cs.get('sap_material_number', '—')}"),
        text("alias-mxm", f"Maximo ITEMNUM · {cs.get('maximo_equipment_id', '—')}"),
        text("alias-fdp", f"FDP CONFIG · {cs.get('fdp_config_id', '—')}"),
        divider("d2"),
        text("eq-h", "Functional equivalents", variant="h3"),
    ]
    eq_ids: list[str] = []
    for i, e in enumerate(eqs[:5]):
        sub = e.get("canonical_id", "?")
        conf = e.get("confidence", 0.0)
        rs = e.get("rationale_source", "")
        comps.append(text(f"eq-{i}", f"→ {sub}  (confidence {conf:.2f})  · {rs}"))
        eq_ids.append(f"eq-{i}")

    comps.append(divider("d3"))
    comps.append(text("spec-h", "Specification", variant="h3"))
    comps.append(text("spec-mfr", f"Manufacturer · {spec.get('manufacturer', '—')}"))
    comps.append(text("spec-yr", f"Introduced · {spec.get('introduced_year', '—')}"))

    # Column wrapping everything, then a Card wrapping the column
    body_children = [c["id"] for c in comps]
    comps.append(column("body", body_children))
    comps.append(card("root", "body"))

    return message_batch("kc-drawer", "root", comps)


def cost_rollup(*, doomed_usd: int, recommended_usd: int, avoided_usd: int) -> list[dict[str, Any]]:
    """Build the cost rollup banner surface."""
    comps = [
        text("doomed-label", "Naive baseline", variant="caption"),
        text("doomed-value", f"${doomed_usd:,}", variant="h2"),
        column("doomed", ["doomed-label", "doomed-value"]),
        text("rec-label", "Agent recommendation", variant="caption"),
        text("rec-value", f"${recommended_usd:,}", variant="h2"),
        column("rec", ["rec-label", "rec-value"]),
        text("avoid-label", "Avoided cost", variant="caption"),
        text("avoid-value", f"${avoided_usd:,}", variant="h2"),
        column("avoid", ["avoid-label", "avoid-value"]),
        row("body", ["doomed", "rec", "avoid"], distribution="spaceBetween", alignment="center"),
        card("root", "body"),
    ]
    return message_batch("cost-rollup", "root", comps)
