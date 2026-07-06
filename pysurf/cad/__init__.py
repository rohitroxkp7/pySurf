"""CAD import (Phase 2): STEP inspection and reading.

Two tiers:

- :mod:`pysurf.cad.step_scan` - dependency-free text scan of a STEP file
  (schema, units, face names, surface types).  Always available.
- :mod:`pysurf.cad.reader` - full topology via pythonOCC (conda-only
  dependency), used when importable.
"""
