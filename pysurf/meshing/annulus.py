"""Analytic annulus (ring) patch.

Natural coordinates:

    i = circumferential direction (seam duplicated, like the cylinder side)
    j = radial direction, inner -> outer

``normal='+z'`` or ``'-z'`` selects the cell-normal direction.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.geometry.frames import place
from pysurf.meshing.edges import from_spec


def annulus(
    radius_inner: float,
    radius_outer: float,
    ni: int,
    nj: int,
    *,
    z: float = 0.0,
    center=(0.0, 0.0, 0.0),
    axis: str = "+z",
    theta0: float = 0.0,
    normal: str = "+z",
    i_spacing=None,
    j_spacing=None,
    name: str = "annulus",
) -> StructuredBlock:
    """Structured patch on a planar annulus normal to ``axis``.

    ``normal`` is in the local frame (before the axis rotation), like
    disk_ogrid.
    """
    if not (0.0 < radius_inner < radius_outer):
        raise ValueError(
            f"need 0 < radius_inner < radius_outer, got {radius_inner}, {radius_outer}"
        )
    if normal not in ("+z", "-z"):
        raise ValueError(f"normal must be '+z' or '-z', got {normal!r}")

    s = from_spec(ni, i_spacing)
    t = from_spec(nj, j_spacing)

    theta = theta0 + 2.0 * np.pi * s
    r = radius_inner + (radius_outer - radius_inner) * t

    xyz = np.empty((ni, nj, 3))
    xyz[:, :, 0] = r[None, :] * np.cos(theta)[:, None]
    xyz[:, :, 1] = r[None, :] * np.sin(theta)[:, None]
    xyz[:, :, 2] = float(z)

    xyz[-1, :, :] = xyz[0, :, :]

    # i counterclockwise + j radially outward gives a -z normal; flip i
    # to standardize on local +z.
    if normal == "+z":
        xyz = xyz[::-1, :, :]
    return StructuredBlock(name, place(xyz, axis, center))
