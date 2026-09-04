# debug_alllayers.py
"""En okunabilir kat görünümü: gerçek duvar geometrisi (katman renkli, ÇİZİLDİĞİ gibi)
+ kapı menteşeleri + açılış yayları (yön) + oda isimleri. Oda tespitini gözle
doğrulamak için referans görsel."""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)
import math

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from core.perception.rooms import _floor_bbox
from core.perception.parse import parse_dxf
from debug_devices import build, DXF
from debug_walls_doors import swing_arcs, served_room

PROPER = {".ABM-DUVAR", ".ABM-SIVA", "PislikMimar.com - duvar", "duv",
          "KOLON", "pencere", "cam"}
DOORLAY = {"kapi", ".KAPI", ".ABM-KAPI"}


def _color(lay):
    if lay in PROPER:
        return ("#d11", 1.7)            # gerçek duvar — kırmızı
    if lay == "ince":
        return ("#ff9800", 1.2)         # mobilya — turuncu
    if lay in DOORLAY:
        return ("#1aa11a", 1.0)         # kapı geometrisi — yeşil
    return ("#dcdcdc", 0.5)             # diğer — açık gri


def _segs(e):
    t = e.dxftype()
    out = []
    try:
        if t == "LINE":
            out = [((e.dxf.start[0], e.dxf.start[1]), (e.dxf.end[0], e.dxf.end[1]))]
        elif t == "LWPOLYLINE":
            p = [(x[0], x[1]) for x in e.get_points()]
            out = list(zip(p, p[1:]))
            if e.closed and len(p) > 2:
                out.append((p[-1], p[0]))
        elif t == "HATCH":
            for pth in e.paths.paths:
                try:
                    v = [(x[0], x[1]) for x in pth.vertices]
                    out += list(zip(v, v[1:]))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def main():
    b = build()
    f = b.floors[0]
    bbox = _floor_bbox(parse_dxf(DXF, target_floor=1, gap=600.0).floors[0], 300.0)
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(DXF)
    msp = doc.modelspace()

    fig, ax = plt.subplots(figsize=(17, 14))
    for e in msp:                                  # gerçek geometri (katman renkli)
        col, lw = _color(e.dxf.layer)
        for a, c in _segs(e):
            if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                ax.plot([a[0], c[0]], [a[1], c[1]], color=col, lw=lw)

    # Yayları gerçek kapılarla sınırla: menteşe bir duvara yakın olmalı (klozet/
    # lavabo fikstür yayları oda ortasında, ~37br uzakta → elenir; gerçek kapı ~5-10br).
    def _near_wall(p, lim=25.0):
        best = float("inf")
        for a, c in f.walls:
            ex, ey = c[0] - a[0], c[1] - a[1]
            L2 = ex * ex + ey * ey or 1.0
            t = max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2))
            d = math.hypot(a[0] + t * ex - p[0], a[1] + t * ey - p[1])
            if d < best:
                best = d
        return best <= lim

    arcs = [a for a in swing_arcs(msp, bbox) if _near_wall(a[0])]
    for hinge, poly, mid in arcs:                  # kapı yayı + menteşe + yön
        ax.plot([p[0] for p in poly], [p[1] for p in poly], color="#0066ff", lw=2.0)
        ax.add_patch(Circle(hinge, 8, facecolor="#0066ff", edgecolor="white",
                            lw=0.8, zorder=6))
        sr = served_room(hinge, mid, f.rooms)
        ax.annotate("", xy=mid, xytext=hinge,
                    arrowprops=dict(arrowstyle="-|>", color="#0066ff", lw=2))
        ax.text(mid[0], mid[1], f"→{sr.raw_name}", fontsize=8, color="#0044cc",
                ha="center", weight="bold", zorder=7)

    for r in f.rooms:                              # oda isimleri (merkez)
        if r.center:
            ax.text(r.center[0], r.center[1], r.raw_name, fontsize=11, ha="center",
                    color="black", weight="bold", zorder=8)

    ax.set_aspect("equal")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_title("Gerçek duvarlar (kırmızı) + mobilya (turuncu) + KAPI yay/yön (mavi) "
                 "+ oda isimleri")
    fig.tight_layout()
    fig.savefig("output/debug_alllayers.png", dpi=110)
    plt.close(fig)
    print(f"kapı yayı: {len(arcs)} | oda: {len(f.rooms)}")
    for hinge, poly, mid in arcs:
        sr = served_room(hinge, mid, f.rooms)
        print(f"  menteşe {tuple(round(v) for v in hinge)} → {sr.raw_name}")


if __name__ == "__main__":
    main()
