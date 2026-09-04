# core/perception/sheets.py
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

from core.perception.parse import _plain, room_label_name
from core.perception.vocab import FLOOR_WORDS, VIEW_KIND_WORDS, fold, has_word
from core.perception.sheet_segment import _TITLE_RE, segment_views  # noqa: F401 (yeniden dışa aktarım)

# Başlık sözlüğü: vocab.VIEW_KIND_WORDS / vocab.FLOOR_WORDS
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


# --- Sınıflama -----------------------------------------------------------------
def _text_height(e):
    try:
        return float(e.dxf.char_height if e.dxftype() == "MTEXT" else e.dxf.height)
    except Exception:
        return 0.0


def _kind_from_title(title: str):
    f = fold(title)
    m = _SCALE_RE.search(f)
    scale = int(m.group(1)) if m else None
    if "detay" in f or "detail" in f:
        return "detail"
    if has_word(title, VIEW_KIND_WORDS["site_plan"]):
        return "site_plan"
    if has_word(title, VIEW_KIND_WORDS["section"]):
        return "section"
    if has_word(title, VIEW_KIND_WORDS["elevation"]):
        return "elevation"
    if "çatı" in f or "cati" in f or "roof" in f:
        return "roof_plan"
    if has_word(title, VIEW_KIND_WORDS["table"]):
        return "table"
    if scale is not None and scale <= 25:      # 1/20, 1/10, 1/5 = detay ölçeği
        return "detail"
    if "plan" in f:
        return "floor_plan"
    return "unknown"


def _floor_from_title(title: str):
    f = fold(title)
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
            if any(w in fold(s) for w in FLOOR_WORDS):
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
