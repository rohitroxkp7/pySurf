# Structured Surface Mesh Generator Development Plan

## 1. Project Goal

Build a codebase that can read CAD geometry exported from SolidWorks, identify or use user-provided labels for primitive/easily meshable surface patches, generate conformal structured surface meshes locally on each patch, and assemble them into a global multiblock structured surface mesh suitable for later export to CGNS, Plot3D, or a pyHyp/ADflow-oriented workflow.

The guiding principle is:

```text
Global complex surface
→ split into simple named local surfaces
→ mesh each surface in local coordinates
→ enforce matching edges
→ assemble as multiblock structured surface mesh
```

The project should **not** initially attempt fully automatic structured mesh generation for arbitrary CAD. Instead, the user should prepare the CAD model in SolidWorks by splitting surfaces into simple, named, meshable patches. The code then reads the geometry and meshing intent, generates local structured grids, and connects them globally.

---

## 2. Core Philosophy

### 2.1 Local/Global Principle

Treat the full geometry as an assembly of local primitive or quasi-primitive surface blocks. Each block is meshed independently in its own local coordinates, then assembled globally using shared named edges.

Each surface block should be represented as:

```text
Block b: X_b[i, j], Y_b[i, j], Z_b[i, j]
```

The global mesh is not one giant structured array. It is a collection of structured blocks:

```text
Block 1: P1[i, j]
Block 2: P2[i, j]
Block 3: P3[i, j]
...
Connectivity table between blocks
```

This is effectively a **block-structured surface mesh**.

### 2.2 Avoid Full Automation Initially

Do not start by trying to discover all block topology automatically from arbitrary CAD.

Instead:

1. Use SolidWorks to split geometry into clean, mostly four-sided patches.
2. Name faces and edges in SolidWorks where possible.
3. Export the geometry to STEP AP242.
4. Provide a sidecar YAML/JSON file containing meshing intent.
5. Let the code generate structured grids for known patch types.

This is a much more realistic and useful first version.

---

## 3. Recommended File Workflow

### 3.1 CAD Geometry Input

Preferred geometry exchange format:

```text
STEP AP242
```

Recommended export path:

```text
SolidWorks → STEP AP242 → OpenCASCADE/pythonOCC → structured surface mesh generator
```

Alternative high-fidelity option if available:

```text
SolidWorks → Parasolid .x_t/.x_b → Parasolid kernel
```

But for an open-source or Python/C++ pipeline, STEP AP242 with OpenCASCADE is the most practical choice.

### 3.2 Meshing Intent Input

Use a sidecar metadata file:

```text
geometry.step
blocking.yaml
```

or:

```text
geometry.step
blocking.json
```

The CAD file stores geometry and topology. The YAML/JSON file stores meshing decisions.

Do **not** rely only on STEP metadata for meshing intent. Face/edge names may not always survive export/import reliably, so the sidecar file should be treated as the source of truth.

### 3.3 Mesh Output Formats

Initial output formats:

1. VTK/VTU/VTP preview output for debugging and visualization.
2. Simple custom JSON/HDF5 debug format for block data.
3. Plot3D multiblock surface output.
4. Structured CGNS output.

Target final output:

```text
Multiblock structured CGNS or Plot3D
```

For ADflow/pyHyp-style workflows, preserving block structure and edge connectivity is more important than simply writing a file with quadrilateral cells.

---

## 4. SolidWorks Preparation Guidelines

Before exporting the geometry, prepare it so that the mesher has an easy job.

### 4.1 Split the Geometry into Meshable Faces

The user should split the model into patches that are:

- Four-sided when possible.
- Free of tiny sliver faces.
- Free of unnecessary holes.
- Free of complex multi-loop trims when avoidable.
- Aligned with natural mesh directions.
- Topologically compatible with neighboring patches.

Examples of good named surfaces:

```text
wing_upper
wing_lower
leading_edge_patch
trailing_edge_patch
tip_cap
cylinder_side
cylinder_top_cap
cylinder_bottom_cap
fillet_patch_01
```

### 4.2 Name Edges

Edges should also be named when possible. Example edge names:

```text
wing_leading_edge
wing_trailing_edge
wing_root_edge
wing_tip_edge
cyl_top_circle
cyl_bottom_circle
cyl_seam
cap_outer_circle
```

These edge names are used in the sidecar YAML/JSON file to specify point counts, grading, orientation, and connectivity.

### 4.3 Split Periodic Faces

For cylinders, cones, and other periodic surfaces, explicitly introduce a seam if needed. Structured meshing requires a logical start/end direction.

For example, a cylinder side surface should have:

```text
circumferential direction: i
axial direction: j
seam edge: explicit edge where theta = 0/2π
```

---

## 5. Sidecar Metadata Design

The sidecar file should describe all surfaces, edges, point counts, topological types, and meshing algorithms.

### 5.1 Example YAML Structure

```yaml
project:
  name: cylinder_test
  units: mm
  description: Structured surface meshing test case

geometry:
  file: geometry.step
  format: step_ap242

edges:
  cyl_top_circle:
    points: 129
    spacing: uniform

  cyl_bottom_circle:
    points: 129
    spacing: uniform

  cyl_seam:
    points: 65
    spacing: uniform

  cap_outer_circle:
    points: 129
    spacing: uniform

surfaces:
  cylinder_side:
    topology: periodic_quad_patch
    surface_type: cylinder
    method: analytic_cylinder
    periodic_i: true
    directions:
      i: circumferential
      j: axial
    edges:
      j_min: cyl_bottom_circle
      j_max: cyl_top_circle
      seam: cyl_seam
    points:
      i: 129
      j: 65

  top_cap:
    topology: disk_ogrid
    surface_type: plane_or_disk
    method: ogrid_cap
    outer_edge: cyl_top_circle
    center_block:
      ni: 33
      nj: 33
    radial_points: 49

output:
  preview_vtk: true
  plot3d: true
  cgns: true
```

### 5.2 Four-Sided Patch Example

```yaml
surfaces:
  wing_upper:
    topology: four_sided_patch
    surface_type: bspline_or_nurbs
    method: transfinite_interpolation
    edges:
      i_min: wing_root_edge
      i_max: wing_tip_edge
      j_min: wing_leading_edge
      j_max: wing_trailing_edge
    points:
      i: 81
      j: 161
    smoothing:
      type: elliptic
      iterations: 100
```

### 5.3 Edge Point Count Rules

For a conformal structured mesh, shared edges must have identical point counts.

For a normal four-sided patch:

```text
bottom edge points == top edge points
left edge points   == right edge points
```

The code should validate this before meshing.

---

## 6. Internal Data Model

### 6.1 Core Objects

Suggested Python-style data model:

```python
class MeshProject:
    cad_model: CADModel
    edges: dict[str, EdgeSpec]
    surfaces: dict[str, SurfaceSpec]
    blocks: list[StructuredBlock]
    connectivity: list[BlockConnection]

class EdgeSpec:
    name: str
    points: int
    spacing: str
    grading: dict | None
    cad_edge_ref: object | None

class SurfaceSpec:
    name: str
    topology: str
    surface_type: str
    method: str
    edges: dict[str, str]
    points: dict[str, int]
    smoothing: dict | None

class StructuredBlock:
    name: str
    ni: int
    nj: int
    xyz: ndarray  # shape = (ni, nj, 3)
    edge_names: dict[str, str]
    local_coordinates: dict | None

class BlockConnection:
    block_a: str
    edge_a: str
    block_b: str
    edge_b: str
    orientation: str
```

### 6.2 CAD Topology Graph

Build a graph representation of the CAD model:

```text
nodes = faces/surfaces
edges = shared CAD edges between faces
```

This graph is useful for:

- Verifying that named surfaces touch where expected.
- Finding neighboring patches.
- Detecting missing connectivity.
- Propagating edge point counts.
- Exporting block-to-block connectivity.

### 6.3 Global Edge Registry

Maintain a global edge registry:

```python
edge_registry = {
    "wing_leading_edge": EdgeSpec(...),
    "wing_trailing_edge": EdgeSpec(...),
    "cyl_top_circle": EdgeSpec(...),
}
```

Each block references global edge names. This ensures conformal matching.

---

## 7. CAD Reader Module

### 7.1 Recommended Library

Use OpenCASCADE through one of the following:

- C++ OpenCASCADE directly.
- pythonOCC.
- CadQuery/OCP wrappers.

For metadata, prefer the XDE/CAF route instead of only a plain STEP geometry reader.

Desired reader behavior:

```text
STEP AP242
→ read CAD model
→ recover faces, edges, wires, shells, solids
→ recover names/colors/properties if available
→ classify primitive surfaces
→ map CAD topology to internal graph
```

### 7.2 Surface Classification

For every CAD face, classify the underlying surface as one of:

```text
plane
cylinder
cone
sphere
torus
surface_of_revolution
surface_of_extrusion
bezier
bspline
unknown
```

This classification helps choose a local meshing method.

### 7.3 Boundary Loop Extraction

For every face, extract:

- Outer wire.
- Inner wires, if any.
- Edges in each wire.
- Edge orientation.
- Vertices/corners.
- Parametric UV curves if available.

This is needed for four-sided patch meshing.

---

## 8. Supported Patch Types

Start with a small set of patch types and expand later.

### 8.1 Four-Sided Patch

General structured quadrilateral patch.

Inputs:

```text
four boundary curves
point counts in i and j
CAD surface map S(u,v) if available
```

Methods:

- Transfinite interpolation.
- CAD UV-space interpolation.
- Optional surface projection.
- Optional smoothing.

Output:

```text
P[i,j], shape = (ni, nj, 3)
```

### 8.2 Analytic Plane Patch

For planar rectangles, squares, and general four-sided planar regions.

Methods:

- Bilinear interpolation.
- Transfinite interpolation.
- Optional local x-y coordinate frame.

### 8.3 Cylindrical Periodic Patch

For cylinder side surfaces.

Natural coordinates:

```text
i = circumferential/theta direction
j = axial/z direction
```

Analytic mapping:

```text
x = x0 + R cos(theta) e1 + R sin(theta) e2 + z axis_dir
```

Support:

- Periodic i direction.
- Explicit seam edge.
- Matching top/bottom circular edges.

### 8.4 Disk O-Grid Cap

For circular caps.

Topology:

```text
center square block
+ 4 curved quadrilateral blocks around the square
```

This avoids a singular polar point at the center.

Useful for:

- Cylinder caps.
- Circular inlet/outlet faces.
- Disk-like surfaces.

### 8.5 Annular Patch

For ring-like surfaces with inner and outer loops.

Natural coordinates:

```text
i = circumferential direction
j = radial direction
```

### 8.6 Wing Surface Patch

For parametric wing surfaces.

Natural coordinates:

```text
i = spanwise direction
j = chordwise direction
```

or vice versa, depending on convention.

Generated from:

- Root airfoil.
- Tip airfoil.
- Spanwise sections.
- Twist.
- Sweep.
- Taper.
- Dihedral.

---

## 9. Meshing Algorithms

### 9.1 Edge Discretization

Each named edge must be discretized first.

Supported spacing types:

```text
uniform
cosine
sine
geometric
tanh
user_defined
```

Example:

```yaml
edges:
  wing_leading_edge:
    points: 161
    spacing: cosine

  boundary_layer_edge:
    points: 65
    spacing: geometric
    ratio: 1.08
```

The edge discretizer should return ordered points:

```text
E[k], k = 0...N-1
```

### 9.2 Transfinite Interpolation for Four-Sided Patches

Given four boundary curves:

```text
bottom: C0(s)
top:    C1(s)
left:   D0(t)
right:  D1(t)
```

Generate interior points using TFI:

```text
P(s,t) = blend of four sides - correction for four corners
```

This is the basic workhorse for structured surface patch generation.

### 9.3 CAD Surface Projection

For curved NURBS/BSpline surfaces, a TFI grid in 3D may not lie exactly on the CAD face.

Possible strategies:

1. Generate points in the CAD face's UV parameter space and evaluate S(u,v).
2. Generate approximate 3D TFI points and project them back to the CAD surface.
3. Use boundary curves in UV space and perform TFI in UV coordinates.

Preferred strategy:

```text
If UV representation is clean:
    do TFI in UV space and evaluate S(u,v)
else:
    do 3D TFI and project to surface
```

### 9.4 Surface Smoothing

After initial point generation, apply optional smoothing while keeping boundary edges fixed.

Methods to implement:

1. Laplacian smoothing.
2. Elliptic smoothing.
3. Spring analogy smoothing.
4. Orthogonality improvement near boundaries.

Initial version can use Laplacian smoothing only.

### 9.5 Edge Orientation Handling

Neighboring blocks may traverse the same shared edge in opposite directions.

The code must detect whether:

```text
edge A order == edge B order
```

or:

```text
edge A order == reversed(edge B order)
```

This affects connectivity export.

---

## 10. Connectivity and Assembly

### 10.1 Block Edge Names

Every block has four logical edges:

```text
i_min
i_max
j_min
j_max
```

Each logical edge maps to a global named edge:

```yaml
surfaces:
  wing_upper:
    edges:
      i_min: wing_root_edge
      i_max: wing_tip_edge
      j_min: wing_leading_edge
      j_max: wing_trailing_edge
```

### 10.2 Conformal Edge Matching

Before assembly, validate:

```text
shared edge point counts match
shared edge endpoints match geometrically
shared edge curves are coincident within tolerance
edge orientations are known
```

### 10.3 Assembly Strategy

Do **not** merge all blocks into one unstructured mesh internally.

Keep:

```text
list of structured blocks
+ connectivity table
```

This preserves the structured nature of the grid.

### 10.4 Connectivity Table Example

```yaml
connectivity:
  - block_a: cylinder_side
    edge_a: j_max
    block_b: top_cap_north
    edge_b: outer_arc
    orientation: same

  - block_a: top_cap_center
    edge_a: i_max
    block_b: top_cap_east
    edge_b: inner_edge
    orientation: reversed
```

The code should generate as much of this automatically as possible from shared named edges, but user override should be allowed.

---

## 11. Cylinder Example Topology

### 11.1 Cylinder Side

The side surface of a cylinder is naturally structured:

```text
i = circumferential direction
j = axial direction
```

One periodic block is enough:

```text
Block: cylinder_side
P[i,j]
periodic in i
```

### 11.2 Cylinder Cap

Use an O-grid-like disk topology:

```text
1 center square block
4 surrounding curved quadrilateral blocks
```

This gives:

```text
top_cap_center
top_cap_north
top_cap_east
top_cap_south
top_cap_west
```

Same for bottom cap.

### 11.3 Full Cylinder Surface Block List

```text
1. cylinder_side
2. top_cap_center
3. top_cap_north
4. top_cap_east
5. top_cap_south
6. top_cap_west
7. bottom_cap_center
8. bottom_cap_north
9. bottom_cap_east
10. bottom_cap_south
11. bottom_cap_west
```

This is a good first test case.

---

## 12. Wing Example Topology

For a simple wing, start with:

```text
wing_upper
wing_lower
leading_edge_patch
trailing_edge_patch
tip_cap
root_patch, if needed
```

Each surface should be a structured patch:

```text
P[i,j]
```

Suggested directions:

```text
i = spanwise
j = chordwise
```

or:

```text
i = chordwise
j = spanwise
```

Pick one convention and enforce it everywhere.

---

## 13. Validation Checks

The code should fail early when the topology is not meshable.

### 13.1 Geometry Checks

- Surface exists in CAD file.
- Named edge exists in CAD file.
- Edge belongs to specified surface.
- Surface has expected number of boundary loops.
- Four-sided patch has four usable sides.
- Periodic surface has a seam when required.

### 13.2 Mesh Checks

- All blocks have valid `ni`, `nj`.
- No zero-area cells.
- No inverted cells.
- Boundary points lie on CAD surfaces within tolerance.
- Shared edge points match within tolerance.
- Adjacent blocks have compatible orientation.

### 13.3 Quality Metrics

Compute and report:

- Minimum cell area.
- Maximum skewness estimate.
- Aspect ratio estimate.
- Smoothness ratio.
- Boundary orthogonality estimate.
- Edge mismatch error between connected blocks.

---

## 14. Visualization and Debugging

Visualization output is essential.

Minimum debug outputs:

1. Surface blocks colored by block name.
2. Edge names shown as labels.
3. Node indices optionally shown for small meshes.
4. Block connectivity graph.
5. Warnings for unmatched edges.
6. Mesh quality report.

Recommended output formats:

```text
.vtp / .vtk for ParaView
.png quick plots for simple cases
.json debug dump of blocks and connectivity
```

---

## 15. Suggested Repository Structure

```text
structured_surface_mesher/
├── README.md
├── plan.md
├── pyproject.toml
├── examples/
│   ├── cylinder/
│   │   ├── geometry.step
│   │   ├── blocking.yaml
│   │   └── run.py
│   ├── rectangle_patch/
│   ├── disk_ogrid/
│   └── simple_wing/
├── src/
│   └── ssm/
│       ├── __init__.py
│       ├── cad/
│       │   ├── reader.py
│       │   ├── topology.py
│       │   └── classify.py
│       ├── specs/
│       │   ├── schema.py
│       │   └── parser.py
│       ├── geometry/
│       │   ├── curves.py
│       │   ├── surfaces.py
│       │   └── projection.py
│       ├── meshing/
│       │   ├── edges.py
│       │   ├── tfi.py
│       │   ├── cylinder.py
│       │   ├── disk_ogrid.py
│       │   ├── smoothing.py
│       │   └── quality.py
│       ├── assembly/
│       │   ├── blocks.py
│       │   ├── connectivity.py
│       │   └── validation.py
│       ├── io/
│       │   ├── vtk_writer.py
│       │   ├── plot3d_writer.py
│       │   └── cgns_writer.py
│       └── cli.py
└── tests/
    ├── test_edge_spacing.py
    ├── test_tfi_patch.py
    ├── test_cylinder.py
    ├── test_disk_ogrid.py
    └── test_connectivity.py
```

---

## 16. Implementation Roadmap

### Phase 0: Minimal Geometry-Free Prototype

Goal: prove the structured block data model without CAD.

Implement:

- Edge spacing functions.
- Four-sided TFI patch from analytic boundary curves.
- Cylinder side analytic patch.
- Disk O-grid cap.
- StructuredBlock class.
- VTK preview writer.

Test cases:

1. Rectangle patch.
2. Curved four-sided patch.
3. Cylinder side.
4. Disk O-grid.
5. Full cylinder surface assembled from blocks.

This phase does not require STEP/OpenCASCADE yet.

### Phase 1: YAML/JSON Spec Parser

Goal: drive the prototype from a metadata file.

Implement:

- YAML parser.
- Edge registry.
- Surface spec parser.
- Point-count validation.
- Block generation from spec.

Test:

```bash
ssm mesh examples/cylinder/blocking.yaml
```

Output:

```text
cylinder_blocks.vtp
quality_report.txt
connectivity.json
```

### Phase 2: CAD Reader Integration

Goal: read STEP files and map named faces/edges.

Implement:

- STEP reader through OpenCASCADE/pythonOCC/OCP.
- Face and edge extraction.
- Surface classification.
- Name/color/property extraction if available.
- CAD topology graph.

Initial CAD test:

```text
SolidWorks cylinder split into named side/cap faces
```

### Phase 3: CAD-Based Edge Discretization

Goal: discretize actual CAD curves instead of analytic placeholder curves.

Implement:

- Edge length parameterization.
- Uniform spacing along CAD edge.
- Curvature-aware spacing later.
- Named edge matching.
- Endpoint tolerance checks.

### Phase 4: CAD-Based Four-Sided Surface Meshing

Goal: mesh CAD faces as structured patches.

Implement:

- Extract four boundary curves of a face.
- Perform TFI in 3D or UV space.
- Project points back to CAD surface if needed.
- Validate surface point error.

### Phase 5: Connectivity and Export

Goal: assemble final multiblock surface mesh.

Implement:

- Shared edge detection from named edges.
- Orientation detection.
- Connectivity table.
- Plot3D surface output.
- Structured CGNS output.

### Phase 6: pyHyp/ADflow-Oriented Workflow

Goal: make the surface grid usable for volume mesh generation.

Implement:

- Export format compatible with pyHyp or conversion tools.
- Boundary naming conventions.
- Multiblock connectivity validation.
- Optional wake attachment surfaces for airfoil/wing cases.

---

## 17. First Development Target

The first useful target should be a full cylinder surface, because it exercises important topology without being too complex.

### 17.1 Cylinder Test Case

Generate:

```text
cylinder_side: periodic structured patch
top_cap: O-grid cap
bottom_cap: O-grid cap
```

Outputs:

```text
cylinder_surface.vtp
cylinder_blocks.json
quality_report.txt
```

Validation:

- Top side edge matches top cap outer boundary.
- Bottom side edge matches bottom cap outer boundary.
- No inverted cells.
- All blocks have valid structured indexing.

### 17.2 After Cylinder, Move to Wing

Second target:

```text
simple wing surface generated from airfoil sections
```

This avoids CAD complexity and directly supports the ADflow/pyHyp use case.

Third target:

```text
SolidWorks-exported STEP wing with named faces/edges
```

---

## 18. Important Design Decisions

### 18.1 Keep Blocks Separate

Do not merge all surface patches into one unstructured mesh.

Keep:

```text
structured blocks + connectivity
```

This is required for downstream structured-grid workflows.

### 18.2 Sidecar Metadata Is the Source of Truth

Even if face/edge names survive STEP export, use the sidecar YAML/JSON to define meshing intent.

CAD tells the code:

```text
what the geometry is
```

Sidecar metadata tells the code:

```text
how to mesh it
```

### 18.3 Start with User-Guided Blocking

Do not initially attempt automatic blocking of arbitrary CAD.

The initial system should assume:

```text
The user has split the CAD into meshable named patches.
```

### 18.4 Build Many Small Meshers

Instead of one huge general mesher, implement multiple local patch meshers:

```text
four_sided_patch_mesher
cylinder_patch_mesher
disk_ogrid_mesher
annulus_mesher
wing_patch_mesher
```

A dispatcher selects the correct one based on `topology` and `method` in the YAML/JSON file.

---

## 19. Possible CLI Design

Example commands:

```bash
ssm validate examples/cylinder/blocking.yaml
ssm mesh examples/cylinder/blocking.yaml --preview
ssm inspect-cad geometry.step
ssm list-faces geometry.step
ssm list-edges geometry.step
ssm quality cylinder_blocks.json
ssm export-cgns cylinder_blocks.json cylinder_surface.cgns
```

Useful development commands:

```bash
ssm debug-face geometry.step --face cylinder_side
ssm debug-edge geometry.step --edge cyl_top_circle
ssm plot-connectivity cylinder_blocks.json
```

---

## 20. Risks and Hard Parts

### 20.1 Name Preservation

Face and edge names may not survive every CAD export/import path reliably.

Mitigation:

- Use STEP AP242.
- Use OpenCASCADE XDE/CAF reader.
- Use colors as fallback labels.
- Use sidecar metadata.
- Provide manual mapping tools.

### 20.2 Edge Orientation

Shared edges may be reversed between neighboring blocks.

Mitigation:

- Compare endpoint coordinates.
- Store orientation explicitly.
- Allow user override in YAML.

### 20.3 Complex Trimmed NURBS Faces

Some CAD faces may have ugly UV parameterization or trimming curves.

Mitigation:

- Ask user to split faces more cleanly in CAD.
- Prefer four-sided patches.
- Use projection fallback.

### 20.4 Junctions and Fillets

Wing-body junctions, fillets, and intersections are difficult.

Mitigation:

- Delay until later phases.
- Start with simple cylinders, disks, rectangles, wings, and ducts.
- Build specialized junction block templates later.

### 20.5 Structured Volume Mesh Is Harder

This project initially generates structured **surface** meshes. Volume meshing is harder and should be handled separately or via pyHyp/ICEM/Pointwise-style extrusion.

---

## 21. Near-Term TODO List

1. Create repository skeleton.
2. Implement `StructuredBlock` class.
3. Implement edge spacing functions.
4. Implement VTK/VTP preview writer.
5. Implement four-sided TFI patch from analytic curves.
6. Implement analytic cylinder side patch.
7. Implement disk O-grid cap patch.
8. Assemble full cylinder surface from blocks.
9. Add mesh quality checks.
10. Add YAML input parser.
11. Add connectivity validation.
12. Add simple Plot3D writer.
13. Integrate STEP reader.
14. Add named face/edge lookup.
15. Add CAD curve discretization.
16. Add CAD surface projection.
17. Add structured CGNS writer.

---

## 22. Minimal First Prototype Specification

The first prototype does not need CAD.

It should take this YAML:

```yaml
project:
  name: analytic_cylinder

surfaces:
  cylinder_side:
    topology: periodic_quad_patch
    method: analytic_cylinder
    radius: 1.0
    height: 5.0
    points:
      i: 129
      j: 65

  top_cap:
    topology: disk_ogrid
    method: analytic_disk_ogrid
    radius: 1.0
    z: 5.0
    center_block:
      ni: 33
      nj: 33
    radial_points: 49

  bottom_cap:
    topology: disk_ogrid
    method: analytic_disk_ogrid
    radius: 1.0
    z: 0.0
    center_block:
      ni: 33
      nj: 33
    radial_points: 49

output:
  vtk: analytic_cylinder.vtp
```

And output a visible multiblock cylinder surface mesh.

This will prove the local/global approach before adding CAD complexity.

---

## 23. Long-Term Vision

The long-term goal is a user-guided structured surface mesher where CAD preparation and code automation work together:

```text
User/CAD system:
    split complex geometry into simple named patches
    identify surfaces and edges
    define meshing intent

Mesher:
    read CAD
    classify surfaces
    generate local structured meshes
    enforce conformity
    assemble multiblock mesh
    export solver-ready structured grid
```

This approach is realistic, extensible, and directly aligned with structured CFD workflows such as ADflow/pyHyp-style grid generation.
