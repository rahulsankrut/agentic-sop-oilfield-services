"""Seed BigQuery tables from `data/*.json`.

TASK-16 Step 3. Idempotent — every table is loaded with WRITE_TRUNCATE
so re-running clobbers the previous load.

Excludes `data/intouch_docs/` (docs go into KC as catalog entries in Step
12) and `data/start_date_variance/` (the variance is reverse-engineered
into `maximo_extract.WORKORDER` history in a follow-up step).

What this script loads (per spec §3 mapping):

  data/canonical_assets.json (30)
    → oilfield_kc.canonical_assets               (30 rows)
    → sap_extract.MARA                           (30)
    → sap_extract.MAKT                           (30)
    → sap_extract.MARC                           (30) — one plant per material
    → sap_extract.MBEW                           (30)
    → maximo_extract.ITEM                        (30)

  data/cross_system_aliases.json (30)
    → oilfield_kc.cross_system_aliases           (30)

  data/customers.json (7)
    → sap_extract.KNA1                           (7)
    → sap_extract.KNVV                           (7)

  data/sap_workforce.json (7 basins)
    → sap_extract.ZHR_WORKFORCE                  (7, snapshot=today)

  data/maximo_inventory.json (11)
    → maximo_extract.ASSET                       (11)
    → maximo_extract.LOCATIONS                   (deduped, ~8)
    → maximo_extract.INVENTORY                   (deduped on item+loc)
    → maximo_extract.INVBALANCES                 (11)
    → sap_extract.MARD                           (1 per available instance)
    → maximo_extract.WORKORDER                   (1 per instance with open recert)

  data/fdp_configurations.json (nested)
    → fdp_extract.CUSTOMER_CONFIG                (flattened, ~25)
    → fdp_extract.APPROVED_SUBSTITUTIONS         (flattened from v?_substitution_accepted)

  data/functional_equivalences.json (12)
    → oilfield_kc.functional_equivalences        (12)

Verification:
    bq query "SELECT COUNT(*) FROM \\`vertex-ai-demos-468803.sap_extract.MARA\\`"     → 30
    bq query "SELECT COUNT(*) FROM \\`vertex-ai-demos-468803.maximo_extract.ASSET\\`" → 11
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime

UTC = UTC  # Python 3.10 compat (datetime.UTC is 3.11+)
from pathlib import Path
from typing import Any

from google.cloud import bigquery

PROJECT = "vertex-ai-demos-468803"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Region → SAP 4-char plant code (WERKS). Each region maps to one plant for v1.
REGION_TO_WERKS = {
    "west_africa": "WAFR",
    "permian": "USPM",
    "gulf_of_mexico": "USGM",
    "north_sea": "GBNS",
    "bohai": "CNBH",
    "south_china_sea": "CNSC",
    "asia_pacific": "APAC",
}

# Region → Maximo SITEID
REGION_TO_SITEID = {
    "west_africa": "LAGOS",
    "permian": "MIDLAND",
    "gulf_of_mexico": "HOU01",
    "north_sea": "ABDN01",
    "bohai": "TIANJIN",
    "south_china_sea": "SCS01",
    "asia_pacific": "DARWIN",
}

# Region → ISO country code for KNA1.LAND1
REGION_TO_COUNTRY = {
    "west_africa": "NG",
    "permian": "US",
    "gulf_of_mexico": "US",
    "north_sea": "GB",
    "bohai": "CN",
    "south_china_sea": "CN",
    "asia_pacific": "AU",
}


def slug(s: str, maxlen: int = 25) -> str:
    """Lowercase, replace whitespace + punctuation with '-', truncate."""
    out = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip()).strip("-").lower()
    return out[:maxlen]


def lgort_code(label: str) -> str:
    """SAP storage-location code (4 chars). Derived from location label."""
    # Take the first word, uppercase, pad/truncate to 4
    first = re.sub(r"[^a-zA-Z]+", "", label.split(",", maxsplit=1)[0])[:3].upper()
    return (first + "1")[:4]


def mtart_for(category: str) -> str:
    """SAP material type. ROH=raw, FERT=finished, HALB=semi-finished."""
    # OFS tools are finished goods
    return "FERT"


def matkl_for(subcategory: str) -> str:
    """SAP material group — 9 chars max, slug of subcategory."""
    return slug(subcategory, 9).upper()


def stprs_for(category: str, subcategory: str) -> float:
    """Standard price in USD. Synthetic but stratified by category."""
    # Stratified to match §3.6 hint: downhole tools $250k-$1.2M, surface $1.5M-$3M.
    base = {
        "downhole_tool": 850_000,
        "drilling_motor": 950_000,
        "mwd": 450_000,
        "lwd": 520_000,
        "surface_pump": 2_200_000,
        "wireline": 380_000,
        "completion_tool": 620_000,
    }
    # Try subcategory first, then category, then default
    return float(base.get(subcategory, base.get(category, 500_000)))


def kunnr_for(customer_index: int) -> str:
    """SAP customer number padded to 10 chars: '0000100001' style."""
    return f"00001000{customer_index + 1:02d}"


def load_data() -> dict[str, Any]:
    """Load all data/*.json + real-data anchors (data/anchors/*.json)."""
    d: dict[str, Any] = {}
    for name in [
        "canonical_assets",
        "cross_system_aliases",
        "customers",
        "fdp_configurations",
        "functional_equivalences",
        "maximo_inventory",
        "sap_workforce",
    ]:
        path = DATA_DIR / f"{name}.json"
        with path.open() as f:
            d[name] = json.load(f)
        log.info("loaded data/%s.json", name)

    # Real-data anchors (TASK-16 Step 4d — Mode C, "real fields, kept IDs").
    # Each anchor file enriches the synthetic kernel with real public data.
    anchors_dir = DATA_DIR / "anchors"
    d["uspto_patents"] = {}
    uspto_path = anchors_dir / "uspto_patents.json"
    if uspto_path.exists():
        with uspto_path.open() as f:
            d["uspto_patents"] = json.load(f)
        log.info(
            "loaded data/anchors/uspto_patents.json (%d real patents)", len(d["uspto_patents"])
        )
    else:
        log.warning(
            "data/anchors/uspto_patents.json missing — manufacturer/intro_year will fall back to JSON kernel"
        )

    d["sec_edgar"] = {}
    sec_path = anchors_dir / "sec_edgar_customers.json"
    if sec_path.exists():
        with sec_path.open() as f:
            d["sec_edgar"] = json.load(f)
        log.info(
            "loaded data/anchors/sec_edgar_customers.json (%d real customer filings)",
            len(d["sec_edgar"]),
        )
    else:
        log.warning(
            "data/anchors/sec_edgar_customers.json missing — KNA1 address/country will fall back to JSON kernel"
        )

    d["bls_qcew"] = {}
    bls_path = anchors_dir / "bls_qcew_workforce.json"
    if bls_path.exists():
        with bls_path.open() as f:
            d["bls_qcew"] = json.load(f)
        log.info("loaded data/anchors/bls_qcew_workforce.json (%d basins)", len(d["bls_qcew"]))
    else:
        log.warning(
            "data/anchors/bls_qcew_workforce.json missing — ZHR_WORKFORCE will lack BLS data"
        )

    d["bsee_workorders"] = {}
    bsee_path = anchors_dir / "bsee_workorders.json"
    if bsee_path.exists():
        with bsee_path.open() as f:
            d["bsee_workorders"] = json.load(f)
        log.info(
            "loaded data/anchors/bsee_workorders.json (%d WO anchors)", len(d["bsee_workorders"])
        )
    else:
        log.warning("data/anchors/bsee_workorders.json missing — WORKORDER will lack BSEE refs")

    return d


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _shorten_assignee(name: str | None) -> str | None:
    """Trim 'SCHLUMBERGER TECHNOLOGY CORP' → 'SCHLUMBERGER' for the 20-char column.

    The harmonized assignee name from Google Patents BQ often has corporate
    suffixes (CORP, INC, LLC, A GE COMPANY LLC, OILFIELD OPERATIONS) that
    bust our STRING(20) MANUFACTURER column. Map to a known short form when
    we recognize the major; otherwise keep the first 20 chars.
    """
    if not name:
        return None
    upper = name.upper()
    knowns = [
        ("SCHLUMBERGER", "Schlumberger"),
        ("HALLIBURTON", "Halliburton"),
        ("BAKER HUGHES", "Baker Hughes"),
        ("NATIONAL OILWELL", "NOV"),
        ("WEATHERFORD", "Weatherford"),
    ]
    for needle, short in knowns:
        if needle in upper:
            return short
    return name[:20].title()


def build_oilfield_kc_canonical_assets(d: dict[str, Any]) -> list[dict]:
    """Build canonical_assets rows. Mode C: keep canonical_id + canonical_label
    from the JSON kernel (scenario continuity); enrich manufacturer and
    introduced_year from real USPTO patents (data/anchors/uspto_patents.json).
    """
    patents = d.get("uspto_patents", {})
    rows = []
    for a in d["canonical_assets"]:
        spec = a.get("specifications", {})
        anchor = patents.get(a["canonical_id"], {})
        rows.append(
            {
                "CANONICAL_ID": a["canonical_id"],
                "CANONICAL_LABEL": a["canonical_label"],
                "CATEGORY": a["category"],
                "SUBCATEGORY": a.get("subcategory"),
                "OPERATING_TEMP_MAX_C": spec.get("operating_temp_max_c"),
                "OPERATING_PRESSURE_MAX_PSI": spec.get("operating_pressure_max_psi"),
                "OUTER_DIAMETER_IN": spec.get("outer_diameter_in"),
                # REAL from USPTO patent assignee; fall back to JSON kernel if anchor missing.
                "MANUFACTURER": _shorten_assignee(anchor.get("assignee")) or a.get("manufacturer"),
                # REAL from USPTO patent filing_year; fall back to JSON kernel.
                "INTRODUCED_YEAR": anchor.get("filing_year") or a.get("introduced_year"),
            }
        )
    return rows


def build_oilfield_kc_cross_system_aliases(d: dict[str, Any]) -> list[dict]:
    rows = []
    for cid, m in d["cross_system_aliases"].items():
        rows.append(
            {
                "CANONICAL_ID": cid,
                "SAP_MATNR": m.get("sap_material_number"),
                "MAXIMO_ITEMNUM": m.get("maximo_equipment_id"),
                "FDP_CONFIG_ID": m.get("fdp_config_id"),
                "INTOUCH_SPEC_REFS": m.get("intouch_spec_refs", []),
            }
        )
    return rows


def build_oilfield_kc_functional_equivalences(d: dict[str, Any]) -> list[dict]:
    rows = []
    for fe in d["functional_equivalences"]:
        rows.append(
            {
                "CANONICAL_ID_A": fe["canonical_id_a"],
                "CANONICAL_ID_B": fe["canonical_id_b"],
                "CONFIDENCE": fe["confidence"],
                "RATIONALE_SOURCE": fe.get("rationale_source"),
                "CUSTOMER_OVERRIDES": json.dumps(fe.get("customer_compatibility_overrides", [])),
            }
        )
    return rows


def build_sap_mara(d: dict[str, Any]) -> list[dict]:
    aliases = d["cross_system_aliases"]
    rows = []
    for a in d["canonical_assets"]:
        cid = a["canonical_id"]
        matnr = aliases.get(cid, {}).get("sap_material_number")
        if matnr is None:
            continue
        year = a.get("introduced_year") or 2020
        rows.append(
            {
                "MANDT": "100",
                "MATNR": matnr,
                "ERSDA": f"{year}-01-01",
                "ERNAM": "SYSTEM",
                "LAEDA": f"{year}-01-01",
                "AENAM": "SYSTEM",
                "MTART": mtart_for(a["category"]),
                "MBRSH": "M",
                "MATKL": matkl_for(a.get("subcategory", "")),
                "MEINS": "EA",
                "BISMT": None,
                "LVORM": False,
            }
        )
    return rows


def build_sap_makt(d: dict[str, Any]) -> list[dict]:
    """MAKTX — real description from USPTO patent title (truncated to 40);
    falls back to the JSON kernel's canonical_label when no anchor.
    """
    aliases = d["cross_system_aliases"]
    patents = d.get("uspto_patents", {})
    rows = []
    for a in d["canonical_assets"]:
        matnr = aliases.get(a["canonical_id"], {}).get("sap_material_number")
        if matnr is None:
            continue
        anchor = patents.get(a["canonical_id"], {})
        real_title = (anchor.get("title") or "").strip()
        # SAP MAKT.MAKTX is CHAR(40) — truncate; if the patent title is too
        # long for 40, prefix the kernel label for readability.
        maktx = (real_title or a["canonical_label"])[:40]
        rows.append(
            {
                "MANDT": "100",
                "MATNR": matnr,
                "SPRAS": "E",
                "MAKTX": maktx,
            }
        )
    return rows


def build_sap_marc(d: dict[str, Any]) -> list[dict]:
    """One MARC row per (MATNR, WERKS). For v1 each material is at WERKS='PT01'."""
    aliases = d["cross_system_aliases"]
    rows = []
    for a in d["canonical_assets"]:
        matnr = aliases.get(a["canonical_id"], {}).get("sap_material_number")
        if matnr is None:
            continue
        rows.append(
            {
                "MANDT": "100",
                "MATNR": matnr,
                "WERKS": "PT01",
                "DISPO": "001",
                "DISMM": "PD",
                "BESKZ": "F",
                "LVORM": False,
            }
        )
    return rows


def build_sap_mbew(d: dict[str, Any]) -> list[dict]:
    aliases = d["cross_system_aliases"]
    rows = []
    for a in d["canonical_assets"]:
        matnr = aliases.get(a["canonical_id"], {}).get("sap_material_number")
        if matnr is None:
            continue
        rows.append(
            {
                "MANDT": "100",
                "MATNR": matnr,
                "BWKEY": "PT01",
                "VPRSV": "S",
                "STPRS": stprs_for(a["category"], a.get("subcategory", "")),
                "PEINH": 1,
                "WAERS": "USD",
            }
        )
    return rows


def build_sap_mard(d: dict[str, Any]) -> list[dict]:
    """One MARD row per available equipment instance — mirrors Maximo INVBALANCES."""
    aliases = d["cross_system_aliases"]
    rows = []
    for inv in d["maximo_inventory"]:
        cid = inv["canonical_id"]
        matnr = aliases.get(cid, {}).get("sap_material_number")
        if matnr is None:
            continue
        region = inv["location"]["region"]
        werks = REGION_TO_WERKS.get(region, "PT01")
        lgort = lgort_code(inv["location"]["label"])
        # LABST=1 when status indicates the asset is on hand; 0 when in use elsewhere.
        labst = (
            1.0 if inv["status"] in ("available", "available_after_recert", "in_repair") else 0.0
        )
        rows.append(
            {
                "MANDT": "100",
                "MATNR": matnr,
                "WERKS": werks,
                "LGORT": lgort,
                "LABST": labst,
                "INSME": 0.0,
            }
        )
    return rows


def build_sap_kna1(d: dict[str, Any]) -> list[dict]:
    """KNA1 — Mode C: keep NAME1 from JSON kernel (scenario continuity);
    enrich LAND1 + ORT01 + STRAS from real SEC EDGAR filings.
    """
    sec = d.get("sec_edgar", {})
    rows = []
    for i, c in enumerate(d["customers"]):
        anchor = sec.get(c["customer_id"], {})
        primary_region = (c.get("regions") or ["permian"])[0]
        # LAND1: ISO-2 country from curated anchor; fall back to region map.
        land1 = anchor.get("iso_country") or REGION_TO_COUNTRY.get(primary_region, "US")
        # ORT01: real city from SEC filing; fall back to region as Title Case.
        ort01 = (anchor.get("city") or primary_region.replace("_", " ").title())[:35]
        # STRAS: real street from SEC filing; fall back to a generic.
        stras = (anchor.get("street1") or "1 Main St")[:35]
        rows.append(
            {
                "MANDT": "100",
                "KUNNR": kunnr_for(i),
                "NAME1": c["name"][:35],
                "LAND1": land1,
                "ORT01": ort01,
                "STRAS": stras,
            }
        )
    return rows


def build_sap_knvv(d: dict[str, Any]) -> list[dict]:
    rows = []
    for i, _c in enumerate(d["customers"]):
        rows.append(
            {
                "MANDT": "100",
                "KUNNR": kunnr_for(i),
                "VKORG": "OFS1",
                "VTWEG": "10",
                "SPART": "01",
            }
        )
    return rows


def build_sap_zhr_workforce(d: dict[str, Any]) -> list[dict]:
    """ZHR_WORKFORCE — Mode C: keep crew/specialist/on_call values from
    JSON kernel (these are operational counts the agents reason on);
    enrich with real BLS QCEW NAICS 211 state employment context for US
    basins (Permian, GoM). Foreign basins get NULL + a synthesis label.
    """
    bls = d.get("bls_qcew", {})
    today = date.today().isoformat()
    rows = []
    for basin, w in d["sap_workforce"].items():
        anchor = bls.get(basin, {})
        rows.append(
            {
                "BASIN": basin,
                "CREW_COUNT_AVAILABLE": w["crew_count_available"],
                "SPECIALIST_COUNT_AVAILABLE": w["specialist_count_available"],
                "ON_CALL_COUNT": w["on_call_count"],
                "NAICS_211_STATE_EMPLOYMENT": anchor.get("naics_211_state_employment"),
                "DATA_SOURCE": (anchor.get("data_source") or "Synthesized — no anchor")[:80],
                "SNAPSHOT_DATE": today,
            }
        )
    return rows


def build_maximo_item(d: dict[str, Any]) -> list[dict]:
    """Maximo ITEM.DESCRIPTION — real patent title (100 chars); falls
    back to canonical_label."""
    aliases = d["cross_system_aliases"]
    patents = d.get("uspto_patents", {})
    rows = []
    for a in d["canonical_assets"]:
        cid = a["canonical_id"]
        itemnum = aliases.get(cid, {}).get("maximo_equipment_id")
        if itemnum is None:
            continue
        anchor = patents.get(cid, {})
        real_title = (anchor.get("title") or "").strip()
        description = (real_title or a["canonical_label"])[:100]
        rows.append(
            {
                "ITEMNUM": itemnum,
                "ITEMSETID": "SET1",
                "DESCRIPTION": description,
                "COMMODITYGROUP": a["category"][:16],
            }
        )
    return rows


def build_maximo_asset(d: dict[str, Any]) -> list[dict]:
    """One row per maximo_inventory entry — the 11 instances."""
    aliases = d["cross_system_aliases"]
    by_cid = {a["canonical_id"]: a for a in d["canonical_assets"]}
    rows = []
    for i, inv in enumerate(d["maximo_inventory"]):
        cid = inv["canonical_id"]
        itemnum = aliases.get(cid, {}).get("maximo_equipment_id")
        canon = by_cid.get(cid, {})
        region = inv["location"]["region"]
        rows.append(
            {
                "ASSETID": i + 1,
                "ASSETNUM": inv["equipment_instance_id"][:25],
                "DESCRIPTION": canon.get("canonical_label", "")[:100],
                "STATUS": inv["status"][:16],
                "LOCATION": slug(inv["location"]["label"]),
                "SITEID": REGION_TO_SITEID.get(region, "DEFAULT")[:16],
                "ORGID": "OFS",
                "PARENT": None,
                "ASSETTYPE": canon.get("category", "")[:16],
                "ITEMNUM": itemnum,
                "SERIALNUM": f"SN-{i + 1:06d}",
                "INSTALLDATE": (
                    canon.get("introduced_year", 2020) and f"{canon['introduced_year']}-06-15"
                ),
            }
        )
    return rows


def _nearest_wpi_port(client, lat: float, lon: float) -> tuple[int, str] | None:
    """Find the nearest WPI port within 200km of (lat, lon).

    Returns (port_index_number, main_port_name) or None for inland locations
    where no port is within 200km.
    """
    sql = """
    SELECT WORLD_PORT_INDEX_NUMBER, MAIN_PORT_NAME,
           ST_DISTANCE(ST_GEOGPOINT(LONGITUDE, LATITUDE),
                       ST_GEOGPOINT(@lon, @lat)) / 1000.0 AS dist_km
    FROM `vertex-ai-demos-468803.worldport_index.ports`
    WHERE LATITUDE IS NOT NULL AND LONGITUDE IS NOT NULL
    ORDER BY dist_km
    LIMIT 1
    """
    from google.cloud import bigquery as bq  # noqa: PLC0415 — local to avoid top-level dep

    job_config = bq.QueryJobConfig(
        query_parameters=[
            bq.ScalarQueryParameter("lat", "FLOAT64", lat),
            bq.ScalarQueryParameter("lon", "FLOAT64", lon),
        ]
    )
    rows = list(client.query(sql, job_config=job_config).result())
    if not rows or rows[0]["dist_km"] > 200:
        return None
    return int(rows[0]["WORLD_PORT_INDEX_NUMBER"]), str(rows[0]["MAIN_PORT_NAME"])


def build_maximo_locations(d: dict[str, Any]) -> list[dict]:
    """Dedup locations from maximo_inventory. Snap each to nearest real
    WPI port (within 200km) — keeps the facility lat/lon as-is but
    attaches a real port reference for logistics grounding.
    """
    # Lazy: use the module-level client if the caller injected it; else create
    from google.cloud import bigquery as bq  # noqa: PLC0415

    client = bq.Client(project=PROJECT)

    seen: dict[tuple, dict] = {}
    for inv in d["maximo_inventory"]:
        loc = inv["location"]
        region = loc["region"]
        siteid = REGION_TO_SITEID.get(region, "DEFAULT")[:16]
        location = slug(loc["label"])
        key = (siteid, location)
        if key in seen:
            continue
        ltype = (
            "STOREROOM"
            if any(
                w in loc["label"].lower() for w in ("storage", "depot", "shop", "yard", "warehouse")
            )
            else "OPERATING"
        )
        lat, lon = loc.get("latitude"), loc.get("longitude")
        port_num: int | None = None
        port_name: str | None = None
        if lat is not None and lon is not None:
            match = _nearest_wpi_port(client, float(lat), float(lon))
            if match:
                port_num, port_name = match
        seen[key] = {
            "LOCATION": location,
            "SITEID": siteid,
            "ORGID": "OFS",
            "DESCRIPTION": loc["label"][:100],
            "TYPE": ltype,
            "STATUS": "OPERATING",
            "LATITUDE": lat,
            "LONGITUDE": lon,
            "REGION": region[:20],
            "WPI_PORT_INDEX_NUMBER": port_num,
            "WPI_PORT_NAME": (port_name or "")[:80] if port_name else None,
        }
    return list(seen.values())


def build_maximo_inventory(d: dict[str, Any]) -> list[dict]:
    """One row per (ITEMNUM, LOCATION, SITEID)."""
    aliases = d["cross_system_aliases"]
    seen: dict[tuple, dict] = {}
    for inv in d["maximo_inventory"]:
        cid = inv["canonical_id"]
        itemnum = aliases.get(cid, {}).get("maximo_equipment_id")
        if itemnum is None:
            continue
        region = inv["location"]["region"]
        siteid = REGION_TO_SITEID.get(region, "DEFAULT")[:16]
        location = slug(inv["location"]["label"])
        key = (itemnum, "SET1", location, siteid)
        if key in seen:
            continue
        seen[key] = {
            "ITEMNUM": itemnum,
            "ITEMSETID": "SET1",
            "LOCATION": location,
            "SITEID": siteid,
            "STATUS": "ACTIVE",
            "ABCTYPE": "A",
        }
    return list(seen.values())


def build_maximo_invbalances(d: dict[str, Any]) -> list[dict]:
    """One bin balance per maximo_inventory instance."""
    aliases = d["cross_system_aliases"]
    today = date.today().isoformat()
    rows = []
    for i, inv in enumerate(d["maximo_inventory"]):
        cid = inv["canonical_id"]
        itemnum = aliases.get(cid, {}).get("maximo_equipment_id")
        if itemnum is None:
            continue
        region = inv["location"]["region"]
        siteid = REGION_TO_SITEID.get(region, "DEFAULT")[:16]
        location = slug(inv["location"]["label"])
        physcnt = (
            1.0 if inv["status"] in ("available", "available_after_recert", "in_repair") else 0.0
        )
        rows.append(
            {
                "ITEMNUM": itemnum,
                "ITEMSETID": "SET1",
                "LOCATION": location,
                "SITEID": siteid,
                "BINNUM": f"A{(i % 5) + 1}",
                "LOTNUM": None,
                "CONDITIONCODE": "REFURB" if inv["status"] == "available_after_recert" else "NEW",
                "PHYSCNT": physcnt,
                "PHYSCNTDATE": today,
                "CURBAL": physcnt,
            }
        )
    return rows


def build_maximo_workorder(d: dict[str, Any]) -> list[dict]:
    """One open RECERT or REPAIR WO per asset that needs work.

    For assets with status='available_after_recert' or 'in_repair', or
    `certification_hours_remaining > 0`, emit one open WO. ESTLABHRS and
    ACTLABHRS are set so that ESTLABHRS - ACTLABHRS = the certification
    hours remaining (Q5 — customer's extract layer materializes the
    cert_hours_remaining derived field with this arithmetic).

    Each WO is anchored to a real BSEE Incident Investigation (Step 4d.5):
    the BSEE incident's lease number + date + accident type populate
    BSEE_LEASE_REF + BSEE_INCIDENT_DATE + REPORTDATE — so the WO models
    a maintenance response to a real publicly-investigated incident.
    """
    bsee = d.get("bsee_workorders", {})
    rows = []
    for i, inv in enumerate(d["maximo_inventory"]):
        cert_hrs = inv.get("certification_hours_remaining", 0) or 0
        status = inv["status"]
        if cert_hrs <= 0 and status not in ("in_repair", "available_after_recert"):
            continue
        region = inv["location"]["region"]
        siteid = REGION_TO_SITEID.get(region, "DEFAULT")[:16]
        worktype = "REPAIR" if status == "in_repair" else "RECERT"
        est = float(max(cert_hrs * 2, 8.0))
        act = est - float(cert_hrs)

        # Pick a BSEE anchor for this asset. Asset-specific first; fall
        # back to __repair_default__ if no targeted anchor exists.
        anchor = bsee.get(inv["equipment_instance_id"]) or bsee.get("__repair_default__") or {}
        report_date = (anchor.get("incident_date") or now_iso()[:10]) + "T00:00:00+00:00"

        rows.append(
            {
                "WONUM": f"WO-{i + 1:06d}",
                "SITEID": siteid,
                "ASSETNUM": inv["equipment_instance_id"][:25],
                "LOCATION": slug(inv["location"]["label"]),
                "STATUS": "INPRG",
                "WORKTYPE": worktype,
                "REPORTDATE": report_date,
                "SCHEDSTART": None,
                "ACTSTART": None,
                "ESTLABHRS": est,
                "ACTLABHRS": act,
                "BSEE_LEASE_REF": (anchor.get("lease_number") or "")[:16] or None,
                "BSEE_INCIDENT_DATE": anchor.get("incident_date"),
            }
        )
    return rows


def build_fdp_customer_config(d: dict[str, Any]) -> list[dict]:
    """Flatten data/fdp_configurations.json — nested {customer: {canonical_id: {approved, notes}}}."""
    aliases = d["cross_system_aliases"]
    today = date.today().isoformat()
    rows = []
    for customer_id, materials in d["fdp_configurations"].items():
        for canonical_id, cfg in materials.items():
            matnr = aliases.get(canonical_id, {}).get("sap_material_number")
            if matnr is None:
                continue
            rows.append(
                {
                    "CUSTOMER_ID": customer_id,
                    "MATNR": matnr,
                    "APPROVED": cfg.get("approved", False),
                    "NOTES": (cfg.get("notes") or "")[:500],
                    "EFFECTIVE_DATE": today,
                }
            )
    return rows


def build_fdp_approved_substitutions(d: dict[str, Any]) -> list[dict]:
    """Explode `v?_substitution_accepted` booleans into rows.

    Looks up the actual substitute via functional_equivalences: any
    `v<X>_substitution_accepted` key inside an FDP entry implies the
    substitute exists somewhere in functional_equivalences as the OTHER
    side of an equivalence with this canonical_id.
    """
    aliases = d["cross_system_aliases"]

    # Build canonical → functional substitutes index from
    # functional_equivalences. If A↔B with confidence>0, then B is a
    # candidate substitute for A and vice versa.
    subs_by_cid: dict[str, list[str]] = {}
    for fe in d["functional_equivalences"]:
        a, b = fe["canonical_id_a"], fe["canonical_id_b"]
        subs_by_cid.setdefault(a, []).append(b)
        subs_by_cid.setdefault(b, []).append(a)

    rows = []
    for customer_id, materials in d["fdp_configurations"].items():
        for canonical_id, cfg in materials.items():
            # Find any v<X>_substitution_accepted keys
            for k, v in cfg.items():
                if not (k.startswith("v") and k.endswith("_substitution_accepted")):
                    continue
                # The substitute is one of the canonical_id's equivalents.
                # In practice each material in the synthetic data has one obvious sub.
                candidates = subs_by_cid.get(canonical_id, [])
                if not candidates:
                    continue
                sub_canonical = candidates[0]  # 1 row per (customer, material, sub)
                matnr_orig = aliases.get(canonical_id, {}).get("sap_material_number")
                matnr_sub = aliases.get(sub_canonical, {}).get("sap_material_number")
                if matnr_orig is None or matnr_sub is None:
                    continue
                rows.append(
                    {
                        "CUSTOMER_ID": customer_id,
                        "MATNR_ORIGINAL": matnr_orig,
                        "MATNR_SUBSTITUTE": matnr_sub,
                        "ACCEPTED": bool(v),
                    }
                )
    return rows


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

# (table_fqn, builder_fn) pairs. Order matters only for readability.
TABLES: list[tuple[str, str]] = [
    ("oilfield_kc.canonical_assets", "build_oilfield_kc_canonical_assets"),
    ("oilfield_kc.cross_system_aliases", "build_oilfield_kc_cross_system_aliases"),
    ("oilfield_kc.functional_equivalences", "build_oilfield_kc_functional_equivalences"),
    ("sap_extract.MARA", "build_sap_mara"),
    ("sap_extract.MAKT", "build_sap_makt"),
    ("sap_extract.MARC", "build_sap_marc"),
    ("sap_extract.MBEW", "build_sap_mbew"),
    ("sap_extract.MARD", "build_sap_mard"),
    ("sap_extract.KNA1", "build_sap_kna1"),
    ("sap_extract.KNVV", "build_sap_knvv"),
    ("sap_extract.ZHR_WORKFORCE", "build_sap_zhr_workforce"),
    ("maximo_extract.ITEM", "build_maximo_item"),
    ("maximo_extract.ASSET", "build_maximo_asset"),
    ("maximo_extract.LOCATIONS", "build_maximo_locations"),
    ("maximo_extract.INVENTORY", "build_maximo_inventory"),
    ("maximo_extract.INVBALANCES", "build_maximo_invbalances"),
    ("maximo_extract.WORKORDER", "build_maximo_workorder"),
    ("fdp_extract.CUSTOMER_CONFIG", "build_fdp_customer_config"),
    ("fdp_extract.APPROVED_SUBSTITUTIONS", "build_fdp_approved_substitutions"),
]


def load_to_bq(client: bigquery.Client, table_fqn: str, rows: list[dict]) -> int:
    """Load `rows` into `<project>.<table_fqn>` with WRITE_TRUNCATE.

    Fetches the destination table's schema and passes it explicitly to the
    load job. Without this, BigQuery's load-from-NDJSON path infers schema
    from the JSON values — "001" becomes INTEGER 1, "F" becomes BOOLEAN
    false, and the carefully-defined DDL types from Step 2 are silently
    replaced. Passing `schema=` locks the load to the DDL contract.
    """
    full = f"{PROJECT}.{table_fqn}"
    table = client.get_table(full)
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        schema=table.schema,
        autodetect=False,
    )
    job = client.load_table_from_json(rows, full, job_config=job_config)
    job.result()  # block until complete
    return job.output_rows or 0


def main() -> None:
    data = load_data()
    builders = globals()
    client = bigquery.Client(project=PROJECT)

    for table_fqn, builder_name in TABLES:
        rows = builders[builder_name](data)
        n = load_to_bq(client, table_fqn, rows)
        log.info("loaded %s: %d rows", table_fqn, n)


if __name__ == "__main__":
    main()
