"""Generate a ready-to-edit pyHyp volume-extrusion script for a surface mesh.

The generated script follows the pattern of pyHyp's own closed-body
example (pyhyp/examples/sphere/runSphere.py).  Open (unmatched) surface
edges are listed as comments next to the BC dictionary so the user can
assign symmetry/splay/constant-plane conditions by 1-based block index
and iLow/iHigh/jLow/jHigh edge - pyHyp's convention, where our i_min ->
iLow, i_max -> iHigh, j_min -> jLow, j_max -> jHigh.
"""

from __future__ import annotations

from pathlib import Path

from pysurf.blocks import BlockConnection, StructuredBlock
from pysurf.assembly.connectivity import open_edges

_EDGE_TO_PYHYP = {"i_min": "iLow", "i_max": "iHigh", "j_min": "jLow", "j_max": "jHigh"}


def write_pyhyp_script(
    blocks: list[StructuredBlock],
    connections: list[BlockConnection],
    plot3d_file: str,
    path,
) -> Path:
    path = Path(path)
    opens = open_edges(blocks, connections)

    index_lines = [
        f"#   block {idx + 1:>3}: {blk.name}  ({blk.ni} x {blk.nj})"
        for idx, blk in enumerate(blocks)
    ]

    if opens:
        by_name = {blk.name: i + 1 for i, blk in enumerate(blocks)}
        bc_comment_lines = ["# Open edges needing a BC (block index is 1-based):"]
        for name, ename, _ranges in opens:
            bc_comment_lines.append(
                f"#   block {by_name[name]} ({name}): {_EDGE_TO_PYHYP[ename]}"
            )
        bc_value = "{}  # <-- fill from the open-edge list above"
    else:
        bc_comment_lines = ["# Surface is watertight (closed body): no edge BCs needed."]
        bc_value = "{}"

    script = f'''"""pyHyp volume extrusion for the pysurf-generated surface mesh.

Auto-generated template - review N, s0, and marchDist before running.
Run inside an environment where pyHyp is built/installed:

    python {path.name}
"""

from pyhyp import pyHyp

# Block index reference (1-based, matching the Plot3D block order):
{chr(10).join(index_lines)}

{chr(10).join(bc_comment_lines)}

options = {{
    # ---------- input ----------
    "inputFile": "{plot3d_file}",
    "fileType": "PLOT3D",
    "unattachedEdgesAreSymmetry": False,
    "outerFaceBC": "farfield",
    "autoConnect": True,
    "BC": {bc_value},
    "families": "wall",

    # ---------- grid ----------
    "N": 65,               # number of layers to march
    "s0": 1e-4,            # first off-wall spacing (set from your y+ target)
    "marchDist": 10.0,     # total march distance (~10x body length for farfield)

    # ---------- pseudo grid ----------
    "cMax": 5.0,

    # ---------- smoothing ----------
    "epsE": 1.0,
    "epsI": 2.0,
    "theta": 3.0,
    "volCoef": 0.25,
    "volBlend": 0.0001,
    "volSmoothIter": 100,
}}

hyp = pyHyp(options=options)
hyp.run()
hyp.writeCGNS("volume.cgns")
'''
    path.write_text(script, encoding="ascii")
    return path
