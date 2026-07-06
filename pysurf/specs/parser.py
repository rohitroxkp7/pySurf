"""YAML/JSON blocking-spec parser and preset dispatcher.

A spec file describes meshing intent::

    project:
      name: cylinder_test

    surfaces:
      cylinder_side:
        preset: cylinder_side          # or a legacy alias like analytic_cylinder
        radius: 1.0
        height: 5.0
        points: {i: 129, j: 65}

      top_cap:
        preset: disk_ogrid
        radius: 1.0
        z: 5.0
        normal: "+z"
        center_block: {ni: 33, nj: 33}
        radial_points: 25

    output:
      directory: output
      vtm: true
      plot3d: true

Each ``surfaces`` entry dispatches to one preset mesher and yields one or
more named StructuredBlocks (multi-block presets use the surface key as
the name prefix).  Unknown keys in a surface entry are an error, so typos
fail fast.
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

from pysurf.blocks import StructuredBlock
from pysurf.meshing.annulus import annulus
from pysurf.meshing.cone import cone_ogrid, cone_side
from pysurf.meshing.cylinder import cylinder_side
from pysurf.meshing.disk_ogrid import disk_ogrid
from pysurf.meshing.plane import plane_patch
from pysurf.meshing.sphere import sphere_cubed


class SpecError(ValueError):
    """A problem in the blocking spec file."""


PRESET_ALIASES = {
    "analytic_cylinder": "cylinder_side",
    "periodic_quad_patch": "cylinder_side",
    "analytic_cone": "cone_side",
    "analytic_cone_ogrid": "cone_ogrid",
    "analytic_disk_ogrid": "disk_ogrid",
    "ogrid_cap": "disk_ogrid",
    "analytic_annulus": "annulus",
    "analytic_plane": "plane",
    "rectangle": "plane",
    "analytic_sphere": "sphere_cubed",
    "sphere": "sphere_cubed",
}

PRESETS = (
    "cylinder_side",
    "cone_side",
    "cone_ogrid",
    "disk_ogrid",
    "annulus",
    "plane",
    "sphere_cubed",
)


def load_spec(path) -> dict:
    path = Path(path)
    if not path.exists():
        raise SpecError(f"spec file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)
    if not isinstance(spec, dict):
        raise SpecError(f"spec file {path} did not parse to a mapping")
    if "surfaces" not in spec or not isinstance(spec["surfaces"], dict) or not spec["surfaces"]:
        raise SpecError("spec needs a non-empty 'surfaces' mapping")
    return spec


# ----------------------------------------------------------------------
# per-surface helpers


def _pop_points(cfg: dict, name: str) -> tuple[int, int]:
    pts = cfg.pop("points", None)
    if not isinstance(pts, dict) or "i" not in pts or "j" not in pts:
        raise SpecError(f"surface '{name}': needs points: {{i: <ni>, j: <nj>}}")
    return int(pts["i"]), int(pts["j"])


def _pop_spacing(cfg: dict) -> tuple:
    spacing = cfg.pop("spacing", {}) or {}
    return spacing.get("i"), spacing.get("j")


def _pop_theta0(cfg: dict) -> float:
    if "theta0_deg" in cfg:
        return math.radians(float(cfg.pop("theta0_deg")))
    return float(cfg.pop("theta0", 0.0))


def _pop_n_arc(cfg: dict, name: str) -> int:
    if "center_block" in cfg:
        cb = cfg.pop("center_block")
        ni, nj = int(cb.get("ni", 0)), int(cb.get("nj", 0))
        if ni != nj or ni < 2:
            raise SpecError(
                f"surface '{name}': center_block must have ni == nj >= 2, got {ni} x {nj}"
            )
        return ni
    if "n_arc" in cfg:
        return int(cfg.pop("n_arc"))
    raise SpecError(f"surface '{name}': needs center_block: {{ni: n, nj: n}} or n_arc: n")


def _pop_n_radial(cfg: dict, name: str) -> int:
    for key in ("radial_points", "n_radial"):
        if key in cfg:
            return int(cfg.pop(key))
    raise SpecError(f"surface '{name}': needs radial_points (or n_radial)")


def _reject_leftovers(cfg: dict, name: str, preset: str):
    if cfg:
        raise SpecError(
            f"surface '{name}' (preset {preset}): unknown option(s) {sorted(cfg)}"
        )


# ----------------------------------------------------------------------


def build_surface(name: str, cfg_in: dict) -> list[StructuredBlock]:
    """Build the block(s) for one surface entry."""
    if not isinstance(cfg_in, dict):
        raise SpecError(f"surface '{name}': entry must be a mapping")
    cfg = dict(cfg_in)
    cfg.pop("topology", None)  # informational, per the plan doc
    cfg.pop("surface_type", None)
    preset = cfg.pop("preset", None) or cfg.pop("method", None)
    if preset is None:
        raise SpecError(f"surface '{name}': missing 'preset' (or 'method')")
    preset = PRESET_ALIASES.get(preset, preset)
    if preset not in PRESETS:
        raise SpecError(
            f"surface '{name}': unknown preset '{preset}'; available: {', '.join(PRESETS)}"
        )

    try:
        if preset == "cylinder_side":
            ni, nj = _pop_points(cfg, name)
            i_sp, j_sp = _pop_spacing(cfg)
            blocks = [
                cylinder_side(
                    radius=float(cfg.pop("radius")),
                    height=float(cfg.pop("height")),
                    ni=ni, nj=nj,
                    center=cfg.pop("center", (0.0, 0.0, 0.0)),
                    axis=str(cfg.pop("axis", "+z")),
                    theta0=_pop_theta0(cfg),
                    i_spacing=i_sp, j_spacing=j_sp,
                    name=name,
                )
            ]

        elif preset == "cone_side":
            ni, nj = _pop_points(cfg, name)
            i_sp, j_sp = _pop_spacing(cfg)
            blocks = [
                cone_side(
                    radius_bottom=float(cfg.pop("radius_bottom")),
                    radius_top=float(cfg.pop("radius_top")),
                    height=float(cfg.pop("height")),
                    ni=ni, nj=nj,
                    center=cfg.pop("center", (0.0, 0.0, 0.0)),
                    axis=str(cfg.pop("axis", "+z")),
                    theta0=_pop_theta0(cfg),
                    i_spacing=i_sp, j_spacing=j_sp,
                    name=name,
                )
            ]

        elif preset == "cone_ogrid":
            blocks = cone_ogrid(
                n_arc=_pop_n_arc(cfg, name),
                n_radial=_pop_n_radial(cfg, name),
                height=float(cfg.pop("height")),
                radius=cfg.pop("radius", None),
                semi_axes=cfg.pop("semi_axes", None),
                center=cfg.pop("center", (0.0, 0.0, 0.0)),
                axis=str(cfg.pop("axis", "+z")),
                theta0=_pop_theta0(cfg),
                square_frac=float(cfg.pop("square_frac", 0.5)),
                radial_spacing=cfg.pop("radial_spacing", None),
                name_prefix=name,
            )

        elif preset == "disk_ogrid":
            blocks = disk_ogrid(
                n_arc=_pop_n_arc(cfg, name),
                n_radial=_pop_n_radial(cfg, name),
                radius=cfg.pop("radius", None),
                semi_axes=cfg.pop("semi_axes", None),
                z=float(cfg.pop("z", 0.0)),
                center=cfg.pop("center", (0.0, 0.0, 0.0)),
                axis=str(cfg.pop("axis", "+z")),
                theta0=_pop_theta0(cfg),
                square_frac=float(cfg.pop("square_frac", 0.5)),
                normal=str(cfg.pop("normal", "+z")),
                split_center=bool(cfg.pop("split_center", False)),
                radial_spacing=cfg.pop("radial_spacing", None),
                name_prefix=name,
            )

        elif preset == "annulus":
            ni, nj = _pop_points(cfg, name)
            i_sp, j_sp = _pop_spacing(cfg)
            r_in = cfg.pop("radius_inner", cfg.pop("r_inner", None))
            r_out = cfg.pop("radius_outer", cfg.pop("r_outer", None))
            if r_in is None or r_out is None:
                raise SpecError(f"surface '{name}': needs radius_inner and radius_outer")
            blocks = [
                annulus(
                    radius_inner=float(r_in), radius_outer=float(r_out),
                    ni=ni, nj=nj,
                    z=float(cfg.pop("z", 0.0)),
                    center=cfg.pop("center", (0.0, 0.0, 0.0)),
                    axis=str(cfg.pop("axis", "+z")),
                    theta0=_pop_theta0(cfg),
                    normal=str(cfg.pop("normal", "+z")),
                    i_spacing=i_sp, j_spacing=j_sp,
                    name=name,
                )
            ]

        elif preset == "plane":
            ni, nj = _pop_points(cfg, name)
            i_sp, j_sp = _pop_spacing(cfg)
            blocks = [
                plane_patch(
                    origin=cfg.pop("origin"),
                    u=cfg.pop("u"),
                    v=cfg.pop("v"),
                    ni=ni, nj=nj,
                    i_spacing=i_sp, j_spacing=j_sp,
                    name=name,
                )
            ]

        elif preset == "sphere_cubed":
            n = cfg.pop("points", None)
            if isinstance(n, dict):
                n = n.get("n") or n.get("i")
            if n is None:
                n = cfg.pop("n", None)
            if n is None:
                raise SpecError(f"surface '{name}': needs points: <n> (points per face edge)")
            blocks = sphere_cubed(
                radius=float(cfg.pop("radius")),
                n=int(n),
                center=cfg.pop("center", (0.0, 0.0, 0.0)),
                name_prefix=name,
            )

        else:  # pragma: no cover - guarded above
            raise SpecError(f"unhandled preset {preset}")

    except KeyError as exc:
        raise SpecError(f"surface '{name}' (preset {preset}): missing option {exc}") from exc

    _reject_leftovers(cfg, name, preset)
    return blocks


def build_from_spec(spec: dict) -> list[StructuredBlock]:
    """Build all blocks from a parsed spec, preserving surface order."""
    blocks: list[StructuredBlock] = []
    names_seen: set[str] = set()
    for name, cfg in spec["surfaces"].items():
        new = build_surface(str(name), cfg)
        for blk in new:
            if blk.name in names_seen:
                raise SpecError(f"duplicate block name '{blk.name}'")
            names_seen.add(blk.name)
        blocks.extend(new)
    return blocks
