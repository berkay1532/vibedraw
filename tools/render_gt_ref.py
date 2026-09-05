#!/usr/bin/env python3
"""GT referans görseli: ham çizgiler üstüne tahminler (oda poligonu yeşil kesik + id/ad, kapı magenta halka + id,
pencere mavi + id). --raw: tahmin yok, yalnız ham çizgiler + oda etiketleri (holdout dosyaları için).

Kullanım: python3 tools/render_gt_ref.py <ad> [--pred output/src02] [--raw] [--dpi 200]
Çıktı: output/gt_ref/<ad>.png (ya da <ad>_raw.png)
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import argparse, json, math
import ezdxf, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def draw_entity(ax, e, col, lw, inb):
    t = e.dxftype()
    try:
        if t == "LINE":
            p, q = e.dxf.start, e.dxf.end
            if inb(p) or inb(q): ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=lw)
        elif t in ("LWPOLYLINE", "ARC", "CIRCLE"):
            for ve in (list(e.virtual_entities()) if t == "LWPOLYLINE" else [e]):
                vt = ve.dxftype()
                if vt == "LINE":
                    p, q = ve.dxf.start, ve.dxf.end
                    if inb(p) or inb(q): ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=lw)
                elif vt in ("ARC", "CIRCLE"):
                    c = ve.dxf.center
                    if not inb(c): continue
                    r = ve.dxf.radius
                    a0, a1 = ((math.radians(ve.dxf.start_angle), math.radians(ve.dxf.end_angle)) if vt == "ARC" else (0.0, 2 * math.pi))
                    if a1 < a0: a1 += 2 * math.pi
                    P = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / 24), c[1] + r * math.sin(a0 + (a1 - a0) * k / 24)) for k in range(25)]
                    ax.plot([p[0] for p in P], [p[1] for p in P], color=col, lw=lw)
        elif t == "INSERT" and inb(e.dxf.insert):
            for ve in e.virtual_entities(): draw_entity(ax, ve, col, lw, inb)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--pred", default="output/src02")
    ap.add_argument("--raw", action="store_true"); ap.add_argument("--dpi", type=int, default=200); a = ap.parse_args()
    pj = json.load(open(f"{a.pred}/{a.name}.json")); fl = pj["floors"][0]; upm = fl["params"]["units_per_meter"]
    pts = [p for r in fl["rooms"] for p in (r["polygon"] or ([r["label_xy"]] if r.get("label_xy") else []))]
    m = 3.0 * upm; x0, y0 = min(p[0] for p in pts) - m, min(p[1] for p in pts) - m; x1, y1 = max(p[0] for p in pts) + m, max(p[1] for p in pts) + m
    inb = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    doc = ezdxf.readfile(pj["source_path"]); msp = doc.modelspace()
    fig, ax = plt.subplots(figsize=(28, 28 * (y1 - y0) / max(1e-6, x1 - x0)))
    for e in msp: draw_entity(ax, e, "0.55", 0.35, inb)
    if a.raw:
        for r in fl["rooms"]:
            if r.get("label_xy"): ax.text(r["label_xy"][0], r["label_xy"][1], r["raw_name"].split("\n")[0], fontsize=6, color="navy", ha="center")
    else:
        for r in fl["rooms"]:
            if r["polygon"]:
                P = r["polygon"] + [r["polygon"][0]]
                ax.plot([p[0] for p in P], [p[1] for p in P], color="green", lw=1.1, ls="--")
            lx, ly = r["label_xy"] or (r["polygon"][0] if r["polygon"] else (0, 0))
            ax.text(lx, ly, f"{r['id']} {r['raw_name'].split(chr(10))[0]}", fontsize=7, color="darkgreen", ha="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
        for o in fl["openings"]:
            c = o["hinge"] or o["center"]
            if o["kind"] == "door":
                ax.plot(c[0], c[1], "o", mfc="none", mec="magenta", ms=9, mew=1.6); ax.text(c[0], c[1], " " + o["id"], fontsize=6, color="magenta", va="bottom")
            else:
                w = (o.get("width") or 0) / 2
                ax.plot([c[0] - w, c[0] + w], [c[1], c[1]], color="dodgerblue", lw=2.2, alpha=0.8); ax.text(c[0], c[1], o["id"], fontsize=5, color="dodgerblue", ha="center", va="bottom")
    ax.set_aspect("equal"); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    ax.set_title(f"{a.name}  upm={upm:.1f}  {'HAM' if a.raw else 'tahmin: yeşil=oda, magenta=kapı menteşesi, mavi=pencere'}", fontsize=10)
    out = f"output/gt_ref/{a.name}{'_raw' if a.raw else ''}.png"
    fig.savefig(out, dpi=a.dpi, bbox_inches="tight"); print(out)


if __name__ == "__main__":
    main()
