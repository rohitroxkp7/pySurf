# CAD test geometries — exact SolidWorks deliverables for Phase 2

Phase 2 starts by answering one question: **do face names survive your
SolidWorks → STEP AP242 export path?** Everything below is designed to
test that, then become the first CAD-driven meshes.

## What a "seam line" is and why the cylinder side needs one

A cylinder's lateral surface in CAD is **one closed periodic face**: its
boundary consists only of the two circles — there is no "left" or
"right" edge, no start/end in the wrap-around direction. A structured
grid, however, needs a logical rectangle with four sides.

The **seam** is a straight split line along the axis (think of the glued
seam on a paper-towel roll). Cutting the side face there lets it unroll
into a rectangle:

```text
        top circle  ->  j_max ──────────────
        seam (θ=0)  ->  i_min │  unrolled   │ i_max  <- seam (θ=2π)
        bottom circle -> j_min ──────────────
              (i_min and i_max are the SAME physical line)
```

This matches exactly how the analytic `cylinder_side` preset stores the
block (duplicated seam column, seam appears as an i_min↔i_max
self-connection).

**How to do it in SolidWorks:** sketch a straight line on a plane through
the cylinder axis, then `Insert → Curve → Split Line → Projection`,
selecting the cylindrical face. One seam is preferred; if the export
behaves oddly with a single split, splitting the side into **two half
faces** (two seam lines 180 deg apart, named `cylinder_side_1`,
`cylinder_side_2`) is also perfectly fine — say which you did.

## General export rules (all three files)

- **One solid body per part file** — no assemblies, no multibody.
- Units: **millimeters**.
- Keep it plain: no fillets, chamfers, threads, or cosmetic features.
- **Name every face**: right-click the face → *Face Properties* → Name.
- **Also give each named face a unique color** (right-click face →
  Appearances): colors are the fallback identifier if names get dropped
  by the exporter (plan §20.1).
- Export: *File → Save As → STEP (*.step)* → **Options → set the version
  to AP242** (not the default AP214).
- Do NOT name edges — SolidWorks has no reliable edge naming, and pySurf
  will derive edges from named-face adjacency instead (e.g. "top circle"
  = the edge shared by `cylinder_side` and `top_cap`).

## File 1: `cylinder.step`

| item | value |
|---|---|
| shape | solid cylinder, ⌀50 mm x 100 mm long |
| axis | along **+x** (base at origin), matching our flow convention |
| side face | split with one axial seam line (see above) |
| face names | `cylinder_side`, `top_cap`, `bottom_cap` |

## File 2: `frustum.step`

| item | value |
|---|---|
| shape | solid conical frustum, base ⌀50 mm, top ⌀20 mm, 80 mm long |
| axis | along +x |
| side face | one axial seam line |
| face names | `cone_side`, `top_cap`, `bottom_cap` |

## File 3: `wing.step`

| item | value |
|---|---|
| shape | loft between two airfoil sections (NACA 0012 or anything handy) |
| root | 100 mm chord at y = 0 |
| tip | 60 mm chord at y = 300 mm (straight taper; sweep/twist optional) |
| trailing edge | **blunt** (cut ~0.5–1 mm flat) — a knife-edge TE makes tangent sliver faces |
| face names | `wing_upper`, `wing_lower`, `wing_te` (the blunt TE strip), `tip_cap`, `root_cap` (or leave the root open — say which) |

If the loft doesn't naturally split upper from lower at the leading
edge, add a split line along the LE curve so `wing_upper` / `wing_lower`
are separate faces.

## Where to put them

Create `cad_tests/` in the repo and drop the three `.step` files there
(committing them is fine — they are small).

## What happens next (so you know what the files feed)

1. `pysurf inspect-cad cad_tests/cylinder.step` (first Phase 2
   deliverable) lists faces/edges, recovered names/colors, and surface
   classification (plane / cylinder / cone / bspline). This tells us how
   much we can trust names vs. needing the color fallback.
2. Then the sidecar YAML gains a `geometry` section. Intended shape
   (final schema confirmed after step 1):

```yaml
project: {name: cad_cylinder, units: mm}

geometry:
  file: cylinder.step
  format: step_ap242

surfaces:
  cylinder_side:
    cad_face: cylinder_side      # face name in the STEP (color fallback ok)
    preset: cad_periodic_side    # meshed via the four_sided machinery
    points: {i: 129, j: 65}
  top_cap:
    cad_face: top_cap
    preset: cad_disk_ogrid
    center_block: {ni: 33, nj: 33}
    radial_points: 25
  bottom_cap:
    cad_face: bottom_cap
    preset: cad_disk_ogrid
    normal: "-z"                 # local frame, as with the analytic caps
    center_block: {ni: 33, nj: 33}
    radial_points: 25
```

Environment note: the STEP reader uses pythonOCC, which is conda-only:
`conda create -n pysurf-cad python=3.11 pythonocc-core -c conda-forge`.
