"""图表绘制：分段压力降柱状图、沿程压力分布、压力降-注射量曲线、截面图。

与界面无关，既供 GUI 调用，也可在无界面环境下导出图片。
"""

from __future__ import annotations

import numpy as np
from matplotlib import rcParams
from matplotlib.patches import Circle, Rectangle

from .geometry import Annular, Circular, Rectangular, Section
from .materials import Material
from .solver import Result, Segment, compute

rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC",
    "Source Han Sans SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei", "DejaVu Sans",
]
rcParams["axes.unicode_minus"] = False

MPA = 1e6
CM3 = 1e-6

BAR_COLOR = "#2a78b8"
LINE_COLOR = "#d1495b"
CURVE_COLOR = "#2a78b8"
MELT_COLOR = "#f4a259"
STEEL_COLOR = "#9aa5b1"


def draw_results(fig, segments: list[Segment], mat: Material, result: Result,
                 shot_volume: float, injection_time: float, t_c: float,
                 vol_range: tuple[float, float]) -> None:
    """在 fig 上绘制三幅图。shot_volume、vol_range 单位为 m³。"""
    fig.clear()
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.45, wspace=0.28)
    ax_bar = fig.add_subplot(gs[0, 0])
    ax_prof = fig.add_subplot(gs[0, 1])
    ax_curve = fig.add_subplot(gs[1, :])

    names = [r.segment.name for r in result.segments]
    dps = np.array([r.pressure_drop / MPA for r in result.segments])
    total = dps.sum()

    # 1. 分段压力降
    x = np.arange(len(names))
    bars = ax_bar.bar(x, dps, color=BAR_COLOR, width=0.6)
    for rect, v in zip(bars, dps):
        pct = v / total * 100 if total > 0 else 0
        ax_bar.annotate(f"{v:.1f}\n({pct:.0f}%)", (rect.get_x() + rect.get_width() / 2, v),
                        xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8)
    ax_bar.set_xticks(x, names, rotation=20, ha="right", fontsize=8)
    ax_bar.set_ylabel("压力降 [MPa]")
    ax_bar.set_title("分段压力降", fontsize=10)
    ax_bar.set_ylim(0, max(dps.max() * 1.3, 1e-3) if len(dps) else 1)
    ax_bar.grid(axis="y", alpha=0.3)

    # 2. 沿程压力分布（入口压力 = 总压降，浇口处为 0）
    pos = [0.0]
    pres = [total]
    for r in result.segments:
        pos.append(pos[-1] + r.segment.length * 1e3)
        pres.append(pres[-1] - r.pressure_drop / MPA)
    ax_prof.plot(pos, pres, "-o", color=LINE_COLOR, ms=4)
    ax_prof.fill_between(pos, pres, color=LINE_COLOR, alpha=0.12)
    for p in pos[1:-1]:
        ax_prof.axvline(p, color="0.75", lw=0.8, ls="--")
    ax_prof.set_xlabel("沿流动路径距离 [mm]")
    ax_prof.set_ylabel("熔体压力 [MPa]")
    ax_prof.set_title("沿程压力分布（浇口处取 0）", fontsize=10)
    ax_prof.set_xlim(0, pos[-1] if pos[-1] > 0 else 1)
    ax_prof.set_ylim(0, max(total * 1.1, 1e-3))
    ax_prof.grid(alpha=0.3)

    # 3. 总压力降随注射量变化
    vmin, vmax = vol_range
    vols = np.linspace(vmin, vmax, 60)
    curve = [compute(segments, mat, v, injection_time, t_c).total_pressure_drop / MPA for v in vols]
    ax_curve.plot(vols / CM3, curve, color=CURVE_COLOR, lw=2)
    ax_curve.plot([shot_volume / CM3], [total], "o", color=LINE_COLOR, ms=9, zorder=5)
    ax_curve.annotate(f"{shot_volume / CM3:.1f} cm³ → {total:.1f} MPa",
                      (shot_volume / CM3, total), xytext=(10, -14), textcoords="offset points",
                      fontsize=9, color=LINE_COLOR)
    ax_curve.axvline(shot_volume / CM3, color=LINE_COLOR, lw=0.8, ls="--")
    ax_curve.set_xlabel("注射量 [cm³]")
    ax_curve.set_ylabel("热流道总压力降 [MPa]")
    ax_curve.set_title(f"总压力降 - 注射量（注射时间 {injection_time:g} s，"
                       f"{mat.name} @ {t_c:g} °C）", fontsize=10)
    ax_curve.set_xlim(vmin / CM3, vmax / CM3)
    ax_curve.set_ylim(0, max(max(curve) * 1.1, 1e-3))
    ax_curve.grid(alpha=0.3)

    fig.suptitle(f"热流道总压力降：{total:.2f} MPa", fontsize=12, fontweight="bold")


def draw_section(ax, section: Section, title: str = "") -> None:
    """绘制流道截面（单位 mm），钢材为灰色，熔体为橙色。"""
    ax.clear()
    ax.set_aspect("equal")
    ax.axis("off")
    if isinstance(section, Circular):
        d = section.diameter * 1e3
        size = d
        ax.add_patch(Rectangle((-size, -size), 2 * size, 2 * size, color=STEEL_COLOR))
        ax.add_patch(Circle((0, 0), d / 2, color=MELT_COLOR))
        _dim(ax, -d / 2, d / 2, 0, f"Ø{d:g}")
    elif isinstance(section, Rectangular):
        w, h = section.width * 1e3, section.height * 1e3
        size = max(w, h)
        ax.add_patch(Rectangle((-size, -size), 2 * size, 2 * size, color=STEEL_COLOR))
        ax.add_patch(Rectangle((-w / 2, -h / 2), w, h, color=MELT_COLOR))
        _dim(ax, -w / 2, w / 2, 0, f"{w:g}")
        ax.annotate(f"{h:g}", (w / 2, 0), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9)
    elif isinstance(section, Annular):
        do, di = section.outer_diameter * 1e3, section.inner_diameter * 1e3
        size = do
        ax.add_patch(Rectangle((-size, -size), 2 * size, 2 * size, color=STEEL_COLOR))
        ax.add_patch(Circle((0, 0), do / 2, color=MELT_COLOR))
        if di > 0:
            ax.add_patch(Circle((0, 0), di / 2, color="#5c6773"))
        _dim(ax, -do / 2, do / 2, do * 0.32, f"Ø{do:g}")
        if di > 0:
            _dim(ax, -di / 2, di / 2, -do * 0.05, f"Ø{di:g}", fontsize=8)
    else:
        size = 1
    ax.set_xlim(-size, size)
    ax.set_ylim(-size, size)
    if title:
        ax.set_title(title, fontsize=9)


def _dim(ax, x0, x1, y, text, fontsize=9):
    ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", lw=0.9))
    ax.text((x0 + x1) / 2, y, text, ha="center", va="bottom", fontsize=fontsize)
