"""Interior-point smoothing for structured surface blocks.

Phase-0 scope: simple Laplacian smoothing with fixed boundaries.  Note
that Laplacian smoothing moves points off curved surfaces (it averages in
3D, not on the surface), so it is intended for planar or gently curved
patches.  CAD-projected smoothing arrives with the Phase 2+ CAD pipeline.
"""

from __future__ import annotations

import numpy as np


def laplacian(xyz: np.ndarray, iterations: int = 20, relaxation: float = 0.5) -> np.ndarray:
    """Laplacian-smooth interior points; boundary points stay fixed.

    ``relaxation`` in (0, 1]: fraction of the move toward the 4-neighbor
    average applied per iteration.
    """
    if not (0.0 < relaxation <= 1.0):
        raise ValueError(f"relaxation must be in (0, 1], got {relaxation}")
    out = np.array(xyz, dtype=float, copy=True)
    for _ in range(iterations):
        avg = 0.25 * (out[:-2, 1:-1] + out[2:, 1:-1] + out[1:-1, :-2] + out[1:-1, 2:])
        out[1:-1, 1:-1] += relaxation * (avg - out[1:-1, 1:-1])
    return out
