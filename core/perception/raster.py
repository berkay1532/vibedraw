# core/perception/raster.py
"""Raster ızgara: bariyer çizimi, dilatasyon, tohum arama, flood-fill.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from core.perception.blocks import _entity_segments, _explode, _is_big_block
from core.perception.openings import DOOR_LAYERS, _block_door_hinge, _door_like_arc
from core.perception.walls import WALL_LAYERS, _ladder_filter


def _dilate(grid: np.ndarray, k: int) -> np.ndarray:
    for _ in range(k):
        d = grid.copy()
        d[1:, :] |= grid[:-1, :]
        d[:-1, :] |= grid[1:, :]
        d[:, 1:] |= grid[:, :-1]
        d[:, :-1] |= grid[:, 1:]
        grid = d
    return grid


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
