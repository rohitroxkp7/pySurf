"""Dependency-free STEP file scanner.

STEP (ISO 10303-21) files are plain ASCII: entities look like

    #17 = ADVANCED_FACE ( 'bottom_cap', ( #27 ), #8, .F. ) ;

This module parses just enough of the DATA section to answer the Phase 2
questions without pythonOCC:

    - which schema/originating system produced the file (AP203/214/242)
    - length units (mm / inch / m)
    - the faces, their user-assigned NAMES, and their surface types
    - basic entity counts

It is a triage tool: full topology (edge adjacency, trimming, exact
geometry) needs the pythonOCC reader.
"""

from __future__ import annotations

import re
from pathlib import Path

# surface entity types we classify (plan section 7.2)
_SURFACE_TYPES = (
    "PLANE",
    "CYLINDRICAL_SURFACE",
    "CONICAL_SURFACE",
    "SPHERICAL_SURFACE",
    "TOROIDAL_SURFACE",
    "SURFACE_OF_REVOLUTION",
    "SURFACE_OF_LINEAR_EXTRUSION",
    "B_SPLINE_SURFACE",
    "B_SPLINE_SURFACE_WITH_KNOTS",
    "BEZIER_SURFACE",
)

_ENTITY_RE = re.compile(r"#(\d+)\s*=\s*(.+)", re.DOTALL)
_TYPE_RE = re.compile(r"^\(?\s*([A-Z_0-9]+)")
_NAME_RE = re.compile(r"'((?:[^']|'')*)'")
_REF_RE = re.compile(r"#(\d+)")
_FLOAT_RE = re.compile(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|[-+]?\d+\.(?:[eE][-+]?\d+)?")


def _split_statements(text: str) -> list[str]:
    """Split the DATA section into `#id = ...` statements."""
    start = text.find("DATA;")
    end = text.find("ENDSEC;", start if start >= 0 else 0)
    body = text[start + 5 : end] if start >= 0 else text
    return [s.strip() for s in body.split(";") if "#" in s and "=" in s]


def scan_step(path) -> dict:
    """Scan a STEP file; returns a report dict (see keys below)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")

    # ---- header
    schema_m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text)
    schema = schema_m.group(1) if schema_m else "unknown"
    ap = {
        "AUTOMOTIVE_DESIGN": "AP214",
        "CONFIG_CONTROL_DESIGN": "AP203",
    }.get(schema.split()[0], "AP242" if "AP242" in schema else schema)
    system_m = re.search(r"FILE_NAME\s*\((?:[^)]|\n)*?'([^']*SolidWorks[^']*|[^']*)'\s*,\s*'[^']*'\s*\)", text)

    # ---- entities
    entities: dict[int, tuple[str, str]] = {}
    for stmt in _split_statements(text):
        m = _ENTITY_RE.match(stmt)
        if not m:
            continue
        eid = int(m.group(1))
        rest = m.group(2).strip()
        tm = _TYPE_RE.match(rest)
        etype = tm.group(1) if tm else "COMPLEX"
        entities[eid] = (etype, rest)

    def by_type(t: str):
        return [(eid, rest) for eid, (etype, rest) in entities.items() if etype == t]

    # ---- units
    units = "unknown"
    if re.search(r"CONVERSION_BASED_UNIT\s*\(\s*'INCH'", text):
        units = "inch"
    elif re.search(r"SI_UNIT\s*\(\s*\.MILLI\.\s*,\s*\.METRE\.", text):
        units = "mm"
    elif re.search(r"LENGTH_UNIT[^;]*SI_UNIT\s*\(\s*\$\s*,\s*\.METRE\.", text):
        units = "m"

    # ---- faces: name + underlying surface type (+ radius where cheap)
    faces = []
    for eid, rest in by_type("ADVANCED_FACE"):
        name_m = _NAME_RE.search(rest)
        name = name_m.group(1) if name_m else ""
        refs = _REF_RE.findall(rest)
        surf_type, radius = "unknown", None
        # last reference before the orientation flag is the surface
        if refs:
            surf_id = int(refs[-1])
            if surf_id in entities:
                surf_type = entities[surf_id][0]
                if surf_type in ("CYLINDRICAL_SURFACE", "CONICAL_SURFACE", "SPHERICAL_SURFACE"):
                    nums = _FLOAT_RE.findall(entities[surf_id][1])
                    radius = float(nums[-1]) if nums else None
        faces.append({"id": eid, "name": name, "surface": surf_type, "radius": radius})

    counts = {}
    for key in ("ADVANCED_FACE", "EDGE_CURVE", "CIRCLE", "LINE", "VERTEX_POINT") + _SURFACE_TYPES:
        n = sum(1 for etype, _ in entities.values() if etype == key)
        if n:
            counts[key] = n

    named = [f for f in faces if f["name"] and f["name"].upper() not in ("", "NONE")]
    return {
        "file": str(path),
        "schema": schema,
        "ap": ap,
        "units": units,
        "n_entities": len(entities),
        "faces": faces,
        "n_faces": len(faces),
        "n_named_faces": len(named),
        "counts": counts,
    }


def format_report(report: dict) -> str:
    lines = [
        f"file    : {report['file']}",
        f"schema  : {report['schema']}  ({report['ap']})",
        f"units   : {report['units']}",
        f"faces   : {report['n_faces']} total, {report['n_named_faces']} named",
        "",
        f"{'face id':>8}  {'name':<24} {'surface':<28} radius",
        "-" * 74,
    ]
    for f in sorted(report["faces"], key=lambda x: x["id"]):
        rad = f"{f['radius']:.6g}" if f["radius"] is not None else "-"
        name = f["name"] if f["name"] and f["name"].upper() != "NONE" else "(unnamed)"
        lines.append(f"#{f['id']:>7}  {name:<24} {f['surface']:<28} {rad}")
    lines.append("")
    lines.append("entity counts: " + ", ".join(f"{k}={v}" for k, v in sorted(report["counts"].items())))
    if report["ap"] != "AP242":
        lines.append("")
        lines.append(f"NOTE: file is {report['ap']}, not AP242 - names survived here, but "
                     "set Save As -> STEP -> Options -> AP242 for future exports.")
    return "\n".join(lines)
