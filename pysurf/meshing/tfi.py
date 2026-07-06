"""Transfinite interpolation (TFI) for four-sided patches.

The workhorse generator for structured quadrilateral patches: given four
boundary curves with matching corners, fill the interior with the standard
linear Coons patch

    P(s,t) =   (1-t) B(s) + t T(s)          (blend bottom/top)
             + (1-s) L(t) + s R(t)          (blend left/right)
             - bilinear corner correction
"""

from __future__ import annotations

import numpy as np


def _chord_param(curve: np.ndarray) -> np.ndarray:
    """Normalized chord-length parameterization of an ordered point set."""
    seg = np.linalg.norm(np.diff(curve, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    if arc[-1] <= 0.0:
        raise ValueError("degenerate boundary curve: zero total length")
    return arc / arc[-1]


def tfi(
    bottom: np.ndarray,
    top: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    s: np.ndarray | None = None,
    t: np.ndarray | None = None,
    corner_tol: float | None = None,
) -> np.ndarray:
    """Fill a four-sided patch with transfinite interpolation.

    Boundary layout (i is the first array index, j the second)::

            top    = j_max edge, (ni, 3), ordered by increasing i
            bottom = j_min edge, (ni, 3), ordered by increasing i
            left   = i_min edge, (nj, 3), ordered by increasing j
            right  = i_max edge, (nj, 3), ordered by increasing j

    Corners must match: bottom[0] == left[0], bottom[-1] == right[0],
    top[0] == left[-1], top[-1] == right[-1].

    ``s``/``t`` are optional interior blending parameters on [0, 1]; by
    default the averaged normalized chord length of the opposing boundary
    pair is used, which propagates boundary clustering into the interior.

    Returns the filled patch, shape (ni, nj, 3), with the boundary curves
    reproduced exactly.
    """
    bottom = np.asarray(bottom, dtype=float)
    top = np.asarray(top, dtype=float)
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)

    ni = bottom.shape[0]
    nj = left.shape[0]
    if top.shape[0] != ni:
        raise ValueError(f"top has {top.shape[0]} points but bottom has {ni}")
    if right.shape[0] != nj:
        raise ValueError(f"right has {right.shape[0]} points but left has {nj}")

    # Corner consistency check, scaled by patch size.
    corners = [
        (bottom[0], left[0], "bottom[0] vs left[0]"),
        (bottom[-1], right[0], "bottom[-1] vs right[0]"),
        (top[0], left[-1], "top[0] vs left[-1]"),
        (top[-1], right[-1], "top[-1] vs right[-1]"),
    ]
    pts = np.vstack([bottom, top, left, right])
    scale = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
    tol = corner_tol if corner_tol is not None else 1.0e-8 * max(scale, 1.0)
    for a, b, label in corners:
        gap = float(np.linalg.norm(a - b))
        if gap > tol:
            raise ValueError(f"TFI corner mismatch ({label}): gap={gap:g} > tol={tol:g}")

    if s is None:
        s = 0.5 * (_chord_param(bottom) + _chord_param(top))
    if t is None:
        t = 0.5 * (_chord_param(left) + _chord_param(right))
    s = np.asarray(s, dtype=float)
    t = np.asarray(t, dtype=float)

    p00 = 0.5 * (bottom[0] + left[0])
    p10 = 0.5 * (bottom[-1] + right[0])
    p01 = 0.5 * (top[0] + left[-1])
    p11 = 0.5 * (top[-1] + right[-1])

    si = s[:, None, None]        # (ni, 1, 1)
    tj = t[None, :, None]        # (1, nj, 1)

    u = (1.0 - tj) * bottom[:, None, :] + tj * top[:, None, :]
    v = (1.0 - si) * left[None, :, :] + si * right[None, :, :]
    uv = (
        (1.0 - si) * (1.0 - tj) * p00
        + si * (1.0 - tj) * p10
        + (1.0 - si) * tj * p01
        + si * tj * p11
    )
    xyz = u + v - uv

    # Reimpose the exact boundary curves (guards against roundoff drift).
    xyz[:, 0, :] = bottom
    xyz[:, -1, :] = top
    xyz[0, :, :] = left
    xyz[-1, :, :] = right
    return xyz
