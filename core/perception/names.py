# core/perception/names.py
"""Katman adı sınıflandırma (Adım 5): kaynak profili + genel sözlük → NameMap.

- `LayerClass`: katmanın rolü. Sınıf → tüketici eşlemesi KODDADIR (profilde değil):
  raster bariyeri BARRIER_CLASSES, duvar taraması WALL_SCAN_CLASSES, duvar taramasından hariç
  WALL_EXCLUDE_CLASSES, kapı DOOR_CLASSES, pencere WINDOW_CLASSES.
- `SourceProfile`: source_profiles/<family_id>.yaml — triage ailesi başına bir dosya; `layers`
  yalnızca ofise özgü adları taşır (kodda hiçbir ofis katman adı yoktur).
- Aile eşleştirme üç kademeli: parmak izi kayıtlı mı → kayıtlı yapısal adlarla örtüşme ≥ STRUCT_MIN →
  tam küme Jaccard ≥ JACCARD_MIN → yoksa boş profil (family: unknown).
- `classify_layers`: 1) profil (güven 0.9), 2) vocab anahtar kelimesi (0.6; kapı+pencere çakışması → window
  0.5), 3) içerik istatistiği ve 4) LLM henüz yok (DECISIONS adayı).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from core.perception.vocab import LAYER_WORDS, fold, has_word

ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = ROOT / "source_profiles"
STRUCT_MIN = 0.5      # kayıtlı yapısal adların en az bu oranı dosyada varsa aile eşleşti (config/ adayı)
JACCARD_MIN = 0.5     # triage aile eşiğiyle aynı
PROFILE_CONF = 0.9    # profil kaynaklı sınıf güveni
KEYWORD_CONF = 0.6    # genel sözlük kaynaklı sınıf güveni (kapı+pencere çakışması: KEYWORD_CONF - 0.1)
# Kapılı tüketim (DECISIONS 2026-09-04 ablasyon): sözlük güvenindeki sınıflar yalnız EKLEYİCİ tüketicilere
# (bariyer, pencere kaynağı, duvar-katmanı güveni, ince-çizgi pencere adayı dışlama) beslenir; duvar taramasından
# HARİÇ tutma ve "kesin kapı" INSERT yolu profil güveni ister (GATED_MIN_CONF).
GATED_MIN_CONF = PROFILE_CONF


class LayerClass(str, Enum):
    wall = "wall"; beam = "beam"; column = "column"; chimney = "chimney"; door = "door"; window = "window"
    furniture = "furniture"; text = "text"; dim = "dim"; grid = "grid"; stair = "stair"; hatch = "hatch"
    revision = "revision"; ignore = "ignore"; unknown = "unknown"


# Sınıf → tüketici (eski hardcode kümelerin anlamı; DECISIONS Adım 5)
BARRIER_CLASSES = frozenset({LayerClass.wall, LayerClass.beam, LayerClass.column, LayerClass.chimney, LayerClass.window})
WALL_SCAN_CLASSES = frozenset({LayerClass.wall})
WALL_EXCLUDE_CLASSES = frozenset({LayerClass.door, LayerClass.text, LayerClass.stair, LayerClass.beam})
DOOR_CLASSES = frozenset({LayerClass.door})
WINDOW_CLASSES = frozenset({LayerClass.window})
_ANNOTATION = frozenset({LayerClass.text, LayerClass.dim, LayerClass.grid, LayerClass.hatch, LayerClass.ignore, LayerClass.revision})


@dataclass
class SourceProfile:
    family_id: str
    label: str = ""
    fingerprints: list = field(default_factory=list)
    layers: dict = field(default_factory=dict)       # katman adı (birebir) → LayerClass
    notes: dict = field(default_factory=dict)
    learned_from: list = field(default_factory=list)
    layer_union: list = field(default_factory=list)  # aile katman birleşimi; yan dosya unions/<fam>.json (Jaccard için)

    @classmethod
    def from_yaml(cls, path: Path) -> "SourceProfile":
        d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        side = path.parent / "unions" / f"{path.stem}.json"
        union = json.loads(side.read_text(encoding="utf-8")) if side.exists() else (d.get("layer_union") or [])
        return cls(family_id=str(d.get("family_id", path.stem)), label=d.get("label", ""),
                   fingerprints=list(d.get("fingerprints") or []),
                   layers={str(k): LayerClass(v) for k, v in (d.get("layers") or {}).items()},
                   notes=dict(d.get("notes") or {}), learned_from=list(d.get("learned_from") or []),
                   layer_union=[str(x) for x in union])


@dataclass
class NameMap:
    """Katman adı → (sınıf, güven, kaynak). Tüketiciler yalnızca `has`/`cls` kullanır."""
    classes: dict = field(default_factory=dict)
    family_id: str = "unknown"
    match: str = "none"            # fingerprint | structural | jaccard | none
    match_score: float = 0.0
    stats: dict = field(default_factory=dict)   # layer_stats (unknown_layer sıralaması için)

    def cls(self, layer: str) -> LayerClass:
        return self.classes.get(layer, (LayerClass.unknown, 0.0, "none"))[0]

    def has(self, layer: str, classes, min_conf: float = 0.0) -> bool:
        c, conf, _ = self.classes.get(layer, (LayerClass.unknown, 0.0, "none"))
        return c in classes and conf >= min_conf

    def summary(self) -> dict:
        out: dict = {}
        for name, (c, conf, src) in self.classes.items():
            if c is not LayerClass.unknown:
                out.setdefault(c.value, []).append(name)
        return out


EMPTY = NameMap()


def load_profiles(profile_dir: Path = PROFILE_DIR) -> list[SourceProfile]:
    if not Path(profile_dir).is_dir():
        return []
    return [SourceProfile.from_yaml(p) for p in sorted(Path(profile_dir).glob("*.yaml"))]


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 1.0


def match_profile(layer_names, profiles: list[SourceProfile], fingerprint: Optional[str] = None):
    """(profil | None, yöntem, skor). Kademeler: parmak izi → yapısal örtüşme → Jaccard."""
    if fingerprint:
        for p in profiles:
            if fingerprint in p.fingerprints:
                return p, "fingerprint", 1.0
    L = {fold(n) for n in layer_names}
    best, best_s = None, 0.0
    for p in profiles:
        keys = {fold(k) for k in p.layers}
        if keys:
            s = len(L & keys) / len(keys)
            if s > best_s:
                best, best_s = p, s
    if best is not None and best_s >= STRUCT_MIN:
        return best, "structural", best_s
    best, best_s = None, 0.0
    for p in profiles:
        if p.layer_union:
            s = _jaccard(L, {fold(n) for n in p.layer_union})
            if s > best_s:
                best, best_s = p, s
    if best is not None and best_s >= JACCARD_MIN:
        return best, "jaccard", best_s
    return None, "none", 0.0


def keyword_class(layer: str):
    """Genel sözlük kademesi: (sınıf, güven). Ek açıklama kelimeleri (yazı/ölçü/aks/tarama) yapısal
    kelimeyi yener (kapı-pencere-yazısı → text); kapı+pencere birlikte → window (düşük güven)."""
    hits = {c for c, words in LAYER_WORDS.items() if has_word(layer, words)}
    hits = {LayerClass(c) for c in hits}
    if not hits:
        return LayerClass.unknown, 0.0
    ann = hits & _ANNOTATION
    if ann:
        for c in (LayerClass.ignore, LayerClass.text, LayerClass.dim, LayerClass.grid, LayerClass.hatch, LayerClass.revision):
            if c in ann:
                return c, KEYWORD_CONF
    if len(hits) == 1:
        return next(iter(hits)), KEYWORD_CONF
    if {LayerClass.door, LayerClass.window} <= hits:
        return LayerClass.window, KEYWORD_CONF - 0.1          # kapı-pencere ortak katmanı: kapı içerebilir (profil notu)
    return LayerClass.unknown, 0.0


def classify_layers(layer_names, profile: Optional[SourceProfile], match: str = "none", score: float = 0.0) -> NameMap:
    nm = NameMap(family_id=profile.family_id if profile else "unknown", match=match, match_score=score)
    for name in layer_names:
        if profile and name in profile.layers:
            nm.classes[name] = (profile.layers[name], PROFILE_CONF, "profile")
            continue
        c, conf = keyword_class(name)
        nm.classes[name] = (c, conf, "keyword" if conf else "none")
    return nm


def names_for(doc, profiles: Optional[list] = None, fingerprint: Optional[str] = None) -> NameMap:
    """Belge → NameMap (profil yükle, aile eşle, sınıfla)."""
    layer_names = [l.dxf.name for l in doc.layers]
    profs = load_profiles() if profiles is None else profiles
    prof, how, score = match_profile(layer_names, profs, fingerprint)
    return classify_layers(layer_names, prof, how, score)


# --- 3. kademe: içerik istatistiği (kullanıcı kararı 2026-09-05) -----------------------------
def layer_stats(doc, upm: float) -> dict:
    """Katman → entity istatistiği (modelspace): n, line, long (≥ long_line_m), short (≤ short_line_m),
    arc, small_arc (≤ small_arc_m), text, dim, hatch, insert."""
    import math
    from core.perception.config import T
    S = T("stats"); long_u, short_u, small_u = S["long_line_m"] * upm, S["short_line_m"] * upm, S["small_arc_m"] * upm
    st: dict = {}
    for e in doc.modelspace():
        try:
            lay = e.dxf.layer
        except Exception:
            continue
        d = st.setdefault(lay, {"n": 0, "line": 0, "long": 0, "short": 0, "arc": 0, "small_arc": 0, "text": 0, "dim": 0, "hatch": 0, "insert": 0})
        d["n"] += 1; t = e.dxftype()
        try:
            if t == "LINE":
                L = math.hypot(e.dxf.end[0] - e.dxf.start[0], e.dxf.end[1] - e.dxf.start[1])
                d["line"] += 1; d["long"] += L >= long_u; d["short"] += L <= short_u
            elif t in ("LWPOLYLINE", "POLYLINE"):
                pts = [(p[0], p[1]) for p in e.get_points("xy")] if t == "LWPOLYLINE" else [(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]
                for a, b in zip(pts, pts[1:]):
                    L = math.hypot(b[0] - a[0], b[1] - a[1]); d["line"] += 1; d["long"] += L >= long_u; d["short"] += L <= short_u
            elif t in ("ARC", "CIRCLE"):
                d["arc"] += 1; d["small_arc"] += e.dxf.radius <= small_u
            elif t in ("TEXT", "MTEXT", "ATTRIB"):
                d["text"] += 1
            elif t == "DIMENSION":
                d["dim"] += 1
            elif t == "HATCH":
                d["hatch"] += 1
            elif t == "INSERT":
                d["insert"] += 1
        except Exception:
            pass
    return st


def stats_class(d: dict):
    """İstatistikten sınıf: (sınıf, güven) ya da (unknown, 0). Uzun düz çizgisi olmayan katman yapısal
    değildir: yazı/ölçü payı yüksekse text/dim, tarama payı yüksekse hatch, küçük yay + kısa çizgi
    yoğunsa furniture, aksi halde ignore. Uzun çizgisi varsa karar verilmez (unknown)."""
    from core.perception.config import T
    S = T("stats"); n = d.get("n", 0)
    if n < S["min_entities"]:
        return LayerClass.unknown, 0.0
    if (d["text"] + d["dim"]) / n >= S["text_share"]:
        return (LayerClass.dim if d["dim"] > d["text"] else LayerClass.text), S["conf"]
    if d["hatch"] / n >= S["hatch_share"]:
        return LayerClass.hatch, S["conf"]
    if d["long"] == 0:
        if (d["small_arc"] + d["short"]) / n >= S["furniture_share"]:
            return LayerClass.furniture, S["conf"]
        return LayerClass.ignore, S["conf"]
    return LayerClass.unknown, 0.0


def wall_like_ratio(d: dict) -> float:
    """Katmanın duvar-benzeri geometri oranı: uzun düz çizgi / tüm çizgi (unknown_layer sıralaması)."""
    return d["long"] / d["line"] if d.get("line") else 0.0


def refine_with_stats(nm: NameMap, stats: dict) -> NameMap:
    """Bilinmeyen katmanları içerik istatistiğiyle sınıflar (kaynak 'stats', güven thresholds stats.conf)."""
    for lay, d in stats.items():
        c, conf, src = nm.classes.get(lay, (LayerClass.unknown, 0.0, "none"))
        if c is LayerClass.unknown:
            c2, conf2 = stats_class(d)
            if c2 is not LayerClass.unknown:
                nm.classes[lay] = (c2, conf2, "stats")
    nm.stats = stats
    return nm


def apply_overrides(nm: NameMap, overrides: Optional[dict]) -> NameMap:
    """HITL katman cevapları (params.extra.hitl_layer_overrides): sınıf güven 1.0, kaynak 'hitl'."""
    for lay, cls in (overrides or {}).items():
        try:
            nm.classes[lay] = (LayerClass(cls), 1.0, "hitl")
        except ValueError:
            pass
    return nm
