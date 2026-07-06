"""Plot3D multiblock surface writer, matched to pyHyp's reader.

pyHyp's Fortran reader (pyhyp/src/3D/readPlot3d.F90) expects:

    - ASCII ("formatted") file; list-directed reads, so only token order
      matters, not line breaks
    - first token: number of blocks
    - then 3 integers per block:  ni  nj  nk   with nk EXACTLY 1
    - then, per block: all X values, then all Y, then all Z,
      with i the fastest index, then j

This writer produces exactly that layout.  A tiny reader is included for
round-trip testing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pysurf.blocks import StructuredBlock


def write_plot3d_surface(blocks: list[StructuredBlock], path) -> Path:
    """Write blocks as an ASCII multiblock Plot3D surface (nk = 1)."""
    path = Path(path)
    lines = [f"{len(blocks)}"]
    for blk in blocks:
        lines.append(f"{blk.ni} {blk.nj} 1")
    for blk in blocks:
        for dim in range(3):
            # order='F' flattens (ni, nj) with i fastest, matching the
            # reader's loops: idim outer, j middle, i inner.
            vals = blk.xyz[:, :, dim].ravel(order="F")
            for start in range(0, len(vals), 5):
                lines.append(" ".join(f"{v:.16g}" for v in vals[start : start + 5]))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def read_plot3d_surface(path) -> list[np.ndarray]:
    """Minimal reader mirroring pyHyp's parsing; for round-trip tests.

    Returns a list of (ni, nj, 3) arrays.
    """
    tokens = Path(path).read_text(encoding="ascii").split()
    pos = 0

    def take(n):
        nonlocal pos
        out = tokens[pos : pos + n]
        if len(out) != n:
            raise ValueError("unexpected end of Plot3D file")
        pos += n
        return out

    n_blocks = int(take(1)[0])
    dims = []
    for _ in range(n_blocks):
        ni, nj, nk = (int(v) for v in take(3))
        if nk != 1:
            raise ValueError(f"k-dimension must be 1, got {nk}")
        dims.append((ni, nj))

    blocks = []
    for ni, nj in dims:
        xyz = np.empty((ni, nj, 3))
        for dim in range(3):
            vals = np.array([float(v) for v in take(ni * nj)])
            xyz[:, :, dim] = vals.reshape((ni, nj), order="F")
        blocks.append(xyz)
    return blocks
