# core/sheets.py
"""Pafta anlama: bir DXF'teki görünümleri (kat planı, kesit, görünüş, çatı, vaziyet,
detay, tablo) uzaysal olarak ayırır ve başlık yazısı + geometrik ipuçlarıyla sınıflar.

Deterministik ilk sürüm: LLM/VLM yok. Belirsiz kalan görünümler kind="unknown" ve düşük
güvenle işaretlenir; ileride VLM yedek sınıflayıcı buraya bağlanır.
"""
from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from core.perception.parse import _plain, looks_like_room_label, room_label_name, _tr_fold

# --- Başlık sözlüğü -----------------------------------------------------------
_KIND_WORDS = {
    "floor_plan": ("kat planı", "kat plani", "planı", "plani", "plan ", "floor plan"),
    "roof_plan": ("çatı planı", "cati plani", "çatı kat", "çatı katı", "roof"),
    "section": ("kesit", "section"),
    "elevation": ("görünüş", "gorunus", "görünüm", "elevation", "cephe"),
    "site_plan": ("vaziyet", "site plan", "yerleşim"),
    "detail": ("detay", "detail", "ö: 1 / 20", "1/20", "1/10", "1/5"),
    "table": ("mahal listesi", "tablo", "liste", "hesab", "cetvel"),
}
_FLOOR_WORDS = ("bodrum", "zemin", "asma", "normal kat", "tip kat", "çatı kat", "cati kat",
                "kat planı", "kat plani", ". kat", ".kat", "giriş kat", "teras kat", "bahçe kat")
_TITLE_RE = re.compile(r"(plan|kesit|kesİt|görünüş|gorunus|görünüm|vaziyet|vazİyet|çatı|cati|detay|"
                       r"section|elevation|floor|roof|site)", re.I)
_SCALE_RE = re.compile(r"1\s*/\s*(\d{1,4})")
_BLOCK_RE = re.compile(r"([A-ZÇĞİÖŞÜ0-9]{1,3})\s*BLOK", re.I)
_FLOOR_NUM_RE = re.compile(r"(\d+)\s*\.?\s*(?:normal\s*)?kat", re.I)


@dataclass
class View:
    index: int
    bbox: tuple                              # (x0, y0, x1, y1) dünya
    kind: str = "unknown"                    # floor_plan|roof_plan|section|elevation|site_plan|detail|table|unknown
    title: Optional[str] = None
    floor_name: Optional[str] = None         # "ZEMİN KAT", "1. KAT", "BODRUM", "ÇATI"
    block: Optional[str] = None              # "B" (B BLOK)
    scale: Optional[int] = None              # 50 (1/50)
    confidence: float = 0.0
    n_entities: int = 0
    n_room_labels: int = 0
    n_door_arcs: int = 0
    n_texts: int = 0
    evidence: list = field(default_factory=list)

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]


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


# --- Sınıflama -----------------------------------------------------------------
def _text_height(e):
    try:
        return float(e.dxf.char_height if e.dxftype() == "MTEXT" else e.dxf.height)
    except Exception:
        return 0.0


def _kind_from_title(title: str):
    f = _tr_fold(title)
    m = _SCALE_RE.search(f)
    scale = int(m.group(1)) if m else None
    if "detay" in f or "detail" in f:
        return "detail"
    if any(w in f for w in _KIND_WORDS["site_plan"]):
        return "site_plan"
    if any(w in f for w in _KIND_WORDS["section"]):
        return "section"
    if any(w in f for w in _KIND_WORDS["elevation"]):
        return "elevation"
    if "çatı" in f or "cati" in f or "roof" in f:
        return "roof_plan"
    if any(w in f for w in _KIND_WORDS["table"]):
        return "table"
    if scale is not None and scale <= 25:      # 1/20, 1/10, 1/5 = detay ölçeği
        return "detail"
    if "plan" in f:
        return "floor_plan"
    return "unknown"


def _floor_from_title(title: str):
    f = _tr_fold(title)
    if "bodrum" in f:
        m = _FLOOR_NUM_RE.search(f)
        return f"{m.group(1)}. BODRUM" if m and "bodrum" in f[: m.start() + 20] else "BODRUM"
    if "zemin" in f or "giriş kat" in f:
        return "ZEMİN KAT"
    if "asma" in f:
        return "ASMA KAT"
    if "çatı" in f or "cati" in f:
        return "ÇATI"
    if "teras kat" in f:
        return "TERAS KAT"
    if "tip kat" in f or "normal kat" in f and not re.search(r"\d", f):
        return "TİP KAT"
    m = _FLOOR_NUM_RE.search(f)
    if m:
        return f"{m.group(1)}. KAT"
    return None


def classify_views(views, ents, upm: float, door_arc_radius=(0.55, 1.3)):
    """Her görünüm için başlık + geometrik ipuçlarıyla View kaydı üretir."""
    out = []
    # Büyük yazılar (başlık adayı): yükseklik medyanının ≥1.3 katı
    heights = [(_text_height(e), i) for i, e in enumerate(ents) if e.dxftype() in ("TEXT", "MTEXT")]
    hs = sorted(h for h, _ in heights if h > 0)
    h_med = hs[len(hs) // 2] if hs else 0.0
    for vi, (bbox, idxs) in enumerate(views):
        x0, y0, x1, y1 = bbox
        v = View(index=vi, bbox=bbox, n_entities=len(idxs))
        texts = []
        for i in idxs:
            e = ents[i]; t = e.dxftype()
            if t in ("TEXT", "MTEXT"):
                s = _plain(e).replace("\n", " ").strip()
                if not s:
                    continue
                v.n_texts += 1
                texts.append((s, _text_height(e), e.dxf.insert[1]))
                if room_label_name(s):
                    v.n_room_labels += 1
            elif t == "INSERT":
                try:
                    for a in e.attribs:
                        if room_label_name(str(a.dxf.text)):
                            v.n_room_labels += 1
                    blk = e.doc.blocks.get(e.dxf.name)
                    sx = abs(e.dxf.xscale) if e.dxf.xscale else 1.0
                    for be in blk:
                        if be.dxftype() == "ARC":
                            r = be.dxf.radius * sx / upm; sw = (be.dxf.end_angle - be.dxf.start_angle) % 360
                            if door_arc_radius[0] <= r <= door_arc_radius[1] and 55 <= sw <= 125:
                                v.n_door_arcs += 1
                                break
                except Exception:
                    pass
            elif t == "ARC":
                try:
                    r = e.dxf.radius / upm; sw = (e.dxf.end_angle - e.dxf.start_angle) % 360
                    if door_arc_radius[0] <= r <= door_arc_radius[1] and 55 <= sw <= 125:
                        v.n_door_arcs += 1
                except Exception:
                    pass
        # Başlık adayları: anahtar kelime + büyük yazı; alt kenara yakın olan tercih
        cands = []
        for s, h, y in texts:
            if not _TITLE_RE.search(s) or len(s) > 60 or re.search(r"\d{4,}", s):
                continue
            score = 0.0
            if h_med and h >= 1.3 * h_med:
                score += 2.0
            if _SCALE_RE.search(s):
                score += 1.5
            if any(w in _tr_fold(s) for w in _FLOOR_WORDS):
                score += 1.0
            rel = (y - y0) / max(1e-6, (y1 - y0))
            if rel < 0.15 or rel > 0.9:            # alt (ya da üst) kenar
                score += 1.0
            cands.append((score, s))
        cands.sort(key=lambda t: -t[0])
        strong = [c for c in cands if c[0] >= 2.0]
        if len({_kind_from_title(c[1]) for c in strong}) > 1:
            v.evidence.append("uyarı: farklı türde birden çok başlık (görünümler birleşmiş olabilir)")
        if cands and cands[0][0] >= 2.0:
            v.title = cands[0][1]
            v.kind = _kind_from_title(v.title)
            v.floor_name = _floor_from_title(v.title)
            m = _SCALE_RE.search(v.title)
            if m:
                v.scale = int(m.group(1))
            m = _BLOCK_RE.search(v.title)
            if m:
                v.block = m.group(1).upper()
            v.confidence = min(1.0, 0.5 + cands[0][0] / 8.0)
            if len({_kind_from_title(c[1]) for c in strong}) > 1:
                v.confidence = min(v.confidence, 0.4)
            v.evidence.append(f"başlık: {v.title}")
        # Geometrik doğrulama / yedek
        geo_plan = v.n_room_labels >= 3 and v.n_door_arcs >= 2
        if geo_plan:
            v.evidence.append(f"geometri: {v.n_room_labels} oda etiketi, {v.n_door_arcs} kapı yayı")
        # Yaysız kapı çizimleri (blok/polyline): çok etiket + çok geometri de plan kanıtıdır
        geo_plan_weak = v.n_room_labels >= 5 and v.n_entities >= 200
        if v.kind in ("unknown", "detail", "table") and geo_plan:
            # başlık yok/yanıltıcı ("PLAN 1/20", mahal tablosu) ama geometri kat planı diyor
            v.kind = "floor_plan"; v.confidence = max(v.confidence, 0.6)
        elif v.kind in ("unknown", "table") and geo_plan_weak:
            v.kind = "floor_plan"; v.confidence = max(v.confidence, 0.5)
            v.evidence.append(f"geometri (zayıf): {v.n_room_labels} oda etiketi, kapı yayı yok")
        elif v.kind == "floor_plan" and geo_plan:
            v.confidence = min(1.0, v.confidence + 0.3)
        elif v.kind == "floor_plan" and v.n_room_labels == 0:
            v.confidence = min(v.confidence, 0.4); v.evidence.append("uyarı: plan denmiş ama oda etiketi yok")
        elif v.kind in ("section", "elevation") and geo_plan:
            # Kesit/görünüşte oda etiketi+kapı yayı olmaz: yanlış bağlanmış başlık → plan
            v.evidence.append(f"başlık '{v.title}' kesit/görünüş diyor ama {v.n_room_labels} etiket + {v.n_door_arcs} kapı yayı var → plan")
            v.kind = "floor_plan"; v.title = None; v.floor_name = None; v.confidence = 0.6
        if v.kind == "unknown" and v.n_room_labels == 0 and v.n_texts > 0 and v.n_entities < 200:
            v.kind = "table"; v.confidence = 0.3
        out.append(v)
    return out


def analyze_sheet(msp, upm: float):
    """Tek giriş noktası: msp → View listesi (bileşen sırasına göre)."""
    seg = segment_views(msp, upm)
    if not seg:
        return []
    views, ents = seg
    return classify_views(views, ents, upm)
