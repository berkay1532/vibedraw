# debug_overlay.py
"""Gerçek mimari altlık (DXF line/arc) + tespit edilen kapı menteşeleri + M2
cihazları aynı görüntüde — AutoCAD'de görünenle birebir teşhis için."""
from __future__ import annotations
import math

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from debug_devices import build, DXF, STYLE


def base_segments(bbox):
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(DXF)
    msp = doc.modelspace()
    segs, arcs = [], []
    for e in msp:
        t = e.dxftype()
        try:
            if t == "LINE":
                a = (e.dxf.start[0], e.dxf.start[1]); b = (e.dxf.end[0], e.dxf.end[1])
                if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                    segs.append((a, b))
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if pts and x0 <= pts[0][0] <= x1 and y0 <= pts[0][1] <= y1:
                    for i in range(len(pts) - 1):
                        segs.append((pts[i], pts[i + 1]))
            elif t == "ARC":
                c = (e.dxf.center[0], e.dxf.center[1])
                if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
                    a0 = math.radians(e.dxf.start_angle); a1 = math.radians(e.dxf.end_angle)
                    if a1 < a0: a1 += 2 * math.pi
                    r = e.dxf.radius
                    pts = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / 16),
                            c[1] + r * math.sin(a0 + (a1 - a0) * k / 16)) for k in range(17)]
                    for i in range(16): arcs.append((pts[i], pts[i + 1]))
        except Exception:
            pass
    return segs, arcs


def main():
    b = build()
    f = b.floors[0]
    xs = [r.center[0] for r in f.rooms] + [d.xy[0] for d in f.doors]
    ys = [r.center[1] for r in f.rooms] + [d.xy[1] for d in f.doors]
    m = 220
    bbox = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)

    segs, arcs = base_segments(bbox)
    fig, ax = plt.subplots(figsize=(18, 14))
    for a, c in segs: ax.plot([a[0], c[0]], [a[1], c[1]], color="#bbb", lw=0.6)
    for a, c in arcs: ax.plot([a[0], c[0]], [a[1], c[1]], color="#e88", lw=0.6)

    # tespit edilen kapı menteşeleri
    for d in f.doors:
        ax.add_patch(Circle(d.xy, 7, facecolor="none", edgecolor="#00bcd4", lw=2, zorder=4))
        ax.text(d.xy[0], d.xy[1] + 12, "kapı", fontsize=6, ha="center", color="#0097a7")
    # cihazlar
    for dv in f.devices:
        color, rad, lab = STYLE.get(dv.kind, ("#000", 4, "?"))
        edge = "black" if dv.covered else "white"
        ax.add_patch(Circle(dv.xy, rad, facecolor=color, edgecolor=edge, lw=1.2, zorder=6))
        ax.text(dv.xy[0], dv.xy[1], lab, fontsize=5, ha="center", va="center",
                color="white", zorder=7)
    for r in f.rooms:
        if r.center:
            ax.text(r.center[0], r.center[1] + 16, r.raw_name, fontsize=7,
                    ha="center", color="#1a1a1a", zorder=8)
    ax.set_aspect("equal"); ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.set_title("M2 cihazlar + kapı menteşeleri — gerçek altlık üstünde")
    fig.tight_layout(); fig.savefig("output/debug_overlay.png", dpi=110); plt.close(fig)
    print("output/debug_overlay.png")


if __name__ == "__main__":
    main()
