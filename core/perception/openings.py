# core/perception/openings.py
"""Kapı açıklıkları: yay imzası, blok menteşesi, açılış yönü, kapalı-kanat bariyeri, aday kümeleme.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

from core.perception.blocks import _explode, _is_big_block
from core.perception.config import T
from core.perception.names import DOOR_CLASSES, EMPTY, GATED_MIN_CONF



def _door_like_arc(ent, sx, amin, amax, sweep=None):
    """Blok içi ARC bir kapı kanadı yayı mı? (yarıçap aralığı + süpürme açısı; thresholds door.arc_sweep_deg)"""
    if ent.dxftype() != "ARC" or not (amin <= ent.dxf.radius * sx <= amax):
        return False
    sweep = T("door", "arc_sweep_deg") if sweep is None else sweep
    a0, a1 = ent.dxf.start_angle, ent.dxf.end_angle
    sw = (a1 - a0) % 360.0
    return sweep[0] <= sw <= sweep[1]


def _block_door_hinge(e, amin=None, amax=None):
    """Kapı bloğunun gerçek MENTEŞE'si = blok içindeki swing ARC merkezi, INSERT'in
    resmi transform matrisi (matrix44) ile dünya koordinatına çevrilmiş.

    matrix44 dönme + ölçek + AYNALAMA (xscale=-1) durumlarını doğru çözer (manuel
    hesabın aksine). (menteşe_x, menteşe_y, kapı_genişliği) döner; ARC yoksa None.
    """
    try:
        m = e.matrix44()
        blk = e.doc.blocks.get(e.dxf.name)
        sx = abs(e.dxf.xscale) if e.dxf.xscale else 1.0
        for ent in blk:
            if ent.dxftype() != "ARC":
                continue
            if amin is not None and not _door_like_arc(ent, sx, amin, amax):
                continue
            wc = m.transform(ent.dxf.center)
            return (wc.x, wc.y, ent.dxf.radius * sx)
    except Exception:
        pass
    return None


def _seg_dist(p, segs):
    best = float("inf")
    for a, b in segs:
        ax, ay = a
        ex, ey = b[0] - a[0], b[1] - a[1]
        L2 = ex * ex + ey * ey or 1.0
        t = max(0.0, min(1.0, ((p[0] - ax) * ex + (p[1] - ay) * ey) / L2))
        d = math.hypot(ax + t * ex - p[0], ay + t * ey - p[1])
        if d < best:
            best = d
    return best


def _door_barriers(swings, walls):
    """Her kapı yayı için KAPALI kanat çizgisi (menteşe→kilit ucu) = açıklığı kapatan bariyer.
    Kapalı uç = kanat ortası duvara en yakın olan uç. Duvar yoksa bariyer üretilmez."""
    out = []
    if not walls:
        return out
    for hinge, _bdir, e1, e2 in swings:
        m1 = ((hinge[0] + e1[0]) / 2, (hinge[1] + e1[1]) / 2)
        m2 = ((hinge[0] + e2[0]) / 2, (hinge[1] + e2[1]) / 2)
        tip = e1 if _seg_dist(m1, walls) <= _seg_dist(m2, walls) else e2
        out.append(((hinge[0], hinge[1]), (tip[0], tip[1])))
    return out


def _cluster_doors(pts, radius=25.0, tags=None):
    """Yakın kapı adaylarını küme merkezine indirger. tags verilirse (pts ile hizalı)
    [(merkez, {etiketler})] döner — kaynak bilgisi (block/arc) için."""
    groups: list[list[tuple[float, float]]] = []
    gtags: list[set] = []
    for i, p in enumerate(pts):
        for gi, g in enumerate(groups):
            if math.hypot(p[0] - g[0][0], p[1] - g[0][1]) < radius:
                g.append(p)
                if tags is not None:
                    gtags[gi].add(tags[i])
                break
        else:
            groups.append([p])
            gtags.append({tags[i]} if tags is not None else set())
    centers = [(sum(q[0] for q in g) / len(g), sum(q[1] for q in g) / len(g)) for g in groups]
    if tags is not None:
        return list(zip(centers, gtags))
    return centers


def _swing_dirs(msp, bbox, amin, amax, big_blocks=False, names=EMPTY):
    """Her kapı yayı için (menteşe, açılış_yön_birimi, uç1, uç2). Standalone + blok.

    Bisektör = kapının açıldığı oda yönü. uç1/uç2 = leaf-tip noktaları (biri KAPALI
    konum = duvara paralel = kilit sövesi yönü; diğeri AÇIK konum).
    """
    x0, y0, x1, y1 = bbox
    out = []
    upm_est = amin / T("door", "upm_from_arc_min_m")

    def _arc_swing(cx, cy, r, a0d, a1d):
        a0 = math.radians(a0d); a1 = math.radians(a1d)
        if a1 < a0:
            a1 += 2 * math.pi
        am = (a0 + a1) / 2
        e1 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
        e2 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
        return ((cx, cy), (math.cos(am), math.sin(am)), e1, e2)

    for e in msp:
        t = e.dxftype()
        if t == "INSERT" and big_blocks and _is_big_block(e, upm_est):
            # Kat planı bloğu: içindeki (iç içe dahil) kapı yayları dünya koordinatında
            for ve in _explode(e):
                if ve.dxftype() == "ARC" and _door_like_arc(ve, 1.0, amin, amax):
                    cx, cy = ve.dxf.center[0], ve.dxf.center[1]
                    if x0 <= cx <= x1 and y0 <= cy <= y1:
                        out.append(_arc_swing(cx, cy, ve.dxf.radius, ve.dxf.start_angle, ve.dxf.end_angle))
            continue
        if t == "ARC" and amin <= e.dxf.radius <= amax:
            cx, cy = e.dxf.center[0], e.dxf.center[1]
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            a0 = math.radians(e.dxf.start_angle); a1 = math.radians(e.dxf.end_angle)
            if a1 < a0:
                a1 += 2 * math.pi
            am = (a0 + a1) / 2
            r = e.dxf.radius
            e1 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
            e2 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
            out.append(((cx, cy), (math.cos(am), math.sin(am)), e1, e2))
        elif t == "INSERT":                       # katman-bağımsız (yarıçap+süpürme süzer)
            # NOT: insert noktası geometriden uzak olabilir (Revit/anonim bloklar) →
            # bbox kontrolü dönüştürülmüş yay merkezi (menteşe) üzerinden yapılır.
            try:
                m = e.matrix44()
                blk = e.doc.blocks.get(e.dxf.name)
                sx = abs(e.dxf.xscale) if e.dxf.xscale else 1.0
                for ent in blk:
                    if names.has(e.dxf.layer, DOOR_CLASSES, GATED_MIN_CONF):   # blok yayı süzgeci gevşetme: profil güveni
                        if ent.dxftype() != "ARC" or not (amin <= ent.dxf.radius * sx <= amax):
                            continue
                    elif not _door_like_arc(ent, sx, amin, amax):
                        continue
                    wc = m.transform(ent.dxf.center)
                    if not (x0 <= wc.x <= x1 and y0 <= wc.y <= y1):
                        continue
                    a0 = math.radians(ent.dxf.start_angle)
                    a1 = math.radians(ent.dxf.end_angle)
                    if a1 < a0:
                        a1 += 2 * math.pi
                    am = (a0 + a1) / 2
                    r = ent.dxf.radius
                    pm = m.transform((ent.dxf.center[0] + r * math.cos(am),
                                      ent.dxf.center[1] + r * math.sin(am)))
                    p0 = m.transform((ent.dxf.center[0] + r * math.cos(a0),
                                      ent.dxf.center[1] + r * math.sin(a0)))
                    p1 = m.transform((ent.dxf.center[0] + r * math.cos(a1),
                                      ent.dxf.center[1] + r * math.sin(a1)))
                    dx, dy = pm.x - wc.x, pm.y - wc.y
                    n = math.hypot(dx, dy) or 1.0
                    out.append(((wc.x, wc.y), (dx / n, dy / n),
                                (p0.x, p0.y), (p1.x, p1.y)))
            except Exception:
                pass
    return out
