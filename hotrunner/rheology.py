"""Cross-WLF 粘度模型。

    η0(T, p) = D1 · exp( -A1 (T - T*) / (A2 + T - T*) )
    T*  = D2 + D3 · p
    A2  = Ã2 + D3 · p
    η(γ̇, T, p) = η0 / (1 + (η0 γ̇ / τ*)^(1-n))
"""

from __future__ import annotations

import math

from .materials import Material

KELVIN = 273.15


def zero_shear_viscosity(mat: Material, t_c: float, p: float = 0.0) -> float:
    """零剪切粘度 η0 [Pa·s]，t_c 为熔体温度 [°C]，p 为压力 [Pa]。"""
    t = t_c + KELVIN
    t_star = mat.D2 + mat.D3 * p
    a2 = mat.A2t + mat.D3 * p
    denom = a2 + t - t_star
    if denom <= 0:
        raise ValueError(f"温度 {t_c} °C 超出 {mat.name} 的 Cross-WLF 有效范围")
    return mat.D1 * math.exp(-mat.A1 * (t - t_star) / denom)


def viscosity(mat: Material, shear_rate: float, t_c: float, p: float = 0.0) -> float:
    """表观粘度 η [Pa·s]。"""
    eta0 = zero_shear_viscosity(mat, t_c, p)
    if shear_rate <= 0:
        return eta0
    return eta0 / (1.0 + (eta0 * shear_rate / mat.tau_s) ** (1.0 - mat.n))


def local_power_index(mat: Material, shear_rate: float, t_c: float, p: float = 0.0) -> float:
    """局部幂律指数 n' = d ln τ / d ln γ̇，介于 n 与 1 之间。"""
    if shear_rate <= 0:
        return 1.0
    eta0 = zero_shear_viscosity(mat, t_c, p)
    x = (eta0 * shear_rate / mat.tau_s) ** (1.0 - mat.n)
    return 1.0 - (1.0 - mat.n) * x / (1.0 + x)
