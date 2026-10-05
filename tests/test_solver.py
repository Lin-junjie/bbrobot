import math

import numpy as np
import pytest

from hotrunner.geometry import Annular, Circular, Rectangular
from hotrunner.materials import MATERIALS
from hotrunner.rheology import viscosity, zero_shear_viscosity
from hotrunner.solver import Segment, compute, default_segments, segment_pressure_drop

MM = 1e-3


def _shear_rate_from_stress(mat, tau, t_c):
    lo, hi = 1e-8, 1e8
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if viscosity(mat, mid, t_c) * mid < tau:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def _exact_tube_dp(mat, d, length, q, t_c):
    """圆管中广义牛顿流体的精确解：Q = πR³/τw³ ∫ τ² γ̇(τ) dτ。"""
    r = d / 2

    def flow(tw):
        taus = np.linspace(0, tw, 800)
        g = np.array([_shear_rate_from_stress(mat, t, t_c) if t > 0 else 0.0 for t in taus])
        return math.pi * r ** 3 / tw ** 3 * np.trapezoid(taus ** 2 * g, taus)

    lo, hi = 1.0, 1e8
    for _ in range(80):
        mid = math.sqrt(lo * hi)
        if flow(mid) < q:
            lo = mid
        else:
            hi = mid
    return 2 * mid * length / r


@pytest.mark.parametrize("name", ["PP", "PC", "PA66"])
def test_circular_matches_exact_solution(name):
    mat = MATERIALS[name]
    seg = Segment("t", Circular(6 * MM), 100 * MM)
    q = 40e-6
    dp = segment_pressure_drop(seg, mat, q, mat.t_default).pressure_drop
    exact = _exact_tube_dp(mat, 6 * MM, 100 * MM, q, mat.t_default)
    # Kozicki/局部 n 近似在 Cross 模型过渡区误差 < 3%，且偏保守（偏大）
    assert exact <= dp * 1.001
    assert dp == pytest.approx(exact, rel=0.03)


def test_newtonian_friction_factors():
    assert Rectangular(1, 1).newtonian_fre() == pytest.approx(14.227, rel=1e-3)
    assert Rectangular(1, 0.5).newtonian_fre() == pytest.approx(15.548, rel=1e-3)
    assert Rectangular(1, 1e-4).newtonian_fre() == pytest.approx(24.0, rel=1e-3)
    assert Annular(1, 0.999).newtonian_fre() == pytest.approx(24.0, rel=1e-3)
    a, b = Circular(1).kozicki()
    assert 16 * (a + b) == pytest.approx(16.0)
    a, b = Rectangular(1, 1).kozicki()
    assert (a, b) == pytest.approx((0.2121, 0.6766), abs=2e-3)


def test_power_law_slit_limit():
    """宽矩形在强剪切变稀区应接近平板缝隙的幂律解析解。"""
    mat = MATERIALS["PP"]
    w, h, length = 400 * MM, 2 * MM, 50 * MM
    q = 2e-4
    r = segment_pressure_drop(Segment("s", Rectangular(w, h), length), mat, q, 230)
    n = r.power_index
    v = q / (w * h)
    gamma_slit = (2 * n + 1) / (3 * n) * 6 * v / h
    assert r.shear_rate == pytest.approx(gamma_slit, rel=0.01)


def test_zero_volume_and_monotonic():
    mat = MATERIALS["ABS"]
    segs = default_segments()
    assert compute(segs, mat, 0.0, 1.0, 240).total_pressure_drop == 0.0
    dps = [compute(segs, mat, v * 1e-6, 1.0, 240).total_pressure_drop for v in (10, 50, 100, 200)]
    assert all(a < b for a, b in zip(dps, dps[1:]))
    hot = compute(segs, mat, 100e-6, 1.0, 260).total_pressure_drop
    assert hot < dps[2]


def test_parallel_split():
    mat = MATERIALS["PP"]
    one = segment_pressure_drop(Segment("a", Circular(5 * MM), 0.05, 1), mat, 10e-6, 230)
    four = segment_pressure_drop(Segment("a", Circular(5 * MM), 0.05, 4), mat, 40e-6, 230)
    assert four.pressure_drop == pytest.approx(one.pressure_drop)


def test_validation():
    with pytest.raises(ValueError):
        segment_pressure_drop(Segment("x", Annular(4 * MM, 5 * MM), 0.01), MATERIALS["PP"], 1e-6, 230)
    with pytest.raises(ValueError):
        compute(default_segments(), MATERIALS["PP"], 1e-4, 0, 230)


def test_library_viscosity_reasonable():
    for m in MATERIALS.values():
        eta = viscosity(m, 1000, m.t_default)
        assert 30 < eta < 600, m.name
        assert zero_shear_viscosity(m, m.t_max) < zero_shear_viscosity(m, m.t_min)


def test_plotting_renders():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from hotrunner import plotting

    mat = MATERIALS["PP"]
    segs = default_segments() + [Segment("方", Rectangular(6 * MM, 6 * MM), 0.02, 4)]
    res = compute(segs, mat, 100e-6, 1.5, 230)
    fig = Figure()
    plotting.draw_results(fig, segs, mat, res, 100e-6, 1.5, 230, (1e-6, 300e-6))
    fig.canvas.draw()
    for s in segs:
        plotting.draw_section(fig.add_subplot(111), s.section, s.name)
