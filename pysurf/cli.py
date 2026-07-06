"""pysurf command-line interface.

    pysurf mesh <blocking.yaml> [--outdir DIR]     generate mesh + all outputs
    pysurf validate <blocking.yaml>                build in memory and check
    pysurf presets                                 list available presets
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pysurf.assembly.connectivity import (
    connectivity_report,
    find_connections,
    validate_conformity,
)
from pysurf.io.json_writer import write_debug_json
from pysurf.io.plot3d_writer import write_plot3d_surface
from pysurf.io.pyhyp_script import write_pyhyp_script
from pysurf.io.vtk_writer import write_vtm, write_vtp_combined
from pysurf.meshing.quality import block_metrics, quality_report
from pysurf.specs.parser import PRESETS, SpecError, build_from_spec, load_spec

_PRESET_HELP = {
    "cylinder_side": "cylinder lateral surface; periodic i with duplicated seam",
    "cone_side": "frustum lateral surface (both radii > 0)",
    "cone_ogrid": "full cone incl. apex: O-grid top view, center split into 4 quads at the apex (8 blocks)",
    "disk_ogrid": "circular/elliptic disk as O-grid cap (5 blocks; 8 with split_center)",
    "annulus": "planar ring, i circumferential / j radial",
    "plane": "planar parallelogram patch spanned by origin + u, v vectors",
    "sphere_cubed": "full sphere as 6 equiangular cubed-sphere blocks",
}


def _build(spec_path: Path):
    spec = load_spec(spec_path)
    blocks = build_from_spec(spec)
    connections = find_connections(blocks)
    return spec, blocks, connections


def _check(blocks, connections) -> list[str]:
    problems = validate_conformity(blocks, connections)
    for blk in blocks:
        m = block_metrics(blk)
        if m["min_normal_dot"] < 0.0:
            problems.append(
                f"block '{blk.name}' folds over itself (min normal dot {m['min_normal_dot']:.3f})"
            )
        if m["n_degenerate"] > 0:
            problems.append(f"block '{blk.name}' has {m['n_degenerate']} degenerate cell(s)")
    return problems


def cmd_mesh(args) -> int:
    spec_path = Path(args.spec)
    spec, blocks, connections = _build(spec_path)

    out_cfg = spec.get("output", {}) or {}
    project = (spec.get("project", {}) or {}).get("name") or spec_path.stem
    outdir = Path(args.outdir) if args.outdir else spec_path.parent / str(
        out_cfg.get("directory", "output")
    )
    outdir.mkdir(parents=True, exist_ok=True)

    def out_name(key: str, default_name: str, default_on: bool = True):
        val = out_cfg.get(key, default_on)
        if val is False or val is None:
            return None
        return outdir / (val if isinstance(val, str) else default_name)

    written = []

    p = out_name("vtm", f"{project}.vtm")
    if p:
        written.append(write_vtm(blocks, p))
    p = out_name("vtp", f"{project}.vtp", default_on=False)
    if p:
        written.append(write_vtp_combined(blocks, p))
    plot3d_path = out_name("plot3d", f"{project}.fmt")
    if plot3d_path:
        written.append(write_plot3d_surface(blocks, plot3d_path))
    p = out_name("json", f"{project}_blocks.json")
    if p:
        written.append(write_debug_json(blocks, connections, p, meta={"project": project}))
    p = out_name("pyhyp_script", f"run_pyhyp_{project}.py")
    if p and plot3d_path:
        written.append(write_pyhyp_script(blocks, connections, plot3d_path.name, p))

    qtext = quality_report(blocks)
    ctext = connectivity_report(blocks, connections)
    p = out_name("quality_report", f"{project}_quality.txt")
    if p:
        p.write_text(qtext + "\n\n" + ctext + "\n", encoding="utf-8")
        written.append(p)

    print(f"project: {project}")
    print(qtext)
    print()
    print(ctext)

    problems = _check(blocks, connections)
    if problems:
        print("\nPROBLEMS:")
        for msg in problems:
            print(f"  - {msg}")

    print("\nwrote:")
    for path in written:
        print(f"  {path}")
    return 1 if problems else 0


def cmd_validate(args) -> int:
    spec_path = Path(args.spec)
    _, blocks, connections = _build(spec_path)
    print(quality_report(blocks))
    print()
    print(connectivity_report(blocks, connections))
    problems = _check(blocks, connections)
    if problems:
        print("\nPROBLEMS:")
        for msg in problems:
            print(f"  - {msg}")
        return 1
    print("\nspec is valid: blocks conform, no folded or degenerate cells")
    return 0


def cmd_presets(_args) -> int:
    print("available presets:")
    for name in PRESETS:
        print(f"  {name:<15} {_PRESET_HELP.get(name, '')}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pysurf", description="structured surface mesher"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_mesh = sub.add_parser("mesh", help="generate mesh and outputs from a blocking spec")
    p_mesh.add_argument("spec", help="path to blocking.yaml")
    p_mesh.add_argument("--outdir", help="output directory (default: <spec dir>/output)")
    p_mesh.set_defaults(func=cmd_mesh)

    p_val = sub.add_parser("validate", help="build in memory and run all checks")
    p_val.add_argument("spec", help="path to blocking.yaml")
    p_val.set_defaults(func=cmd_validate)

    p_pre = sub.add_parser("presets", help="list available surface presets")
    p_pre.set_defaults(func=cmd_presets)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
