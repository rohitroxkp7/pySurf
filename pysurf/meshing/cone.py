"""Analytic cone patches.

Two presets live here:

``cone_side``
    Frustum lateral surface (both radii > 0), meshed like the cylinder
    side: i circumferential with duplicated seam, j axial, outward
    normals.  A sharp apex is rejected because it would collapse an
    entire block edge to a point.

``cone_ogrid``
    Full cone lateral surface INCLUDING the apex, meshed the right way:
    viewed along the axis the cone is a disk O-grid whose center square
    is split into 4 sub-squares whose single common vertex is the apex
    (the cone axis passes through it).  Every mesh point of the top-view
    layout is lifted onto the cone by  z = h * (1 - rho/R),  so the apex
    is a regular corner vertex shared by 4 quads instead of a degenerate
    collapsed edge - a topology hyperbolic extruders such as pyHyp
    accept as an ordinary internal node.

    8 blocks: 4 center sub-quads + 4 outer quadrants.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.geometry.frames import place
from pysurf.meshing.edges import from_spec
from pysurf.meshing.disk_ogrid import _ogrid_2d


def cone_side(
    radius_bottom: float,
    radius_top: float,
    height: float,
    ni: int,
    nj: int,
    *,
    center=(0.0, 0.0, 0.0),
    axis: str = "+z",
    theta0: float = 0.0,
    i_spacing=None,
    j_spacing=None,
    name: str = "cone_side",
) -> StructuredBlock:
    """Structured patch on the side surface of a conical frustum.

    ``center`` is the global position of the bottom circle center;
    ``axis`` is the global direction of the frustum axis (local +z).
    """
    if radius_bottom <= 0.0 or radius_top <= 0.0:
        raise ValueError(
            f"frustum radii must be > 0 (got bottom={radius_bottom}, top={radius_top}); "
            "for a sharp apex use the cone_ogrid preset, which resolves the apex "
            "as a regular vertex of 4 quads"
        )
    if height <= 0.0:
        raise ValueError(f"height must be > 0, got {height}")

    s = from_spec(ni, i_spacing)
    t = from_spec(nj, j_spacing)

    theta = theta0 + 2.0 * np.pi * s
    r = radius_bottom + (radius_top - radius_bottom) * t
    z = height * t

    xyz = np.empty((ni, nj, 3))
    xyz[:, :, 0] = r[None, :] * np.cos(theta)[:, None]
    xyz[:, :, 1] = r[None, :] * np.sin(theta)[:, None]
    xyz[:, :, 2] = z[None, :]

    xyz[-1, :, :] = xyz[0, :, :]
    return StructuredBlock(name, place(xyz, axis, center))


def cone_ogrid(
    n_arc: int,
    n_radial: int,
    *,
    height: float,
    radius: float | None = None,
    semi_axes=None,
    center=(0.0, 0.0, 0.0),
    axis: str = "+z",
    theta0: float = 0.0,
    square_frac: float = 0.5,
    radial_spacing=None,
    name_prefix: str = "cone",
) -> list[StructuredBlock]:
    """Full cone lateral surface with the apex resolved as an O-grid.

    Parameters
    ----------
    n_arc : points along each 90-degree base arc; must be ODD so the
        center split lands on grid nodes.  To attach a side/cap with
        ni_side points along the full base circle: ni_side - 1 == 4*(n_arc - 1).
    n_radial : points from the center diamond out to the base circle.
    height : apex sits at distance ``height`` from the base center along
        ``axis``; the base circle lies in the plane through ``center``
        normal to ``axis``.  The base must be closed by a separate cap
        (disk_ogrid with the same axis/center and normal='-z') for a
        watertight body.
    radius / semi_axes : base circle radius, or (a, b) for an elliptic cone.
    axis : global direction of the base->apex axis (local +z), e.g. '-x'
        for a tip pointing upstream with the body extending along +x.

    Normals point outward, matching a closed body with a base cap of
    (local) normal '-z'.

    Returns 8 blocks: ``{prefix}_c0..c3`` (apex sub-quads) and
    ``{prefix}_q0..q3`` (outer quadrants).
    """
    if semi_axes is not None:
        a, b = (float(v) for v in semi_axes)
    elif radius is not None:
        a = b = float(radius)
    else:
        raise ValueError("cone_ogrid requires either radius or semi_axes")
    if a <= 0.0 or b <= 0.0:
        raise ValueError(f"semi-axes must be > 0, got ({a}, {b})")
    if height <= 0.0:
        raise ValueError(f"height must be > 0, got {height}")

    parts = _ogrid_2d(
        n_arc, n_radial, a, b, theta0, square_frac,
        split_center=True, radial_spacing=radial_spacing,
    )

    blocks = []
    for suffix, xy in parts:
        # Relative radial position on the (possibly elliptic) disk:
        # 1.0 on the base circle, 0.0 at the apex.
        rho = np.sqrt((xy[:, :, 0] / a) ** 2 + (xy[:, :, 1] / b) ** 2)
        rho = np.clip(rho, 0.0, 1.0)
        xyz = np.empty(xy.shape[:2] + (3,))
        xyz[:, :, 0] = xy[:, :, 0]
        xyz[:, :, 1] = xy[:, :, 1]
        xyz[:, :, 2] = height * (1.0 - rho)
        blocks.append(StructuredBlock(f"{name_prefix}_{suffix}", place(xyz, axis, center)))
    return blocks
