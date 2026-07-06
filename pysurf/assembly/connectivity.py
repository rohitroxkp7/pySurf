"""Block-to-block connectivity detection and conformity validation.

Connectivity is discovered geometrically: two block edges (or an edge and
a contiguous subrange of a longer edge) are connected when their points
coincide within tolerance, either in the same order or reversed.

Subrange matching matters for topologies like the cylinder: the side
patch's top edge is one full 129-point circle, while each O-grid cap arc
covers only a quarter of it (33 points).  Each arc then matches indices
[0..32], [32..64], [64..96], [96..128] of the side edge.

A periodic seam appears naturally as a self-connection: the cylinder
side's i_min and i_max edges hold identical coordinates, so they match as
an ordinary connection between two edges of the same block.
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import EDGE_NAMES, BlockConnection, StructuredBlock, bounding_box


def _default_tol(blocks: list[StructuredBlock]) -> float:
    lo, hi = bounding_box(blocks)
    diag = float(np.linalg.norm(hi - lo))
    return max(1.0e-9 * diag, 1.0e-12)


def _match_window(a: np.ndarray, b: np.ndarray, tol: float) -> float | None:
    """Max pointwise gap if a matches b elementwise within tol, else None."""
    gaps = np.linalg.norm(a - b, axis=1)
    mx = float(gaps.max())
    return mx if mx <= tol else None


def _find_edge_matches(a: np.ndarray, b: np.ndarray, tol: float):
    """All matches of (short) edge ``a`` against contiguous windows of ``b``.

    Yields tuples (range_a, range_b, orientation, max_gap) with inclusive
    point-index ranges.  range_b is given in traversal order: for a
    'reversed' match range_b[0] > range_b[1], meaning a[0] pairs with
    b[range_b[0]] and a[-1] with b[range_b[1]].
    """
    m, n = len(a), len(b)
    # Candidate anchors: indices of b coinciding with a[0].
    d0 = np.linalg.norm(b - a[0], axis=1)
    for k in np.nonzero(d0 <= tol)[0]:
        k = int(k)
        if k + m <= n:
            gap = _match_window(a, b[k : k + m], tol)
            if gap is not None:
                yield (0, m - 1), (k, k + m - 1), "same", gap
        if k - m + 1 >= 0:
            gap = _match_window(a, b[k - m + 1 : k + 1][::-1], tol)
            if gap is not None:
                yield (0, m - 1), (k, k - m + 1), "reversed", gap


def find_connections(
    blocks: list[StructuredBlock], tol: float | None = None
) -> list[BlockConnection]:
    """Detect all conformal edge connections among ``blocks``."""
    if tol is None:
        tol = _default_tol(blocks)

    edges = [
        (blk.name, ename, np.asarray(blk.edge(ename), dtype=float))
        for blk in blocks
        for ename in EDGE_NAMES
    ]

    conns: list[BlockConnection] = []
    seen: set[tuple] = set()
    for ia in range(len(edges)):
        name_a, edge_a, pts_a = edges[ia]
        for ib in range(ia + 1, len(edges)):
            name_b, edge_b, pts_b = edges[ib]
            # Orient so the shorter edge slides along the longer one.
            if len(pts_a) <= len(pts_b):
                short, long_ = (name_a, edge_a, pts_a), (name_b, edge_b, pts_b)
                swapped = False
            else:
                short, long_ = (name_b, edge_b, pts_b), (name_a, edge_a, pts_a)
                swapped = True

            for r_short, r_long, orient, gap in _find_edge_matches(
                short[2], long_[2], tol
            ):
                if swapped:
                    ca = (long_[0], long_[1], _sorted_range(r_long))
                    cb = (short[0], short[1], r_short)
                    range_a, range_b = _reorient(r_long, r_short)
                else:
                    ca = (short[0], short[1], r_short)
                    cb = (long_[0], long_[1], _sorted_range(r_long))
                    range_a, range_b = r_short, r_long
                key = (ca[0], ca[1], tuple(sorted(range_a)), cb[0], cb[1], tuple(sorted(range_b)))
                if key in seen:
                    continue
                seen.add(key)
                conns.append(
                    BlockConnection(
                        block_a=ca[0],
                        edge_a=ca[1],
                        range_a=tuple(int(v) for v in range_a),
                        block_b=cb[0],
                        edge_b=cb[1],
                        range_b=tuple(int(v) for v in range_b),
                        orientation=orient,
                        max_gap=gap,
                    )
                )
    return conns


def _sorted_range(r: tuple[int, int]) -> tuple[int, int]:
    return (min(r), max(r))


def _reorient(r_long, r_short):
    """Normalize a swapped match so side A traverses forward."""
    if r_long[0] <= r_long[1]:
        return r_long, r_short
    # long side was traversed backwards; flip both so A goes forward
    return (r_long[1], r_long[0]), (r_short[1], r_short[0])


def covered_cell_intervals(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge inclusive point-index ranges into covered cell intervals."""
    ivals = sorted(tuple(sorted(r)) for r in ranges)
    merged: list[list[int]] = []
    for lo, hi in ivals:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged if hi > lo]


def open_edges(
    blocks: list[StructuredBlock], connections: list[BlockConnection]
) -> list[tuple[str, str, list[tuple[int, int]]]]:
    """Edges (or edge portions) not matched to any neighbor.

    Returns (block_name, edge_name, uncovered inclusive point ranges).
    These are the free boundary edges that need boundary conditions in a
    downstream extrusion (pyHyp BC dict) - or indicate a missing patch.
    """
    cover: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for c in connections:
        cover.setdefault((c.block_a, c.edge_a), []).append(c.range_a)
        cover.setdefault((c.block_b, c.edge_b), []).append(c.range_b)

    out = []
    for blk in blocks:
        for ename in EDGE_NAMES:
            n = blk.edge_length(ename)
            covered = covered_cell_intervals(cover.get((blk.name, ename), []))
            uncovered = []
            pos = 0
            for lo, hi in covered:
                if lo > pos:
                    uncovered.append((pos, lo))
                pos = max(pos, hi)
            if pos < n - 1:
                uncovered.append((pos, n - 1))
            if uncovered:
                out.append((blk.name, ename, uncovered))
    return out


def validate_conformity(
    blocks: list[StructuredBlock],
    connections: list[BlockConnection],
    tol: float | None = None,
) -> list[str]:
    """Return a list of human-readable problems (empty = all good)."""
    if tol is None:
        tol = _default_tol(blocks)
    problems = []
    by_name = {b.name: b for b in blocks}
    for c in connections:
        na = abs(c.range_a[1] - c.range_a[0]) + 1
        nb = abs(c.range_b[1] - c.range_b[0]) + 1
        if na != nb:
            problems.append(
                f"{c.block_a}.{c.edge_a}{c.range_a} <-> {c.block_b}.{c.edge_b}{c.range_b}: "
                f"point counts differ ({na} vs {nb})"
            )
        if c.max_gap > tol:
            problems.append(
                f"{c.block_a}.{c.edge_a} <-> {c.block_b}.{c.edge_b}: "
                f"gap {c.max_gap:g} exceeds tolerance {tol:g}"
            )
        for name in (c.block_a, c.block_b):
            if name not in by_name:
                problems.append(f"connection references unknown block '{name}'")
    return problems


def connectivity_report(
    blocks: list[StructuredBlock], connections: list[BlockConnection]
) -> str:
    lines = [f"{len(connections)} connection(s):"]
    for c in connections:
        lines.append(
            f"  {c.block_a:<20} {c.edge_a:<6} [{c.range_a[0]:>4},{c.range_a[1]:>4}]  <->  "
            f"{c.block_b:<20} {c.edge_b:<6} [{c.range_b[0]:>4},{c.range_b[1]:>4}]  "
            f"({c.orientation}, gap={c.max_gap:.2e})"
        )
    opens = open_edges(blocks, connections)
    if opens:
        lines.append(f"{len(opens)} open (unmatched) edge(s) - these need BCs downstream:")
        for name, ename, ranges in opens:
            rs = ", ".join(f"[{lo},{hi}]" for lo, hi in ranges)
            lines.append(f"  {name:<20} {ename:<6} uncovered point range(s): {rs}")
    else:
        lines.append("no open edges: surface is watertight")
    return "\n".join(lines)
