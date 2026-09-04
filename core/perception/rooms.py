# core/perception/rooms.py
"""Oda ayrıştırma: çok kademeli mühür, dışlayıcı bölge tercihi, takma ad birleştirme, Voronoi.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from core.perception.ir_v1 import Floor, Room
from core.perception.raster import _Raster, _flood, _seed_candidates, _seed_free


def _floor_bbox(floor: Floor, margin: float):
    xs = [r.label_xy[0] for r in floor.rooms]
    ys = [r.label_xy[1] for r in floor.rooms]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


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
