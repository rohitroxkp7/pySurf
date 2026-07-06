"""Mesh quality metrics for structured surface blocks.

Metrics per block:

    min/max/mean cell area      (quad split into two triangles)
    max aspect ratio            (opposing mean edge lengths)
    max skew                    (worst corner-angle deviation from 90 deg)
    min normal dot              (worst dot product between adjacent cell
                                 normals; < 0 means the surface folds over
                                 itself, i.e. "inverted" cells)
    n_degenerate                (cells with ~zero area)
"""

from __future__ import annotations

import numpy as np

from pysurf.blocks import StructuredBlock


def _cell_corners(xyz: np.ndarray):
    a = xyz[:-1, :-1]  # (i,   j)
    b = xyz[1:, :-1]   # (i+1, j)
    c = xyz[1:, 1:]    # (i+1, j+1)
    d = xyz[:-1, 1:]   # (i,   j+1)
    return a, b, c, d


def cell_areas(block: StructuredBlock) -> np.ndarray:
    """Cell areas, shape (ni-1, nj-1), via triangle split ABC + ACD."""
    a, b, c, d = _cell_corners(block.xyz)
    t1 = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=2)
    t2 = 0.5 * np.linalg.norm(np.cross(c - a, d - a), axis=2)
    return t1 + t2


def aspect_ratios(block: StructuredBlock) -> np.ndarray:
    """Per-cell aspect ratio from mean opposing edge lengths."""
    a, b, c, d = _cell_corners(block.xyz)
    li = 0.5 * (np.linalg.norm(b - a, axis=2) + np.linalg.norm(c - d, axis=2))
    lj = 0.5 * (np.linalg.norm(d - a, axis=2) + np.linalg.norm(c - b, axis=2))
    lo = np.minimum(li, lj)
    hi = np.maximum(li, lj)
    return np.divide(hi, lo, out=np.full_like(hi, np.inf), where=lo > 0)


def skew_angles_deg(block: StructuredBlock) -> np.ndarray:
    """Per-cell worst deviation of a corner angle from 90 degrees."""
    a, b, c, d = _cell_corners(block.xyz)
    worst = np.zeros(a.shape[:2])
    for p, q, r in ((a, b, d), (b, c, a), (c, d, b), (d, a, c)):
        e1 = q - p
        e2 = r - p
        n1 = np.linalg.norm(e1, axis=2)
        n2 = np.linalg.norm(e2, axis=2)
        denom = n1 * n2
        cosang = np.divide(
            np.einsum("ijk,ijk->ij", e1, e2), denom,
            out=np.zeros(denom.shape), where=denom > 0,
        )
        ang = np.degrees(np.arccos(np.clip(cosang, -1.0, 1.0)))
        worst = np.maximum(worst, np.abs(ang - 90.0))
    return worst


def min_normal_dot(block: StructuredBlock) -> float:
    """Worst dot product between neighboring cell normals.

    1.0 for a flat patch; values near -1 mean the mesh folds back on
    itself.  Any negative value should be treated as an inverted-cell
    error for extrusion purposes.
    """
    n = block.cell_normals(normalize=True)
    dots = [
        np.einsum("ijk,ijk->ij", n[1:, :], n[:-1, :]),
        np.einsum("ijk,ijk->ij", n[:, 1:], n[:, :-1]),
    ]
    return float(min(d.min() for d in dots if d.size)) if any(d.size for d in dots) else 1.0


def block_metrics(block: StructuredBlock, degenerate_rel_tol: float = 1.0e-12) -> dict:
    areas = cell_areas(block)
    mean_area = float(areas.mean())
    return {
        "name": block.name,
        "ni": block.ni,
        "nj": block.nj,
        "n_cells": block.n_cells,
        "min_area": float(areas.min()),
        "max_area": float(areas.max()),
        "mean_area": mean_area,
        "max_aspect": float(aspect_ratios(block).max()),
        "max_skew_deg": float(skew_angles_deg(block).max()),
        "min_normal_dot": min_normal_dot(block),
        "n_degenerate": int((areas <= degenerate_rel_tol * max(mean_area, 1e-300)).sum()),
    }


def quality_report(blocks: list[StructuredBlock]) -> str:
    """Human-readable fixed-width quality table plus warnings."""
    rows = [block_metrics(b) for b in blocks]
    header = (
        f"{'block':<24} {'ni x nj':>9} {'cells':>7} {'min area':>11} "
        f"{'max AR':>8} {'skew(deg)':>9} {'nrm dot':>8} {'degen':>6}"
    )
    lines = [header, "-" * len(header)]
    warnings = []
    for r in rows:
        lines.append(
            f"{r['name']:<24} {r['ni']:>4}x{r['nj']:<4} {r['n_cells']:>7} "
            f"{r['min_area']:>11.4e} {r['max_aspect']:>8.2f} "
            f"{r['max_skew_deg']:>9.2f} {r['min_normal_dot']:>8.3f} {r['n_degenerate']:>6}"
        )
        if r["n_degenerate"] > 0:
            warnings.append(f"WARNING: block '{r['name']}' has {r['n_degenerate']} degenerate cell(s)")
        if r["min_normal_dot"] < 0.0:
            warnings.append(
                f"WARNING: block '{r['name']}' folds over itself "
                f"(min neighbor-normal dot = {r['min_normal_dot']:.3f})"
            )
    total_cells = sum(r["n_cells"] for r in rows)
    total_pts = sum(r["ni"] * r["nj"] for r in rows)
    lines.append("-" * len(header))
    lines.append(f"{len(rows)} blocks, {total_pts} points, {total_cells} cells")
    if warnings:
        lines.append("")
        lines.extend(warnings)
    return "\n".join(lines)
