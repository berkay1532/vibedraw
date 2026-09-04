# core/perception/sheet_segment.py
"""Pafta anlama — görünüm AYRIMI: geometriyi hücrelere işaretle, bağlı bileşenler, geniş
bileşenleri sütun/satır boşluğu ve oda-etiketi kümeleriyle böl, metinleri görünüme bağla.

Adım 3: core/perception/sheets.py'den taşındı (400 satır sınırı); mantık değişmedi."""
from __future__ import annotations

import math
import re
from collections import deque

import numpy as np

from core.perception.parse import _plain, room_label_name

# Başlık benzeri metin (plan/kesit/görünüş/...): metinleri görünüme bağlarken kullanılır.
_TITLE_RE = re.compile(r"(plan|kesit|kesİt|görünüş|gorunus|görünüm|vaziyet|vazİyet|çatı|cati|detay|"
                       r"section|elevation|floor|roof|site)", re.I)


# --- Geometri toplama ----------------------------------------------------------
def _entity_points(e):
    t = e.dxftype()
    try:
        if t == "LINE":
            return [(e.dxf.start[0], e.dxf.start[1]), (e.dxf.end[0], e.dxf.end[1])]
        if t == "LWPOLYLINE":
            return [(p[0], p[1]) for p in e.get_points()]
        if t == "POLYLINE":
            return [(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]
        if t in ("ARC", "CIRCLE"):
            c = e.dxf.center
            return [(c[0], c[1])]
        if t in ("TEXT", "MTEXT", "INSERT"):
            p = e.dxf.insert
            return [(p[0], p[1])]
        if t == "HATCH":
            pts = []
            for path in e.paths:
                for v in getattr(path, "vertices", []) or []:
                    pts.append((v[0], v[1]))
            return pts[:50]
    except Exception:
        return []
    return []


def _dilate(grid, k):
    out = grid.copy()
    for _ in range(k):
        g = out.copy()
        g[1:, :] |= out[:-1, :]; g[:-1, :] |= out[1:, :]
        g[:, 1:] |= out[:, :-1]; g[:, :-1] |= out[:, 1:]
        out = g
    return out


_GEOM_TYPES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "HATCH", "INSERT", "SPLINE", "ELLIPSE")


def _sample_points(e, step):
    """Geometri entity'sini step aralığıyla örnekle (uzun çizgiler arada hücre bırakmasın)."""
    t = e.dxftype()
    pts = _entity_points(e)
    if t in ("LINE", "LWPOLYLINE", "POLYLINE") and len(pts) >= 2:
        out = []
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, by - ay)
            n = max(1, int(L / step))
            out += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n + 1)]
        return out
    return pts


def segment_views(msp, upm: float, cell_m: float = 0.5, gap_m: float = 1.2, min_entities: int = 25):
    """GEOMETRİYİ (metin/ölçü hariç) hücrelere işaretle, gap_m/2 genişlet, bağlı bileşenler =
    görünümler. Metinler sonradan en yakın görünüme atanır (başlıklar çizimin dışında durur).
    Döner: ([(bbox, entity_indexleri)], ents) — büyükten küçüğe."""
    cell = cell_m * upm
    ents = list(msp)
    pts_per_ent = [(_sample_points(e, cell) if e.dxftype() in _GEOM_TYPES else []) for e in ents]
    allx = [x for pts in pts_per_ent for x, _ in pts]
    ally = [y for pts in pts_per_ent for _, y in pts]
    if not allx:
        return []
    x0, y0 = min(allx), min(ally)
    W = int((max(allx) - x0) / cell) + 3
    H = int((max(ally) - y0) / cell) + 3
    if W * H > 40_000_000:                     # aşırı büyük çizim: hücreyi büyüt
        f = math.sqrt(W * H / 40_000_000)
        cell *= f; W = int(W / f) + 3; H = int(H / f) + 3
    grid = np.zeros((H, W), dtype=bool)
    ent_cells = []
    for pts in pts_per_ent:
        cells = set()
        for x, y in pts:
            c, r = int((x - x0) / cell) + 1, int((y - y0) / cell) + 1
            if 0 <= r < H and 0 <= c < W:
                grid[r, c] = True; cells.add((r, c))
        ent_cells.append(cells)
    k = max(1, int(round(gap_m * upm / 2 / cell)))
    dil = _dilate(grid, k)
    labels = np.zeros((H, W), dtype=np.int32)
    n = 0
    rows, cols = np.where(dil)
    for r, c in zip(rows.tolist(), cols.tolist()):
        if labels[r, c]:
            continue
        n += 1
        dq = deque([(r, c)]); labels[r, c] = n
        while dq:
            rr, cc = dq.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r2, c2 = rr + dr, cc + dc
                if 0 <= r2 < H and 0 <= c2 < W and dil[r2, c2] and labels[r2, c2] == 0:
                    labels[r2, c2] = n; dq.append((r2, c2))
    groups: dict[int, list] = {}
    for i, cells in enumerate(ent_cells):
        if not cells:
            continue
        r, c = next(iter(cells))
        groups.setdefault(int(labels[r, c]), []).append(i)
    out = []
    for lab, idxs in groups.items():
        if lab == 0 or len(idxs) < min_entities:
            continue
        xs = [x for i in idxs for x, _ in pts_per_ent[i]]
        ys = [y for i in idxs for _, y in pts_per_ent[i]]
        out.append([(min(xs), min(ys), max(xs), max(ys)), idxs])
    # Yan yana dizilmiş kat planları (aralık < gap) tek bileşen olabilir: 40 m'den geniş/uzun
    # bileşenleri, tam boy BOŞ sütun/satır şeritlerinden böl (bir kez).
    def _split(entry):
        bbox, idxs = entry
        w_m = (bbox[2] - bbox[0]) / upm; h_m = (bbox[3] - bbox[1]) / upm
        if w_m < 40 and h_m < 40:
            return [entry]
        cells = set()
        for i in idxs:
            cells |= ent_cells[i]
        if not cells:
            return [entry]
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        axis = 1 if w_m >= h_m else 0           # 1: sütunlara göre (x), 0: satırlara göre (y)
        from collections import Counter as _C
        occ = _C(cs) if axis == 1 else _C(rs)
        lo, hi = (c0, c1) if axis == 1 else (r0, r1)
        med = sorted(occ.values())[len(occ) // 2] if occ else 1
        thin = max(1, int(0.35 * med))          # çerçeve/zemin çizgileri (2 hücre) boşluğu bozmasın; oda içi ≥6
        cuts, run = [], 0
        for v in range(lo, hi + 1):
            if occ.get(v, 0) > thin:
                run = 0
            else:
                run += 1
                if run == 2:                    # ≥2 (neredeyse) boş hücre (≥1 m) şerit
                    cuts.append(v - 1)
        if not cuts:
            return [entry]
        parts: dict[int, list] = {}
        for i in idxs:
            cc = ent_cells[i]
            if not cc:
                continue
            v = next(iter(cc))[axis]
            part = sum(1 for cut in cuts if v > cut)
            parts.setdefault(part, []).append(i)
        res = []
        for part_idxs in parts.values():
            if len(part_idxs) < min_entities:
                continue
            xs = [x for i in part_idxs for x, _ in pts_per_ent[i]]
            ys = [y for i in part_idxs for _, y in pts_per_ent[i]]
            res.append([(min(xs), min(ys), max(xs), max(ys)), part_idxs])
        return res or [entry]

    out = [e2 for e1 in out for e2 in _split(e1)]

    # Hâlâ geniş (>45 m) ve çok oda etiketli bileşen = yan yana birden çok kat planı
    # (çerçeve/ölçü çizgileriyle bağlı). Oda etiketlerini 8 m'lik 2B kümelere ayır; her
    # kümenin bbox'ı (+2 m) bir görünüm olur; geometri en yakın kümeye gider.
    def _split_by_labels(entry):
        bbox, idxs = entry
        if max(bbox[2] - bbox[0], bbox[3] - bbox[1]) / upm < 45:
            return [entry]
        labs = []
        bx0, by0, bx1, by1 = bbox
        for e in ents:                          # metinler henüz bileşene bağlı değil → bbox içi tüm yazılar
            try:
                t = e.dxftype()
                if t in ("TEXT", "MTEXT"):
                    px, py = e.dxf.insert[0], e.dxf.insert[1]
                    if bx0 <= px <= bx1 and by0 <= py <= by1 and room_label_name(_plain(e)):
                        labs.append((px, py))
                elif t == "INSERT":
                    px, py = e.dxf.insert[0], e.dxf.insert[1]
                    if bx0 <= px <= bx1 and by0 <= py <= by1 and any(room_label_name(str(a.dxf.text)) for a in e.attribs):
                        labs.append((px, py))
            except Exception:
                pass
        if len(labs) < 6:
            return [entry]
        gap = 8.0 * upm
        parent = list(range(len(labs)))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for a in range(len(labs)):
            for b in range(a + 1, len(labs)):
                if math.hypot(labs[a][0] - labs[b][0], labs[a][1] - labs[b][1]) <= gap:
                    parent[find(a)] = find(b)
        groups: dict[int, list] = {}
        for a, pt in enumerate(labs):
            groups.setdefault(find(a), []).append(pt)
        clusters = [g for g in groups.values() if len(g) >= 3]
        if len(clusters) < 2:
            return [entry]
        boxes = []
        for g in clusters:
            xs = [q[0] for q in g]; ys = [q[1] for q in g]
            boxes.append([min(xs) - 2 * upm, min(ys) - 2 * upm, max(xs) + 2 * upm, max(ys) + 2 * upm])
        parts: list[list] = [[] for _ in boxes]
        for i in idxs:
            pts = pts_per_ent[i] or _entity_points(ents[i])
            if not pts:
                continue
            cx = sum(q[0] for q in pts) / len(pts); cy = sum(q[1] for q in pts) / len(pts)
            best, bd = None, None
            for k, (bx0, by0, bx1, by1) in enumerate(boxes):
                d = max(0.0, bx0 - cx, cx - bx1) + max(0.0, by0 - cy, cy - by1)
                if bd is None or d < bd:
                    best, bd = k, d
            if bd is not None and bd <= 6 * upm:
                parts[best].append(i)
        res = []
        for part_idxs in parts:
            if len(part_idxs) < min_entities:
                continue
            xs = [x for i in part_idxs for x, _ in (pts_per_ent[i] or _entity_points(ents[i]))]
            ys = [y for i in part_idxs for _, y in (pts_per_ent[i] or _entity_points(ents[i]))]
            res.append([(min(xs), min(ys), max(xs), max(ys)), part_idxs])
        return res or [entry]

    out = [e2 for e1 in out for e2 in _split_by_labels(e1)]
    out.sort(key=lambda t: -len(t[1]))
    # Metinleri (ve ölçüleri) en yakın görünüme ata: bbox'ı 2.5 m genişletilmiş görünüm içindeyse
    pad = 2.5 * upm
    for i, e in enumerate(ents):
        if e.dxftype() not in ("TEXT", "MTEXT"):
            continue
        try:
            px, py = e.dxf.insert[0], e.dxf.insert[1]
            txt = _plain(e)
        except Exception:
            continue
        best, bd = None, None
        for v in out:
            (bx0, by0, bx1, by1) = v[0]
            if bx0 - pad <= px <= bx1 + pad and by0 - pad <= py <= by1 + pad:
                d = math.hypot(px - (bx0 + bx1) / 2, py - (by0 + by1) / 2)
                if bd is None or d < bd:
                    best, bd = v, d
        if best is None and _TITLE_RE.search(txt or ""):
            # Başlıklar çizimin altında, ölçü zincirlerinin ötesinde durabilir (≤12 m)
            for v in out:
                (bx0, by0, bx1, by1) = v[0]
                if bx0 - pad <= px <= bx1 + pad and by0 - 12 * upm <= py < by0:
                    d = by0 - py
                    if bd is None or d < bd:
                        best, bd = v, d
        if best is not None:
            best[1].append(i)
    return [(tuple(b), idx) for b, idx in out], ents
