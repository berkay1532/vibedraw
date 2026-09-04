# core/perception/polygons.py
"""Maske → oda poligonu: staircase çıkarımı, kenar snap, basamak giderme, dik köşe zorlama.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

from core.perception.raster import _Raster


def _snap_coord(v, coords, tol):
    best, bd = v, tol
    for c in coords:
        if abs(c - v) < bd:
            bd, best = abs(c - v), c
    return best


def _dedupe_colinear(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 0.05 or abs(p[1] - out[-1][1]) > 0.05:
            out.append((float(p[0]), float(p[1])))
    res = []
    m = len(out)
    for i in range(m):
        a, b, c = out[(i - 1) % m], out[i], out[(i + 1) % m]
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(cross) > 1e-6:
            res.append(b)
    return res


def _edge_snap_rect(coords, cx, cy, tol=4.0):
    """Yatay kenarın y'sini, dikey kenarın x'ini en yakın duvar hattına oturt
    (vertex değil KENAR snap -> rectilinearlik korunur)."""
    pts = [list(p) for p in coords]
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if abs(b[1] - a[1]) < abs(b[0] - a[0]):       # yatay kenar
            ny = _snap_coord((a[1] + b[1]) / 2, cy, tol)
            a[1] = ny; b[1] = ny
        else:                                          # dikey kenar
            nx = _snap_coord((a[0] + b[0]) / 2, cx, tol)
            a[0] = nx; b[0] = nx
    return _dedupe_colinear(pts)


def _emanhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _remove_small_steps(pts, min_len=8.0):
    """Kısa kenarları, daha uzun komşu duvara hizalayıp yut (rectilinear sadeleştirme)."""
    pts = [tuple(p) for p in pts]
    while len(pts) > 4:
        n = len(pts)
        i = min(range(n), key=lambda k: _emanhattan(pts[k], pts[(k + 1) % n]))
        a, b = pts[i], pts[(i + 1) % n]
        if _emanhattan(a, b) >= min_len:
            break
        prev, nxt = pts[(i - 1) % n], pts[(i + 2) % n]
        lp, ln = _emanhattan(prev, a), _emanhattan(b, nxt)
        if abs(a[1] - b[1]) < abs(a[0] - b[0]):        # kısa yatay kenar
            xs = a[0] if lp >= ln else b[0]
            pts[i] = (xs, a[1]); pts[(i + 1) % n] = (xs, b[1])
        else:                                          # kısa dikey kenar
            ystar = a[1] if lp >= ln else b[1]
            pts[i] = (a[0], ystar); pts[(i + 1) % n] = (b[0], ystar)
        pts = _dedupe_colinear(pts)
    return pts


def _force_rectilinear(pts):
    """Kalan her diyagonal kenarı L-köşeye (90°) böl. Dik odalar için."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        out.append(a)
        if abs(b[0] - a[0]) > 0.5 and abs(b[1] - a[1]) > 0.5:
            out.append((a[0], b[1]))
    return _dedupe_colinear(out)


def _staircase_polygon(mask, raster: _Raster):
    """Maskenin piksel sınırından saf-rectilinear (H/V) staircase poligon.

    Kenarlar TAMSAYI piksel koordinatlarında (2c±1, 2r±1) kurulur; polygonize bittikten
    sonra dünyaya çevrilir. Dünya koordinatında (ör. 4.4 milyon birim) kurulunca kayan
    nokta hassasiyeti halkayı kapatamıyor ve polygonize boş dönüyordu.
    """
    res = raster.res
    ys, xs = np.where(mask)
    if len(xs) < 3:
        return None
    cells = set(zip(xs.tolist(), ys.tolist()))
    edges = []
    for (c, r) in cells:
        X, Y = 2 * c, 2 * r
        if (c, r - 1) not in cells:
            edges.append(((X - 1, Y - 1), (X + 1, Y - 1)))
        if (c, r + 1) not in cells:
            edges.append(((X - 1, Y + 1), (X + 1, Y + 1)))
        if (c - 1, r) not in cells:
            edges.append(((X - 1, Y - 1), (X - 1, Y + 1)))
        if (c + 1, r) not in cells:
            edges.append(((X + 1, Y - 1), (X + 1, Y + 1)))
    if not edges:
        return None
    polys = list(polygonize(unary_union([LineString(e) for e in edges])))
    if not polys:
        return None
    best = max(polys, key=lambda p: p.area)
    from shapely.geometry import Polygon as _P
    return _P([(raster.x0 + X / 2.0 * res, raster.y0 + Y / 2.0 * res)
               for X, Y in best.exterior.coords])


def _mask_polygon(mask, raster: _Raster, cx, cy, angled_walls):
    """Maskeden CAD-kalitesinde oda poligonu.

    Oda dik mi açılı mı sınıflandırılır:
    - Dik oda (yakınında gerçek açılı duvar yok): KENAR-snap + küçük-basamak
      giderme + L-köşe zorlama -> saf 90° (Manhattan) sınır.
    - Açılı oda (Balkon gibi, yakınında uzun açılı duvar var): konkav + DP ->
      açılı duvarı tek diyagonal kenarla takip eder.
    """
    raw = _staircase_polygon(mask, raster)
    if raw is None:
        return None

    # Eşikler res (birim/piksel) ile ölçeklenir -> farklı dosya ölçeklerinde tutarlı.
    rs = raster.res
    is_angled = any(raw.boundary.distance(w) < 12.0 for w in angled_walls)
    if is_angled:
        poly = raw.simplify(rs * 3.0)
    else:
        pts = _edge_snap_rect(list(raw.exterior.coords)[:-1], cx, cy, tol=4.0 * rs)
        pts = _remove_small_steps(pts, min_len=8.0 * rs)
        pts = _force_rectilinear(pts)   # son adım: saf 90° garantisi
        from shapely.geometry import Polygon as _P
        poly = _P(pts).buffer(0)
        if poly.geom_type != "Polygon" or poly.is_empty:
            poly = raw.simplify(raster.res * 2.0)
    if poly.geom_type != "Polygon":
        return None
    return [(float(x), float(y)) for x, y in poly.exterior.coords]
