"""VTK XML writers (no vtk package required).

Produces ParaView-readable files:

    write_vtp(block, path)            one block as PolyData quads
    write_vtp_combined(blocks, path)  all blocks in one .vtp with a
                                      BlockId cell array for coloring
    write_vtm(blocks, path)           a .vtm multiblock index plus one
                                      .vtp per block (block names show up
                                      in the ParaView tree)

Quad winding follows the block's (i, j) right-hand orientation, so
ParaView's surface normals agree with the mesher's normal convention.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pysurf.blocks import StructuredBlock


def _fmt_floats(values: np.ndarray, per_line: int = 3) -> str:
    flat = np.asarray(values).ravel()
    lines = []
    for start in range(0, len(flat), per_line):
        lines.append(" ".join(f"{v:.17g}" for v in flat[start : start + per_line]))
    return "\n".join(lines)


def _fmt_ints(values, per_line: int = 12) -> str:
    flat = list(values)
    lines = []
    for start in range(0, len(flat), per_line):
        lines.append(" ".join(str(v) for v in flat[start : start + per_line]))
    return "\n".join(lines)


def _quad_connectivity(ni: int, nj: int, offset: int = 0) -> np.ndarray:
    """Quad corner indices, point id p(i, j) = i * nj + j, CCW in (i, j)."""
    i, j = np.meshgrid(np.arange(ni - 1), np.arange(nj - 1), indexing="ij")
    p00 = i * nj + j
    p10 = (i + 1) * nj + j
    p11 = (i + 1) * nj + (j + 1)
    p01 = i * nj + (j + 1)
    conn = np.stack([p00, p10, p11, p01], axis=-1).reshape(-1, 4)
    return conn + offset


def _polydata_xml(points: np.ndarray, quads: np.ndarray, cell_arrays: dict | None = None) -> str:
    n_pts = len(points)
    n_cells = len(quads)
    offsets = 4 * (np.arange(n_cells) + 1)

    cell_data = ""
    if cell_arrays:
        chunks = []
        for name, arr in cell_arrays.items():
            chunks.append(
                f'        <DataArray type="Int32" Name="{name}" format="ascii">\n'
                f"{_fmt_ints(np.asarray(arr).ravel())}\n"
                f"        </DataArray>\n"
            )
        cell_data = "      <CellData>\n" + "".join(chunks) + "      </CellData>\n"

    return (
        '<?xml version="1.0"?>\n'
        '<VTKFile type="PolyData" version="1.0" byte_order="LittleEndian">\n'
        "  <PolyData>\n"
        f'    <Piece NumberOfPoints="{n_pts}" NumberOfVerts="0" NumberOfLines="0" '
        f'NumberOfStrips="0" NumberOfPolys="{n_cells}">\n'
        f"{cell_data}"
        "      <Points>\n"
        '        <DataArray type="Float64" NumberOfComponents="3" format="ascii">\n'
        f"{_fmt_floats(points)}\n"
        "        </DataArray>\n"
        "      </Points>\n"
        "      <Polys>\n"
        '        <DataArray type="Int64" Name="connectivity" format="ascii">\n'
        f"{_fmt_ints(quads.ravel())}\n"
        "        </DataArray>\n"
        '        <DataArray type="Int64" Name="offsets" format="ascii">\n'
        f"{_fmt_ints(offsets)}\n"
        "        </DataArray>\n"
        "      </Polys>\n"
        "    </Piece>\n"
        "  </PolyData>\n"
        "</VTKFile>\n"
    )


def write_vtp(block: StructuredBlock, path) -> Path:
    """Write one block as a .vtp PolyData file."""
    path = Path(path)
    points = block.xyz.reshape(-1, 3)
    quads = _quad_connectivity(block.ni, block.nj)
    path.write_text(_polydata_xml(points, quads), encoding="ascii")
    return path


def write_vtp_combined(blocks: list[StructuredBlock], path) -> Path:
    """Write all blocks into a single .vtp with a BlockId cell array."""
    path = Path(path)
    pts_list, quad_list, ids = [], [], []
    offset = 0
    for bid, blk in enumerate(blocks):
        pts_list.append(blk.xyz.reshape(-1, 3))
        quads = _quad_connectivity(blk.ni, blk.nj, offset)
        quad_list.append(quads)
        ids.append(np.full(len(quads), bid, dtype=np.int32))
        offset += blk.n_points
    xml = _polydata_xml(
        np.vstack(pts_list), np.vstack(quad_list), {"BlockId": np.concatenate(ids)}
    )
    path.write_text(xml, encoding="ascii")
    return path


def write_vtm(blocks: list[StructuredBlock], path) -> Path:
    """Write a .vtm multiblock index plus one .vtp per block.

    Block .vtp files go into a sibling directory named after the .vtm
    stem; ParaView shows each block by name in the pipeline browser.
    """
    path = Path(path)
    if path.suffix != ".vtm":
        path = path.with_suffix(".vtm")
    subdir = path.parent / path.stem
    subdir.mkdir(parents=True, exist_ok=True)

    entries = []
    for idx, blk in enumerate(blocks):
        vtp_path = subdir / f"{blk.name}.vtp"
        write_vtp(blk, vtp_path)
        rel = f"{path.stem}/{blk.name}.vtp"
        entries.append(f'    <DataSet index="{idx}" name="{blk.name}" file="{rel}"/>')

    xml = (
        '<?xml version="1.0"?>\n'
        '<VTKFile type="vtkMultiBlockDataSet" version="1.0" byte_order="LittleEndian">\n'
        "  <vtkMultiBlockDataSet>\n"
        + "\n".join(entries)
        + "\n  </vtkMultiBlockDataSet>\n"
        "</VTKFile>\n"
    )
    path.write_text(xml, encoding="ascii")
    return path
