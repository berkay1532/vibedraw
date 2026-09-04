# core/geometry.py
"""Aşama: Geometri temeli (M1).

Duvar/kapı parçalarından raster flood-fill ile oda poligonu ve temsilî merkez
çıkarır; kapıları tespit eder. Yöntem: morfolojik kapama (duvarları kalınlaştır)
ile kapı/balkon açıklıklarını mühürle, sonra her oda etiketinden flood-fill.

Saf fonksiyon: LangGraph/pipeline'dan bağımsız çağrılabilir ve test edilebilir.
"""
from __future__ import annotations
import math
from collections import deque

import numpy as np
import ezdxf
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union

from core.perception.ir_v1 import BuildingIR, Floor, Room, Door

# Bariyer sayılan katmanlar (oda sınırını oluşturanlar).
# .ABM-SIVA = sıva = duvarın İÇ YÜZÜ (oda sınırı için en kritik katman),
# .ABM-KİRİŞ = kiriş. Bunlar olmadan snap hedefi eksik kalıp poligon jaggy oluyordu.
WALL_LAYERS = {
    "duv", "PislikMimar.com - duvar", ".ABM-DUVAR", ".ABM-SIVA", ".ABM-KİRİŞ",
    "KOLON", "pencere", "cam", "KAPI_PENCERE", "BACA",
}  # NOT: "ince" çıkarıldı — mutfak tezgahı/dolap gibi mobilya da orada (duvar değil)
DOOR_LAYERS = {"kapi", ".KAPI", ".ABM-KAPI"}


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


def _floor_bbox(floor: Floor, margin: float):
    xs = [r.label_xy[0] for r in floor.rooms]
    ys = [r.label_xy[1] for r in floor.rooms]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def _dilate(grid: np.ndarray, k: int) -> np.ndarray:
    for _ in range(k):
        d = grid.copy()
        d[1:, :] |= grid[:-1, :]
        d[:-1, :] |= grid[1:, :]
        d[:, 1:] |= grid[:, :-1]
        d[:, :-1] |= grid[:, 1:]
        grid = d
    return grid


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


class _Raster:
    """Hedef kat için duvar/kapı raster ızgarası + koordinat dönüşümü."""

    def __init__(self, msp, bbox, res: float, seal: int, extra_segs=None,
                 door_arc_radius=None, big_blocks=False):
        """extra_segs: katman-bağımsız tespit edilmiş duvar/pencere parçaları — bariyer
        olarak WALL_LAYERS'a EK çizilir (mimarın katman adlarından bağımsızlık)."""
        self.x0, self.y0, self.x1, self.y1 = bbox
        self.res = res
        self.W = int((self.x1 - self.x0) / res) + 1
        self.H = int((self.y1 - self.y0) / res) + 1
        grid = np.zeros((self.H, self.W), dtype=bool)
        self.door_raw: list[tuple[float, float]] = []
        self.door_blocks: list[tuple[float, float]] = []  # INSERT kapı blokları (yüksek güven)
        self.arcs: list[tuple[float, float, float]] = []  # tüm ARC'lar (kapı yayı adayı)
        door_segs: list = []                        # kapı katmanı çizgileri (bariyer adayı)

        for e in msp:
            lay = e.dxf.layer
            # Kapı katmanındaki BLOK yerleşimi = kesin kapı (insert noktası).
            if e.dxftype() == "INSERT":
                if lay in DOOR_LAYERS:
                    # Gerçek menteşe = blok içi swing ARC merkezi (matrix44). Yoksa insert.
                    hinge = _block_door_hinge(e)
                    ix, iy = (hinge[0], hinge[1]) if hinge else (e.dxf.insert[0], e.dxf.insert[1])
                    if self._in_bbox(ix, iy):
                        self.door_blocks.append((ix, iy))
                        self.door_raw.append((ix, iy))
                    continue
                # Katman-bağımsız: HERHANGİ bir blokta kapı-yarıçaplı 60-120° yay = kapı
                # (Revit/yabancı şablonlarda kapı katmanı adı bilinmiyor).
                if door_arc_radius is not None:
                    hinge = _block_door_hinge(e, *door_arc_radius)
                    if hinge and self._in_bbox(hinge[0], hinge[1]):
                        self.door_blocks.append((hinge[0], hinge[1]))
                        self.door_raw.append((hinge[0], hinge[1]))
                continue
            if e.dxftype() == "INSERT" and big_blocks and door_arc_radius is not None and _is_big_block(e, door_arc_radius[0] / 0.55):
                for ve in _explode(e):
                    if ve.dxftype() == "ARC" and _door_like_arc(ve, 1.0, *door_arc_radius):
                        cx_, cy_ = ve.dxf.center[0], ve.dxf.center[1]
                        if self._in_bbox(cx_, cy_):
                            self.arcs.append((cx_, cy_, ve.dxf.radius))
                continue
            # ARC = kapı açılış yayı adayı (yarıçapı sonra kapı genişliğine göre süzülür).
            if e.dxftype() == "ARC":
                cx_, cy_ = e.dxf.center[0], e.dxf.center[1]
                if self._in_bbox(cx_, cy_):
                    self.arcs.append((cx_, cy_, e.dxf.radius))
                # devam: yay duvar katmanındaysa bariyer olarak da çizilebilir
            if lay not in WALL_LAYERS and lay not in DOOR_LAYERS:
                continue
            segs, allp = _entity_segments(e)
            # Kapı katmanı çizgileri BARİYER DEĞİL: kapı bir açıklıktır; kapalı kanat
            # mührü _door_barriers ile ayrıca çizilir. (Referans dosyada merdiven
            # basamakları 'kapi' katmanındaydı → merdiven alanı bölünüyordu.)
            if lay in WALL_LAYERS:
                for a, b in segs:
                    if self._in_bbox(*a) or self._in_bbox(*b):
                        self._draw(grid, a, b)
            elif lay in DOOR_LAYERS:
                for a, b in segs:
                    if self._in_bbox(*a) or self._in_bbox(*b):
                        door_segs.append(((a[0], a[1]), (b[0], b[1])))
            if lay in DOOR_LAYERS and allp:
                cx = sum(p[0] for p in allp) / len(allp)
                cy = sum(p[1] for p in allp) / len(allp)
                if self._in_bbox(cx, cy):
                    self.door_raw.append((cx, cy))

        for a, b in (extra_segs or []):
            if self._in_bbox(*a) or self._in_bbox(*b):
                self._draw(grid, a, b)
        # Kapı katmanı çizgileri: kapı KANADI (sürgülü/yaysız kapıda tek bariyer) çizilir;
        # aynı katmana çizilmiş MERDİVEN basamakları (≥4 eşit aralıklı paralel) çizilmez.
        if door_segs:
            upm_est = (door_arc_radius[0] / 0.55) if door_arc_radius else 100.0
            for a, b in _ladder_filter(door_segs, 0.15 * upm_est, 1.0 * upm_est):
                self._draw(grid, a, b)

        # base: dilatasyonsuz gerçek duvarlar (extent geri kazanımı için).
        self.base = grid
        # grid: morfolojik kapama (dilate) — kapı/balkon açıklıkları mühürlü
        # (doğru topoloji/ayrışma için).
        self.grid = _dilate(grid, seal)
        self.seal = seal

    def to_px(self, x, y):
        return int((x - self.x0) / self.res), int((y - self.y0) / self.res)

    def to_world(self, c, r):
        return self.x0 + c * self.res, self.y0 + r * self.res

    def _in_bbox(self, x, y):
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def _draw(self, grid, p, q):
        ca, ra = self.to_px(*p)
        cb, rb = self.to_px(*q)
        n = max(abs(cb - ca), abs(rb - ra)) + 1
        for i in range(n):
            t = i / max(n - 1, 1)
            c = int(round(ca + (cb - ca) * t))
            r = int(round(ra + (rb - ra) * t))
            if 0 <= r < self.H and 0 <= c < self.W:
                grid[r, c] = True


def _door_like_arc(ent, sx, amin, amax, sweep=(55.0, 125.0)):
    """Blok içi ARC bir kapı kanadı yayı mı? (yarıçap aralığı + süpürme açısı)"""
    if ent.dxftype() != "ARC" or not (amin <= ent.dxf.radius * sx <= amax):
        return False
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


def _seed_candidates(grid, sr, sc, max_rad=12):
    """Etiket pikselinden başlayarak artan halkalarda boş pikselleri (aday tohumları)
    yakından uzağa üretir. Etiket klozet/dolap çizgisine denk gelebilir; ilk boş piksel
    küçük bir kapalı fikstür içi olabilir → çağıran, akış boyutuna göre aday seçer."""
    H, W = grid.shape
    if 0 <= sr < H and 0 <= sc < W and not grid[sr, sc]:
        yield sr, sc
    for rad in range(1, max_rad + 1):
        for dr in range(-rad, rad + 1):
            for dc in (-rad, rad) if abs(dr) != rad else range(-rad, rad + 1):
                r, c = sr + dr, sc + dc
                if 0 <= r < H and 0 <= c < W and not grid[r, c]:
                    yield r, c


def _seed_free(grid, sr, sc, max_rad=12):
    """Tohum duvara denk gelirse en yakın boş piksele kaydır."""
    for r, c in _seed_candidates(grid, sr, sc, max_rad):
        return r, c
    return sr, sc


def _flood(grid, sr, sc):
    H, W = grid.shape
    mask = np.zeros_like(grid)
    if not (0 <= sr < H and 0 <= sc < W) or grid[sr, sc]:
        return mask, 0
    dq = deque([(sr, sc)])
    mask[sr, sc] = True
    cnt = 0
    while dq:
        r, c = dq.popleft()
        cnt += 1
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r2, c2 = r + dr, c + dc
            if 0 <= r2 < H and 0 <= c2 < W and not grid[r2, c2] and not mask[r2, c2]:
                mask[r2, c2] = True
                dq.append((r2, c2))
    return mask, cnt


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


def _wall_lines(msp, bbox, ang_tol=10.0, angled_min_len=15.0, cluster_tol=3.0, extra_segs=None):
    """Duvarlardan: eksen-x kümeleri, eksen-y kümeleri, gerçek açılı duvar çizgileri.
    extra_segs: katman-bağımsız tespit edilmiş duvar parçaları (snap hedefine eklenir)."""
    x0, y0, x1, y1 = bbox
    xs, ys, angled = [], [], []

    def _segs():
        for e in msp:
            if e.dxf.layer in WALL_LAYERS:
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
# referans için duruyor, kullanılmıyor. Ayrıntı: docs/HITL_QUESTIONS.md #3.
_ANNO_LAYER_WORDS = ("yazi", "yazı", "text", "txt", "anno", "olcu", "ölçü", "dim",
                     "aks", "axis", "grid", "lejant", "legend")


def _is_anno_layer(name: str) -> bool:
    f = (name or "").replace("İ", "i").replace("I", "ı").casefold()
    return any(w in f for w in _ANNO_LAYER_WORDS)


WALL_EXCLUDE_LAYERS = DOOR_LAYERS | {
    "YAZI", "MAHAL ADI", "MERDİVEN YAZI", "merdiven", "MERDIVEN YAZI",
    ".ABM-KİRİŞ", ".ABM-KIRIS",
}


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


WINDOW_LAYERS = {"pencere", "cam", "KAPEN", "KAPI_PENCERE"}


WINDOW_WORDS = ("pencere", "window", "glz", "glazing", "fenetre", "ventana", "cam ")


def _window_word(name: str) -> bool:
    f = (name or "").replace("İ", "i").replace("I", "ı").casefold() + " "
    return any(w in f for w in WINDOW_WORDS)


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


def _pair_filter(segs, tmin=4.0, tmax=42.0, ang_tol_deg=8.0, min_overlap=18.0, aux=None):
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
                break
    if aux is not None:                       # kaynak bilgisi: segs ile hizalı yan liste
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
                   label_pts=None, with_sources=False):
    """TÜM düz duvar geometrisi (katman-bağımsız) — cihaz snap + M3 routing için.
    tmin/tmax/min_overlap çizim biriminde (varsayılanlar 1 birim = 1 cm için).

    Katman etiketine güvenmez (mimar tutarsız: dış duvar 'ince'de, bazıları hatch/'0').
    Düz çizgi (LINE/LWPOLYLINE) + HATCH sınırı alınır; yuvarlak tesisat (ARC/CIRCLE),
    kapı/metin/merdiven katmanları dışlanır (sahte duvar olmasın).
    """
    x0, y0, x1, y1 = bbox

    def inb(a, b):
        return ((x0 <= a[0] <= x1 and y0 <= a[1] <= y1) or
                (x0 <= b[0] <= x1 and y0 <= b[1] <= y1))

    segs = []
    srcs = []                                     # with_sources: "pair+layer" | "pair"
    upm_est = tmin / 0.06 if tmin else 100.0
    frame_area = 3.0 * upm_est * upm_est
    for e in msp:
        if e.dxf.layer in WALL_EXCLUDE_LAYERS:
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
                if ve.dxf.layer in WALL_EXCLUDE_LAYERS:
                    continue
                if ve.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE"):
                    cand += _entity_segments(ve)[0]
        else:
            continue                              # ARC/CIRCLE/TEXT atla
        lay_ok = e.dxf.layer in WALL_LAYERS
        for a, b in cand:
            if inb(a, b) and math.hypot(b[0] - a[0], b[1] - a[1]) >= min_len:
                segs.append(((a[0], a[1]), (b[0], b[1])))
                srcs.append("pair+layer" if lay_ok else "pair")
    if with_sources:
        return _pair_filter(segs, tmin=tmin, tmax=tmax, min_overlap=min_overlap, aux=srcs)
    return _pair_filter(segs, tmin=tmin, tmax=tmax, min_overlap=min_overlap)


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


def _segment_rooms(rasters, rooms, leak_fraction: float, seed_rad: int = 12):
    """Odaları etiketle ve dilatasyonun yediği alanı gerçek duvara geri kazan.

    rasters: aynı bbox/res, ARTAN mühür sırasıyla (küçük→büyük). Her oda için, flood
    bölgesi başka bir oda etiketi İÇERMEYEN (dışlayıcı) ilk mühür kabul edilir: küçük
    mühür dar odaları/küçük WC'leri korur, büyük mühür kapısı tespit edilememiş
    açıklıklardan akmayı durdurur. Hiçbir mühürde ayrışmazsa (açık plan / kapısız
    geçiş) en büyük mühür bölgesi, içindeki etiketlere göre Voronoi ile bölüşülür.

    Döner: labels (HxW int; oda indeksi 1..N, 0=boş/duvar), idx->room eşlemesi.
    """
    if isinstance(rasters, _Raster):
        rasters = [rasters]
    base_r = rasters[0]
    H, W = base_r.grid.shape
    total = H * W
    labels = np.zeros((H, W), dtype=np.int32)
    idx_room: dict[int, Room] = {}
    sources: dict[int, str] = {}                  # oda idx → hangi yol (kaynak bilgisi)

    # Her raster için tohumlar (duvara denk gelirse en yakın boş piksel)
    seeds = []
    for raster in rasters:
        sd = []
        for room in rooms:
            c0, r0 = raster.to_px(*room.label_xy)
            sd.append(_seed_free(raster.grid, r0, c0, seed_rad))
        seeds.append(sd)

    def _touches_border(mask):
        """Raster kenarına değen bölge = bina DIŞI (sızıntı): bina dışındaki not/etiket
        (ör. 'FRANSIZ BALKON KORKULUK', 'betonarme subasman merdiveni', çatı planı
        etiketi) tüm arka planı oda yapıyordu."""
        return bool(mask[0, :].any() or mask[-1, :].any() or mask[:, 0].any() or mask[:, -1].any())

    def _best_flood(raster, k, i):
        """Etikete yakın aday tohumlardan akış bölgesi seç. Tercih sırası:
        (1) ≥30 hücrelik ve başka etiket İÇERMEYEN (dışlayıcı) ilk bölge — etiket duvara
        yakınsa tohum yanlış tarafa (komşu odaya) düşebilir, bu durumda diğer taraftaki
        aday kazanır; (2) yoksa ≥30 hücrelik ilk bölge (birleşik; sonra Voronoi)."""
        c0, r0 = raster.to_px(*rooms[i - 1].label_xy)
        tried = 0
        seen = []
        rejected = []                             # büyük dış sızıntı maskeleri (tekrar taranmasın)
        others = [seeds[k][j] for j in range(len(rooms)) if j != i - 1]
        for sr, sc in _seed_candidates(raster.grid, r0, c0, seed_rad):
            if any(m[sr, sc] for m, _, _, _ in seen) or any(m[sr, sc] for m in rejected):
                continue                          # zaten akıtılmış bölge
            mask, cnt = _flood(raster.grid, sr, sc)
            tried += 1
            if cnt >= 30:
                border = _touches_border(mask)
                if border and cnt / total > 0.2:
                    rejected.append(mask)         # dışarı sızıntı (arka plan) → asla oda değil
                    continue
                seen.append((mask, cnt, (sr, sc), border))
            if tried >= 40 or len(seen) >= 4:
                break
        # Dışlayıcı (başka etiket içermeyen) ilk aday tercih edilir. (Denenip geri alınan:
        # "en büyük adayın ≥%40'ı" cep filtresi — sızıntılı birleşik bölge büyük olunca
        # gerçek küçük odayı da reddediyordu. Duvar çıkıntıları arasındaki küçük cep vakası
        # geometriyle ayrılamıyor → HITL soru adayı, docs/HITL_QUESTIONS.md #1.)
        # Tercih: dışlayıcı & kenara değmeyen → dışlayıcı (kenara değen, küçük: açık balkon)
        # → kenara değmeyen ilk aday → kalan.
        for want_border in (False, True):
            for mask, cnt, sd, border in seen:
                if border == want_border and not any(mask[o] for o in others):
                    seeds[k][i - 1] = sd
                    return mask, cnt, border
        for want_border in (False, True):
            for mask, cnt, sd, border in seen:
                if border == want_border:
                    seeds[k][i - 1] = sd
                    return mask, cnt, border
        return None, 0, False

    pending = []
    for i, room in enumerate(rooms, start=1):
        placed = False
        last = None
        for k, raster in enumerate(rasters):
            mask, cnt, border = _best_flood(raster, k, i)
            if mask is None or cnt / total > leak_fraction:
                continue
            others = [j for j in range(len(rooms)) if j != i - 1 and mask[seeds[k][j]]]
            if others:
                last = (mask, k, others)
                continue
            labels[mask & (labels == 0)] = i
            idx_room[i] = room
            sources[i] = "edge_fragment" if border else "exclusive"
            placed = True
            break
        if not placed and last is not None:
            pending.append((i, room, last))

    # Birleştirme (takma ad): EN BÜYÜK mühürde bile aynı bölgeyi paylaşan etiketler
    # arasında ne duvar ne kapı var → tek oda, diğer etiketler takma ad. Merdiven
    # etiketleri hariç (kot farkı = fiziksel ayrım) → onlar Voronoi ile bölünür.
    merged: dict[int, list] = {}
    if len(rasters) > 1 or True:
        big_k = len(rasters) - 1
        groups: dict[int, list] = {}
        for i, room, (mask, k, others) in pending:
            if k != big_k:
                continue
            key = min([i - 1] + others)
            groups.setdefault(key, []).append((i, room, mask, others))
        done = set()
        for key, members in groups.items():
            idxs = sorted({m[0] for m in members} | {o + 1 for m in members for o in m[3]})
            names = [rooms[j - 1].raw_name for j in idxs]
            if any(_is_stair(nm) for nm in names):
                continue                                   # Voronoi'ye bırak
            # birincil = grupta zaten dışlayıcı yerleşmiş oda varsa o; yoksa en küçük indeks
            placed_idx = [j for j in idxs if j in idx_room]
            prim = placed_idx[0] if placed_idx else idxs[0]
            union = np.zeros_like(labels, dtype=bool)
            for _, _, mask, _ in members:
                union |= mask
            labels[union & (labels == 0)] = prim
            idx_room[prim] = rooms[prim - 1]
            sources[prim] = "alias_merge"
            merged[prim] = [rooms[j - 1] for j in idxs if j != prim]
            for j in idxs:
                done.add(j)
        pending = [pr for pr in pending if pr[0] not in done]

    # Son çare: birleşik bölgeyi içindeki etiketlere göre Voronoi ile paylaştır.
    for i, room, (mask, k, others) in pending:
        ys, xs = np.where(mask & (labels == 0))
        if len(xs) == 0:
            continue
        sr, sc = seeds[k][i - 1]
        d_self = (ys - sr) ** 2 + (xs - sc) ** 2
        d_oth = np.full_like(d_self, np.iinfo(np.int64).max)
        for j in others:
            r2, c2 = seeds[k][j]
            d_oth = np.minimum(d_oth, (ys - r2) ** 2 + (xs - c2) ** 2)
        sel = d_self <= d_oth
        if sel.sum() < 30:
            continue
        labels[ys[sel], xs[sel]] = i
        idx_room[i] = room
        sources[i] = "voronoi"

    # Çok-kaynaklı sınırlı büyüme (gerçek duvarlara kadar geri kazanım).
    free = ~base_r.base
    dq = deque()
    ys, xs = np.where(labels > 0)
    for r, c in zip(ys.tolist(), xs.tolist()):
        dq.append((r, c, 0))
    max_d = max(r.seal for r in rasters) + 2
    while dq:
        r, c, d = dq.popleft()
        if d >= max_d:
            continue
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r2, c2 = r + dr, c + dc
            if (0 <= r2 < H and 0 <= c2 < W
                    and labels[r2, c2] == 0 and free[r2, c2]):
                labels[r2, c2] = labels[r, c]
                dq.append((r2, c2, d + 1))

    return labels, idx_room, merged, sources


def _is_stair(name: str) -> bool:
    f = (name or "").replace("İ", "i").replace("I", "ı").casefold()
    return "merdiven" in f or "stair" in f


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


def _swing_dirs(msp, bbox, amin, amax, big_blocks=False):
    """Her kapı yayı için (menteşe, açılış_yön_birimi, uç1, uç2). Standalone + blok.

    Bisektör = kapının açıldığı oda yönü. uç1/uç2 = leaf-tip noktaları (biri KAPALI
    konum = duvara paralel = kilit sövesi yönü; diğeri AÇIK konum).
    """
    x0, y0, x1, y1 = bbox
    out = []
    upm_est = amin / 0.55

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
                    if e.dxf.layer in DOOR_LAYERS:
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


def _room_by_swing(hinge, bdir, rooms, max_dist=460.0):
    """Kapının açıldığı oda: yay yönündeki (cos>0.2) odalar arası score=cos-0.4·(d/D) max.

    'En yakın etiket' değil 'yay YÖNÜ'; merkezi oda etiketi (Banyo) fazla sahiplenmez,
    bitişik kapılar (Salon/Mutfak) açılış yönüyle ayrışır.
    """
    bx, by = bdir
    best, bscore = None, -9.0
    for r in rooms:
        lx, ly = r.label_xy
        dx, dy = lx - hinge[0], ly - hinge[1]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        cos = (bx * dx + by * dy) / d            # bdir birim
        if cos < 0.2:
            continue
        score = cos - 0.4 * (d / max_dist)
        if score > bscore:
            bscore, best = score, r
    return best


def reconstruct(building: BuildingIR, dxf_path: str, *,
                res: float = 1.0, seal: int = 8, margin: float = 25.0,
                leak_fraction: float = 0.45, door_max_boundary_dist: float = 15.0,
                vlm_door_points: list | None = None,
                door_arc_radius: tuple = (50.0, 130.0),
                door_wall_dist: float = 25.0,
                units_per_meter: float | None = None) -> BuildingIR:
    """M1 giriş noktası: her kat için oda merkezi/poligonu doldur, kapıları tespit et.

    geometry_ok=False olan odalar (sızma/boş) için center=label_xy fallback uygulanır.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    for floor in building.floors:
        if not floor.rooms:
            continue
        bbox = _floor_bbox(floor, margin)
        # Katman-bağımsız duvar/pencere tespiti ÖNCE: raster bariyeri bunlardan da beslenir.
        if units_per_meter:   # duvar kalınlığı 4-45 cm, boyuna örtüşme ≥18 cm (metre-tabanlı)
            # tmin 6 cm: 4 cm'lik "duvar" yapıda yok (duş kabini camı, cam bölme, çift çizgi
            # kaplama 2-4 cm → duvar sayılmaz); en ince bölme duvarı 7-8 cm.
            wk = dict(tmin=0.06 * units_per_meter, tmax=0.45 * units_per_meter,
                      min_overlap=0.18 * units_per_meter)
        else:
            wk = {}
        label_pts = [rm.label_xy for rm in floor.rooms]
        wk["label_pts"] = label_pts
        floor.walls, floor.wall_sources = _wall_segments(msp, bbox, min_len=8.0 * res, with_sources=True, **wk)
        # ADAPTİF: modelspace'te oda başına <8 duvar parçası bulunduysa plan büyük ihtimalle
        # BLOK içinde yerleştirilmiş → ≥3 m'lik blokların içine de bakılır.
        # (Koşulsuz açmak Revit export'larında sahte duvar üretip IoU'yu düşürdü.)
        big = False
        if len(floor.walls) < 8 * len(floor.rooms):
            walls_b, srcs_b = _wall_segments(msp, bbox, min_len=8.0 * res, big_blocks=True, with_sources=True, **wk)
            if len(walls_b) > len(floor.walls):
                floor.walls, floor.wall_sources = walls_b, srcs_b
                big = True
        floor.big_blocks = big
        floor.windows, floor.window_sources = _window_segments(
            msp, bbox, min_len=8.0 * res, upm=units_per_meter, walls=floor.walls, big_blocks=big,
            with_sources=True)
        # Kapı yayları (katman-bağımsız) → kapalı kanat bariyeri: açıklık mühürlenir,
        # böylece genel mühür küçük tutulabilir (dar odalar/WC kaybolmaz).
        amin, amax = door_arc_radius
        swing = _swing_dirs(msp, bbox, amin, amax, big_blocks=big)
        barriers = _door_barriers(swing, floor.walls)
        extra = floor.walls + floor.windows + barriers
        seal_small = max(3, int(round(0.25 * units_per_meter / res))) if units_per_meter else max(3, seal // 2)
        seals = sorted({seal_small, seal})
        rasters = [_Raster(msp, bbox, res, sl, extra_segs=extra, door_arc_radius=door_arc_radius, big_blocks=big)
                   for sl in seals]
        raster = rasters[-1]                      # kapı adayları vb. için (büyük mühür = tam bariyer)
        seed_rad = int(round(0.7 * units_per_meter / res)) if units_per_meter else 12
        labels, idx_room, merged, room_sources = _segment_rooms(rasters, floor.rooms, leak_fraction, seed_rad=seed_rad)
        # Takma ad birleştirme: birleşen etiketler oda listesinden çıkar, birincile eklenir.
        alias_rooms = set()
        for prim, others in merged.items():
            primary = floor.rooms[prim - 1]
            for o in others:
                primary.aliases.append(o.raw_name)
                primary.alias_xy.append(o.label_xy)
                alias_rooms.add(id(o))
        if alias_rooms:
            floor.rooms = [rm for rm in floor.rooms if id(rm) not in alias_rooms]
        recovered = {i: (labels == i) for i in idx_room}
        wall_xs, wall_ys, angled_walls = _wall_lines(
            msp, bbox, angled_min_len=15.0 * res, cluster_tol=3.0 * res, extra_segs=floor.walls)

        for room in floor.rooms:
            idx = next((i for i, r in idx_room.items() if r is room), None)
            if idx is None or int(recovered[idx].sum()) < 30:
                # Fallback: güvenilir geometri yok, etiket noktasını kullan.
                room.geometry_ok = False
                room.center = room.label_xy
                room.polygon = None
                room.source = "fallback"
                continue
            room.source = room_sources.get(idx, "exclusive")
            mask = recovered[idx]
            ys, xs = np.where(mask)
            cx, cy = raster.to_world(float(xs.mean()), float(ys.mean()))
            room.geometry_ok = True
            room.center = (cx, cy)
            room.polygon = _mask_polygon(mask, raster, wall_xs, wall_ys, angled_walls)

        # Kapı konumlarını belirle:
        #  - vlm_door_points verildiyse: adayları VLM kapılarıyla DOĞRULA (manuel/VLM mod)
        #  - verilmediyse: deterministik filtre (oda sınırına uzak sahteleri ele)
        from shapely.geometry import Polygon as _P, Point as _Pt
        room_polys = [(r, _P(r.polygon).buffer(0))
                      for r in floor.rooms if r.polygon]
        # Kapı adayları: kapı BLOKLARI (kesin) + kapı-genişliği YAYLARI (kesin).
        # İkisi de yeterince yoksa ham kapı-katmanı kümelemesine düş.
        swing_arcs = [(x, y) for (x, y, rr) in raster.arcs if amin <= rr <= amax]
        primary = list(raster.door_blocks) + swing_arcs
        used_primary = len(primary) >= 2
        cand_src: dict = {}                       # aday merkezi → kaynak (block+arc | arc | block | layer_raw)
        if used_primary:
            tagged = _cluster_doors(primary, radius=max(20.0, amin * 0.5),
                                    tags=["block"] * len(raster.door_blocks) + ["arc"] * len(swing_arcs))
            candidates = [c for c, _ in tagged]
            for c, t in tagged:
                cand_src[c] = "block+arc" if t == {"block", "arc"} else next(iter(t))
        else:
            candidates = _cluster_doors(raster.door_raw)
            cand_src = {c: "layer_raw" for c in candidates}

        if vlm_door_points:
            from core.perception.vlm_doors import validate_doors
            # tol=10: yalnızca çok yakın aday varsa ince-ayar snap; yoksa VLM noktası korunur
            door_pts = validate_doors(candidates, vlm_door_points, tol=10.0)
        elif used_primary:
            # Blok + yay = yüksek güven; gürültü filtresi gerekmez.
            door_pts = candidates
        else:
            # Fallback (ham kapı-katmanı): oda sınırına uzak sahteleri ele.
            door_pts = []
            for (dx, dy) in candidates:
                if room_polys:
                    bd = min(poly.exterior.distance(_Pt(dx, dy))
                             for _, poly in room_polys)
                    if bd > door_max_boundary_dist:
                        continue
                door_pts.append((dx, dy))

        # Fikstür yaylarını (klozet/lavabo vb.) ELE: gerçek kapı menteşesi bir DUVARIN
        # üstündedir (~5-10 br); fikstür yayı merkezi oda ortasında (>30 br). Geniş
        # margin'de bbox'a giren fikstürlerin sahte-kapı olmasını engeller.
        def _dist_walls(p):
            best = float("inf")
            for a, b in floor.walls:
                ax, ay = a
                ex, ey = b[0] - a[0], b[1] - a[1]
                L2 = ex * ex + ey * ey or 1.0
                t = max(0.0, min(1.0, ((p[0] - ax) * ex + (p[1] - ay) * ey) / L2))
                d = math.hypot(ax + t * ex - p[0], ay + t * ey - p[1])
                if d < best:
                    best = d
            return best
        if floor.walls:   # duvar yoksa filtre uygulanmaz (_dist_walls yine tanımlı: inf döner)
            door_pts = [p for p in door_pts if _dist_walls(p) <= door_wall_dist]

        # Kapı = menteşe (blok matrix44 / yay merkezi). Standart: tüm kapılar menteşede.
        # room_name = AÇILIŞ YAYI YÖNÜ ile (etiket-mesafesi değil): menteşeye en yakın
        # yayı bul, bisektör yönündeki odayı seç. Yay eşleşmezse merkez-mesafesi fallback.
        floor.doors = []
        for (dx, dy) in door_pts:
            sd = min(swing, key=lambda s: math.hypot(s[0][0] - dx, s[0][1] - dy),
                     default=None)
            room, strike = None, None
            if sd is not None and math.hypot(sd[0][0] - dx, sd[0][1] - dy) <= door_wall_dist * 1.6:
                room = _room_by_swing((dx, dy), sd[1], floor.rooms)
                # kilit sövesi = KAPALI kanat ucu = kanat ortası bir duvara YASLI olan
                # uç (açık kanat oda boşluğuna gider, duvara uzak). Köşe menteşelerde
                # 'en yakın duvara paralel' testi yanılıyordu; bu test kapının asıl
                # duvarını doğru bulur.
                def _leaf_mid_wall(ep):
                    return _dist_walls(((dx + ep[0]) / 2, (dy + ep[1]) / 2))
                strike = sd[2] if _leaf_mid_wall(sd[2]) <= _leaf_mid_wall(sd[3]) else sd[3]
            if room is None:                       # yay yok → eski merkez-mesafesi
                room = min(floor.rooms,
                           key=lambda r: math.hypot((r.center or r.label_xy)[0] - dx,
                                                    (r.center or r.label_xy)[1] - dy),
                           default=None)
            floor.doors.append(Door(xy=(dx, dy), source=cand_src.get((dx, dy), "vlm" if vlm_door_points else None),
                                    room_name=room.raw_name if room else None,
                                    strike_xy=strike))

    return building


def estimate_units_from_doors(dxf_path: str, bbox, upm_prior: float, door_m: float = 0.875,
                              min_doors: int = 3, msp=None):
    """Kapı yayı yarıçaplarından birim/metre.

    Yarıçaplar karışık: fikstür yayları (~45 cm), dar banyo kapıları (60-70), ana kapılar
    (80-95), semboller (2-3 cm). Etiket öncülü (upm_prior) kaba olabilir (tablo/lejant
    etiketleri) → birden çok öncül denenir (etiket, 10, 100, 1000 birim/m) ve en çok yay
    içeren EN BÜYÜK küme (max'ın %85'i ve üstü) alınır; ortalaması ≈ ana kapı kanadı
    (≈0.875 m). Kümede ≥min_doors yay yoksa None.
    """
    if msp is None:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    # Öncül sırası: etiket tahmini; başarısızsa cm (100) ve mm (1000). Küçük öncüller
    # (10) sembol yaylarını kapı sanıp yanlış ölçek veriyor → denenmez; "en çok yay"
    # seçimi de aynı tuzağa düşüyordu → ilk başarılı öncül alınır.
    for prior in (upm_prior, 100.0, 1000.0):
        sw = _swing_dirs(msp, bbox, 0.3 * prior, 2.0 * prior)
        radii = sorted(math.hypot(e1[0] - h[0], e1[1] - h[1]) for h, _b, e1, _e2 in sw)
        if len(radii) < min_doors:
            continue
        # Yukarıdan aşağı: birkaç büyük aykırı yay (merdiven/eğri duvar) tepede tek
        # kalabilir → ≥min_doors üyeli ilk %85-kümesi ana kapı kanadı sayılır.
        for k in range(len(radii) - 1, -1, -1):
            rmax = radii[k]
            top = [r for r in radii[:k + 1] if r >= 0.85 * rmax]
            if len(top) >= min_doors:
                return (sum(top) / len(top)) / door_m
    return None
