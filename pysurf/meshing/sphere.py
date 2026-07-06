"""Cubed-sphere preset: a full sphere as six conformal structured blocks.

Uses the equiangular gnomonic mapping: each cube face is parameterized by
angles xi, eta in [-pi/4, pi/4]; a point direction is built from
(tan(xi), tan(eta)) and normalized onto the sphere.  Equiangular spacing
gives near-uniform cells and, importantly, the six faces share identical
edge point sets, so the assembly is conformal by construction.

All six faces are oriented so cell normals point radially outward.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.meshing.edges import distribution


def sphere_cubed(
    radius: float,
    n: int,
    *,
    center=(0.0, 0.0, 0.0),
    name_prefix: str = "sphere",
) -> list[StructuredBlock]:
    """Mesh a full sphere as six n x n blocks (cubed-sphere layout)."""
    if radius <= 0.0:
        raise ValueError(f"radius must be > 0, got {radius}")
    if n < 2:
        raise ValueError(f"need n >= 2 points per face edge, got {n}")

    c = np.asarray(center, dtype=float)
    ang = (distribution(n, "uniform") - 0.5) * (np.pi / 2.0)  # [-pi/4, pi/4]
    ta = np.tan(ang)

    A = ta[:, None]  # varies along i
    B = ta[None, :]  # varies along j
    one = np.ones((n, n))

    # (name, direction components) chosen so i x j points outward.
    faces = {
        "px": (one, A * one, B * one),
        "nx": (-one, -A * one, B * one),
        "py": (-A * one, one, B * one),
        "ny": (A * one, -one, B * one),
        "pz": (A * one, B * one, one),
        "nz": (A * one, -B * one, -one),
    }

    blocks = []
    for tag, (dx, dy, dz) in faces.items():
        d = np.stack([dx, dy, dz], axis=-1)
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        blocks.append(StructuredBlock(f"{name_prefix}_{tag}", c + radius * d))
    return blocks
