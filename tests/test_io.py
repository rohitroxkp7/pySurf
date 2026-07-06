import xml.etree.ElementTree as ET

import numpy as np

from pysurf.assembly.connectivity import find_connections
from pysurf.io.json_writer import write_debug_json
from pysurf.io.plot3d_writer import read_plot3d_surface, write_plot3d_surface
from pysurf.io.pyhyp_script import write_pyhyp_script
from pysurf.io.vtk_writer import write_vtm, write_vtp, write_vtp_combined
from pysurf.meshing.cylinder import cylinder_side
from pysurf.meshing.disk_ogrid import disk_ogrid


def _cyl_blocks():
    side = cylinder_side(radius=1.0, height=2.0, ni=17, nj=5)
    caps = disk_ogrid(n_arc=5, n_radial=3, radius=1.0, z=2.0, name_prefix="top")
    return [side] + caps


def test_vtp_parses_and_counts(tmp_path):
    blk = _cyl_blocks()[0]
    path = write_vtp(blk, tmp_path / "side.vtp")
    root = ET.parse(path).getroot()
    piece = root.find(".//Piece")
    assert int(piece.get("NumberOfPoints")) == blk.n_points
    assert int(piece.get("NumberOfPolys")) == blk.n_cells


def test_vtp_combined(tmp_path):
    blocks = _cyl_blocks()
    path = write_vtp_combined(blocks, tmp_path / "all.vtp")
    root = ET.parse(path).getroot()
    piece = root.find(".//Piece")
    assert int(piece.get("NumberOfPoints")) == sum(b.n_points for b in blocks)
    assert int(piece.get("NumberOfPolys")) == sum(b.n_cells for b in blocks)
    names = [da.get("Name") for da in root.findall(".//CellData/DataArray")]
    assert "BlockId" in names


def test_vtm_references_exist(tmp_path):
    blocks = _cyl_blocks()
    path = write_vtm(blocks, tmp_path / "mesh.vtm")
    root = ET.parse(path).getroot()
    refs = [ds.get("file") for ds in root.findall(".//DataSet")]
    assert len(refs) == len(blocks)
    for ref in refs:
        assert (tmp_path / ref).exists()


def test_plot3d_roundtrip(tmp_path):
    blocks = _cyl_blocks()
    path = write_plot3d_surface(blocks, tmp_path / "surf.fmt")
    back = read_plot3d_surface(path)
    assert len(back) == len(blocks)
    for orig, rd in zip(blocks, back):
        assert rd.shape == orig.xyz.shape
        assert np.allclose(rd, orig.xyz, atol=1e-12)


def test_plot3d_header_layout(tmp_path):
    blocks = _cyl_blocks()
    path = write_plot3d_surface(blocks, tmp_path / "surf.fmt")
    tokens = path.read_text().split()
    assert int(tokens[0]) == len(blocks)
    # 3 dims per block, k always 1
    for b in range(len(blocks)):
        ni, nj, nk = (int(v) for v in tokens[1 + 3 * b : 4 + 3 * b])
        assert (ni, nj) == (blocks[b].ni, blocks[b].nj)
        assert nk == 1


def test_json_debug(tmp_path):
    blocks = _cyl_blocks()
    conns = find_connections(blocks)
    path = write_debug_json(blocks, conns, tmp_path / "dbg.json")
    import json

    doc = json.loads(path.read_text())
    assert len(doc["blocks"]) == len(blocks)
    assert len(doc["connections"]) == len(conns)


def test_pyhyp_script_generated(tmp_path):
    blocks = _cyl_blocks()
    conns = find_connections(blocks)
    path = write_pyhyp_script(blocks, conns, "surf.fmt", tmp_path / "run_pyhyp.py")
    text = path.read_text()
    assert "from pyhyp import pyHyp" in text
    assert '"fileType": "PLOT3D"' in text
    # cylinder without a bottom cap has open edges -> BC guidance present
    assert "Open edges needing a BC" in text
