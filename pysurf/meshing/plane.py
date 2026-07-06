"""Analytic planar four-sided patch (rectangle / parallelogram).

The patch is spanned by two edge vectors from an origin point:

    P(s, t) = origin + s * u + t * v

so it works in any plane and any orientation.  The cell normals point
along u x v.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.meshing.edges import from_spec


def plane_patch(
    origin,
    u,
    v,
    ni: int,
    nj: int,
    *,
    i_spacing=None,
    j_spacing=None,
    name: str = "plate",
) -> StructuredBlock:
    """Structured patch on a parallelogram spanned by vectors u and v."""
    origin = np.asarray(origin, dtype=float)
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    if origin.shape != (3,) or u.shape != (3,) or v.shape != (3,):
        raise ValueError("origin, u, v must each be 3-vectors")
    if np.linalg.norm(np.cross(u, v)) <= 0.0:
        raise ValueError("u and v must not be parallel (degenerate patch)")

    s = from_spec(ni, i_spacing)
    t = from_spec(nj, j_spacing)

    xyz = origin + s[:, None, None] * u + t[None, :, None] * v
    return StructuredBlock(name, xyz)
