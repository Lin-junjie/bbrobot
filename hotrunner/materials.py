"""内置常用材料的 Cross-WLF 粘度参数库。

参数格式与 Moldflow 一致（SI 单位）：
    n      —— 幂律指数（无量纲）
    tau_s  —— τ*，临界剪切应力 [Pa]
    D1     —— [Pa·s]
    D2     —— [K]
    D3     —— [K/Pa]（压力相关项，库中取 0）
    A1     —— [-]
    A2t    —— Ã2 [K]

注意：库中数值为同类牌号的“典型值”，按各材料在推荐加工温度、
剪切速率 1000 1/s 下的典型粘度标定，仅用于方案评估。
做精确计算时请使用所选牌号的实测数据（可在界面中自定义材料）。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Material:
    name: str
    n: float
    tau_s: float
    D1: float
    D2: float
    A1: float
    A2t: float = 51.6
    D3: float = 0.0
    t_min: float = 180.0  # 推荐熔体温度下限 [°C]
    t_max: float = 260.0  # 推荐熔体温度上限 [°C]
    description: str = ""

    @property
    def t_default(self) -> float:
        return round((self.t_min + self.t_max) / 2.0)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Material":
        return cls(**d)


_LIBRARY = [
    Material("PP", 0.28, 2.5e4, 4.6166e12, 263.15, 25.0, t_min=200, t_max=260,
             description="聚丙烯（均聚，通用级）"),
    Material("HDPE", 0.33, 4.0e4, 1.2869e11, 153.15, 20.0, t_min=200, t_max=260,
             description="高密度聚乙烯"),
    Material("ABS", 0.29, 3.5e4, 5.5269e12, 373.15, 27.0, t_min=220, t_max=260,
             description="丙烯腈-丁二烯-苯乙烯（通用级）"),
    Material("PC", 0.20, 5.0e5, 4.7763e12, 417.15, 30.0, t_min=280, t_max=320,
             description="聚碳酸酯（中粘度）"),
    Material("PC/ABS", 0.25, 1.0e5, 8.0410e12, 383.15, 28.0, t_min=240, t_max=280,
             description="PC/ABS 合金"),
    Material("PA6", 0.40, 1.5e5, 1.1306e11, 323.15, 25.0, t_min=230, t_max=270,
             description="尼龙 6（未增强）"),
    Material("PA66", 0.40, 2.0e5, 1.2713e11, 323.15, 25.0, t_min=270, t_max=300,
             description="尼龙 66（未增强）"),
    Material("POM", 0.30, 1.0e5, 1.5810e12, 223.15, 25.0, t_min=190, t_max=215,
             description="聚甲醛（共聚）"),
    Material("PBT", 0.35, 1.0e5, 2.1366e11, 323.15, 25.0, t_min=235, t_max=265,
             description="聚对苯二甲酸丁二醇酯"),
    Material("PS", 0.25, 3.0e4, 1.9614e12, 373.15, 26.0, t_min=200, t_max=240,
             description="通用级聚苯乙烯 GPPS"),
    Material("PMMA", 0.25, 1.0e5, 1.0267e13, 378.15, 28.0, t_min=220, t_max=260,
             description="聚甲基丙烯酸甲酯（亚克力）"),
    Material("PET", 0.40, 1.5e5, 2.2961e11, 342.15, 25.0, t_min=270, t_max=290,
             description="聚对苯二甲酸乙二醇酯"),
]

MATERIALS: dict[str, Material] = {m.name: m for m in _LIBRARY}


def get_material(name: str) -> Material:
    try:
        return MATERIALS[name]
    except KeyError:
        raise KeyError(f"材料库中没有 {name!r}，可选：{', '.join(MATERIALS)}") from None
