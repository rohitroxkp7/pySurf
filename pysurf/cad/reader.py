"""STEP reader built on pythonOCC (conda: pythonocc-core).

Recovers what the Phase 2 pipeline needs from a STEP file:

    - every face with its user-assigned NAME (SolidWorks Face Properties
      names ride on the STEP ADVANCED_FACE entities and are recovered via
      the transfer-reader entity <-> shape mapping)
    - surface classification per face (plan section 7.2)
    - unique edges, their curve types and lengths
    - edge -> adjacent-faces mapping (so "the top circle" can be
      identified as the edge shared by cylinder_side and top_cap without
      any edge naming in CAD)

Everything is reported in mm (OpenCASCADE converts units on read).
"""

from __future__ import annotations

from pathlib import Path

from OCC.Core.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCC.Core.GeomAbs import (
    GeomAbs_BezierSurface,
    GeomAbs_BSplineCurve,
    GeomAbs_BSplineSurface,
    GeomAbs_Circle,
    GeomAbs_Cone,
    GeomAbs_Cylinder,
    GeomAbs_Ellipse,
    GeomAbs_Line,
    GeomAbs_Plane,
    GeomAbs_Sphere,
    GeomAbs_SurfaceOfExtrusion,
    GeomAbs_SurfaceOfRevolution,
    GeomAbs_Torus,
)
from OCC.Core.GProp import GProp_GProps
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.StepRepr import StepRepr_RepresentationItem
from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopTools import (
    TopTools_IndexedDataMapOfShapeListOfShape,
    TopTools_IndexedMapOfShape,
)
from OCC.Core.TopoDS import topods

try:  # static-method wrappers moved between pythonocc versions
    from OCC.Core.TopExp import topexp as _topexp
except ImportError:  # pragma: no cover
    from OCC.Core.TopExp import TopExp as _topexp

try:
    from OCC.Core.BRepGProp import brepgprop as _brepgprop
except ImportError:  # pragma: no cover
    from OCC.Core import BRepGProp as _brepgprop


_SURFACE_NAMES = {
    GeomAbs_Plane: "plane",
    GeomAbs_Cylinder: "cylinder",
    GeomAbs_Cone: "cone",
    GeomAbs_Sphere: "sphere",
    GeomAbs_Torus: "torus",
    GeomAbs_BezierSurface: "bezier",
    GeomAbs_BSplineSurface: "bspline",
    GeomAbs_SurfaceOfRevolution: "surface_of_revolution",
    GeomAbs_SurfaceOfExtrusion: "surface_of_extrusion",
}

_CURVE_NAMES = {
    GeomAbs_Line: "line",
    GeomAbs_Circle: "circle",
    GeomAbs_Ellipse: "ellipse",
    GeomAbs_BSplineCurve: "bspline",
}


def _count(shape, kind) -> int:
    exp = TopExp_Explorer(shape, kind)
    n = 0
    while exp.More():
        n += 1
        exp.Next()
    return n


def _entity_name(transfer_reader, shape) -> str:
    """Recover the STEP entity name attached to a transferred shape."""
    item = transfer_reader.EntityFromShapeResult(shape, 1)
    if item is None:
        return ""
    rep = StepRepr_RepresentationItem.DownCast(item)
    if rep is None or rep.Name() is None:
        return ""
    name = rep.Name().ToCString()
    return "" if name.upper() == "NONE" else name


def _surface_info(face) -> tuple[str, dict]:
    ga = BRepAdaptor_Surface(face)
    stype = _SURFACE_NAMES.get(ga.GetType(), "unknown")
    params: dict = {}
    if stype == "cylinder":
        cyl = ga.Cylinder()
        params["radius"] = cyl.Radius()
        ax = cyl.Axis().Direction()
        params["axis"] = (ax.X(), ax.Y(), ax.Z())
    elif stype == "cone":
        cone = ga.Cone()
        params["semi_angle_deg"] = abs(cone.SemiAngle()) * 57.29577951308232
        params["ref_radius"] = cone.RefRadius()
        ax = cone.Axis().Direction()
        params["axis"] = (ax.X(), ax.Y(), ax.Z())
    elif stype == "sphere":
        params["radius"] = ga.Sphere().Radius()
    elif stype == "plane":
        n = ga.Plane().Axis().Direction()
        params["normal"] = (n.X(), n.Y(), n.Z())
    return stype, params


def _edge_length(edge) -> float:
    props = GProp_GProps()
    _brepgprop.LinearProperties(edge, props)
    return props.Mass()


def read_step(path) -> dict:
    """Read a STEP file; return the face/edge/adjacency model as dicts."""
    path = Path(path)
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise IOError(f"failed to read STEP file: {path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    tr = reader.WS().TransferReader()

    # unique edge map + edge -> faces adjacency
    edge_map = TopTools_IndexedMapOfShape()
    _topexp.MapShapes(shape, TopAbs_EDGE, edge_map)
    adjacency = TopTools_IndexedDataMapOfShapeListOfShape()
    _topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, adjacency)

    faces = []
    face_index_of = {}
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    idx = 0
    while exp.More():
        face = topods.Face(exp.Current())
        stype, params = _surface_info(face)
        edge_ids = []
        eexp = TopExp_Explorer(face, TopAbs_EDGE)
        while eexp.More():
            edge_ids.append(edge_map.FindIndex(eexp.Current()))
            eexp.Next()
        faces.append(
            {
                "index": idx,
                "name": _entity_name(tr, face),
                "surface": stype,
                "params": params,
                "edges": sorted(set(edge_ids)),
            }
        )
        face_index_of[idx] = face
        idx += 1
        exp.Next()

    # name lookup for adjacency reporting
    def face_label(i):
        f = faces[i]
        return f["name"] or f"face{f['index']}"

    edges = []
    for eid in range(1, edge_map.Size() + 1):
        edge = topods.Edge(edge_map.FindKey(eid))
        ca = BRepAdaptor_Curve(edge)
        owners = [f["index"] for f in faces if eid in f["edges"]]
        edges.append(
            {
                "index": eid,
                "curve": _CURVE_NAMES.get(ca.GetType(), "other"),
                "length_mm": _edge_length(edge),
                "faces": [face_label(i) for i in owners],
            }
        )

    return {
        "file": str(path),
        "n_solids": _count(shape, TopAbs_SOLID),
        "n_shells": _count(shape, TopAbs_SHELL),
        "faces": faces,
        "edges": edges,
    }


def inspect_cad(path) -> str:
    """Human-readable full-topology report of a STEP file."""
    m = read_step(path)
    lines = [
        f"file   : {m['file']}",
        f"bodies : {m['n_solids']} solid(s), {m['n_shells']} shell(s)   "
        "(all lengths in mm)",
        "",
        f"{'idx':>4}  {'face name':<22} {'surface':<12} {'edges':<14} params",
        "-" * 78,
    ]
    for f in m["faces"]:
        name = f["name"] or "(unnamed)"
        ptxt = ", ".join(
            f"{k}={tuple(round(x, 4) for x in v) if isinstance(v, tuple) else round(v, 4)}"
            for k, v in f["params"].items()
        )
        etxt = ",".join(str(e) for e in f["edges"])
        lines.append(f"{f['index']:>4}  {name:<22} {f['surface']:<12} {etxt:<14} {ptxt}")

    lines += [
        "",
        f"{'edge':>4}  {'curve':<9} {'length':>10}  shared by faces",
        "-" * 60,
    ]
    for e in m["edges"]:
        shared = "  <->  ".join(e["faces"]) if len(e["faces"]) > 1 else f"{e['faces'][0]} (boundary!)"
        lines.append(f"{e['index']:>4}  {e['curve']:<9} {e['length_mm']:>10.4g}  {shared}")

    unnamed = [f for f in m["faces"] if not f["name"]]
    if unnamed:
        lines += ["", f"WARNING: {len(unnamed)} unnamed face(s) - name them in CAD or map by index"]
    return "\n".join(lines)
