# core/perception/blocks.py
"""Blok (INSERT) yardımcıları: geometri açma, boyut, entity segmentleri.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math


def _entity_segments(e):
    """Bir entity'yi (LINE/LWPOLYLINE/ARC) dünya-koordinatlı segment listesine çevirir."""
    t = e.dxftype()
    if t == "LINE":
        a = (e.dxf.start[0], e.dxf.start[1])
        b = (e.dxf.end[0], e.dxf.end[1])
        return [(a, b)], [a, b]
    if t == "LWPOLYLINE":
        p = [(pp[0], pp[1]) for pp in e.get_points()]
        segs = list(zip(p, p[1:]))
        if e.closed and len(p) > 2:
            segs.append((p[-1], p[0]))
        return segs, p
    if t == "ARC":
        cx, cy, rr = e.dxf.center[0], e.dxf.center[1], e.dxf.radius
        a0 = math.radians(e.dxf.start_angle)
        a1 = math.radians(e.dxf.end_angle)
        if a1 < a0:
            a1 += 2 * math.pi
        steps = max(4, int((a1 - a0) / 0.2))
        pts = []
        for i in range(steps + 1):
            a = a0 + (a1 - a0) * i / steps
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        return list(zip(pts, pts[1:])), [(cx, cy)]
    return [], []


def _block_extent(e, depth=2):
    """INSERT'in (iç içe) geometrisinin dünya bbox'ı; boşsa None."""
    xs, ys = [], []
    for ve in _explode(e, depth):
        t = ve.dxftype()
        try:
            if t == "LINE":
                xs += [ve.dxf.start[0], ve.dxf.end[0]]; ys += [ve.dxf.start[1], ve.dxf.end[1]]
            elif t == "LWPOLYLINE":
                P = ve.get_points()
                xs += [q[0] for q in P]; ys += [q[1] for q in P]
        except Exception:
            pass
    if len(xs) < 4:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _is_big_block(e, upm, min_m=3.0):
    """Blok bir 'çizim kabı' mı (kat planı/daire bloğu)? Uzun kenarı ≥ min_m metre.
    Mobilya/sembol blokları < 3 m; kat planı blokları 5-30 m."""
    ext = _block_extent(e)
    if ext is None:
        return False
    return max(ext[2] - ext[0], ext[3] - ext[1]) >= min_m * upm


def _explode(e, depth=3):
    """INSERT'i (iç içe bloklar dahil) dünya koordinatlı sanal entity'lere açar."""
    try:
        for ve in e.virtual_entities():
            if ve.dxftype() == "INSERT":
                if depth > 0:
                    yield from _explode(ve, depth - 1)
            else:
                yield ve
    except Exception:
        return
