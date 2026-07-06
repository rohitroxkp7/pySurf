from pathlib import Path

import pytest

from pysurf.cli import main
from pysurf.specs.parser import SpecError, build_from_spec, load_spec

EXAMPLES = sorted(
    p for p in (Path(__file__).parent.parent / "examples").glob("*/blocking.yaml")
)


@pytest.mark.parametrize("spec_path", EXAMPLES, ids=lambda p: p.parent.name)
def test_examples_build(spec_path):
    spec = load_spec(spec_path)
    blocks = build_from_spec(spec)
    assert len(blocks) >= 1


def test_cylinder_example_block_count():
    spec = load_spec(Path(__file__).parent.parent / "examples/cylinder/blocking.yaml")
    blocks = build_from_spec(spec)
    assert len(blocks) == 11  # side + 2 caps x 5


def test_unknown_option_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "surfaces:\n"
        "  s:\n"
        "    preset: cylinder_side\n"
        "    radius: 1.0\n"
        "    height: 2.0\n"
        "    points: {i: 9, j: 5}\n"
        "    radiuss: 2.0\n"
    )
    with pytest.raises(SpecError, match="unknown option"):
        build_from_spec(load_spec(bad))


def test_missing_preset_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("surfaces:\n  s:\n    radius: 1.0\n")
    with pytest.raises(SpecError, match="preset"):
        build_from_spec(load_spec(bad))


def test_cli_mesh_cylinder(tmp_path, capsys):
    spec = Path(__file__).parent.parent / "examples/cylinder/blocking.yaml"
    rc = main(["mesh", str(spec), "--outdir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "watertight" in out
    assert (tmp_path / "cylinder.vtm").exists()
    assert (tmp_path / "cylinder.fmt").exists()
    assert (tmp_path / "run_pyhyp_cylinder.py").exists()


def test_cli_validate_ok(capsys):
    spec = Path(__file__).parent.parent / "examples/sphere/blocking.yaml"
    rc = main(["validate", str(spec)])
    assert rc == 0
    assert "valid" in capsys.readouterr().out


def test_cli_presets(capsys):
    rc = main(["presets"])
    assert rc == 0
    assert "cone_ogrid" in capsys.readouterr().out
