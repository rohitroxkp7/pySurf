import numpy as np
import pytest

from pysurf.meshing.annulus import annulus
from pysurf.meshing.cone import cone_ogrid, cone_side
from pysurf.meshing.cylinder import cylinder_side
from pysurf.meshing.disk_ogrid import disk_ogrid
from pysurf.meshing.plane import plane_patch
from pysurf.meshing.quality import block_metrics, cell_areas
from pysurf.meshing.sphere import sphere_cubed


def _no_folding(blocks):
    for blk in blocks:
        m = block_metrics(blk)
        assert m["min_normal_dot"] > 0.0, f"{blk.name} folds (dot={m['min_normal_dot']})"
        assert m["n_degenerate"] == 0, f"{blk.name} has degenerate cells"


# ----------------------------------------------------------- cylinder
def test_cylinder_geometry():
    blk = cylinder_side(radius=2.0, height=5.0, ni=65, nj=17)
    r = np.hypot(blk.xyz[:, :, 0], blk.xyz[:, :, 1])
    assert np.allclose(r, 2.0, atol=1e-12)
    assert blk.xyz[:, :, 2].min() == 0.0 and blk.xyz[:, :, 2].max() == 5.0
    # duplicated seam
    assert np.array_equal(blk.xyz[0], blk.xyz[-1])
    _no_folding([blk])


def test_cylinder_normals_outward():
    blk = cylinder_side(radius=1.0, height=2.0, ni=65, nj=17)
    n = blk.cell_normals()
    centers = 0.25 * (
        blk.xyz[:-1, :-1] + blk.xyz[1:, :-1] + blk.xyz[1:, 1:] + blk.xyz[:-1, 1:]
    )
    radial = centers.copy()
    radial[:, :, 2] = 0.0
    radial /= np.linalg.norm(radial, axis=2, keepdims=True)
    dots = np.einsum("ijk,ijk->ij", n, radial)
    assert dots.min() > 0.9


# ----------------------------------------------------------- cone side
def test_cone_side_radii_and_apex_rejection():
    blk = cone_side(radius_bottom=1.0, radius_top=0.4, height=1.5, ni=33, nj=9)
    r = np.hypot(blk.xyz[:, :, 0], blk.xyz[:, :, 1])
    assert np.allclose(r[:, 0], 1.0, atol=1e-12)
    assert np.allclose(r[:, -1], 0.4, atol=1e-12)
    _no_folding([blk])
    with pytest.raises(ValueError, match="cone_ogrid"):
        cone_side(radius_bottom=1.0, radius_top=0.0, height=1.0, ni=17, nj=5)


# ----------------------------------------------------------- disk O-grid
def test_disk_ogrid_basic():
    blocks = disk_ogrid(n_arc=17, n_radial=9, radius=1.5)
    assert len(blocks) == 5
    all_pts = np.vstack([b.xyz.reshape(-1, 3) for b in blocks])
    r = np.hypot(all_pts[:, 0], all_pts[:, 1])
    assert r.max() <= 1.5 + 1e-12
    assert np.allclose(all_pts[:, 2], 0.0)
    # outer boundary lies exactly on the circle
    for b in blocks:
        if b.name.endswith(("q0", "q1", "q2", "q3")):
            outer = b.edge("j_max")
            assert np.allclose(np.hypot(outer[:, 0], outer[:, 1]), 1.5, atol=1e-12)
    _no_folding(blocks)


@pytest.mark.parametrize("normal,sign", [("+z", 1.0), ("-z", -1.0)])
def test_disk_ogrid_normal_direction(normal, sign):
    blocks = disk_ogrid(n_arc=9, n_radial=5, radius=1.0, normal=normal)
    for b in blocks:
        nz = b.cell_normals()[:, :, 2]
        assert np.all(sign * nz > 0.9), b.name


def test_disk_ogrid_split_center():
    blocks = disk_ogrid(n_arc=9, n_radial=5, radius=1.0, split_center=True)
    assert len(blocks) == 8
    # the disk center is a corner of each of the 4 center sub-blocks
    count = 0
    for b in blocks:
        if "_c" in b.name:
            corners = [b.xyz[0, 0], b.xyz[-1, 0], b.xyz[0, -1], b.xyz[-1, -1]]
            count += sum(np.allclose(c[:2], 0.0, atol=1e-12) for c in corners)
    assert count == 4
    _no_folding(blocks)
    with pytest.raises(ValueError, match="odd"):
        disk_ogrid(n_arc=8, n_radial=5, radius=1.0, split_center=True)


def test_elliptic_disk_boundary():
    a, b = 2.0, 1.0
    blocks = disk_ogrid(n_arc=17, n_radial=9, semi_axes=(a, b))
    for blk in blocks:
        if blk.name.endswith(("q0", "q1", "q2", "q3")):
            outer = blk.edge("j_max")
            val = (outer[:, 0] / a) ** 2 + (outer[:, 1] / b) ** 2
            assert np.allclose(val, 1.0, atol=1e-12)
    _no_folding(blocks)


# ----------------------------------------------------------- cone O-grid
def test_cone_ogrid_on_surface_and_apex():
    R, H = 1.0, 2.0
    blocks = cone_ogrid(n_arc=17, n_radial=9, radius=R, height=H)
    assert len(blocks) == 8
    apex_hits = 0
    for b in blocks:
        pts = b.xyz.reshape(-1, 3)
        rho = np.hypot(pts[:, 0], pts[:, 1]) / R
        assert np.allclose(pts[:, 2], H * (1.0 - rho), atol=1e-12), b.name
        if b.name.split("_")[-1].startswith("c"):
            corners = [b.xyz[0, 0], b.xyz[-1, 0], b.xyz[0, -1], b.xyz[-1, -1]]
            apex_hits += sum(np.allclose(c, [0, 0, H], atol=1e-12) for c in corners)
    # apex is a corner vertex of exactly the 4 center sub-blocks
    assert apex_hits == 4
    _no_folding(blocks)


def test_cone_ogrid_requires_odd_arc():
    with pytest.raises(ValueError, match="odd"):
        cone_ogrid(n_arc=16, n_radial=9, radius=1.0, height=1.0)


def test_cone_ogrid_normals_outward():
    blocks = cone_ogrid(n_arc=17, n_radial=9, radius=1.0, height=2.0)
    for b in blocks:
        n = b.cell_normals()
        centers = 0.25 * (b.xyz[:-1, :-1] + b.xyz[1:, :-1] + b.xyz[1:, 1:] + b.xyz[:-1, 1:])
        # outward for a cone (apex up) = radially out and tilted up:
        # dot with (x, y, r*(H/R)... ) simplified: radial + z-up component
        radial = centers.copy()
        radial[:, :, 2] = 0.0
        nrm = np.linalg.norm(radial, axis=2, keepdims=True)
        ok = nrm[:, :, 0] > 1e-9
        radial = np.divide(radial, nrm, out=np.zeros_like(radial), where=nrm > 0)
        outward = radial + np.array([0.0, 0.0, 0.5])  # cone slope R/H = 0.5
        outward /= np.linalg.norm(outward, axis=2, keepdims=True)
        dots = np.einsum("ijk,ijk->ij", n, outward)
        assert dots[ok].min() > 0.5, b.name


# ----------------------------------------------------------- annulus
def test_annulus_geometry_and_normal():
    blk = annulus(radius_inner=0.5, radius_outer=2.0, ni=33, nj=9)
    r = np.hypot(blk.xyz[:, :, 0], blk.xyz[:, :, 1])
    assert np.allclose(r.min(), 0.5) and np.allclose(r.max(), 2.0)
    assert np.all(blk.cell_normals()[:, :, 2] > 0.9)
    blk2 = annulus(radius_inner=0.5, radius_outer=2.0, ni=33, nj=9, normal="-z")
    assert np.all(blk2.cell_normals()[:, :, 2] < -0.9)
    with pytest.raises(ValueError):
        annulus(radius_inner=2.0, radius_outer=0.5, ni=17, nj=5)


# ----------------------------------------------------------- plane
def test_plane_patch():
    blk = plane_patch([0, 0, 0], [2, 0, 0], [0, 1, 0], ni=9, nj=5)
    assert np.allclose(cell_areas(blk).sum(), 2.0, atol=1e-12)
    with pytest.raises(ValueError):
        plane_patch([0, 0, 0], [1, 0, 0], [2, 0, 0], ni=5, nj=5)


# ----------------------------------------------------------- sphere
def test_sphere_cubed():
    R = 1.5
    blocks = sphere_cubed(radius=R, n=17)
    assert len(blocks) == 6
    for b in blocks:
        d = np.linalg.norm(b.xyz.reshape(-1, 3), axis=1)
        assert np.allclose(d, R, atol=1e-12)
        # outward normals: dot(normal, radial direction) > 0
        n = b.cell_normals()
        centers = 0.25 * (b.xyz[:-1, :-1] + b.xyz[1:, :-1] + b.xyz[1:, 1:] + b.xyz[:-1, 1:])
        centers /= np.linalg.norm(centers, axis=2, keepdims=True)
        assert np.einsum("ijk,ijk->ij", n, centers).min() > 0.9, b.name
    _no_folding(blocks)
