# debug_step.py
"""Cihaz yerleşimini ADIM ADIM doğrulama. Sadece istenen cihaz tiplerini, temiz
duvar görünümü + kapı yayları üstünde çizer.

Kullanım:
    python3 debug_step.py light switch     # Adım 1-2: armatür + anahtar
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)
import sys
import math

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from core.perception.rooms import _floor_bbox
from core.perception.pipeline import select_plan
from debug_devices import build, DXF, STYLE
from debug_alllayers import PROPER, _segs
from debug_walls_doors import swing_arcs, served_room


def main():
    kinds = sys.argv[1:] or ["light", "switch"]
    b = build()
    f = b.floors[0]
    bbox = _floor_bbox(select_plan(DXF).floor, 250.0)
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(DXF)
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(16, 13))
    for e in msp:                                  # duvarlar (kırmızı), gerisi soluk
        lay = e.dxf.layer
        col = "#e33" if lay in PROPER else "#eee"
        lw = 1.3 if lay in PROPER else 0.4
        for a, c in _segs(e):
            if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                ax.plot([a[0], c[0]], [a[1], c[1]], color=col, lw=lw, zorder=1)

    def near_wall(p, lim=25.0):
        best = min((_pp(p, a, c) for a, c in f.walls), default=9e9)
        return best <= lim

    arcs = [a for a in swing_arcs(msp, bbox) if near_wall(a[0])]
    for hinge, poly, mid in arcs:                  # kapılar (yay + yön)
        ax.plot([p[0] for p in poly], [p[1] for p in poly], color="#00aacc", lw=1.6, zorder=2)
        ax.add_patch(Circle(hinge, 7, facecolor="#00aacc", edgecolor="white", lw=0.6, zorder=3))
        ax.annotate("", xy=mid, xytext=hinge,
                    arrowprops=dict(arrowstyle="->", color="#00aacc", lw=1.4), zorder=2)

    for dv in f.devices:                           # istenen cihaz tipleri
        if dv.kind not in kinds:
            continue
        color, rad, lab = STYLE.get(dv.kind, ("#000", 5, "?"))
        edge = "black" if dv.covered else "white"   # kapaklı priz = siyah halka
        ax.add_patch(Circle(dv.xy, rad + 2, facecolor=color, edgecolor=edge,
                            lw=1.6 if dv.covered else 1.0, zorder=6))
        ax.text(dv.xy[0], dv.xy[1], lab, fontsize=7, ha="center", va="center",
                color="white", weight="bold", zorder=7)
        if dv.kind == "appliance" and dv.label:      # beyaz eşya adını yaz
            ax.text(dv.xy[0], dv.xy[1] - 22, dv.label, fontsize=8, ha="center",
                    color="#b71c1c", weight="bold", zorder=8)

    for r in f.rooms:
        if r.center:
            ax.text(r.center[0], r.center[1] + 30, r.raw_name, fontsize=9,
                    ha="center", color="black", zorder=8)
    ax.set_aspect("equal"); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_title(f"Adım doğrulama: {', '.join(kinds)}  (duvar=kırmızı, kapı=mavi yay)")
    fig.tight_layout(); fig.savefig("output/debug_step.png", dpi=105); plt.close(fig)
    from collections import Counter
    print("çizilen:", dict(Counter(d.kind for d in f.devices if d.kind in kinds)))


def _pp(p, a, b):
    ex, ey = b[0] - a[0], b[1] - a[1]
    L2 = ex * ex + ey * ey or 1.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2))
    return math.hypot(a[0] + t * ex - p[0], a[1] + t * ey - p[1])


if __name__ == "__main__":
    main()
