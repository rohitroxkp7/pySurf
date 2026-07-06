"""pysurf - structured surface mesher.

A user-guided multiblock structured surface mesh generator. Geometry is
described as a collection of named structured blocks P[i, j] -> (x, y, z)
plus a connectivity table between blocks, per the local/global principle:

    global complex surface
    -> split into simple named local surfaces
    -> mesh each surface in local coordinates
    -> enforce matching edges
    -> assemble as multiblock structured surface mesh
"""

from pysurf.blocks import StructuredBlock, BlockConnection, EDGE_NAMES

__version__ = "0.1.0"

__all__ = ["StructuredBlock", "BlockConnection", "EDGE_NAMES", "__version__"]
