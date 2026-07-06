import numpy as np
import pytest

from pysurf.meshing.tfi import tfi


def _line(p0, p1, n):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) * np.asarray(p0, float) + t * np.asarray(p1, float)


def test_unit_square_reproduces_bilinear():
    ni, nj = 9, 7
    bottom = _line([0, 0, 0], [1, 0, 0], ni)
    top = _line([0, 1, 0], [1, 1, 0], ni)
    left = _line([0, 0, 0], [0, 1, 0], nj)
    right = _line([1, 0, 0], [1, 1, 0], nj)
    xyz = tfi(bottom, top, left, right)
    s = np.linspace(0, 1, ni)
    t = np.linspace(0, 1, nj)
    exact = np.zeros((ni, nj, 3))
    exact[:, :, 0] = s[:, None]
    exact[:, :, 1] = t[None, :]
    assert np.allclose(xyz, exact, atol=1e-12)


def test_boundary_reproduction_curved():
    ni, nj = 21, 11
    s = np.linspace(0, 1, ni)
    t = np.linspace(0, 1, nj)
    bottom = np.column_stack([s, 0.2 * np.sin(np.pi * s), np.zeros(ni)])
    top = np.column_stack([s, 1.0 + 0.1 * np.sin(2 * np.pi * s), np.zeros(ni)])
    left = np.column_stack([np.zeros(nj), t, np.zeros(nj)])
    right = np.column_stack([np.ones(nj), t, np.zeros(nj)])
    xyz = tfi(bottom, top, left, right)
    assert np.allclose(xyz[:, 0, :], bottom, atol=1e-12)
    assert np.allclose(xyz[:, -1, :], top, atol=1e-12)
    assert np.allclose(xyz[0, :, :], left, atol=1e-12)
    assert np.allclose(xyz[-1, :, :], right, atol=1e-12)


def test_corner_mismatch_raises():
    ni, nj = 5, 5
    bottom = _line([0, 0, 0], [1, 0, 0], ni)
    top = _line([0, 1, 0], [1, 1, 0], ni)
    left = _line([0.5, 0, 0], [0, 1, 0], nj)  # wrong corner
    right = _line([1, 0, 0], [1, 1, 0], nj)
    with pytest.raises(ValueError, match="corner mismatch"):
        tfi(bottom, top, left, right)
