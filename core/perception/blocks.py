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


def block_geom_stats(doc, msp, upm, door_band, bbox=None, max_points=3) -> dict:
    """Blok envanteri (v0.2-1): blok adı → {n, arc, arc_door, w, h, ents, layers, xy}.

    n: modelspace yerleşim sayısı; arc/arc_door: blok TANIMINDAKİ yay sayısı ve kapı yarıçap bandındaki yay sayısı;
    w/h: blok tanımının yerel uzun/kısa kenarı (m, ölçek 1 varsayımı — yerleşim ölçeği candidate tarafında);
    layers: yerleşim katmanı sayacı; xy: ilk `max_points` yerleşim noktası (HITL crop). bbox verilirse yalnız o kattaki
    yerleşimler sayılır."""
    import collections
    out = {}
    counts = collections.defaultdict(lambda: {"n": 0, "layers": collections.Counter(), "xy": []})
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        try:
            name = e.dxf.name; ix, iy = float(e.dxf.insert[0]), float(e.dxf.insert[1])
        except Exception:
            continue
        if bbox and not (bbox[0] <= ix <= bbox[2] and bbox[1] <= iy <= bbox[3]):
            continue
        c = counts[name]; c["n"] += 1
        try:
            c["layers"][e.dxf.layer] += 1
        except Exception:
            pass
        if len(c["xy"]) < max_points:
            c["xy"].append((ix, iy))
    amin, amax = door_band
    for name, c in counts.items():
        if str(name).startswith("*"):
            continue
        arc = arc_door = 0; xs = []; ys = []; ents = 0
        try:
            blk = doc.blocks.get(name)
            for ent in blk:
                ents += 1
                t = ent.dxftype()
                if t == "ARC":
                    arc += 1
                    if amin <= ent.dxf.radius <= amax:
                        arc_door += 1
                    xs += [ent.dxf.center[0] - ent.dxf.radius, ent.dxf.center[0] + ent.dxf.radius]
                    ys += [ent.dxf.center[1] - ent.dxf.radius, ent.dxf.center[1] + ent.dxf.radius]
                elif t == "LINE":
                    xs += [ent.dxf.start[0], ent.dxf.end[0]]; ys += [ent.dxf.start[1], ent.dxf.end[1]]
                elif t == "LWPOLYLINE":
                    P = ent.get_points(); xs += [q[0] for q in P]; ys += [q[1] for q in P]
        except Exception:
            pass
        w = h = None
        if len(xs) >= 2:
            dx, dy = max(xs) - min(xs), max(ys) - min(ys)
            w, h = round(max(dx, dy) / upm, 3), round(min(dx, dy) / upm, 3)
        out[name] = {"n": c["n"], "arc": arc, "arc_door": arc_door, "w": w, "h": h, "ents": ents,
                     "layers": dict(c["layers"].most_common(3)), "xy": c["xy"]}
    return out


def block_local_axis(doc, name):
    """Blok tanımının yerel uzun kenarı: (uzunluk, yatay_mı). Geometri yoksa None."""
    xs, ys = [], []
    try:
        for ent in doc.blocks.get(name):
            t = ent.dxftype()
            if t == "LINE":
                xs += [ent.dxf.start[0], ent.dxf.end[0]]; ys += [ent.dxf.start[1], ent.dxf.end[1]]
            elif t == "LWPOLYLINE":
                P = ent.get_points(); xs += [q[0] for q in P]; ys += [q[1] for q in P]
            elif t == "ARC":
                xs += [ent.dxf.center[0] - ent.dxf.radius, ent.dxf.center[0] + ent.dxf.radius]
                ys += [ent.dxf.center[1] - ent.dxf.radius, ent.dxf.center[1] + ent.dxf.radius]
    except Exception:
        return None
    if len(xs) < 2:
        return None
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    return (max(dx, dy), dx >= dy)


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
