import numpy as np
import pytest

from pysurf.assembly.connectivity import find_connections, open_edges, validate_conformity
from pysurf.geometry.frames import place, rotation_for_axis
from pysurf.meshing.cone import cone_ogrid
from pysurf.meshing.cylinder import cylinder_side
from pysurf.meshing.disk_ogrid import disk_ogrid


@pytest.mark.parametrize("axis", ["+x", "-x", "+y", "-y", "+z", "-z"])
def test_rotations_proper_and_correct(axis):
    R = rotation_for_axis(axis)
    assert np.isclose(np.linalg.det(R), 1.0)  # proper rotation: normals preserved
    sign = 1.0 if axis[0] == "+" else -1.0
    idx = "xyz".index(axis[1])
    expect = np.zeros(3)
    expect[idx] = sign
    assert np.allclose(R @ np.array([0.0, 0.0, 1.0]), expect)


def test_bad_axis_rejected():
    with pytest.raises(ValueError, match="axis"):
        place(np.zeros((2, 2, 3)), axis="x")


def test_cylinder_along_x():
    blk = cylinder_side(radius=1.0, height=5.0, ni=33, nj=9, axis="+x")
    pts = blk.xyz.reshape(-1, 3)
    assert np.allclose(np.hypot(pts[:, 1], pts[:, 2]), 1.0, atol=1e-12)
    assert pts[:, 0].min() == 0.0 and pts[:, 0].max() == 5.0


def test_cone_tip_to_base_along_plus_x():
    # tip at origin, base circle in the x = 2 plane: axis '-x', center (2,0,0)
    H, R = 2.0, 1.0
    blocks = cone_ogrid(n_arc=17, n_radial=9, radius=R, height=H,
                        axis="-x", center=(H, 0.0, 0.0))
    pts = np.vstack([b.xyz.reshape(-1, 3) for b in blocks])
    # tip present at the origin
    assert np.min(np.linalg.norm(pts, axis=1)) < 1e-12
    # every point on the cone: cross-stream radius = x / (H/R)
    r_yz = np.hypot(pts[:, 1], pts[:, 2])
    assert np.allclose(r_yz, pts[:, 0] * (R / H), atol=1e-12)
    assert pts[:, 0].min() >= -1e-12 and np.isclose(pts[:, 0].max(), H)


def test_closed_cone_along_x_watertight_and_outward():
    H, R = 2.0, 1.0
    cone = cone_ogrid(n_arc=9, n_radial=7, radius=R, height=H,
                      axis="-x", center=(H, 0, 0), name_prefix="cone")
    cap = disk_ogrid(n_arc=9, n_radial=5, radius=R, axis="-x",
                     center=(H, 0, 0), z=0.0, normal="-z", name_prefix="cap")
    blocks = cone + cap
    conns = find_connections(blocks)
    assert validate_conformity(blocks, conns) == []
    assert open_edges(blocks, conns) == []
    # cap normals must point outward = +x (downstream of the base)
    for b in cap:
        nx = b.cell_normals()[:, :, 0]
        assert np.all(nx > 0.9), b.name
    # cone normals: away from the x axis, tilted upstream (-x)
    for b in cone:
        n = b.cell_normals()
        centers = 0.25 * (b.xyz[:-1, :-1] + b.xyz[1:, :-1] + b.xyz[1:, 1:] + b.xyz[:-1, 1:])
        radial = centers.copy()
        radial[:, :, 0] = 0.0
        nrm = np.linalg.norm(radial, axis=2, keepdims=True)
        ok = nrm[:, :, 0] > 1e-9
        radial = np.divide(radial, nrm, out=np.zeros_like(radial), where=nrm > 0)
        outward = radial + np.array([-0.5, 0.0, 0.0])  # slope R/H, upstream tilt
        outward /= np.linalg.norm(outward, axis=2, keepdims=True)
        dots = np.einsum("ijk,ijk->ij", n, outward)
        assert dots[ok].min() > 0.5, b.name
