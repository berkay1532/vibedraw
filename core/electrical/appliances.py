# core/electrical/appliances.py
"""Beyaz eşya konum tespiti — elektrik motoruna ait; perception IR'ında yer almaz.

`detect_appliances(building, dxf_path)` BuildingIR'daki katların oda etiketlerinden
bbox çıkarır ve DXF'te ocak sembolünü arar. Perception'daki eski `_detect_stove`
(core/geometry.py) buraya taşındı; mantık birebir aynı.
"""
from __future__ import annotations

import ezdxf


def _floor_bbox(floor, margin: float):
    xs = [r.label_xy[0] for r in floor.rooms]
    ys = [r.label_xy[1] for r in floor.rooms]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def detect_stove(msp, bbox):
    """Ocak: 'ince' katmanında eşit yarıçaplı 4 dairenin 2x2 ızgarası (4 göz).

    Bulunursa ocak merkezini (4 göz centroidi) döner, yoksa None.
    """
    x0, y0, x1, y1 = bbox
    circ = []
    for e in msp:
        if e.dxf.layer == "ince" and e.dxftype() == "CIRCLE":
            cx, cy, r = e.dxf.center[0], e.dxf.center[1], e.dxf.radius
            if x0 <= cx <= x1 and y0 <= cy <= y1 and 5 <= r <= 20:
                circ.append((cx, cy, r))
    # yarıçapa göre grupla, her grupta 2x2 ızgara ara
    circ.sort(key=lambda c: c[2])
    for i, (cx, cy, r) in enumerate(circ):
        grp = [c for c in circ if abs(c[2] - r) < 2.0]
        if len(grp) < 4:
            continue
        xs = sorted({round(c[0]) for c in grp})
        ys = sorted({round(c[1]) for c in grp})
        # 2 belirgin x ve 2 belirgin y kümesi (yakınları birleştir)
        def _two_clusters(vals):
            cl = []
            for v in vals:
                if cl and abs(cl[-1][-1] - v) < 15:
                    cl[-1].append(v)
                else:
                    cl.append([v])
            return cl
        cx_cl, cy_cl = _two_clusters(xs), _two_clusters(ys)
        if len(cx_cl) == 2 and len(cy_cl) == 2:
            gx = [sum(c) / len(c) for c in cx_cl]
            gy = [sum(c) / len(c) for c in cy_cl]
            # 4 köşede de daire var mı
            ok = all(any(abs(c[0] - mx) < 18 and abs(c[1] - my) < 18 for c in grp)
                     for mx in gx for my in gy)
            if ok:
                return (sum(gx) / 2, sum(gy) / 2)
    return None


def detect_appliances(building, dxf_path: str, margin: float = 250.0) -> dict:
    """Kat indeksi → {beyaz eşya adı: (x, y)} sözlüğü. Şimdilik yalnız ocak.
    (Eski davranış: reconstruct her kat için margin'li bbox içinde ocak arıyordu.)"""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    out: dict = {}
    for floor in building.floors:
        if not floor.rooms:
            continue
        stove = detect_stove(msp, _floor_bbox(floor, margin))
        if stove is not None:
            out.setdefault(floor.index, {})["Ocak/Fırın"] = stove
    return out
