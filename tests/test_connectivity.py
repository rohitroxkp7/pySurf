import numpy as np

from pysurf.blocks import StructuredBlock
from pysurf.assembly.connectivity import (
    find_connections,
    open_edges,
    validate_conformity,
)
from pysurf.meshing.cone import cone_ogrid
from pysurf.meshing.cylinder import cylinder_side
from pysurf.meshing.disk_ogrid import disk_ogrid
from pysurf.meshing.plane import plane_patch
from pysurf.meshing.sphere import sphere_cubed


def _conn_set(conns):
    out = set()
    for c in conns:
        out.add((c.block_a, c.edge_a, c.block_b, c.edge_b, c.orientation))
    return out


def test_two_abutting_rectangles_same_orientation():
    left = plane_patch([0, 0, 0], [1, 0, 0], [0, 1, 0], 5, 9, name="left")
    right = plane_patch([1, 0, 0], [1, 0, 0], [0, 1, 0], 5, 9, name="right")
    conns = find_connections([left, right])
    assert len(conns) == 1
    c = conns[0]
    assert {c.block_a, c.block_b} == {"left", "right"}
    assert c.orientation == "same"
    assert validate_conformity([left, right], conns) == []


def test_reversed_orientation_detected():
    left = plane_patch([0, 0, 0], [1, 0, 0], [0, 1, 0], 5, 9, name="left")
    # right block built so its shared edge runs the opposite way (j downward)
    right = plane_patch([1, 1, 0], [1, 0, 0], [0, -1, 0], 5, 9, name="right")
    conns = find_connections([left, right])
    assert len(conns) == 1
    assert conns[0].orientation == "reversed"


def test_cylinder_seam_self_connection():
    side = cylinder_side(radius=1.0, height=2.0, ni=33, nj=9)
    conns = find_connections([side])
    assert len(conns) == 1
    c = conns[0]
    assert c.block_a == c.block_b == "cylinder_side"
    assert {c.edge_a, c.edge_b} == {"i_min", "i_max"}


def test_full_cylinder_watertight():
    ni_side = 33  # 32 intervals -> n_arc = 9
    side = cylinder_side(radius=1.0, height=2.0, ni=ni_side, nj=9)
    top = disk_ogrid(n_arc=9, n_radial=5, radius=1.0, z=2.0, normal="+z", name_prefix="top")
    bot = disk_ogrid(n_arc=9, n_radial=5, radius=1.0, z=0.0, normal="-z", name_prefix="bot")
    blocks = [side] + top + bot
    conns = find_connections(blocks)
    assert validate_conformity(blocks, conns) == []
    # watertight: no open edges anywhere
    assert open_edges(blocks, conns) == []
    # each cap contributes 4 subrange matches against the side circle
    side_top_matches = [
        c for c in conns
        if ("cylinder_side" in (c.block_a, c.block_b)) and any(b.startswith("top_q") for b in (c.block_a, c.block_b))
    ]
    assert len(side_top_matches) == 4


def test_closed_cone_watertight():
    cone = cone_ogrid(n_arc=9, n_radial=7, radius=1.0, height=2.0, name_prefix="cone")
    cap = disk_ogrid(n_arc=9, n_radial=5, radius=1.0, z=0.0, normal="-z", name_prefix="cap")
    blocks = cone + cap
    conns = find_connections(blocks)
    assert validate_conformity(blocks, conns) == []
    assert open_edges(blocks, conns) == []


def test_open_cone_reports_base_edges():
    cone = cone_ogrid(n_arc=9, n_radial=7, radius=1.0, height=2.0, name_prefix="cone")
    conns = find_connections(cone)
    opens = open_edges(cone, conns)
    # exactly the 4 outer arcs of the quadrant blocks are open
    open_blocks = {name for name, _e, _r in opens}
    assert open_blocks == {"cone_q0", "cone_q1", "cone_q2", "cone_q3"}
    assert len(opens) == 4


def test_sphere_watertight():
    blocks = sphere_cubed(radius=1.0, n=9)
    conns = find_connections(blocks)
    # 12 cube edges -> 12 connections
    assert len(conns) == 12
    assert open_edges(blocks, conns) == []
    assert validate_conformity(blocks, conns) == []


def test_subrange_match_ranges():
    # short edge (5 pts) against a long edge (13 pts): match sits at an
    # interior index range of the long edge
    long_blk = plane_patch([0, 0, 0], [3, 0, 0], [0, 1, 0], 13, 5, name="long")
    short_blk = plane_patch([0.5, -1, 0], [1, 0, 0], [0, 1, 0], 5, 5, name="short")
    # shift short so its top edge lies on long's bottom edge from x=0.5..1.5
    conns = find_connections([long_blk, short_blk])
    assert len(conns) == 1
    c = conns[0]
    rng = c.range_a if c.block_a == "long" else c.range_b
    assert tuple(sorted(rng)) == (2, 6)  # x=0.5 -> idx 2, x=1.5 -> idx 6
