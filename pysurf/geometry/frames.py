"""Axis-aligned placement of blocks built in a local +z frame.

Every axisymmetric preset (cylinder, cone, disk, annulus) constructs its
mesh in a local frame whose symmetry axis is +z, then places it into the
global frame with a proper rotation (determinant +1, so surface-normal
consistency and outward orientation are preserved) plus a translation.

``axis`` names the GLOBAL direction of the preset's local +z axis:

    "+z" (default)   identity
    "-z"             flipped upside down
    "+x" / "-x"      axis along the x direction
    "+y" / "-y"      axis along the y direction

Example: a cone with its tip pointing upstream along -x (tip -> base
parallel to +x, y cross-stream) uses axis="-x" - the apex direction
(base -> tip, local +z) maps to global -x.
"""

from __future__ import annotations

import numpy as np

# Proper rotations R (det = +1) with R @ [0,0,1] = named direction.
_ROTATIONS = {
    "+z": np.eye(3),
    "-z": np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]),
    "+x": np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]),
    "-x": np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]),
    "+y": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]),
    "-y": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]),
}


def rotation_for_axis(axis: str) -> np.ndarray:
    try:
        return _ROTATIONS[axis]
    except KeyError:
        raise ValueError(
            f"axis must be one of {sorted(_ROTATIONS)}, got {axis!r}"
        ) from None


def place(xyz: np.ndarray, axis: str = "+z", center=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Rotate a local-frame (ni, nj, 3) array onto ``axis`` and translate.

    ``center`` is the global position of the local origin.
    """
    R = rotation_for_axis(axis)
    return xyz @ R.T + np.asarray(center, dtype=float)
