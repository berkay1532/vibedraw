# core/perception/walls.py
"""Duvar tespiti: katman kümeleri, paralel-çift filtresi, merdiven/çerçeve elemesi, snap hedefleri.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

from shapely.geometry import LineString, Point

from core.perception.blocks import _entity_segments, _explode, _is_big_block
from core.perception.names import (BARRIER_CLASSES, EMPTY, GATED_MIN_CONF, GRAPH_EDGE_CLASSES, WALL_EXCLUDE_CLASSES,
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


# --- Adım 9: duvar grafı (5a) ------------------------------------------------------------
# Yüz parçaları (paralel çift) → merkez hatları → uç-uç birleştirme (snap) → düğümleme → WallGraph.
# Kapı/geçiş açıklıkları geçici kenar (closure) olarak kapatılır; rooms.graph_faces polygonize eder.
from dataclasses import dataclass, field as _field


@dataclass
class WallGraph:
    edges: list = _field(default_factory=list)      # merkez hattı kenarları [((x,y),(x,y)), ...] (snap sonrası; topoloji)
    face_edges: list = _field(default_factory=list) # duvar YÜZÜ/bariyer kenarları (snap sonrası; polygonize bunlarla)
    cavities: list = _field(default_factory=list)   # yüz çifti boşluk poligonları (merkez hattı ± kalınlık/2) — yüz eleme
    closures: list = _field(default_factory=list)   # geçici kenarlar: kapı kanadı / pencere / geçiş kapatması
    thickness: float = 0.0                          # baskın kalınlık (çizim birimi)
    snap_tol: float = 0.0                           # kullanılan uç-uç toleransı (birim)
    stats: dict = _field(default_factory=dict)      # rapor: yüz/merkez hattı/kapatma sayıları


def centerlines(segs, tmin, tmax, ang_tol_deg=8.0, min_overlap=18.0):
    """Paralel yüz çiftlerinden merkez hatları: örtüşen aralıkta, iki yüzün ortasında bir parça.

    _pair_filter ile aynı eşleşme kuralı; her sırasız çift için tek hat üretir. Döner: [(a, b, kalınlık)].
    """
    n = len(segs)
    dirs = []
    for (a, b) in segs:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        dirs.append((dx / L, dy / L, L, math.atan2(dy, dx)))
    ang_tol = math.radians(ang_tol_deg)
    out, seen = [], set()
    for i in range(n):
        ax, ay = segs[i][0]
        ux, uy, Li, ai = dirs[i]
        for j in range(i + 1, n):
            vx, vy, Lj, aj = dirs[j]
            if abs(((aj - ai + math.pi / 2) % math.pi) - math.pi / 2) > ang_tol:
                continue
            (cx, cy), (dx2, dy2) = segs[j]
            mx, my = (cx + dx2) / 2, (cy + dy2) / 2
            side = (mx - ax) * (-uy) + (my - ay) * ux          # işaretli dik mesafe
            perp = abs(side)
            if not (tmin <= perp <= tmax):
                continue
            p0, p1 = sorted(((cx - ax) * ux + (cy - ay) * uy, (dx2 - ax) * ux + (dy2 - ay) * uy))
            lo, hi = max(0.0, p0), min(Li, p1)
            if hi - lo < min_overlap:
                continue
            s = 1.0 if side > 0 else -1.0
            ox, oy = -uy * s * perp / 2, ux * s * perp / 2       # j tarafına yarım kalınlık
            key = (i, j)
            if key in seen:
                continue
            seen.add(key)
            out.append(((ax + ux * lo + ox, ay + uy * lo + oy), (ax + ux * hi + ox, ay + uy * hi + oy), perp))
    return out


def _merge_collinear(lines, tol_perp, tol_gap, ang_tol_deg=8.0):
    """Doğrultudaş ve yakın (dik mesafe ≤ tol_perp) merkez hatlarını birleştir: aynı eksende örtüşen /
    ≤ tol_gap boşluklu aralıklar tek parçaya iner (yinelenen çift hatları ve parçalı duvarları giderir)."""
    ang_tol = math.radians(ang_tol_deg)
    clusters = []                                   # [ux, uy, offset, [(s0, s1), ...], n]
    for a, b in lines:
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        ux, uy = dx / L, dy / L
        if uy < 0 or (abs(uy) < 1e-12 and ux < 0):
            ux, uy = -ux, -uy                       # yön normalize (θ ∈ [0, π))
        off = a[0] * (-uy) + a[1] * ux
        best = None
        for k, c in enumerate(clusters):
            cos = abs(ux * c[0] + uy * c[1])
            if cos < math.cos(ang_tol):
                continue
            offc = a[0] * (-c[1]) + a[1] * c[0]
            if abs(offc - c[2]) <= tol_perp:
                best = k; break
        if best is None:
            clusters.append([ux, uy, off, [], 0]); best = len(clusters) - 1
        c = clusters[best]
        s0 = a[0] * c[0] + a[1] * c[1]; s1 = b[0] * c[0] + b[1] * c[1]
        c[3].append((min(s0, s1), max(s0, s1)))
        offc = a[0] * (-c[1]) + a[1] * c[0]
        c[2] = (c[2] * c[4] + offc) / (c[4] + 1); c[4] += 1
    out = []
    for ux, uy, off, iv, _ in clusters:
        iv.sort(); merged = []
        for s0, s1 in iv:
            if merged and s0 <= merged[-1][1] + tol_gap:
                merged[-1][1] = max(merged[-1][1], s1)
            else:
                merged.append([s0, s1])
        nx, ny = -uy, ux
        for s0, s1 in merged:
            if s1 - s0 > 1e-6:
                out.append(((nx * off + ux * s0, ny * off + uy * s0), (nx * off + ux * s1, ny * off + uy * s1)))
    return out


def _snap_lines(lines, tol, extend_tol):
    """Uç-uç birleştirme: tol içindeki uçlar tek düğüme çekilir; sarkan uçlar extend_tol içindeki
    bir hatta dik izdüşümüne uzatılır (T-birleşim). Düğümleme unary_union'da yapılır."""
    if not lines:
        return []
    pts = []
    for a, b in lines:
        pts.append(list(a)); pts.append(list(b))
    # 1) uç kümeleme (greedy)
    centers = []
    assign = []
    for p in pts:
        best, bd = None, None
        for k, c in enumerate(centers):
            d = math.hypot(c[0] - p[0], c[1] - p[1])
            if d <= tol and (bd is None or d < bd):
                best, bd = k, d
        if best is None:
            centers.append([p[0], p[1], 1]); assign.append(len(centers) - 1)
        else:
            c = centers[best]; n = c[2]
            c[0] = (c[0] * n + p[0]) / (n + 1); c[1] = (c[1] * n + p[1]) / (n + 1); c[2] = n + 1
            assign.append(best)
    snapped = []
    for k in range(len(lines)):
        ca, cb = centers[assign[2 * k]], centers[assign[2 * k + 1]]
        a, b = (ca[0], ca[1]), (cb[0], cb[1])
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
            snapped.append([a, b])
    # 2) sarkan uçları yakın hatta uzat (T-birleşim / köşe): diğer hattın SONSUZ doğrusuna dik izdüşüm;
    #    izdüşüm parametresi hattın [-extend_tol, L+extend_tol] aralığındaysa kabul (köşede iki uç birlikte kapanır)
    deg = {}
    for a, b in snapped:
        deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
    for k, (a, b) in enumerate(snapped):
        for end in (0, 1):
            p = (a, b)[end]
            if deg.get(p, 0) != 1:
                continue
            best, bd, bp = None, None, None
            for m, (c, d) in enumerate(snapped):
                if m == k:
                    continue
                dx, dy = d[0] - c[0], d[1] - c[1]; L = math.hypot(dx, dy)
                if L < 1e-9:
                    continue
                ux, uy = dx / L, dy / L
                t_ = (p[0] - c[0]) * ux + (p[1] - c[1]) * uy
                if t_ < -extend_tol or t_ > L + extend_tol:
                    continue
                q = (c[0] + ux * t_, c[1] + uy * t_)
                dist = math.hypot(q[0] - p[0], q[1] - p[1])
                if dist > extend_tol or dist < 1e-9:
                    continue
                o = (a, b)[1 - end]                                 # kendi hattının öteki ucu
                sx, sy = p[0] - o[0], p[1] - o[1]; SL = math.hypot(sx, sy) or 1.0
                sx, sy = sx / SL, sy / SL
                if abs(sx * ux + sy * uy) > 0.94:
                    continue                                        # paralel hatta yanal kayma yok
                if ((q[0] - p[0]) * sx + (q[1] - p[1]) * sy) / dist < 0.7:
                    continue                                        # yalnız kendi doğrultusunda ileri uzat
                if bd is None or dist < bd:
                    best, bd, bp = m, dist, q
            if bp is not None and bd > 1e-6:
                snapped[k][end] = bp
    return [(tuple(a), tuple(b)) for a, b in snapped]


def _closure_for(seg, edges, t, ext, cos_tol):
    """Bir açıklık parçasını (kapalı kapı kanadı / pencere camı) doğrultudaş ve bitişik en yakın merkez hattının
    doğrusuna izdüşürür, iki uçtan ext kadar uzatır. Yoksa None."""
    a, b = seg
    lx, ly = b[0] - a[0], b[1] - a[1]; LL = math.hypot(lx, ly)
    if LL < 1e-6:
        return None
    lx, ly = lx / LL, ly / LL
    best = None
    for (c, d) in edges:
        dx, dy = d[0] - c[0], d[1] - c[1]; L = math.hypot(dx, dy)
        if L < 1e-9 or abs(lx * (dx / L) + ly * (dy / L)) < cos_tol:
            continue                                               # doğrultudaş değil
        ux, uy = dx / L, dy / L
        da = abs((a[0] - c[0]) * (-uy) + (a[1] - c[1]) * ux)
        db = abs((b[0] - c[0]) * (-uy) + (b[1] - c[1]) * ux)
        if da > t or db > t:
            continue                                               # parça bu hattın üstünde değil
        ta = (a[0] - c[0]) * ux + (a[1] - c[1]) * uy
        tb = (b[0] - c[0]) * ux + (b[1] - c[1]) * uy
        gap = min(abs(ta), abs(ta - L), abs(tb), abs(tb - L))      # parça ucu hattın ucuna yakın mı
        if gap > 2 * t:
            continue
        key = (gap, da + db)
        if best is None or key < best[0]:
            best = (key, (c, ux, uy, ta, tb))
    if best is None:
        return None
    c, ux, uy, ta, tb = best[1]
    lo, hi = min(ta, tb) - ext, max(ta, tb) + ext
    return ((c[0] + ux * lo, c[1] + uy * lo), (c[0] + ux * hi, c[1] + uy * hi))


def build_wall_graph(walls, thickness_units, upm, G, door_leaves=None, windows=None, closures_extra=None, barrier_segs=None,
                     face_walls=None):
    """Yüz parçaları → WallGraph. G = thresholds 'graph' bölümü; thickness_units baskın kalınlık (birim).

    edges: merkez hatları (paralel yüz çiftleri → orta hat → doğrultudaş birleştirme → uç snap; topoloji).
    face_edges: duvar yüzleri (face_walls: GRAPH_EDGE_CLASSES katmanındaki yüz parçaları; None → walls) + kenar sınıfı
    katman çizgileri (barrier_segs) + kapı/pencere kapatmaları (snap sonrası) — rooms.graph_faces bunları polygonize eder
    (flood-fill'in vektör eşdeğeri). Pencereler kapı gibi mühürlenir (geçici kenar), pencere katmanı çizgisi kenar üretmez.
    door_leaves: openings._door_barriers çıktısı (menteşe, kapalı uç); kanat iki uçtan uzatılır ve uçlarına
    duvar kalınlığı boyunca dik kapak eklenir (kanat iki yüzü de keser). closures_extra: ek geçici kenarlar.
    """
    t = float(thickness_units or 0.0)
    if t <= 0:
        return WallGraph(stats={"reason": "no_thickness"})
    tmin, tmax = G["pair_thickness_m"][0] * upm, G["pair_thickness_m"][1] * upm
    cl = centerlines(walls, tmin=max(tmin, 1e-3), tmax=tmax, ang_tol_deg=G["pair_ang_tol_deg"],
                     min_overlap=G["min_overlap_m"] * upm)
    lines = [(a, b) for a, b, _ in cl]
    snap_tol = G["snap_tol_frac"] * t
    lines = _merge_collinear(lines, G["merge_perp_frac"] * t, snap_tol, G["pair_ang_tol_deg"])
    edges = _snap_lines(lines, snap_tol, G["extend_tol_m"] * upm)
    fsegs = list(walls if face_walls is None else face_walls) + list(barrier_segs or [])
    fl = _merge_collinear(fsegs, G["face_merge_perp_frac"] * t, snap_tol, G["face_merge_ang_tol_deg"])
    closures, n_door = [], 0
    ext = G["door_closure_extend_frac"] * t
    cap = G["door_cap_frac"] * t
    for hinge, tip in (door_leaves or []):
        dx, dy = tip[0] - hinge[0], tip[1] - hinge[1]; L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        ux, uy = dx / L, dy / L; nx, ny = -uy, ux
        closures.append(((hinge[0] - ux * ext, hinge[1] - uy * ext), (tip[0] + ux * ext, tip[1] + uy * ext)))
        for q in (hinge, tip):                                        # dik kapaklar: kanat iki yüzü de keser
            closures.append(((q[0] - nx * cap, q[1] - ny * cap), (q[0] + nx * cap, q[1] + ny * cap)))
        n_door += 1
    for a, b in (windows or []):                                      # pencere açıklığı: kapı gibi mühür (geçici kenar)
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        ux, uy = dx / L, dy / L
        closures.append(((a[0] - ux * ext, a[1] - uy * ext), (b[0] + ux * ext, b[1] + uy * ext)))
    face_edges = _snap_lines(fl + closures, snap_tol, G["extend_tol_m"] * upm)
    cav = [LineString([a, b]).buffer(th / 2.0, cap_style=2) for a, b, th in cl]
    for c in (closures_extra or []):
        closures.append(c)
    return WallGraph(edges=edges, face_edges=face_edges, cavities=cav, closures=closures, thickness=t, snap_tol=snap_tol,
                     stats={"faces_in": len(walls if face_walls is None else face_walls), "barrier_segs": len(barrier_segs or []),
                            "window_closures": len(windows or []), "centerlines": len(cl),
                            "merged": len(lines), "edges": len(edges), "face_edges": len(face_edges), "door_closures": n_door})


def wall_cavities(segs, thickness_units, upm, G):
    """Yüz parçaları → merkez hattı × kalınlık boşluk poligonları (build_wall_graph.cavities ile aynı hesap, alt küme için:
    ince çizgi birleştirme testinde kiriş sınıfı çiftler 'kalın' sayılmaz → kiriş izdüşümü odayı bölmez)."""
    t = float(thickness_units or 0.0)
    if t <= 0 or not segs:
        return []
    tmin, tmax = G["pair_thickness_m"][0] * upm, G["pair_thickness_m"][1] * upm
    cl = centerlines(segs, tmin=max(tmin, 1e-3), tmax=tmax, ang_tol_deg=G["pair_ang_tol_deg"], min_overlap=G["min_overlap_m"] * upm)
    return [LineString([a, b]).buffer(th / 2.0, cap_style=2) for a, b, th in cl]


def passage_closures(edges, G, upm):
    """Geçiş açıklıkları: sarkan (derece 1, başka hatta değmeyen) bir uçtan kendi doğrultusunda [passage_min, passage_max] m
    uzaklıkta doğrultudaş başka bir sarkan uç varsa geçici kapatma kenarı. Raster mühürünün vektör eşdeğeri;
    kapısız geçişler ve T-birleşim sonrası devam eden duvar boşlukları burada kapanır."""
    from shapely.geometry import LineString as _LS, Point as _Pt
    deg, dirs = {}, {}
    for a, b in edges:
        deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1.0
        dirs.setdefault(a, []).append((dx / L, dy / L)); dirs.setdefault(b, []).append((dx / L, dy / L))
    els = [_LS(e) for e in edges]
    def _dangling(p):
        if deg.get(p, 0) != 1:
            return False
        pt = _Pt(p)
        return sum(1 for e in els if e.distance(pt) <= 1e-6) <= 1     # yalnız kendi hattı: gerçek sarkan uç
    dang = [p for p in deg if _dangling(p)]
    lo, hi = G["passage_min_m"] * upm, G["passage_max_m"] * upm
    cos_tol = math.cos(math.radians(G["passage_ang_tol_deg"]))
    out, used = [], set()
    for p in dang:                                                    # yalnız sarkan ↔ sarkan (düğüme kapatma odaları böldü)
        if p in used:
            continue
        ux, uy = dirs[p][0]
        best, bd = None, None
        for q in dang:
            if q == p or q in used:
                continue
            gx, gy = q[0] - p[0], q[1] - p[1]; L = math.hypot(gx, gy)
            if not (lo <= L <= hi):
                continue
            if abs((ux * gx + uy * gy) / L) < cos_tol:
                continue                                              # kendi doğrultusunda değil
            if not any(abs(vx * ux + vy * uy) >= cos_tol for vx, vy in dirs[q]):
                continue                                              # karşı uçta duvar aynı doğrultuda devam etmiyor
            if bd is None or L < bd:
                best, bd = q, L
        if best is not None:
            out.append((p, best)); used.add(p); used.add(best)
    return out


def stair_footprints(msp, bbox, names, buffer_units, min_area_units, big_blocks=False):
    """Merdiven sınıfı katmanlardaki çizgilerden ayak izi poligonları (birleşik tampon → dışbükey zarf)."""
    from shapely.geometry import LineString as _LS
    from shapely.ops import unary_union as _uu
    from core.perception.names import LayerClass as _LC
    segs = []
    x0, y0, x1, y1 = bbox
    for e in msp:
        try:
            lay = e.dxf.layer
        except Exception:
            continue
        ents = [e]
        if e.dxftype() == "INSERT":
            if not big_blocks:
                continue
            ents = list(_explode(e))
        for ve in ents:
            try:
                vl = ve.dxf.layer
            except Exception:
                continue
            if not names.has(vl, {_LC.stair}, 0.0) and not names.has(lay, {_LC.stair}, 0.0):
                continue
            if ve.dxftype() not in ("LINE", "LWPOLYLINE", "POLYLINE"):
                continue
            ss, _ = _entity_segments(ve)
            for a, b in ss:
                if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                    segs.append(_LS([a, b]))
    if not segs:
        return []
    u = _uu([s.buffer(buffer_units) for s in segs])
    polys = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    return [p.convex_hull for p in polys if p.area >= min_area_units]


def barrier_segments(msp, bbox, names, classes=BARRIER_CLASSES):
    """Raster bariyerinin vektör eşdeğeri: `classes` sınıfı (varsayılan bariyer: wall/beam/column/chimney/window; duvar grafı
    için GRAPH_EDGE_CLASSES) katmanlardaki LINE/LWPOLYLINE/ARC parçaları (INSERT hariç; blok içi duvarlar
    _wall_segments(big_blocks) ile gelir)."""
    x0, y0, x1, y1 = bbox
    out = []
    for e in msp:
        if e.dxftype() == "INSERT":
            continue
        try:
            lay = e.dxf.layer
        except Exception:
            continue
        if not names.has(lay, classes):
            continue
        if e.dxftype() == "HATCH":
            segs = _hatch_segments(e)
        else:
            segs, _ = _entity_segments(e)
        for a, b in segs:
            if (x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or (x0 <= b[0] <= x1 and y0 <= b[1] <= y1):
                out.append(((a[0], a[1]), (b[0], b[1])))
    return out
