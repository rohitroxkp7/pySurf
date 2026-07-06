"""Core structured-block data model.

A :class:`StructuredBlock` is a single logically rectangular surface patch
stored as an ``(ni, nj, 3)`` float array.  The four logical edges are named

    i_min : xyz[0, :]    (runs along increasing j)
    i_max : xyz[-1, :]   (runs along increasing j)
    j_min : xyz[:, 0]    (runs along increasing i)
    j_max : xyz[:, -1]   (runs along increasing i)

The surface normal convention follows the right-hand rule: the normal of a
cell points along  d(P)/di x d(P)/dj.  All preset generators produce blocks
whose normals point outward from the body (required for hyperbolic volume
extrusion with pyHyp, which marches along that normal).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

EDGE_NAMES = ("i_min", "i_max", "j_min", "j_max")


class StructuredBlock:
    """One structured surface patch P[i, j] -> (x, y, z)."""

    def __init__(self, name: str, xyz: np.ndarray):
        xyz = np.asarray(xyz, dtype=float)
        if xyz.ndim != 3 or xyz.shape[2] != 3:
            raise ValueError(
                f"block '{name}': xyz must have shape (ni, nj, 3), got {xyz.shape}"
            )
        if xyz.shape[0] < 2 or xyz.shape[1] < 2:
            raise ValueError(
                f"block '{name}': need at least 2 points in each direction, "
                f"got {xyz.shape[0]} x {xyz.shape[1]}"
            )
        self.name = name
        self.xyz = xyz

    # ------------------------------------------------------------------
    @property
    def ni(self) -> int:
        return self.xyz.shape[0]

    @property
    def nj(self) -> int:
        return self.xyz.shape[1]

    @property
    def n_points(self) -> int:
        return self.ni * self.nj

    @property
    def n_cells(self) -> int:
        return (self.ni - 1) * (self.nj - 1)

    def __repr__(self) -> str:
        return f"StructuredBlock({self.name!r}, {self.ni} x {self.nj})"

    # ------------------------------------------------------------------
    def edge(self, which: str) -> np.ndarray:
        """Ordered (n, 3) points of a logical edge.

        ``i_min``/``i_max`` are ordered by increasing j;
        ``j_min``/``j_max`` are ordered by increasing i.
        """
        if which == "i_min":
            return self.xyz[0, :, :]
        if which == "i_max":
            return self.xyz[-1, :, :]
        if which == "j_min":
            return self.xyz[:, 0, :]
        if which == "j_max":
            return self.xyz[:, -1, :]
        raise KeyError(f"unknown edge '{which}', expected one of {EDGE_NAMES}")

    def edge_length(self, which: str) -> int:
        return self.nj if which in ("i_min", "i_max") else self.ni

    # ------------------------------------------------------------------
    def flipped_i(self, name: str | None = None) -> "StructuredBlock":
        """Copy with the i direction reversed (flips the surface normal)."""
        return StructuredBlock(name or self.name, self.xyz[::-1, :, :].copy())

    def flipped_j(self, name: str | None = None) -> "StructuredBlock":
        """Copy with the j direction reversed (flips the surface normal)."""
        return StructuredBlock(name or self.name, self.xyz[:, ::-1, :].copy())

    def transposed(self, name: str | None = None) -> "StructuredBlock":
        """Copy with i and j swapped (flips the surface normal)."""
        return StructuredBlock(name or self.name, self.xyz.transpose(1, 0, 2).copy())

    # ------------------------------------------------------------------
    def cell_normals(self, normalize: bool = True) -> np.ndarray:
        """Per-cell normals via the cross product of the cell diagonals.

        Shape (ni-1, nj-1, 3).  Direction follows the right-hand rule
        (i cross j).  For planar quads, half the magnitude of the
        unnormalized vector equals the cell area.
        """
        p = self.xyz
        d1 = p[1:, 1:] - p[:-1, :-1]
        d2 = p[:-1, 1:] - p[1:, :-1]
        n = np.cross(d1, d2)
        if normalize:
            mag = np.linalg.norm(n, axis=2, keepdims=True)
            n = np.divide(n, mag, out=np.zeros_like(n), where=mag > 0)
        return n

    def bounding_box(self) -> tuple[np.ndarray, np.ndarray]:
        pts = self.xyz.reshape(-1, 3)
        return pts.min(axis=0), pts.max(axis=0)


def bounding_box(blocks: list[StructuredBlock]) -> tuple[np.ndarray, np.ndarray]:
    los, his = zip(*(b.bounding_box() for b in blocks))
    return np.min(los, axis=0), np.max(his, axis=0)


@dataclass
class BlockConnection:
    """A conformal point-to-point match between two block edges.

    ``range_*`` are inclusive (start, end) point indices along the edge.
    A full-edge match covers (0, n-1); a subrange match happens when a
    short edge (e.g. one 90-degree cap arc) abuts part of a long edge
    (e.g. a full periodic circle).  ``orientation`` is 'same' when both
    edges traverse the shared points in the same order, else 'reversed'.
    """

    block_a: str
    edge_a: str
    range_a: tuple[int, int]
    block_b: str
    edge_b: str
    range_b: tuple[int, int]
    orientation: str
    max_gap: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["range_a"] = list(d["range_a"])
        d["range_b"] = list(d["range_b"])
        return d
