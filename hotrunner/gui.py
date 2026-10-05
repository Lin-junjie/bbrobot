"""热流道压力降计算 —— 图形界面（tkinter + matplotlib）。"""

from __future__ import annotations

import csv
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import plotting  # noqa: E402  (同时完成中文字体设置)
from .geometry import Annular, Circular, Rectangular  # noqa: E402
from .materials import MATERIALS, Material  # noqa: E402
from .solver import Segment, compute, default_segments  # noqa: E402

MM = 1e-3
CM3 = 1e-6

SECTION_TYPES = ["圆形", "方形", "矩形", "环形"]


def section_type_name(sec) -> str:
    if isinstance(sec, Circular):
        return "圆形"
    if isinstance(sec, Annular):
        return "环形"
    return sec.label  # 方形 / 矩形


class SegmentDialog(tk.Toplevel):
    """新增/编辑流道段，带截面实时预览。"""

    def __init__(self, master, segment: Segment | None = None):
        super().__init__(master)
        self.title("流道段参数")
        self.transient(master)
        self.resizable(False, False)
        self.result: Segment | None = None

        seg = segment or Segment("新流道段", Circular(8 * MM), 50 * MM, 1)
        sec = seg.section
        self.v_name = tk.StringVar(value=seg.name)
        self.v_type = tk.StringVar(value=section_type_name(sec))
        self.v_d = tk.DoubleVar(value=getattr(sec, "diameter", 8 * MM) / MM)
        self.v_w = tk.DoubleVar(value=getattr(sec, "width", 8 * MM) / MM)
        self.v_h = tk.DoubleVar(value=getattr(sec, "height", 6 * MM) / MM)
        self.v_do = tk.DoubleVar(value=getattr(sec, "outer_diameter", 6 * MM) / MM)
        self.v_di = tk.DoubleVar(value=getattr(sec, "inner_diameter", 3 * MM) / MM)
        self.v_len = tk.DoubleVar(value=seg.length / MM)
        self.v_par = tk.IntVar(value=seg.parallel)

        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="n")
        r = 0
        ttk.Label(frm, text="名称").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_name, width=16).grid(row=r, column=1, pady=2)
        r += 1
        ttk.Label(frm, text="截面类型").grid(row=r, column=0, sticky="w")
        cb = ttk.Combobox(frm, textvariable=self.v_type, values=SECTION_TYPES,
                          state="readonly", width=14)
        cb.grid(row=r, column=1, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self._layout())
        r += 1

        self.dim_frame = ttk.Frame(frm)
        self.dim_frame.grid(row=r, column=0, columnspan=2, sticky="we")
        r += 1
        ttk.Label(frm, text="长度 [mm]").grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.v_len, width=16).grid(row=r, column=1, pady=2)
        r += 1
        ttk.Label(frm, text="并联支路数").grid(row=r, column=0, sticky="w")
        ttk.Spinbox(frm, from_=1, to=128, textvariable=self.v_par, width=14).grid(row=r, column=1, pady=2)
        r += 1
        ttk.Label(frm, text="（流量按并联数平分）", foreground="gray").grid(row=r, column=0, columnspan=2)
        r += 1
        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="确定", command=self._ok).pack(side="left", padx=4)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="left", padx=4)

        self.fig = Figure(figsize=(2.6, 2.6), dpi=90)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().grid(row=0, column=1, padx=(0, 10), pady=10)

        for v in (self.v_d, self.v_w, self.v_h, self.v_do, self.v_di):
            v.trace_add("write", lambda *a: self._preview())
        self._layout()
        self.grab_set()
        self.wait_visibility()
        self.focus_set()

    def _layout(self):
        for w in self.dim_frame.winfo_children():
            w.destroy()
        t = self.v_type.get()
        fields = {
            "圆形": [("直径 [mm]", self.v_d)],
            "方形": [("边长 [mm]", self.v_w)],
            "矩形": [("宽 [mm]", self.v_w), ("高 [mm]", self.v_h)],
            "环形": [("外径 [mm]", self.v_do), ("内径(芯/鱼雷) [mm]", self.v_di)],
        }[t]
        for i, (lbl, var) in enumerate(fields):
            ttk.Label(self.dim_frame, text=lbl).grid(row=i, column=0, sticky="w")
            ttk.Entry(self.dim_frame, textvariable=var, width=16).grid(row=i, column=1, pady=2, padx=(8, 0))
        self._preview()

    def _section(self):
        t = self.v_type.get()
        if t == "圆形":
            sec = Circular(self.v_d.get() * MM)
        elif t == "方形":
            sec = Rectangular(self.v_w.get() * MM, self.v_w.get() * MM)
        elif t == "矩形":
            sec = Rectangular(self.v_w.get() * MM, self.v_h.get() * MM)
        else:
            sec = Annular(self.v_do.get() * MM, self.v_di.get() * MM)
        sec.validate()
        return sec

    def _preview(self):
        try:
            sec = self._section()
        except (tk.TclError, ValueError):
            return
        plotting.draw_section(self.ax, sec, f"{section_type_name(sec)}截面  Dh={sec.hydraulic_diameter / MM:.2f} mm")
        self.canvas.draw_idle()

    def _ok(self):
        try:
            seg = Segment(self.v_name.get().strip() or "流道段", self._section(),
                          self.v_len.get() * MM, int(self.v_par.get()))
            seg.validate()
        except (tk.TclError, ValueError) as e:
            messagebox.showerror("参数错误", str(e), parent=self)
            return
        self.result = seg
        self.destroy()


class MaterialDialog(tk.Toplevel):
    """新建/编辑自定义 Cross-WLF 材料。"""

    FIELDS = [("name", "名称", str), ("n", "n", float), ("tau_s", "τ* [Pa]", float),
              ("D1", "D1 [Pa·s]", float), ("D2", "D2 [K]", float), ("D3", "D3 [K/Pa]", float),
              ("A1", "A1", float), ("A2t", "Ã2 [K]", float),
              ("t_min", "推荐温度下限 [°C]", float), ("t_max", "推荐温度上限 [°C]", float)]

    def __init__(self, master, base: Material):
        super().__init__(master)
        self.title("自定义材料（Cross-WLF）")
        self.transient(master)
        self.result: Material | None = None
        frm = ttk.Frame(self, padding=10)
        frm.pack()
        self.vars = {}
        for i, (key, lbl, _) in enumerate(self.FIELDS):
            val = getattr(base, key)
            if key == "name":
                val = f"{val}-自定义"
            v = tk.StringVar(value=str(val))
            self.vars[key] = v
            ttk.Label(frm, text=lbl).grid(row=i, column=0, sticky="w")
            ttk.Entry(frm, textvariable=v, width=18).grid(row=i, column=1, pady=2)
        btns = ttk.Frame(frm)
        btns.grid(row=len(self.FIELDS), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btns, text="确定", command=self._ok).pack(side="left", padx=4)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="left", padx=4)
        self.grab_set()

    def _ok(self):
        try:
            kw = {key: typ(self.vars[key].get()) for key, _, typ in self.FIELDS}
            if not 0 < kw["n"] <= 1:
                raise ValueError("n 应在 (0, 1] 内")
            if kw["t_min"] >= kw["t_max"]:
                raise ValueError("温度下限应小于上限")
            self.result = Material(description="自定义材料", **kw)
        except ValueError as e:
            messagebox.showerror("参数错误", str(e), parent=self)
            return
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("热流道压力降计算（Cross-WLF）")
        self.geometry("1400x880")
        self.minsize(1100, 720)

        self.materials: dict[str, Material] = dict(MATERIALS)
        self.segments: list[Segment] = default_segments()
        self.result = None
        self._pending = None

        self.v_mat = tk.StringVar(value="PP")
        self.v_temp = tk.DoubleVar(value=MATERIALS["PP"].t_default)
        self.v_vol = tk.DoubleVar(value=120.0)
        self.v_vol_max = tk.DoubleVar(value=300.0)
        self.v_time = tk.DoubleVar(value=1.5)

        self._build_menu()
        self._build_layout()
        self._on_material(initial=True)
        self._refresh_segments()
        self.schedule_update()

    # ---------- 界面搭建 ----------
    def _build_menu(self):
        mb = tk.Menu(self)
        fm = tk.Menu(mb, tearoff=False)
        fm.add_command(label="打开方案…", command=self.load_project)
        fm.add_command(label="保存方案…", command=self.save_project)
        fm.add_separator()
        fm.add_command(label="导出结果 CSV…", command=self.export_csv)
        fm.add_command(label="导出图表 PNG…", command=self.export_png)
        fm.add_separator()
        fm.add_command(label="退出", command=self.destroy)
        mb.add_cascade(label="文件", menu=fm)
        self.config(menu=mb)

    def _build_layout(self):
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=8)
        right = ttk.Frame(paned, padding=(0, 8, 8, 8))
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        # 材料
        lf = ttk.LabelFrame(left, text="材料（Cross-WLF）", padding=6)
        lf.pack(fill="x")
        row = ttk.Frame(lf)
        row.pack(fill="x")
        self.cb_mat = ttk.Combobox(row, textvariable=self.v_mat, state="readonly", width=16,
                                   values=list(self.materials))
        self.cb_mat.pack(side="left")
        self.cb_mat.bind("<<ComboboxSelected>>", lambda e: self._on_material())
        ttk.Button(row, text="自定义…", command=self.custom_material).pack(side="left", padx=4)
        self.lbl_mat = ttk.Label(lf, text="", foreground="#444", justify="left", font=("TkFixedFont", 9))
        self.lbl_mat.pack(fill="x", pady=(4, 0))

        # 工艺参数
        pf = ttk.LabelFrame(left, text="工艺参数（拖动滑块，图表随动）", padding=6)
        pf.pack(fill="x", pady=(8, 0))
        self.s_temp = self._slider(pf, "熔体温度 [°C]", self.v_temp, 150, 350, 0, 1)
        self.s_vol = self._slider(pf, "注射量 [cm³]", self.v_vol, 1, 300, 2, 1)
        rowm = ttk.Frame(pf)
        rowm.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(rowm, text="注射量滑块上限 [cm³]").pack(side="left")
        e = ttk.Entry(rowm, textvariable=self.v_vol_max, width=8)
        e.pack(side="left", padx=4)
        e.bind("<Return>", lambda ev: self._on_vol_max())
        e.bind("<FocusOut>", lambda ev: self._on_vol_max())
        self._slider(pf, "注射时间 [s]", self.v_time, 0.1, 10, 5, 0.05)
        self.lbl_flow = ttk.Label(pf, text="", foreground="#2a78b8")
        self.lbl_flow.grid(row=7, column=0, columnspan=3, sticky="w", pady=(4, 0))
        pf.columnconfigure(1, weight=1)

        # 流道段
        sf = ttk.LabelFrame(left, text="热流道各段（沿一条流动路径，入口 → 浇口）", padding=6)
        sf.pack(fill="both", expand=True, pady=(8, 0))
        cols = ("name", "type", "size", "len", "par")
        self.tv_seg = ttk.Treeview(sf, columns=cols, show="headings", height=7, selectmode="browse")
        for c, t, w in zip(cols, ("名称", "截面", "尺寸[mm]", "长度[mm]", "并联"),
                           (110, 50, 90, 70, 45)):
            self.tv_seg.heading(c, text=t)
            self.tv_seg.column(c, width=w, anchor="center")
        self.tv_seg.pack(fill="x")
        self.tv_seg.bind("<<TreeviewSelect>>", lambda e: self._draw_selected_section())
        self.tv_seg.bind("<Double-1>", lambda e: self.edit_segment())
        bf = ttk.Frame(sf)
        bf.pack(fill="x", pady=4)
        for txt, cmd in (("添加", self.add_segment), ("编辑", self.edit_segment),
                         ("删除", self.delete_segment), ("上移", lambda: self.move_segment(-1)),
                         ("下移", lambda: self.move_segment(1))):
            ttk.Button(bf, text=txt, command=cmd, width=6).pack(side="left", padx=1)

        self.sec_fig = Figure(figsize=(3.2, 2.5), dpi=90)
        self.sec_ax = self.sec_fig.add_subplot(111)
        self.sec_canvas = FigureCanvasTkAgg(self.sec_fig, master=sf)
        self.sec_canvas.get_tk_widget().pack(fill="both", expand=True)

        # 右侧：图表 + 结果表
        self.fig = Figure(figsize=(9, 6), dpi=96)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        tb = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
        tb.update()
        tb.pack(side="top", fill="x")
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        rf = ttk.LabelFrame(right, text="分段计算结果（单支路）", padding=4)
        rf.pack(side="bottom", fill="x")
        rcols = ("name", "q", "v", "gamma", "eta", "tau", "n", "dp", "t")
        heads = ("名称", "流量[cm³/s]", "流速[m/s]", "壁面剪切速率[1/s]", "粘度[Pa·s]",
                 "剪切应力[kPa]", "n'", "压力降[MPa]", "流经时间[s]")
        self.tv_res = ttk.Treeview(rf, columns=rcols, show="headings", height=7)
        for c, t in zip(rcols, heads):
            self.tv_res.heading(c, text=t)
            self.tv_res.column(c, width=105, anchor="center")
        self.tv_res.pack(fill="x")

    def _slider(self, parent, label, var, lo, hi, row, res):
        ttk.Label(parent, text=label).grid(row=row, column=0, columnspan=2, sticky="w")
        ent = ttk.Entry(parent, textvariable=var, width=8)
        ent.grid(row=row, column=2, sticky="e")
        ent.bind("<Return>", lambda e: self.schedule_update())
        ent.bind("<FocusOut>", lambda e: self.schedule_update())
        sc = tk.Scale(parent, variable=var, from_=lo, to=hi, orient="horizontal",
                      resolution=res, showvalue=False, length=300,
                      command=lambda v: self.schedule_update())
        sc.grid(row=row + 1, column=0, columnspan=3, sticky="we")
        return sc

    # ---------- 事件 ----------
    def _on_material(self, initial=False):
        m = self.materials[self.v_mat.get()]
        self.lbl_mat.config(text=(
            f"{m.description}\n"
            f"n={m.n:g}  τ*={m.tau_s:.3g} Pa\n"
            f"D1={m.D1:.4g} Pa·s  D2={m.D2:g} K\n"
            f"A1={m.A1:g}  Ã2={m.A2t:g} K  D3={m.D3:g}\n"
            f"推荐熔体温度 {m.t_min:g}–{m.t_max:g} °C"))
        self.s_temp.config(from_=m.t_min - 40, to=m.t_max + 40)
        if not initial:
            self.v_temp.set(m.t_default)
        self.schedule_update()

    def _on_vol_max(self):
        try:
            vmax = float(self.v_vol_max.get())
        except (tk.TclError, ValueError):
            return
        if vmax > 1:
            self.s_vol.config(to=vmax)
            if self.v_vol.get() > vmax:
                self.v_vol.set(vmax)
            self.schedule_update()

    def schedule_update(self):
        if self._pending is not None:
            self.after_cancel(self._pending)
        self._pending = self.after(40, self.update_results)

    def _params(self):
        return (self.materials[self.v_mat.get()], float(self.v_temp.get()),
                float(self.v_vol.get()) * CM3, float(self.v_time.get()),
                float(self.v_vol_max.get()) * CM3)

    def update_results(self):
        self._pending = None
        try:
            mat, t_c, vol, t_inj, vmax = self._params()
            if not self.segments:
                raise ValueError("请至少添加一个流道段")
            self.result = compute(self.segments, mat, vol, t_inj, t_c)
            plotting.draw_results(self.fig, self.segments, mat, self.result, vol, t_inj, t_c,
                                  (vmax * 0.01, max(vmax, vol)))
        except (tk.TclError, ValueError) as e:
            self.lbl_flow.config(text=f"⚠ {e}", foreground="#c0392b")
            return
        q = vol / t_inj
        self.lbl_flow.config(text=f"总体积流量 Q = {q / CM3:.1f} cm³/s    "
                                  f"总压力降 = {self.result.total_pressure_drop / 1e6:.2f} MPa",
                             foreground="#2a78b8")
        self.canvas.draw_idle()
        self.tv_res.delete(*self.tv_res.get_children())
        for r in self.result.segments:
            self.tv_res.insert("", "end", values=(
                r.segment.name, f"{r.flow_rate / CM3:.1f}", f"{r.velocity:.3f}",
                f"{r.shear_rate:.0f}", f"{r.viscosity:.1f}", f"{r.shear_stress / 1e3:.1f}",
                f"{r.power_index:.3f}", f"{r.pressure_drop / 1e6:.2f}", f"{r.residence_time:.3f}"))
        self.tv_res.insert("", "end", values=("合计", "", "", "", "", "", "",
                                              f"{self.result.total_pressure_drop / 1e6:.2f}",
                                              f"{sum(r.residence_time for r in self.result.segments):.3f}"))

    # ---------- 流道段管理 ----------
    def _refresh_segments(self, select: int | None = None):
        self.tv_seg.delete(*self.tv_seg.get_children())
        for i, s in enumerate(self.segments):
            self.tv_seg.insert("", "end", iid=str(i), values=(
                s.name, section_type_name(s.section), s.section.describe(),
                f"{s.length / MM:g}", s.parallel))
        if self.segments:
            idx = 0 if select is None else max(0, min(select, len(self.segments) - 1))
            self.tv_seg.selection_set(str(idx))
        self._draw_selected_section()
        self.schedule_update()

    def _selected(self) -> int | None:
        sel = self.tv_seg.selection()
        return int(sel[0]) if sel else None

    def _draw_selected_section(self):
        i = self._selected()
        if i is None:
            self.sec_ax.clear()
            self.sec_ax.axis("off")
        else:
            s = self.segments[i]
            plotting.draw_section(self.sec_ax, s.section,
                                  f"{s.name}：{section_type_name(s.section)}截面  "
                                  f"Dh={s.section.hydraulic_diameter / MM:.2f} mm")
        self.sec_canvas.draw_idle()

    def add_segment(self):
        dlg = SegmentDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            i = self._selected()
            pos = len(self.segments) if i is None else i + 1
            self.segments.insert(pos, dlg.result)
            self._refresh_segments(pos)

    def edit_segment(self):
        i = self._selected()
        if i is None:
            return
        dlg = SegmentDialog(self, self.segments[i])
        self.wait_window(dlg)
        if dlg.result:
            self.segments[i] = dlg.result
            self._refresh_segments(i)

    def delete_segment(self):
        i = self._selected()
        if i is None:
            return
        del self.segments[i]
        self._refresh_segments(i)

    def move_segment(self, d):
        i = self._selected()
        if i is None or not 0 <= i + d < len(self.segments):
            return
        self.segments[i], self.segments[i + d] = self.segments[i + d], self.segments[i]
        self._refresh_segments(i + d)

    def custom_material(self):
        dlg = MaterialDialog(self, self.materials[self.v_mat.get()])
        self.wait_window(dlg)
        if dlg.result:
            self.materials[dlg.result.name] = dlg.result
            self.cb_mat.config(values=list(self.materials))
            self.v_mat.set(dlg.result.name)
            self._on_material()

    # ---------- 文件 ----------
    def save_project(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("热流道方案", "*.json")])
        if not path:
            return
        mat, t_c, vol, t_inj, vmax = self._params()
        data = {"material": mat.to_dict(), "melt_temperature": t_c,
                "shot_volume_cm3": vol / CM3, "shot_volume_max_cm3": vmax / CM3,
                "injection_time": t_inj, "segments": [s.to_dict() for s in self.segments]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("热流道方案", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            mat = Material.from_dict(data["material"])
            segs = [Segment.from_dict(d) for d in data["segments"]]
        except (OSError, KeyError, TypeError, ValueError) as e:
            messagebox.showerror("打开失败", str(e))
            return
        self.materials[mat.name] = mat
        self.cb_mat.config(values=list(self.materials))
        self.v_mat.set(mat.name)
        self._on_material(initial=True)
        self.v_temp.set(data.get("melt_temperature", mat.t_default))
        self.v_vol_max.set(data.get("shot_volume_max_cm3", 300.0))
        self._on_vol_max()
        self.v_vol.set(data.get("shot_volume_cm3", 100.0))
        self.v_time.set(data.get("injection_time", 1.5))
        self.segments = segs
        self._refresh_segments()

    def export_csv(self):
        if not self.result:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["名称", "截面", "尺寸[mm]", "长度[mm]", "并联数", "单支路流量[cm3/s]",
                        "流速[m/s]", "壁面剪切速率[1/s]", "粘度[Pa·s]", "剪切应力[kPa]",
                        "n'", "压力降[MPa]"])
            for r in self.result.segments:
                s = r.segment
                w.writerow([s.name, section_type_name(s.section), s.section.describe(),
                            f"{s.length / MM:g}", s.parallel, f"{r.flow_rate / CM3:.3f}",
                            f"{r.velocity:.4f}", f"{r.shear_rate:.1f}", f"{r.viscosity:.2f}",
                            f"{r.shear_stress / 1e3:.2f}", f"{r.power_index:.4f}",
                            f"{r.pressure_drop / 1e6:.3f}"])
            w.writerow(["合计"] + [""] * 10 + [f"{self.result.total_pressure_drop / 1e6:.3f}"])

    def export_png(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.fig.savefig(path, dpi=150, bbox_inches="tight")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
