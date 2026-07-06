"""Disk O-grid cap: a circular or elliptic disk meshed as conformal blocks.

Topology (avoids the singular polar point at the center)::

        1 center quad block ("diamond", corners on the boundary diagonals)
      + 4 curved quadrilateral blocks between the diamond and the boundary

With ``split_center=True`` the center diamond is instead split into
2 x 2 = 4 sub-quads meeting at the disk center, so the center becomes a
regular mesh vertex shared by exactly 4 cells.  This is required when the
center point is geometrically meaningful - e.g. the apex of a cone (see
:func:`pysurf.meshing.cone.cone_ogrid`), which lifts this same 2-D layout
onto the cone surface.

Quadrant q spans boundary angle [theta0 + q*90deg, theta0 + (q+1)*90deg].
The quadrant boundaries deliberately start AT theta0 (not 45 degrees off)
so that each outer arc is a contiguous index range of an attached
cylinder/cone side edge that also starts at theta0 - this keeps cap<->side
connectivity detectable without wrapping across the side's seam.

Conformity rules when attaching to a side patch with ni_side points:

    ni_side - 1  ==  4 * (n_arc - 1)        (arc intervals add up)
    side i_spacing must be uniform          (arcs are sampled uniformly)

Normals: ``normal='+z'`` orients all blocks with +z normals (use for a
top cap), ``'-z'`` for a bottom cap, so a closed body keeps outward
normals everywhere.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.geometry.frames import place
from pysurf.meshing.edges import distribution, from_spec


def _ogrid_2d(
    n_arc: int,
    n_radial: int,
    a: float,
    b: float,
    theta0: float,
    square_frac: float,
    split_center: bool,
    radial_spacing=None,
) -> list[tuple[str, np.ndarray]]:
    """Build the planar O-grid layout in 2-D, centered on the origin.

    Returns ``(suffix, xy)`` pairs where ``xy`` has shape (ni, nj, 2) and
    every block is oriented so that i cross j points out of the plane
    (+z).  Suffixes: ``center`` (or ``c0..c3`` when split) and ``q0..q3``.
    """
    if n_arc < 2 or n_radial < 2:
        raise ValueError("n_arc and n_radial must each be >= 2")
    if split_center and n_arc % 2 == 0:
        raise ValueError(
            f"split_center requires an odd n_arc (so the diamond side has a "
            f"midpoint grid node), got n_arc={n_arc}"
        )
    if not (0.0 < square_frac < 1.0):
        raise ValueError(f"square_frac must be in (0, 1), got {square_frac}")

    s = distribution(n_arc, "uniform")
    t = from_spec(n_radial, radial_spacing)

    def boundary(theta):
        theta = np.atleast_1d(theta)
        return np.stack([a * np.cos(theta), b * np.sin(theta)], axis=-1)

    corner_theta = theta0 + 0.5 * np.pi * np.arange(4)
    corners = square_frac * boundary(corner_theta)  # (4, 2)

    def bilinear(c00, c10, c11, c01, u, v):
        """Bilinear quad; u along c00->c10, v along c00->c01."""
        uu = u[:, None, None]
        vv = v[None, :, None]
        return (
            (1.0 - uu) * (1.0 - vv) * c00
            + uu * (1.0 - vv) * c10
            + uu * vv * c11
            + (1.0 - uu) * vv * c01
        )

    parts: list[tuple[str, np.ndarray]] = []

    if not split_center:
        # Single diamond: u along C0->C1, v along C0->C3 gives +z.
        parts.append(("center", bilinear(corners[0], corners[1], corners[2], corners[3], s, s)))
    else:
        # 2x2 split: each sub-quad has corners
        #   C_q, mid(C_q,C_{q+1}), origin, mid(C_{q-1},C_q)
        # so the origin (cone apex) is a regular vertex of 4 quads.
        n_half = (n_arc + 1) // 2
        u = distribution(n_half, "uniform")
        origin = np.zeros(2)
        for q in range(4):
            c_q = corners[q]
            mid_next = 0.5 * (corners[q] + corners[(q + 1) % 4])
            mid_prev = 0.5 * (corners[(q - 1) % 4] + corners[q])
            parts.append((f"c{q}", bilinear(c_q, mid_next, origin, mid_prev, u, u)))

    # Quadrants: linear blend between diamond side (inner) and boundary
    # arc (outer).  i counterclockwise along the arc + j radially outward
    # gives -z; flip i afterwards to standardize on +z.
    for q in range(4):
        c_start = corners[q]
        c_end = corners[(q + 1) % 4]
        inner = (1.0 - s)[:, None] * c_start + s[:, None] * c_end
        outer = boundary(theta0 + (q + s) * 0.5 * np.pi)
        quad = (1.0 - t)[None, :, None] * inner[:, None, :] + t[None, :, None] * outer[:, None, :]
        parts.append((f"q{q}", quad[::-1, :, :]))

    return parts


def disk_ogrid(
    n_arc: int,
    n_radial: int,
    *,
    radius: float | None = None,
    semi_axes=None,
    z: float = 0.0,
    center=(0.0, 0.0, 0.0),
    axis: str = "+z",
    theta0: float = 0.0,
    square_frac: float = 0.5,
    normal: str = "+z",
    split_center: bool = False,
    radial_spacing=None,
    name_prefix: str = "cap",
) -> list[StructuredBlock]:
    """Mesh a circular/elliptic disk as an O-grid (5 or 8 conformal blocks).

    Parameters
    ----------
    n_arc : points along each 90-degree boundary arc (the center block is
        n_arc x n_arc, or four (n_arc+1)/2 sub-blocks when split).
    n_radial : points from the center diamond to the boundary.
    radius : circle radius (or pass ``semi_axes=(a, b)`` for an ellipse).
    z : offset of the disk plane along ``axis`` from ``center``
        (convenient for cylinder/cone caps sharing the body's frame).
    axis : global direction of the local +z axis; give a cap the SAME
        axis/center as the side/cone it closes so the circles coincide.
    square_frac : size of the center diamond as a fraction of the radius.
    normal : '+z' or '-z' - cell-normal direction IN THE LOCAL FRAME
        (before the axis rotation).  A cap closing the far end of a body
        uses '+z', the near end (e.g. a cone base) uses '-z'.
    split_center : split the center diamond into 4 sub-quads meeting at
        the disk center (multiple-of-4 center split, minimum 4).
    """
    if semi_axes is not None:
        a, b = (float(v) for v in semi_axes)
    elif radius is not None:
        a = b = float(radius)
    else:
        raise ValueError("disk_ogrid requires either radius or semi_axes")
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"semi-axes must be > 0, got ({a}, {b})")
    if normal not in ("+z", "-z"):
        raise ValueError(f"normal must be '+z' or '-z', got {normal!r}")

    parts = _ogrid_2d(n_arc, n_radial, a, b, theta0, square_frac, split_center, radial_spacing)

    blocks = []
    for suffix, xy in parts:
        xyz = np.empty(xy.shape[:2] + (3,))
        xyz[:, :, :2] = xy
        xyz[:, :, 2] = float(z)
        if normal == "-z":
            xyz = xyz[::-1, :, :]  # flip i: local normal +z -> -z
        blocks.append(StructuredBlock(f"{name_prefix}_{suffix}", place(xyz, axis, center)))
    return blocks
