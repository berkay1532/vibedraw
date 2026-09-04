# debug_walls_doors.py
"""Duvarlar (kırmızı) + kapı açılış YAYLARI ve süpürme yönü (kapı hangi odaya açılıyor).
Yay yönü → kapı→oda eşleşmesinin temeli. Standalone ARC + blok kapı (matrix44) işlenir.
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)
import math
from collections import deque

import numpy as np
import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from core.geometry import _floor_bbox, _Raster, _staircase_polygon, _dilate, DOOR_LAYERS
from core.parse import parse_dxf
from debug_devices import build, DXF

AMIN, AMAX = 55.0, 130.0


def _close(mask, k):
    """Morfolojik kapama: ince iç-duvar çentiklerini doldur (dilate sonra erode)."""
    return ~_dilate(~_dilate(mask, k), k)


def building_outline(margin=300.0, res=3.0, dilate=8, close_k=22, simplify=16.0):
    """Dış duvarların İÇ YÜZÜ konturu (elektrik için doğru hat: oda tarafı).

    Yöntem: kabuğu (duvar+pencere+kolon) rasterle → dışarıdan flood-fill →
    ulaşılamayan = bina içi boş alan (iç yüzde, ama duvar-dilate kadar içeride) →
    morfolojik KAPAMA ile iç duvar çentiklerini sil → dilate kadar (res·dilate)
    DIŞARI öteleyerek tam iç yüze getir (duvar kalınlığı tahmini gerekmez).
    Geniş margin şart (gerçek dış duvarlar oda sınırlarının hemen dışında).
    """
    bb = parse_dxf(DXF, target_floor=1, gap=600.0)
    bbox = _floor_bbox(bb.floors[0], margin)
    doc = ezdxf.readfile(DXF)
    R = _Raster(doc.modelspace(), bbox, res=res, seal=10)
    grid = _dilate(R.base, dilate)               # kapı/küçük boşlukları köprüle
    H, W = grid.shape
    free = ~grid
    outside = np.zeros_like(grid)
    dq = deque()
    for c in range(W):
        for r in (0, H - 1):
            if free[r, c]:
                outside[r, c] = True; dq.append((r, c))
    for r in range(H):
        for c in (0, W - 1):
            if free[r, c]:
                outside[r, c] = True; dq.append((r, c))
    while dq:
        r, c = dq.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < H and 0 <= nc < W and free[nr, nc] and not outside[nr, nc]:
                outside[nr, nc] = True; dq.append((nr, nc))
    interior = _close(free & ~outside, close_k)  # iç boş alan, çentikler dolu
    poly = _staircase_polygon(interior, R)
    if poly is None:
        return None, bbox
    inner = poly.buffer(dilate * res, join_style=2)   # +dilate = gerçek iç yüz
    return inner.simplify(simplify), bbox


def _arc_polyline(cx, cy, r, a0, a1, n=24):
    if a1 < a0:
        a1 += 2 * math.pi
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n),
             cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def swing_arcs(msp, bbox):
    """Dünya-koordinatlı kapı yayları: (hinge, polyline, mid_pt). Standalone + blok."""
    x0, y0, x1, y1 = bbox
    out = []
    for e in msp:
        t = e.dxftype()
        if t == "ARC" and AMIN <= e.dxf.radius <= AMAX:
            cx, cy = e.dxf.center[0], e.dxf.center[1]
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            a0 = math.radians(e.dxf.start_angle); a1 = math.radians(e.dxf.end_angle)
            poly = _arc_polyline(cx, cy, e.dxf.radius, a0, a1)
            out.append(((cx, cy), poly, poly[len(poly) // 2]))
        elif t == "INSERT" and e.dxf.layer in DOOR_LAYERS:
            ip = e.dxf.insert
            if not (x0 <= ip[0] <= x1 and y0 <= ip[1] <= y1):
                continue                       # başka kattaki blok kapı
            try:
                m = e.matrix44()
                blk = e.doc.blocks.get(e.dxf.name)
                sx = abs(e.dxf.xscale) if e.dxf.xscale else 1.0
                for ent in blk:
                    if ent.dxftype() != "ARC":
                        continue
                    r = ent.dxf.radius * sx
                    if not (AMIN <= r <= AMAX):
                        continue
                    wc = m.transform(ent.dxf.center)
                    a0 = math.radians(ent.dxf.start_angle)
                    a1 = math.radians(ent.dxf.end_angle)
                    if a1 < a0:
                        a1 += 2 * math.pi
                    # blok-uzayında örnekle, matrix44 ile dünyaya taşı
                    poly = []
                    for k in range(25):
                        a = a0 + (a1 - a0) * k / 24
                        p = m.transform((ent.dxf.center[0] + ent.dxf.radius * math.cos(a),
                                         ent.dxf.center[1] + ent.dxf.radius * math.sin(a)))
                        poly.append((p.x, p.y))
                    out.append(((wc.x, wc.y), poly, poly[len(poly) // 2]))
            except Exception:
                pass
    return out


def served_room(hinge, mid, rooms, max_dist=460.0):
    """Yayın süpürdüğü YÖNDEKİ oda: bisektörle en hizalı etiket (yakındakiler arası).

    'En yakın etiket' değil 'yön'; bu sayede merkezi Banyo etiketi fazla sahiplenmez,
    Salon/Mutfak (aynı duvarda bitişik kapılar) açılış yönüyle ayrışır.
    """
    bx, by = mid[0] - hinge[0], mid[1] - hinge[1]
    bn = math.hypot(bx, by) or 1.0
    best, bscore = rooms[0], -9.0
    for r in rooms:
        dx, dy = r.label_xy[0] - hinge[0], r.label_xy[1] - hinge[1]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        cos = (bx * dx + by * dy) / (bn * d)
        if cos < 0.2:                               # yay yönünde değil → ele
            continue
        score = cos - 0.4 * (d / max_dist)          # hizalama ana, uzaklık hafif ceza
        if score > bscore:
            bscore, best = score, r
    return best


def main():
    b = build(); f = b.floors[0]
    outline, bbox = building_outline()            # dış duvar konturu + geniş bbox
    doc = ezdxf.readfile(DXF); msp = doc.modelspace()
    arcs = swing_arcs(msp, bbox)

    fig, ax = plt.subplots(figsize=(16, 13))
    if outline is not None:                        # dış duvar İÇ YÜZÜ (mavi)
        polys = outline.geoms if outline.geom_type == "MultiPolygon" else [outline]
        for i, gg in enumerate(polys):
            xs, ys = gg.exterior.xy
            ax.plot(xs, ys, color="#1565c0", lw=3.5,
                    label="dış duvar iç yüzü" if i == 0 else None)
    for a, c in f.walls:                            # İÇ duvar (kırmızı)
        ax.plot([a[0], c[0]], [a[1], c[1]], color="red", lw=1.3)
    for r in f.rooms:
        ax.text(r.center[0], r.center[1], r.raw_name, fontsize=8, ha="center", color="black")
    for hinge, poly, mid in arcs:                   # kapı yayı + açılış yönü
        ax.plot([p[0] for p in poly], [p[1] for p in poly], color="#00897b", lw=1.5)
        sr = served_room(hinge, mid, f.rooms)
        ax.annotate("", xy=mid, xytext=hinge,
                    arrowprops=dict(arrowstyle="->", color="#e65100", lw=1.8))
        ax.text(mid[0], mid[1], f"→{sr.raw_name}", fontsize=7, color="#e65100",
                ha="center", weight="bold")
    ax.set_aspect("equal"); ax.set_xlim(bbox[0], bbox[2]); ax.set_ylim(bbox[1], bbox[3])
    ax.legend(loc="upper right")
    ax.set_title("İç duvarlar (kırmızı) + dış duvar İÇ YÜZÜ (mavi) + kapı açılış yönleri")
    fig.tight_layout(); fig.savefig("output/debug_walls_doors.png", dpi=100); plt.close(fig)
    nv = (len(outline.geoms) if outline and outline.geom_type == "MultiPolygon"
          else (len(outline.exterior.coords) if outline else 0))
    print(f"dış duvar iç yüz köşe/parça: {nv} | iç duvar: {len(f.walls)} | kapı yayı: {len(arcs)}")
    for hinge, poly, mid in arcs:
        sr = served_room(hinge, mid, f.rooms)
        print(f"  menteşe {tuple(round(v) for v in hinge)} → {sr.raw_name}")


if __name__ == "__main__":
    main()
