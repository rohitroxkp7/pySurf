from pathlib import Path

import pytest

from pysurf.cad.step_scan import format_report, scan_step

STEP = Path(__file__).parent.parent / "step_files" / "cylinder.step"


@pytest.mark.skipif(not STEP.exists(), reason="sample STEP file not present")
def test_scan_cylinder_names_and_types():
    r = scan_step(STEP)
    assert r["ap"] == "AP214"
    assert r["units"] == "inch"
    assert r["n_faces"] == 4
    assert r["n_named_faces"] == 4
    names = sorted(f["name"] for f in r["faces"])
    assert names == ["bottom_cap", "cylinder_side", "cylinder_side", "top_cap"]
    cyls = [f for f in r["faces"] if f["surface"] == "CYLINDRICAL_SURFACE"]
    assert len(cyls) == 2
    assert all(abs(f["radius"] - 1.408937293167895) < 1e-9 for f in cyls)


@pytest.mark.skipif(not STEP.exists(), reason="sample STEP file not present")
def test_scan_report_renders():
    text = format_report(scan_step(STEP))
    assert "cylinder_side" in text
    assert "AP214" in text
