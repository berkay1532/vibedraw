# core/perception/parse.py
"""Etiket çıkarımı ve kat kümeleme (katman-bağımsız).

Adım 4: eski YAZI-katmanı yolu (`extract_yazi_texts`, `cluster_floors` x-only, `parse_dxf`) silindi;
tek yol `extract_room_labels` → `dedupe_labels` → `cluster_floors_2d` → `pick_plan_floor`
(orkestrasyon: `pipeline.select_plan`). Kelime listeleri `vocab.py`'de."""
from __future__ import annotations
import math
import re
from dataclasses import dataclass

import ezdxf

from core.perception.config import T
from core.perception.ir_v1 import Room, Floor
from core.perception.vocab import NON_ROOM_WORDS, ROOM_WORDS, SHORT_ROOM_WORDS, fold

AREA_RE = re.compile(r"A\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*m\s*[²2]", re.IGNORECASE)


@dataclass
class YaziText:
    content: str
    xy: tuple[float, float]


_UESC_RE = re.compile(r"\\U\+([0-9A-Fa-f]{4})")


def decode_dxf_text(s: str) -> str:
    r"""DXF metin kaçışlarını çöz: \U+00C7 → Ç, \U+00B2 → ², %%c/%%d/%%p, \P → satır."""
    s = _UESC_RE.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace("\\P", "\n").replace("%%c", "Ø").replace("%%C", "Ø").replace("%%d", "°").replace("%%p", "±")
    return s


def _plain(entity) -> str:
    """MTEXT/TEXT içeriğini biçim kodlarından ve DXF kaçışlarından arındır."""
    if entity.dxftype() == "MTEXT":
        raw = entity.plain_text()
    else:
        raw = entity.dxf.text
    return decode_dxf_text(raw).strip()


# --- Katman-bağımsız oda etiketi çıkarımı ------------------------------------------
_NOISE_RE = re.compile(r"^[\d\s.,/x×+\-]*$")  # sadece sayı/ölçü
_WORD_RE = re.compile(r"[a-zçğıöşü]+")


def looks_like_room_label(content: str) -> bool:
    c = content.strip()
    if not c or len(c) > 40 or _NOISE_RE.match(c) or is_area_text(c):
        return False
    if ":" in c or len(c.split()) > 4:            # "ODA SİCİL NO :", uzun cümleler
        return False
    if sum(ch.isdigit() for ch in c) > 4:        # kod/ölçü yazıları
        return False
    f = fold(c)
    if any(w in f for w in NON_ROOM_WORDS):      # "ÇAMAŞIR MAK.YERİ", "MUTFAK DOLABI", "KAT PLANI"
        return False
    words = set(_WORD_RE.findall(f))
    for w in ROOM_WORDS:
        if w in SHORT_ROOM_WORDS:
            if w in words:                        # "oda" tam kelime; "sicil no"daki 'no' değil
                return True
        elif w in f:
            return True
    return False


def room_label_name(content: str):
    """Metin bir oda etiketiyse (alan eki ayrılmış) adı, değilse None.
    'SALON+ MUTFAK\\nA:19.50 M²' → 'SALON+ MUTFAK'."""
    if not content:
        return None
    m = AREA_RE.search(content)
    name = (content[:m.start()] + content[m.end():]).strip(" \n\t-") if m else content.strip()
    return name if name and looks_like_room_label(name) else None


def extract_room_labels(dxf_path: str, msp=None) -> list[YaziText]:
    """Katman adına bakmadan modelspace'teki TEXT/MTEXT ve INSERT ATTRIB'lerinden
    oda-adı gibi görünen metinleri toplar. Alan yazıları ("A: 12m²") da eklenir
    (pair_names_with_areas için). msp verilirse dosya yeniden okunmaz (DXF tek okuma)."""
    if msp is None:
        msp = ezdxf.readfile(dxf_path).modelspace()
    out: list[YaziText] = []
    for e in msp:
        t = e.dxftype()
        if t in ("MTEXT", "TEXT"):
            content = _plain(e)
            if not content:
                continue
            x, y, *_ = e.dxf.insert
            # "SALON+ MUTFAK A:19.50 M²" gibi ad+alan tek metinde olabilir: alan ekini ayır.
            m = AREA_RE.search(content)
            name_part = (content[:m.start()] + content[m.end():]).strip(" \n\t-") if m else content
            if m:
                out.append(YaziText(content=f"A: {m.group(1).replace(',', '.')}m²", xy=(float(x), float(y))))
            if name_part and looks_like_room_label(name_part):
                out.append(YaziText(content=name_part, xy=(float(x), float(y))))
        elif t == "INSERT":
            try:
                attribs = list(e.attribs)
            except Exception:
                continue
            for a in attribs:
                content = str(a.dxf.text).strip()
                if content and looks_like_room_label(content):
                    x, y, *_ = e.dxf.insert
                    out.append(YaziText(content=content, xy=(float(x), float(y))))
    return out


def dedupe_labels(labels: list[YaziText], tol: float) -> list[YaziText]:
    """Aynı (katlanmış) isimli ve birbirine tol'dan yakın etiketlerden birini tutar.
    Lejant/antet tekrarlarını ve çift yazılmış etiketleri eler."""
    kept: list[YaziText] = []
    for t in labels:
        f = fold(t.content)
        dup = any(fold(k.content) == f and
                  math.hypot(k.xy[0] - t.xy[0], k.xy[1] - t.xy[1]) <= tol for k in kept)
        if not dup:
            kept.append(t)
    return kept


def cluster_floors_2d(rooms: list[Room], gap: float) -> list[Floor]:
    """Odaları 2B tek-bağlantı (single-linkage) ile kümeler: iki etiket arası mesafe ≤ gap
    ise aynı kat/çizim. Plan ile üstündeki kesit/görünüş ayrı kümeye düşer (x-only
    kümelemeden farkı bu). Küme sırası: sol-alt'tan sağ-üst'e."""
    if not rooms:
        return []
    n = len(rooms)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = rooms[i].label_xy, rooms[j].label_xy
            if math.hypot(a[0] - b[0], a[1] - b[1]) <= gap:
                parent[find(i)] = find(j)
    groups: dict[int, list[Room]] = {}
    for i, r in enumerate(rooms):
        groups.setdefault(find(i), []).append(r)
    ordered = sorted(groups.values(), key=lambda g: (min(r.label_xy[0] for r in g), min(r.label_xy[1] for r in g)))
    return [Floor(index=i, rooms=g) for i, g in enumerate(ordered)]


def is_area_text(content: str) -> bool:
    return AREA_RE.search(content) is not None


def parse_area(content: str) -> float:
    m = AREA_RE.search(content)
    if not m:
        raise ValueError(f"Alan yazısı değil: {content!r}")
    return float(m.group(1))


def grid_likeness(rooms: list[Room], tol: float) -> float:
    """Etiketlerin bir TABLO gibi dizilme derecesi (0..1). Mahal listesi/lejant tablolarında
    etiketler az sayıda sütunda ve satır satır hizalıdır; planda oda merkezleri dağınıktır.
    Skor = (x'i ≤3 sütuna sığan etiket oranı + y'si başka bir etiketle hizalı oranı) / 2."""
    if len(rooms) < 3:
        return 0.0
    xs = [r.label_xy[0] for r in rooms]
    ys = [r.label_xy[1] for r in rooms]
    cols: list[float] = []
    for x in sorted(xs):
        if not cols or abs(x - cols[-1]) > tol:
            cols.append(x)
    col_score = 1.0 if len(cols) <= 3 else max(0.0, 1.0 - (len(cols) - 3) / len(rooms))
    aligned = sum(1 for i, y in enumerate(ys) if any(j != i and abs(y - ys[j]) <= tol for j in range(len(ys))))
    return (col_score + aligned / len(rooms)) / 2


def pick_plan_floor(floors: list[Floor], upm: float, table_thr: float | None = None, table_max_n: int | None = None) -> Floor | None:
    """Kat kümeleri arasından PLAN olanı seç: tablo-benzeri (grid_likeness ≥ eşik VE
    ≤table_max_n etiket) kümeler elenir, kalanların en kalabalığı alınır; hepsi tabloysa en
    kalabalık. (Çok daireli katlarda aynı tip dairelerin etiketleri de hizalıdır → büyük
    kümeler tablo sayılmaz.)"""
    L = T("labels")
    table_thr = L["table_thr"] if table_thr is None else table_thr
    table_max_n = L["table_max_n"] if table_max_n is None else table_max_n
    cand = [f for f in floors if len(f.rooms) >= L["min_rooms"]]
    if not cand:
        return None
    plans = [f for f in cand if not (len(f.rooms) <= table_max_n and grid_likeness(f.rooms, L["grid_tol_m"] * upm) >= table_thr)]
    pool = plans or cand
    return max(pool, key=lambda f: len(f.rooms))
