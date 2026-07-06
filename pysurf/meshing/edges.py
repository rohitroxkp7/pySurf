"""Edge discretization: 1-D point-distribution functions.

Every distribution returns ``n`` monotonically increasing values on
``[0, 1]`` including both endpoints.  These normalized parameters are the
building block for all patch meshers: a preset evaluates its analytic
curve/surface at these parameter values.

Supported kinds:

    uniform                 equal spacing
    cosine                  clusters at both ends (half-cosine stretching)
    sine                    clusters at one end (param: side='start'|'end')
    geometric               geometric growth   (param: ratio, >1 clusters at start)
    tanh                    clusters at both ends (param: beta, larger = stronger)
    user                    explicit values    (param: values=[...])
"""

from __future__ import annotations

import numpy as np


def distribution(n: int, kind: str = "uniform", **params) -> np.ndarray:
    """Return ``n`` normalized parameter values on [0, 1]."""
    if n < 2:
        raise ValueError(f"need at least 2 points, got n={n}")

    t = np.linspace(0.0, 1.0, n)

    if kind == "uniform":
        s = t

    elif kind == "cosine":
        s = 0.5 * (1.0 - np.cos(np.pi * t))

    elif kind == "sine":
        side = params.get("side", "start")
        if side == "start":
            # derivative -> 0 at t=0: clusters near the start
            s = 1.0 - np.cos(0.5 * np.pi * t)
        elif side == "end":
            # derivative -> 0 at t=1: clusters near the end
            s = np.sin(0.5 * np.pi * t)
        else:
            raise ValueError(f"sine spacing: side must be 'start' or 'end', got {side!r}")

    elif kind == "geometric":
        ratio = float(params.get("ratio", 1.1))
        if ratio <= 0.0:
            raise ValueError(f"geometric spacing: ratio must be > 0, got {ratio}")
        if abs(ratio - 1.0) < 1.0e-12:
            s = t
        else:
            # n-1 intervals with sizes d, d*r, d*r^2, ... normalized to sum 1.
            # ratio > 1 makes the first interval smallest (clusters at start).
            k = np.arange(n, dtype=float)
            s = (ratio**k - 1.0) / (ratio ** (n - 1) - 1.0)

    elif kind == "tanh":
        beta = float(params.get("beta", 2.0))
        if beta <= 0.0:
            raise ValueError(f"tanh spacing: beta must be > 0, got {beta}")
        s = 0.5 * (1.0 + np.tanh(beta * (2.0 * t - 1.0)) / np.tanh(beta))

    elif kind == "user":
        values = params.get("values")
        if values is None:
            raise ValueError("user spacing requires 'values'")
        s = np.asarray(values, dtype=float)
        if s.ndim != 1 or len(s) != n:
            raise ValueError(f"user spacing: expected {n} values, got shape {s.shape}")
        if abs(s[0]) > 1.0e-12 or abs(s[-1] - 1.0) > 1.0e-12:
            raise ValueError("user spacing: values must start at 0 and end at 1")
        if np.any(np.diff(s) <= 0.0):
            raise ValueError("user spacing: values must be strictly increasing")

    else:
        raise ValueError(f"unknown spacing kind '{kind}'")

    # Pin the endpoints exactly so shared edges match bit-for-bit.
    s = np.asarray(s, dtype=float).copy()
    s[0], s[-1] = 0.0, 1.0
    return s


def from_spec(n: int, spec: dict | str | None) -> np.ndarray:
    """Build a distribution from a YAML-style spec.

    ``spec`` may be None (uniform), a string kind, or a dict like
    ``{"kind": "geometric", "ratio": 1.08}``.
    """
    if spec is None:
        return distribution(n, "uniform")
    if isinstance(spec, str):
        return distribution(n, spec)
    if isinstance(spec, dict):
        params = dict(spec)
        kind = params.pop("kind", "uniform")
        return distribution(n, kind, **params)
    raise TypeError(f"spacing spec must be None, str, or dict, got {type(spec)}")


def resample_polyline(points: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Resample a polyline at normalized arc-length positions ``s``.

    ``points`` is (m, 3) ordered along the curve; ``s`` is a distribution
    on [0, 1].  Returns (len(s), 3).  Used to rediscretize an existing
    (finely sampled) curve with a chosen spacing; endpoints are preserved
    exactly.
    """
    points = np.asarray(points, dtype=float)
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    total = arc[-1]
    if total <= 0.0:
        raise ValueError("degenerate polyline: zero total length")
    arc /= total
    out = np.empty((len(s), 3))
    for c in range(3):
        out[:, c] = np.interp(s, arc, points[:, c])
    out[0], out[-1] = points[0], points[-1]
    return out
