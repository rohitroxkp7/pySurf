"""JSON debug dump of blocks, quality metrics, and connectivity."""

from __future__ import annotations

import json
from pathlib import Path

from pysurf.blocks import BlockConnection, StructuredBlock
from pysurf.meshing.quality import block_metrics
from pysurf.assembly.connectivity import open_edges


def write_debug_json(
    blocks: list[StructuredBlock],
    connections: list[BlockConnection],
    path,
    meta: dict | None = None,
    include_coords: bool = False,
) -> Path:
    path = Path(path)
    doc = {
        "meta": meta or {},
        "blocks": [],
        "connections": [c.to_dict() for c in connections],
        "open_edges": [
            {"block": name, "edge": edge, "uncovered_ranges": [list(r) for r in ranges]}
            for name, edge, ranges in open_edges(blocks, connections)
        ],
    }
    for blk in blocks:
        entry = block_metrics(blk)
        lo, hi = blk.bounding_box()
        entry["bbox_min"] = lo.tolist()
        entry["bbox_max"] = hi.tolist()
        if include_coords:
            entry["xyz"] = blk.xyz.tolist()
        doc["blocks"].append(entry)
    path.write_text(json.dumps(doc, indent=2), encoding="ascii")
    return path
