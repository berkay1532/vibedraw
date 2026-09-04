# core/perception/windows.py
"""Pencere tespiti: katman çizgileri, pencere blokları, duvar bandındaki ince paralel çizgi grupları.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

from core.perception.blocks import _entity_segments, _explode, _is_big_block
from core.perception.openings import _door_like_arc
from core.perception.walls import WALL_EXCLUDE_LAYERS


WINDOW_LAYERS = {"pencere", "cam", "KAPEN", "KAPI_PENCERE"}


WINDOW_WORDS = ("pencere", "window", "glz", "glazing", "fenetre", "ventana", "cam ")


def _window_word(name: str) -> bool:
    f = (name or "").replace("İ", "i").replace("I", "ı").casefold() + " "
    return any(w in f for w in WINDOW_WORDS)


def _near_parallel_wall(mid, ux, uy, walls, upm, perp_tol=0.25, along_tol=0.3):
    """mid, (ux,uy) eksenine paralel bir duvar parçasının doğrusuna perp_tol m içinde ve
    boyuna along_tol m payla parçanın üzerinde mi?"""
    for wa, wb in walls:
        wdx, wdy = wb[0] - wa[0], wb[1] - wa[1]
        WL = math.hypot(wdx, wdy) or 1.0
        wux, wuy = wdx / WL, wdy / WL
        if abs(wux * ux + wuy * uy) < 0.97:
            continue
        perp = abs((mid[0] - wa[0]) * (-wuy) + (mid[1] - wa[1]) * wux)
        along = (mid[0] - wa[0]) * wux + (mid[1] - wa[1]) * wuy
        if perp <= perp_tol * upm and -along_tol * upm <= along <= WL + along_tol * upm:
            return True
    return False


def _insert_window(e, upm, x0, y0, x1, y1, walls=None, with_source=False):
    """INSERT bir pencere bloğu mu? Kabul: ad/katman anahtar kelimesi VEYA (duvara paralel
    ve ≤25 cm yakın + 0.4-4 m uzun + uzun eksene paralel ≥2 çizgi). Kapı bloğu (≥0.65 m
    yarıçaplı 55-125° yay) reddedilir; küçük kanat yayları (pencere) kabul edilir.
    Pencere ekseni parçası döner, değilse None."""
    # Tüm geometriyi topla; aykırı parçalar (630 m uzakta çizgi vb.) MEDYAN noktaya göre
    # 5 m dışındaysa atılır. Insert noktası geometriden uzak olabilir → ona güvenilmez.
    raw_pts = []
    ents = list(_explode(e))
    for ve in ents:
        t = ve.dxftype()
        try:
            if t == "LINE":
                raw_pts += [(ve.dxf.start[0], ve.dxf.start[1]), (ve.dxf.end[0], ve.dxf.end[1])]
            elif t == "LWPOLYLINE":
                raw_pts += [(q[0], q[1]) for q in ve.get_points()]
        except Exception:
            pass
    if len(raw_pts) < 4:
        return None
    sx_ = sorted(q[0] for q in raw_pts); sy_ = sorted(q[1] for q in raw_pts)
    ip = (sx_[len(sx_) // 2], sy_[len(sy_) // 2])
    if not (x0 <= ip[0] <= x1 and y0 <= ip[1] <= y1):
        return None
    pts, lines = [], []
    R = 5.0 * upm
    def _ok(q):
        return math.hypot(q[0] - ip[0], q[1] - ip[1]) <= R
    for ve in ents:
        t = ve.dxftype()
        if t == "LINE":
            a, b = ve.dxf.start, ve.dxf.end
            a, b = (a[0], a[1]), (b[0], b[1])
            if _ok(a) and _ok(b):
                lines.append((a, b)); pts += [a, b]
        elif t == "LWPOLYLINE":
            P = [(q[0], q[1]) for q in ve.get_points()]
            P = [q for q in P if _ok(q)]
            for i in range(len(P) - 1):
                lines.append((P[i], P[i + 1]))
            pts += P
        elif t == "ARC" and _door_like_arc(ve, 1.0, 0.65 * upm, 1.5 * upm):
            return None                          # kapı bloğu
    if len(pts) < 4:
        return None
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    long_, short = max(w, h), min(w, h)
    ax = (1.0, 0.0) if w >= h else (0.0, 1.0)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    keyword = _window_word(e.dxf.name) or _window_word(e.dxf.layer)
    if not keyword:
        if not (0.4 * upm <= long_ <= 4.0 * upm and short <= 1.2 * upm):
            return None
        n_par = 0
        for a, b in lines:
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L >= 0.5 * long_ and abs(dx * ax[0] + dy * ax[1]) / L > 0.97:
                n_par += 1
        if n_par < 2:
            return None
        if not _near_parallel_wall((cx, cy), ax[0], ax[1], walls or [], upm):
            return None
    elif not (0.3 * upm <= long_ <= 4.5 * upm):
        return None
    seg = ((min(xs), cy), (max(xs), cy)) if w >= h else ((cx, min(ys)), (cx, max(ys)))
    if with_source:
        return seg, ("block_keyword" if keyword else "block_geometry")
    return seg


def _thin_line_windows(msp, bbox, upm, walls):
    """Serbest çizgilerden pencere: duvar bandı içinde, birbirine ≤10 cm mesafede, boyuna
    örtüşen ≥2 paralel çizgi grubu (cam çizgileri). Duvar yüzleri hariç."""
    x0, y0, x1, y1 = bbox
    wall_set = {(round(a[0], 1), round(a[1], 1), round(b[0], 1), round(b[1], 1)) for a, b in walls}
    segs = []
    for e in msp:
        if e.dxf.layer in WALL_EXCLUDE_LAYERS or e.dxftype() not in ("LINE", "LWPOLYLINE", "POLYLINE"):
            continue
        for a, b in _entity_segments(e)[0]:
            if not ((x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or (x0 <= b[0] <= x1 and y0 <= b[1] <= y1)):
                continue
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if not (0.4 * upm <= L <= 3.5 * upm):
                continue
            if (round(a[0], 1), round(a[1], 1), round(b[0], 1), round(b[1], 1)) in wall_set:
                continue
            segs.append(((a[0], a[1]), (b[0], b[1])))
    n = len(segs)
    if n < 2:
        return []
    dirs = []
    for a, b in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        dirs.append((dx / L, dy / L, L, math.atan2(dy, dx)))
    used = [False] * n
    out = []
    tol_perp, ang_tol = 0.10 * upm, math.radians(6)
    for i in range(n):
        if used[i]:
            continue
        ax, ay = segs[i][0]
        ux, uy, Li, ai = dirs[i]
        grp = [i]
        for j in range(i + 1, n):
            if used[j]:
                continue
            vx, vy, Lj, aj = dirs[j]
            if abs(((aj - ai + math.pi / 2) % math.pi) - math.pi / 2) > ang_tol:
                continue
            (cx, cy), (dx2, dy2) = segs[j]
            mx, my = (cx + dx2) / 2, (cy + dy2) / 2
            if abs((mx - ax) * (-uy) + (my - ay) * ux) > tol_perp:
                continue
            p0, p1 = sorted(((cx - ax) * ux + (cy - ay) * uy, (dx2 - ax) * ux + (dy2 - ay) * uy))
            if min(Li, p1) - max(0.0, p0) >= 0.6 * min(Li, Lj):
                grp.append(j)
        if len(grp) < 2:
            continue
        for k in grp:
            used[k] = True
        # grup ekseni: boyuna en uzun yayılım
        ts = []
        for k in grp:
            for q in segs[k]:
                ts.append((q[0] - ax) * ux + (q[1] - ay) * uy)
        t0, t1 = min(ts), max(ts)
        if not (0.4 * upm <= t1 - t0 <= 4.0 * upm):
            continue
        mid = (ax + ux * (t0 + t1) / 2, ay + uy * (t0 + t1) / 2)
        # duvar bandında ve duvara paralel mi? Pencere duvar BOŞLUĞUNDA durur: duvar
        # parçasının doğrusuna dik uzaklık ≤30 cm ve boyuna olarak parçanın ≤1 m ötesinde.
        ok = False
        for wa, wb in walls:
            wdx, wdy = wb[0] - wa[0], wb[1] - wa[1]
            WL = math.hypot(wdx, wdy) or 1.0
            wux, wuy = wdx / WL, wdy / WL
            if abs(wux * ux + wuy * uy) < 0.97:
                continue
            perp = abs((mid[0] - wa[0]) * (-wuy) + (mid[1] - wa[1]) * wux)
            along = (mid[0] - wa[0]) * wux + (mid[1] - wa[1]) * wuy
            if perp <= 0.30 * upm and -1.0 * upm <= along <= WL + 1.0 * upm:
                ok = True
                break
        if ok:
            out.append(((ax + ux * t0, ay + uy * t0), (ax + ux * t1, ay + uy * t1)))
    return out


def _dedupe_windows(wins, tol, aux=None):
    out, out_aux = [], []
    for i, w in enumerate(wins):
        m = ((w[0][0] + w[1][0]) / 2, (w[0][1] + w[1][1]) / 2)
        if any(math.hypot(m[0] - (o[0][0] + o[1][0]) / 2, m[1] - (o[0][1] + o[1][1]) / 2) <= tol for o in out):
            continue
        out.append(w)
        if aux is not None:
            out_aux.append(aux[i])
    if aux is not None:
        return out, out_aux
    return out


def _window_segments(msp, bbox, min_len=8.0, upm=None, walls=None, big_blocks=False, with_sources=False):
    """Pencere parçaları — cihaz yerleşiminde yasak bölge.
    (1) WINDOW_LAYERS çizgileri; upm verilirse ek olarak (2) pencere BLOKLARI (ad/katman
    anahtar kelimesi ya da ince-uzun cam geometrisi) ve (3) duvar bandındaki ince paralel
    çizgi grupları (katman-bağımsız)."""
    x0, y0, x1, y1 = bbox
    segs = []
    for e in msp:
        if e.dxf.layer not in WINDOW_LAYERS:
            continue
        if e.dxftype() not in ("LINE", "LWPOLYLINE", "POLYLINE"):
            continue
        for a, b in _entity_segments(e)[0]:
            if ((x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or
                    (x0 <= b[0] <= x1 and y0 <= b[1] <= y1)):
                if math.hypot(b[0] - a[0], b[1] - a[1]) >= min_len:
                    segs.append(((a[0], a[1]), (b[0], b[1])))
    if not upm:
        return (segs, ["layer"] * len(segs)) if with_sources else segs
    extra, extra_src = [], []
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        if big_blocks and _is_big_block(e, upm):
            try:
                inner = [ve for ve in e.virtual_entities() if ve.dxftype() == "INSERT"]
            except Exception:
                inner = []
            for ve in inner:
                r = _insert_window(ve, upm, x0, y0, x1, y1, walls=walls, with_source=True)
                if r:
                    extra.append(r[0]); extra_src.append(r[1])
            continue
        r = _insert_window(e, upm, x0, y0, x1, y1, walls=walls, with_source=True)
        if r:
            extra.append(r[0]); extra_src.append(r[1])
    thin = _thin_line_windows(msp, bbox, upm, walls or [])
    extra += thin; extra_src += ["thin_lines"] * len(thin)
    ded, ded_src = _dedupe_windows(extra, 0.3 * upm, aux=extra_src)
    if with_sources:
        return segs + ded, ["layer"] * len(segs) + ded_src
    return segs + ded
