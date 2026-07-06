# Four-sided patch design ("morphed rectangle" / p1–p2 edge pairs)

Design note for the `four_sided` preset — the generalization of pySurf from
analytic primitives to arbitrary user-defined patches, and the code path
that Phase 4 CAD meshing will flow through.

## Concept

Any surface patch bounded by **four edges** (straight lines, arcs, or
curved splines) is treated as a rectangle that has been morphed in 3D:

```text
   D ────── top ────── C            (0,1) ────────── (1,1)
   │                    │              │                │
 left                 right    <==   logical unit square
   │                    │              │                │
   A ──── bottom ────── B            (0,0) ────────── (1,0)
```

The user names the two pairs of opposite edges:

```text
p1 pair:  bottom / top     ->  block edges j_min / j_max
p2 pair:  left / right     ->  block edges i_min / i_max
```

The mesher discretizes each edge, then fills the interior by marching
from each point on an edge to the corresponding point on its opposite
edge. Any geometry decomposed into such patches (with shared edges)
becomes a conformal multiblock structured surface mesh.

## The math: transfinite interpolation (TFI)

The interior fill is the linear Coons patch, already implemented in
`pysurf/meshing/tfi.py`:

```text
P(s,t) = (1-t) B(s) + t T(s) + (1-s) L(t) + s R(t) - bilinear corner term
```

**Key caveat — TFI does not automatically "follow the contour".** It
blends through 3D space; interior points lie on the intended surface only
when that surface *is* the Coons surface of its edges (planar, ruled,
lofted patches). For a genuinely curved surface there are two remedies,
per plan §9.3:

1. **Parameter-space TFI (preferred with CAD):** run the rectangle
   mapping in the surface's (u,v) parameter space, then evaluate S(u,v).
   Every point lands exactly on the surface.
2. **3D TFI + projection:** interpolate in 3D, then closest-point-project
   onto the target surface. Works without a clean parameterization; this
   is also the engine behind the bounding-box-projection idea (project a
   box-face grid onto a wing suction surface — but *fit* the boundary
   grid line to the trim curve rather than clipping cells, since a
   structured block must stay a full ni x nj array).

## Preconditions (what makes a patch four-sideable)

- Exactly four boundary edges meeting at four corners (endpoint
  coincidence is validated; sliver corners near 0/180 deg give bad cells
  — split the patch instead).
- Opposite edges share the point count: p1 pair shares ni, p2 pair nj.
- Patches with 3 or 5+ edges, interior holes, or strong concavity must be
  subdivided first (the user-guided blocking philosophy, plan §2.2).
- Pure TFI can fold on concave patches: Laplacian/elliptic smoothing and
  the folding detector (`min_normal_dot < 0`) are the guards.

Terminology: this is a *boundary-conforming mapped mesh* (not conformal
in the angle-preserving sense).

## Global edge registry — conformity by construction

Every edge is defined **once** in a global registry and referenced by
name from patches (plan §6.3). Two patches naming the same edge receive
the identical discretized point set, so shared edges match exactly with
no tolerance games. Validation: opposite-pair counts, corner closure,
duplicate names.

Edge direction is detected automatically from endpoint matching, so users
never need to worry which way a spline was authored; reversal is handled
like everywhere else in the connectivity layer.

## Proposed YAML schema

```yaml
edges:                      # global registry: defined once, shared by patches
  le_spline:
    points: 65
    spacing: {kind: cosine}
    curve: {spline: [[x,y,z], [x,y,z], ...]}     # interpolating spline
  te_line:
    points: 65
    spacing: uniform
    curve: {line: [[0,0,0], [1,0,0]]}
  root_arc:
    points: 33
    curve: {arc: {center: [..], radius: r, start_deg: a0, end_deg: a1, plane_normal: [..]}}
  tip_curve:
    points: 33
    curve: {file: tip.dat}                       # Selig-style point file

surfaces:
  panel_a:
    preset: four_sided
    edges: {j_min: te_line, j_max: le_spline, i_min: root_arc, i_max: tip_curve}
    # equivalent pairing view: p1 = (j_min, j_max), p2 = (i_min, i_max)
    interior:
      smoothing: {type: laplacian, iterations: 50}
    project_to: none        # later: analytic surface | CAD face (Phase 4)
```

Controls, in order of importance:

1. **Edge registry conformity** (counts, shared discretization).
2. **Corners**: four-edge closure, auto direction detection.
3. **Per-edge spacing** (uniform/cosine/sine/geometric/tanh/user — built),
   propagated into the interior via chord-length blending in TFI.
4. **Interior quality**: smoothing iterations; later boundary
   orthogonality weighting and elliptic smoothing.
5. **Projection target**: none (Coons surface) | analytic | CAD.

## Relationship to the roadmap

- The **wing preset** is this machinery plus section lofting.
- **Phase 4 CAD meshing is the same pipeline** with one substitution:
  boundary curves come from named STEP edges instead of YAML splines, and
  `project_to` points at the CAD face (parameter-space TFI when the UV is
  clean, projection fallback otherwise).

## Implementation checklist

- [ ] `curves.py`: line / arc / interpolating spline / point-file curve
      types with arc-length discretization (reuse `resample_polyline`)
- [ ] global edge registry in the spec parser + count/corner validation
- [ ] `four_sided` preset: registry edges -> TFI -> optional smoothing
- [ ] `project_to` hook (analytic surfaces first, CAD faces in Phase 4)
- [ ] tests: reproduce plane/annulus-quadrant meshes via four_sided;
      folding guard on a concave patch; shared-edge conformity between
      two four_sided patches
