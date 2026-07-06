import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.meshing.plane import plane_patch
from pysurf.meshing.quality import (
    aspect_ratios,
    block_metrics,
    cell_areas,
    min_normal_dot,
    quality_report,
    skew_angles_deg,
)


def test_unit_square_metrics():
    blk = plane_patch([0, 0, 0], [1, 0, 0], [0, 1, 0], 5, 5)
    areas = cell_areas(blk)
    assert np.allclose(areas, (0.25) ** 2)
    assert np.allclose(aspect_ratios(blk), 1.0)
    assert np.allclose(skew_angles_deg(blk), 0.0, atol=1e-9)
    assert min_normal_dot(blk) > 0.999999


def test_folded_block_flagged():
    # build a 3x2 block whose middle column folds back over the first
    xyz = np.zeros((3, 2, 3))
    xyz[:, :, 0] = np.array([[0.0, 0.0], [1.0, 1.0], [0.5, 0.5]])  # x goes 0 -> 1 -> 0.5
    xyz[:, :, 1] = np.array([[0.0, 1.0], [0.0, 1.0], [0.0, 1.0]])
    blk = StructuredBlock("folded", xyz)
    assert min_normal_dot(blk) < 0.0
    m = block_metrics(blk)
    assert m["min_normal_dot"] < 0.0
    report = quality_report([blk])
    assert "folds over itself" in report


def test_degenerate_cells_flagged():
    xyz = np.zeros((3, 3, 3))
    xyz[:, :, 0] = np.array([[0, 0, 0], [0, 0, 0], [1, 1, 1]])  # first cell row zero width
    xyz[:, :, 1] = np.array([[0, 0.5, 1]] * 3)
    blk = StructuredBlock("degen", xyz)
    m = block_metrics(blk)
    assert m["n_degenerate"] > 0
