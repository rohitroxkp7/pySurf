import numpy as np
import pytest

from pysurf.meshing.edges import distribution, from_spec, resample_polyline


ALL_KINDS = [
    ("uniform", {}),
    ("cosine", {}),
    ("sine", {}),
    ("sine", {"side": "end"}),
    ("geometric", {"ratio": 1.1}),
    ("tanh", {"beta": 2.5}),
]


@pytest.mark.parametrize("kind,params", ALL_KINDS)
def test_endpoints_count_monotonic(kind, params):
    s = distribution(21, kind, **params)
    assert len(s) == 21
    assert s[0] == 0.0 and s[-1] == 1.0
    assert np.all(np.diff(s) > 0)


@pytest.mark.parametrize("kind", ["uniform", "cosine", "tanh"])
def test_symmetric_kinds(kind):
    s = distribution(17, kind)
    assert np.allclose(s + s[::-1], 1.0, atol=1e-12)


def test_geometric_ratio_property():
    r = 1.25
    s = distribution(11, "geometric", ratio=r)
    d = np.diff(s)
    assert np.allclose(d[1:] / d[:-1], r, rtol=1e-9)
    # ratio > 1 clusters at the start
    assert d[0] < d[-1]


def test_sine_clusters_correct_end():
    d_start = np.diff(distribution(21, "sine", side="start"))
    assert d_start[0] < d_start[-1]
    d_end = np.diff(distribution(21, "sine", side="end"))
    assert d_end[0] > d_end[-1]


def test_user_values():
    vals = [0.0, 0.1, 0.5, 1.0]
    s = distribution(4, "user", values=vals)
    assert np.allclose(s, vals)
    with pytest.raises(ValueError):
        distribution(4, "user", values=[0.0, 0.5, 0.4, 1.0])
    with pytest.raises(ValueError):
        distribution(3, "user", values=[0.0, 0.5, 0.9])


def test_errors():
    with pytest.raises(ValueError):
        distribution(1, "uniform")
    with pytest.raises(ValueError):
        distribution(5, "nope")
    with pytest.raises(ValueError):
        distribution(5, "sine", side="middle")


def test_from_spec_forms():
    assert np.allclose(from_spec(5, None), np.linspace(0, 1, 5))
    assert np.allclose(from_spec(5, "uniform"), np.linspace(0, 1, 5))
    s = from_spec(5, {"kind": "geometric", "ratio": 2.0})
    assert np.allclose(np.diff(s)[1:] / np.diff(s)[:-1], 2.0)


def test_resample_polyline():
    line = np.column_stack([np.linspace(0, 2, 50), np.zeros(50), np.zeros(50)])
    s = distribution(5, "uniform")
    out = resample_polyline(line, s)
    assert np.allclose(out[:, 0], [0.0, 0.5, 1.0, 1.5, 2.0], atol=1e-9)
