"""热流道分段压力降计算。

熔体沿一条流动路径（主射嘴 → 分流板 → 热嘴 → 浇口）依次流过各段，
总压力降为各段压力降之和。某段若有 N 条并联支路（如一出四的热嘴），
则该段每条支路的流量为 Q / N。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Section, section_from_dict
from .materials import Material
from .rheology import viscosity, local_power_index


@dataclass
class Segment:
    name: str
    section: Section
    length: float  # [m]
    parallel: int = 1  # 并联支路数

    def validate(self) -> None:
        self.section.validate()
        if self.length <= 0:
            raise ValueError(f"{self.name}: 长度必须大于 0")
        if self.parallel < 1:
            raise ValueError(f"{self.name}: 并联数至少为 1")

    def to_dict(self) -> dict:
        return {"name": self.name, "section": self.section.to_dict(),
                "length": self.length, "parallel": self.parallel}

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(d["name"], section_from_dict(d["section"]), d["length"], d.get("parallel", 1))


@dataclass
class SegmentResult:
    segment: Segment
    flow_rate: float      # 单支路流量 [m³/s]
    velocity: float       # 平均流速 [m/s]
    shear_rate: float     # 壁面剪切速率 [1/s]
    viscosity: float      # 壁面粘度 [Pa·s]
    shear_stress: float   # 壁面剪切应力 [Pa]
    power_index: float    # 局部幂律指数 n'
    pressure_drop: float  # [Pa]
    residence_time: float # 平均流速下的流经时间 [s]


@dataclass
class Result:
    segments: list[SegmentResult] = field(default_factory=list)

    @property
    def total_pressure_drop(self) -> float:
        return sum(r.pressure_drop for r in self.segments)


def segment_pressure_drop(seg: Segment, mat: Material, q_total: float, t_c: float,
                          tol: float = 1e-8, max_iter: int = 200) -> SegmentResult:
    """计算单段压力降。q_total 为进入热流道系统的总体积流量 [m³/s]。"""
    seg.validate()
    sec = seg.section
    q = q_total / seg.parallel
    area = sec.area
    dh = sec.hydraulic_diameter
    v = q / area
    residence = seg.length / v if v > 0 else float("inf")
    if q <= 0:
        return SegmentResult(seg, 0.0, 0.0, 0.0, viscosity(mat, 0.0, t_c), 0.0, 1.0, 0.0, residence)

    a, b = sec.kozicki()
    nominal = 8.0 * v / dh
    n_loc = 1.0
    for _ in range(max_iter):
        gamma = nominal * (a + b * n_loc) / n_loc
        n_new = local_power_index(mat, gamma, t_c)
        if abs(n_new - n_loc) < tol:
            n_loc = n_new
            break
        n_loc = 0.5 * (n_loc + n_new)
    gamma = nominal * (a + b * n_loc) / n_loc
    eta = viscosity(mat, gamma, t_c)
    tau = eta * gamma
    dp = 4.0 * tau * seg.length / dh
    return SegmentResult(seg, q, v, gamma, eta, tau, n_loc, dp, residence)


def compute(segments: list[Segment], mat: Material, shot_volume: float,
            injection_time: float, t_c: float) -> Result:
    """shot_volume [m³] 经过热流道的注射量（全部型腔 + 冷料），injection_time [s]。"""
    if injection_time <= 0:
        raise ValueError("注射时间必须大于 0")
    if shot_volume < 0:
        raise ValueError("注射量不能为负")
    q = shot_volume / injection_time
    return Result([segment_pressure_drop(s, mat, q, t_c) for s in segments])


def default_segments() -> list[Segment]:
    """一出四热流道系统示例。"""
    from .geometry import Circular, Annular
    mm = 1e-3
    return [
        Segment("主射嘴", Circular(10 * mm), 60 * mm, 1),
        Segment("一级分流道", Circular(12 * mm), 100 * mm, 2),
        Segment("二级分流道", Circular(10 * mm), 60 * mm, 4),
        Segment("热嘴流道", Circular(6 * mm), 80 * mm, 4),
        Segment("热嘴尖(环形)", Annular(4 * mm, 2 * mm), 10 * mm, 4),
    ]
