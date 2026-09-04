# core/perception/walls.py
"""Duvar tespiti: katman kümeleri, paralel-çift filtresi, merdiven/çerçeve elemesi, snap hedefleri.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

from shapely.geometry import LineString

from core.perception.blocks import _entity_segments, _explode, _is_big_block
from core.perception.names import (BARRIER_CLASSES, EMPTY, GATED_MIN_CONF, WALL_EXCLUDE_CLASSES,
                                   WALL_SCAN_CLASSES)
from core.perception.vocab import ANNO_LAYER_WORDS, fold




def _ladder_filter(segs, dmin, dmax, ang_tol_deg=8.0, min_overlap_frac=0.5, min_neighbors=3):
    """'Merdiven' gruplarını ele: bir parçanın dmin..dmax dik mesafede, boyuna ≥%50 örtüşen
    ≥min_neighbors paralel komşusu varsa basamak çizgisidir (kapı kanadı 1-2 çizgidir)."""
    n = len(segs)
    if n < min_neighbors + 1:
        return segs
    dirs = []
    for a, b in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        dirs.append((dx / L, dy / L, L, math.atan2(dy, dx)))
    ang_tol = math.radians(ang_tol_deg)
    out = []
    for i in range(n):
        ax, ay = segs[i][0]
        ux, uy, Li, ai = dirs[i]
        cnt = 0
        for j in range(n):
            if j == i:
                continue
            vx, vy, Lj, aj = dirs[j]
            if abs(((aj - ai + math.pi / 2) % math.pi) - math.pi / 2) > ang_tol:
                continue
            (cx, cy), (dx2, dy2) = segs[j]
            mx, my = (cx + dx2) / 2, (cy + dy2) / 2
            perp = abs((mx - ax) * (-uy) + (my - ay) * ux)
            if not (dmin <= perp <= dmax):
                continue
            p0, p1 = sorted(((cx - ax) * ux + (cy - ay) * uy, (dx2 - ax) * ux + (dy2 - ay) * uy))
            if min(Li, p1) - max(0.0, p0) >= min_overlap_frac * min(Li, Lj):
                cnt += 1
                if cnt >= min_neighbors:
                    break
        if cnt < min_neighbors:
            out.append(segs[i])
    return out


def _cluster(vals, tol=3.0):
    """Yakın koordinatları (duvar hatları) tek temsile indir."""
    vals = sorted(set(round(v, 1) for v in vals))
    out = []
    for v in vals:
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def _wall_lines(msp, bbox, ang_tol=10.0, angled_min_len=15.0, cluster_tol=3.0, extra_segs=None, names=EMPTY):
    """Duvarlardan: eksen-x kümeleri, eksen-y kümeleri, gerçek açılı duvar çizgileri.
    extra_segs: katman-bağımsız tespit edilmiş duvar parçaları (snap hedefine eklenir)."""
    x0, y0, x1, y1 = bbox
    xs, ys, angled = [], [], []

    def _segs():
        for e in msp:
            if names.has(e.dxf.layer, BARRIER_CLASSES):      # bariyer sınıfı = snap hedefi
                yield from _entity_segments(e)[0]
        yield from (extra_segs or [])

    for a, b in _segs():
        if True:
            if not (x0 <= a[0] <= x1 and y0 <= a[1] <= y1):
                continue
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            if L < 2.0:
                continue
            ang = math.degrees(math.atan2(abs(dy), abs(dx)))
            if ang < ang_tol:
                ys += [a[1], b[1]]
            elif ang > 90 - ang_tol:
                xs += [a[0], b[0]]
            elif L > angled_min_len:
                angled.append(LineString([a, b]))
    return _cluster(xs, cluster_tol), _cluster(ys, cluster_tol), angled


# Duvar tespitinden hariç: kapı, metin, merdiven (basamak), KİRİŞ (tavan elemanı —
# oda ortasından geçer, duvar değil; çiftli gidince sahte duvar yapıyordu)
# DENENDİ ve GERİ ALINDI: "yazı/ölçü/aks" adlı katmanları duvar adayından çıkarmak ölçümü
# düşürdü (bazı CAD export'larında "ANNO" adlı katmanlarda gerçek geometri var). Fonksiyon
# referans için duruyor, kullanılmıyor. Ayrıntı: docs/HITL_QUESTIONS.md #3. Kelimeler vocab.ANNO_LAYER_WORDS.
def _is_anno_layer(name: str) -> bool:
    return any(w in fold(name) for w in ANNO_LAYER_WORDS)




def _hatch_segments(e):
    """HATCH sınır yolunu segmentlere çevirir (dolu duvar/kolon poché'si)."""
    out = []
    for pth in e.paths.paths:
        pts = []
        try:
            pts = [(v[0], v[1]) for v in pth.vertices]
        except Exception:
            try:
                for edge in pth.edges:
                    if hasattr(edge, "start") and hasattr(edge, "end"):
                        out.append(((edge.start[0], edge.start[1]),
                                    (edge.end[0], edge.end[1])))
            except Exception:
                pass
        out += list(zip(pts, pts[1:]))
        if len(pts) > 2:
            out.append((pts[-1], pts[0]))
    return out


def _pair_filter(segs, tmin=4.0, tmax=42.0, ang_tol_deg=8.0, min_overlap=18.0, aux=None, with_thickness=False):
    """Duvar = belli kalınlıkta yan yana İKİ paralel yüz. Eşi olmayan parçayı eler.

    Korkuluk X'i (paralel değil), tek tesisat çizgisi (eşsiz), tezgâh (çok kalın >tmax)
    elenir; gerçek duvar yüzleri (eğik dış duvar dahil) kalır.
    """
    n = len(segs)
    dirs = []
    for (a, b) in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        dirs.append((dx / L, dy / L, L, math.atan2(dy, dx)))
    ang_tol = math.radians(ang_tol_deg)
    keep = [False] * n
    thick = [None] * n                        # eşleşen çiftin dik mesafesi (kalınlık, birim)
    for i in range(n):
        ax, ay = segs[i][0]
        ux, uy, Li, ai = dirs[i]
        for j in range(n):
            if j == i:
                continue
            vx, vy, Lj, aj = dirs[j]
            if abs(((aj - ai + math.pi / 2) % math.pi) - math.pi / 2) > ang_tol:
                continue                                   # paralel değil
            (cx, cy), (dx2, dy2) = segs[j]
            mx, my = (cx + dx2) / 2, (cy + dy2) / 2
            perp = abs((mx - ax) * (-uy) + (my - ay) * ux)  # dik mesafe (kalınlık)
            if not (tmin <= perp <= tmax):
                continue
            p0, p1 = sorted(((cx - ax) * ux + (cy - ay) * uy,
                             (dx2 - ax) * ux + (dy2 - ay) * uy))
            if min(Li, p1) - max(0.0, p0) >= min_overlap:   # boyuna örtüşme
                keep[i] = keep[j] = True
                if thick[i] is None:
                    thick[i] = perp
                if thick[j] is None:
                    thick[j] = perp
                break
    if aux is not None:                       # kaynak bilgisi: segs ile hizalı yan liste
        if with_thickness:
            return ([s for s, k in zip(segs, keep) if k], [a for a, k in zip(aux, keep) if k],
                    [t for t, k in zip(thick, keep) if k])
        return [s for s, k in zip(segs, keep) if k], [a for a, k in zip(aux, keep) if k]
    return [s for s, k in zip(segs, keep) if k]


def _is_label_frame(e, label_pts, max_area):
    """Kapalı, küçük (≤max_area) ve içinde oda etiketi olan polyline = etiket ÇERÇEVESİ
    (zone stamp / mahal kutusu) — duvar değil; uzun kenarları ≤45 cm aralıklı olduğu
    için paralel-çift filtresini geçip odayı kutunun içine hapsediyordu."""
    if not label_pts or e.dxftype() != "LWPOLYLINE" or not e.closed:
        return False
    try:
        P = [(q[0], q[1]) for q in e.get_points()]
    except Exception:
        return False
    if len(P) < 3:
        return False
    xs = [q[0] for q in P]; ys = [q[1] for q in P]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if (x1 - x0) * (y1 - y0) > max_area:
        return False
    return any(x0 <= lx <= x1 and y0 <= ly <= y1 for lx, ly in label_pts)


def _wall_segments(msp, bbox, min_len=8.0, tmin=4.0, tmax=42.0, min_overlap=18.0, big_blocks=False,
                   label_pts=None, with_sources=False, names=EMPTY, with_signals=False):
    """TÜM düz duvar geometrisi (katman-bağımsız) — cihaz snap + M3 routing için.
    tmin/tmax/min_overlap çizim biriminde (varsayılanlar 1 birim = 1 cm için).

    Katman etiketine güvenmez (mimar tutarsız: dış duvar mobilya katmanında, bazıları hatch/'0').
    Düz çizgi (LINE/LWPOLYLINE) + HATCH sınırı alınır; yuvarlak tesisat (ARC/CIRCLE),
    kapı/metin/merdiven katmanları dışlanır (sahte duvar olmasın).
    """
    x0, y0, x1, y1 = bbox

    def inb(a, b):
        return ((x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or
                (x0 <= b[0] <= x1 and y0 <= b[1] <= y1))

    segs = []
    srcs = []                                     # with_sources: "pair+layer" | "pair"
    lays = []                                     # with_signals: segmentin katmanı (sinyal: layer_class_vote)
    upm_est = tmin / 0.06 if tmin else 100.0
    frame_area = 3.0 * upm_est * upm_est
    for e in msp:
        if names.has(e.dxf.layer, WALL_EXCLUDE_CLASSES, GATED_MIN_CONF):   # hariç tutma profil güveni ister
            continue
        t = e.dxftype()
        if t in ("LINE", "LWPOLYLINE", "POLYLINE"):
            if _is_label_frame(e, label_pts, frame_area):
                continue
            cand = _entity_segments(e)[0]
        elif t == "HATCH":
            cand = _hatch_segments(e)
        elif t == "INSERT" and big_blocks and _is_big_block(e, upm_est):
            # Kat planı/daire BLOK olarak yerleştirilmiş çizimler: içindeki düz çizgiler
            # de duvar adayı. Mobilya blokları (<3 m) girmez.
            cand = []
            for ve in _explode(e):
                if names.has(ve.dxf.layer, WALL_EXCLUDE_CLASSES, GATED_MIN_CONF):
                    continue
                if ve.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE"):
                    cand += _entity_segments(ve)[0]
        else:
            continue                              # ARC/CIRCLE/TEXT atla
        lay_ok = names.has(e.dxf.layer, WALL_SCAN_CLASSES)
        for a, b in cand:
            if inb(a, b) and math.hypot(b[0] - a[0], b[1] - a[1]) >= min_len:
                segs.append(((a[0], a[1]), (b[0], b[1])))
                srcs.append("pair+layer" if lay_ok else "pair")
                lays.append(e.dxf.layer)
    if with_signals:                              # (segs, srcs, layers, thickness) — sinyal motoru için
        out, aux, thick = _pair_filter(segs, tmin=tmin, tmax=tmax, min_overlap=min_overlap,
                                       aux=list(zip(srcs, lays)), with_thickness=True)
        return out, [a[0] for a in aux], [a[1] for a in aux], thick
    if with_sources:
        return _pair_filter(segs, tmin=tmin, tmax=tmax, min_overlap=min_overlap, aux=srcs)
    return _pair_filter(segs, tmin=tmin, tmax=tmax, min_overlap=min_overlap)
