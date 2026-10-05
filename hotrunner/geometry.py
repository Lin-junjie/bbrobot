"""流道截面几何：圆形、矩形（含方形）、环形。

压力降计算采用 Kozicki 广义方法（对圆管即 Rabinowitsch 修正）：

    γ̇w = (a + b·n') / n' · 8V / Dh
    ΔP = 4 τw L / Dh

其中 a、b 为截面几何常数，满足牛顿流体时 f·Re = 16 (a + b)。
本模块用解析/级数解精确求出 a + b，再用 Kozicki 文献表给出 a 的占比。
所有尺寸单位均为 m。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 矩形截面：短边/长边 α → a / (a + b)，取自 Kozicki 等 (1966) 的表格
_RECT_RATIO_TABLE = [
    (0.00, 0.5000 / 1.5000),
    (0.25, 0.3212 / 1.1394),
    (0.50, 0.2440 / 0.9716),
    (0.75, 0.2178 / 0.9044),
    (1.00, 0.2121 / 0.8887),
]


def _interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


class Section:
    kind: str = ""
    label: str = ""

    @property
    def area(self) -> float:
        raise NotImplementedError

    @property
    def perimeter(self) -> float:
        raise NotImplementedError

    @property
    def hydraulic_diameter(self) -> float:
        return 4.0 * self.area / self.perimeter

    def kozicki(self) -> tuple[float, float]:
        """返回几何常数 (a, b)。"""
        raise NotImplementedError

    def validate(self) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError


@dataclass
class Circular(Section):
    diameter: float

    kind = "circle"
    label = "圆形"

    @property
    def area(self):
        return math.pi * self.diameter ** 2 / 4.0

    @property
    def perimeter(self):
        return math.pi * self.diameter

    def kozicki(self):
        return 0.25, 0.75

    def validate(self):
        if self.diameter <= 0:
            raise ValueError("圆形流道直径必须大于 0")

    def describe(self):
        return f"Ø{self.diameter * 1e3:g}"

    def to_dict(self):
        return {"kind": self.kind, "diameter": self.diameter}


@dataclass
class Rectangular(Section):
    width: float
    height: float

    kind = "rect"

    @property
    def label(self):
        return "方形" if math.isclose(self.width, self.height) else "矩形"

    @property
    def area(self):
        return self.width * self.height

    @property
    def perimeter(self):
        return 2.0 * (self.width + self.height)

    @property
    def aspect(self) -> float:
        """短边/长边，0 < α ≤ 1。"""
        return min(self.width, self.height) / max(self.width, self.height)

    def newtonian_fre(self) -> float:
        """牛顿流体充分发展层流的 f·Re（基于水力直径），级数精确解。"""
        alpha = self.aspect
        # 半边长：长边 2A，短边 2B
        a_half = 1.0
        b_half = alpha
        s = 0.0
        for i in range(1, 400, 2):
            s += math.tanh(i * math.pi * a_half / (2.0 * b_half)) / i ** 5
        # Q·μ/G
        q = (4.0 * b_half ** 3 * a_half / 3.0) * (1.0 - 192.0 * b_half / (math.pi ** 5 * a_half) * s)
        area = 4.0 * a_half * b_half
        dh = 4.0 * area / (4.0 * (a_half + b_half))
        v = q / area
        return dh ** 2 / (2.0 * v)

    def kozicki(self):
        total = self.newtonian_fre() / 16.0
        ratio = _interp(_RECT_RATIO_TABLE, self.aspect)
        return ratio * total, (1.0 - ratio) * total

    def validate(self):
        if self.width <= 0 or self.height <= 0:
            raise ValueError("矩形流道宽、高必须大于 0")

    def describe(self):
        if math.isclose(self.width, self.height):
            return f"□{self.width * 1e3:g}"
        return f"{self.width * 1e3:g}×{self.height * 1e3:g}"

    def to_dict(self):
        return {"kind": self.kind, "width": self.width, "height": self.height}


@dataclass
class Annular(Section):
    outer_diameter: float
    inner_diameter: float

    kind = "annulus"
    label = "环形"

    @property
    def kappa(self) -> float:
        return self.inner_diameter / self.outer_diameter

    @property
    def area(self):
        return math.pi * (self.outer_diameter ** 2 - self.inner_diameter ** 2) / 4.0

    @property
    def perimeter(self):
        return math.pi * (self.outer_diameter + self.inner_diameter)

    def newtonian_fre(self) -> float:
        k = self.kappa
        if k <= 0:
            return 16.0
        if k >= 1 - 1e-9:
            return 24.0
        return 16.0 * (1 - k) ** 2 / ((1 + k ** 2) - (1 - k ** 2) / math.log(1 / k))

    def kozicki(self):
        total = self.newtonian_fre() / 16.0
        k = self.kappa
        # κ→0 退化为圆管 (a 占 1/4)，κ>0 时 Kozicki 表中 a 占比约为 1/3
        ratio = 0.25 if k <= 0 else 1.0 / 3.0
        return ratio * total, (1.0 - ratio) * total

    def validate(self):
        if self.outer_diameter <= 0 or self.inner_diameter < 0:
            raise ValueError("环形流道尺寸必须为正")
        if self.inner_diameter >= self.outer_diameter:
            raise ValueError("环形流道内径必须小于外径")

    def describe(self):
        return f"Ø{self.outer_diameter * 1e3:g}/Ø{self.inner_diameter * 1e3:g}"

    def to_dict(self):
        return {"kind": self.kind, "outer_diameter": self.outer_diameter,
                "inner_diameter": self.inner_diameter}


def section_from_dict(d: dict) -> Section:
    kind = d["kind"]
    if kind == "circle":
        return Circular(d["diameter"])
    if kind == "rect":
        return Rectangular(d["width"], d["height"])
    if kind == "annulus":
        return Annular(d["outer_diameter"], d["inner_diameter"])
    raise ValueError(f"未知截面类型 {kind!r}")
