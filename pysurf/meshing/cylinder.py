"""Analytic cylinder side patch (periodic quad patch with an explicit seam).

Natural coordinates:

    i = circumferential (theta) direction
    j = axial direction

The seam (theta = theta0) is stored twice: column i=0 and column i=ni-1
hold identical coordinates, so the block is logically non-periodic and the
seam shows up as an ordinary block connection (i_min <-> i_max of the same
block).  This matches how multiblock structured solvers expect periodic
surfaces to be delivered.

Normals point radially outward (i runs counterclockwise when viewed from
+axis, j runs along +axis).
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.geometry.frames import place
from pysurf.meshing.edges import from_spec


def cylinder_side(
    radius: float,
    height: float,
    ni: int,
    nj: int,
    *,
    center=(0.0, 0.0, 0.0),
    axis: str = "+z",
    theta0: float = 0.0,
    i_spacing=None,
    j_spacing=None,
    name: str = "cylinder_side",
) -> StructuredBlock:
    """Structured patch on the side surface of a circular cylinder.

    ``center`` is the global position of the *bottom* circle center;
    ``axis`` is the global direction of the cylinder axis (local +z).
    ``ni`` counts circumferential points including the duplicated seam
    point (so there are ni-1 unique circumferential stations).
    """
    if radius <= 0.0:
        raise ValueError(f"radius must be > 0, got {radius}")
    if height <= 0.0:
        raise ValueError(f"height must be > 0, got {height}")

    s = from_spec(ni, i_spacing)
    t = from_spec(nj, j_spacing)

    theta = theta0 + 2.0 * np.pi * s
    z = height * t

    xyz = np.empty((ni, nj, 3))
    xyz[:, :, 0] = radius * np.cos(theta)[:, None]
    xyz[:, :, 1] = radius * np.sin(theta)[:, None]
    xyz[:, :, 2] = z[None, :]

    # Close the seam exactly (cos/sin roundoff would leave a ~1e-16 gap).
    xyz[-1, :, :] = xyz[0, :, :]
    return StructuredBlock(name, place(xyz, axis, center))
