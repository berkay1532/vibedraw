# debug_devices.py
"""M2 görsel doğrulama: cihazları (aydınlatma/anahtar/priz/beyaz eşya) M1
geometrisi + mimari altlık üstüne çizer. DXF + PNG üretir.

Kullanım:
    python3 debug_devices.py            # input-2-clean 1.kat
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)
import os

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from core.parse import parse_dxf
from core.geometry import reconstruct
from core.devices import place_devices, place_m3_nodes

DXF = "ornekler/input-2-clean.dxf"

# cihaz tipi -> (renk, çap, etiket)
STYLE = {
    "light":     ("#e8a000", 6, "L"),   # aydınlatma
    "switch":    ("#1565c0", 5, "A"),   # anahtar
    "socket":    ("#2e7d32", 5, "P"),   # priz
    "junction":  ("#6a1b9a", 4, "B"),   # buat
    "appliance": ("#c62828", 6, "X"),   # beyaz eşya
    "panel":     ("#000000", 9, "P"),   # pano (sigorta kutusu)
}


def build():
    b = parse_dxf(DXF, target_floor=1, gap=600.0)
    b = reconstruct(b, DXF, res=3.0, seal=18, margin=250)
    b = place_devices(b)
    b = place_m3_nodes(b)
    return b


def render_png(building, out_png):
    floor = building.floors[0]
    fig, ax = plt.subplots(figsize=(16, 12))
    # oda poligonları + merkez
    for r in floor.rooms:
        if r.polygon:
            xs = [p[0] for p in r.polygon] + [r.polygon[0][0]]
            ys = [p[1] for p in r.polygon] + [r.polygon[0][1]]
            ax.plot(xs, ys, color="#999", lw=0.8)
        if r.center:
            ax.text(r.center[0], r.center[1] - 14, r.raw_name,
                    fontsize=7, ha="center", color="#444")
    # kapılar
    for d in floor.doors:
        ax.add_patch(Circle(d.xy, 4, color="#00bcd4", alpha=0.5))
    # cihazlar
    for dv in floor.devices:
        color, rad, lab = STYLE.get(dv.kind, ("#000", 4, "?"))
        edge = "black" if dv.covered else "none"      # kapaklı priz = siyah halka
        lw = 1.8 if dv.covered else 0
        ax.add_patch(Circle(dv.xy, rad, facecolor=color, edgecolor=edge,
                            linewidth=lw, zorder=5))
        ax.text(dv.xy[0], dv.xy[1], lab, fontsize=6, ha="center", va="center",
                color="white", zorder=6)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_title(f"M2 cihazlar — {len(floor.devices)} adet")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def render_dxf(building, out_dxf):
    doc = ezdxf.readfile(DXF)
    msp = doc.modelspace()
    layers = {"light": ("M2-AYDINLATMA", 2), "switch": ("M2-ANAHTAR", 5),
              "socket": ("M2-PRIZ", 3), "junction": ("M2-BUAT", 6),
              "appliance": ("M2-BEYAZESYA", 1)}
    for name, col in layers.values():
        if name not in doc.layers:
            doc.layers.add(name, color=col)
    if "M2-KAPI" not in doc.layers:
        doc.layers.add("M2-KAPI", color=4)
    floor = building.floors[0]
    for dv in floor.devices:
        lname = layers.get(dv.kind, ("M2-DIGER", 7))[0]
        msp.add_circle(dv.xy, 8, dxfattribs={"layer": lname})
    for d in floor.doors:                       # kapı menteşeleri (doğrulama için)
        msp.add_circle(d.xy, 6, dxfattribs={"layer": "M2-KAPI"})
    os.makedirs(os.path.dirname(out_dxf) or ".", exist_ok=True)
    doc.saveas(out_dxf)


def main():
    b = build()
    floor = b.floors[0]
    render_png(b, "output/debug_m2.png")
    render_dxf(b, "output/debug_m2.dxf")
    from collections import Counter
    c = Counter(d.kind for d in floor.devices)
    print(f"odalar={len(floor.rooms)} kapılar={len(floor.doors)} cihazlar={dict(c)}")
    for r in floor.rooms:
        print(f"  {r.raw_name:14s} center={r.center} ok={r.geometry_ok}")


if __name__ == "__main__":
    main()
