# core/triage.py
"""Veri seti tarama: bir klasördeki DWG/DXF dosyalarını profilleyip
mimar 'ailelerine' (katman parmak izi) göre gruplar ve aday kat planlarını raporlar.

Amaç: 'N farklı mimardan M dosya' hedefine ulaşıp ulaşmadığımızı ölçmek.
Saf fonksiyonlar; CLI için triage_dataset.py.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf import recover

# Oda adı sözlüğü (alt-dizgi eşleşmesi, Türkçe casefold sonrası)
ROOM_VOCAB = (
    "depo", "ofis", "çalışma odası", "sandık", "vestiyer", "giyinme", "kazan", "sığınak",
    "salon", "oturma", "mutfak", "yatak", "çocuk", "ebeveyn", "banyo", "wc",
    "tuvalet", "hol", "antre", "koridor", "balkon", "oda", "merdiven", "kiler",
    "giriş", "teras", "çamaşır", "sofa",
    "living", "kitchen", "bedroom", "bathroom", "hall", "balcony", "corridor",
)

DWG_EXT = {".dwg"}
DXF_EXT = {".dxf"}


def tr_fold(s: str) -> str:
    """Türkçe güvenli casefold: İ→i, I→ı, sonra casefold."""
    return s.replace("İ", "i").replace("I", "ı").casefold()


def room_hits(texts: list[str]) -> dict[str, int]:
    """Metin listesinde oda sözlüğü eşleşmelerini sayar (metin başına en fazla 1 kelime)."""
    hits: Counter = Counter()
    for t in texts:
        f = tr_fold(t)
        for w in ROOM_VOCAB:
            if w in f:
                hits[w] += 1
                break
    return dict(hits)


def layer_fingerprint(layers) -> str:
    """Katman adı kümesinin büyük/küçük harf bağımsız 8 karakterlik hash'i."""
    norm = sorted({tr_fold(l).strip() for l in layers})
    return hashlib.sha1("|".join(norm).encode("utf-8")).hexdigest()[:8]


@dataclass
class FileProfile:
    path: str
    ok: bool
    error: Optional[str] = None
    dxf_version: str = ""
    units: int = 0                      # $INSUNITS (0=birimsiz,4=mm,5=cm,6=m)
    n_entities: int = 0
    type_counts: dict = field(default_factory=dict)
    layers: list = field(default_factory=list)
    fingerprint: str = ""
    n_lines: int = 0                    # LINE + LWPOLYLINE + POLYLINE
    n_arcs: int = 0
    n_hatch: int = 0
    n_inserts: int = 0
    block_names: list = field(default_factory=list)
    n_texts: int = 0
    room_hits: dict = field(default_factory=dict)
    n_room_texts: int = 0
    bbox: Optional[tuple] = None        # (xmin, ymin, xmax, ymax)
    verdict: str = "HATA"               # ADAY | ZAYIF | HATA

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def extent(self) -> tuple[float, float]:
        if not self.bbox:
            return (0.0, 0.0)
        return (self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1])


def _plain(e) -> str:
    from core.perception.parse import decode_dxf_text
    try:
        if e.dxftype() == "MTEXT":
            return decode_dxf_text(e.plain_text()).strip()
        return decode_dxf_text(str(e.dxf.text)).strip()
    except Exception:
        return ""


def _read(path: str):
    try:
        return ezdxf.readfile(path)
    except Exception:
        doc, auditor = recover.readfile(path)
        return doc


def profile_dxf(path: str) -> FileProfile:
    p = FileProfile(path=path, ok=False)
    try:
        doc = _read(path)
    except Exception as ex:  # bozuk/okunamaz dosya
        p.error = f"{type(ex).__name__}: {ex}"[:200]
        return p

    msp = doc.modelspace()
    p.ok = True
    p.dxf_version = doc.dxfversion
    p.units = int(doc.header.get("$INSUNITS", 0))
    p.layers = sorted(l.dxf.name for l in doc.layers)
    p.fingerprint = layer_fingerprint(p.layers)

    types: Counter = Counter()
    texts: list[str] = []
    blocks: Counter = Counter()
    xs: list[float] = []
    ys: list[float] = []

    def _bbox_add(e):
        try:
            if e.dxftype() in ("LINE",):
                for pt in (e.dxf.start, e.dxf.end):
                    xs.append(pt[0]); ys.append(pt[1])
            elif e.dxftype() == "LWPOLYLINE":
                for pt in e.get_points("xy"):
                    xs.append(pt[0]); ys.append(pt[1])
            elif e.dxftype() in ("TEXT", "MTEXT", "INSERT", "CIRCLE", "ARC"):
                c = e.dxf.insert if hasattr(e.dxf, "insert") else e.dxf.center
                xs.append(c[0]); ys.append(c[1])
        except Exception:
            pass

    for e in msp:
        t = e.dxftype()
        types[t] += 1
        _bbox_add(e)
        if t in ("TEXT", "MTEXT"):
            s = _plain(e)
            if s:
                texts.append(s)
        elif t == "INSERT":
            blocks[e.dxf.name] += 1
            # Revit/blok etiketleri: oda adı INSERT'in ATTRIB'lerinde olabilir
            try:
                for a in e.attribs:
                    s = str(a.dxf.text).strip()
                    if s:
                        texts.append(s)
            except Exception:
                pass
            # blok içindeki sabit metinler de oda adı taşıyabilir
            try:
                for be in doc.blocks[e.dxf.name]:
                    if be.dxftype() in ("TEXT", "MTEXT"):
                        s = _plain(be)
                        if s:
                            texts.append(s)
            except Exception:
                pass

    p.n_entities = sum(types.values())
    p.type_counts = dict(types)
    p.n_lines = types["LINE"] + types["LWPOLYLINE"] + types["POLYLINE"]
    p.n_arcs = types["ARC"]
    p.n_hatch = types["HATCH"]
    p.n_inserts = types["INSERT"]
    p.block_names = [n for n, _ in blocks.most_common(15)]
    p.n_texts = len(texts)
    p.room_hits = room_hits(texts)
    p.n_room_texts = sum(p.room_hits.values())
    if xs and ys:
        p.bbox = (min(xs), min(ys), max(xs), max(ys))

    if p.n_room_texts >= 3 and p.n_lines >= 20:
        p.verdict = "ADAY"
    else:
        p.verdict = "ZAYIF"
    return p


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def group_families(profiles: list[FileProfile], threshold: float = 0.5) -> list[list[FileProfile]]:
    """Katman kümesi Jaccard benzerliği ≥ threshold ise aynı aile (greedy, tek geçiş)."""
    fams: list[list[FileProfile]] = []
    fam_layers: list[set] = []
    for p in profiles:
        if not p.ok:
            continue
        L = {tr_fold(l) for l in p.layers}
        best, best_i = 0.0, -1
        for i, fl in enumerate(fam_layers):
            s = jaccard(L, fl)
            if s > best:
                best, best_i = s, i
        if best_i >= 0 and best >= threshold:
            fams[best_i].append(p)
            fam_layers[best_i] |= L
        else:
            fams.append([p])
            fam_layers.append(set(L))
    fams.sort(key=len, reverse=True)
    return fams


def scan_files(root: str) -> list[Path]:
    out = []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if Path(f).suffix.lower() in DWG_EXT | DXF_EXT:
                out.append(Path(dirpath) / f)
    return sorted(out)


ODA_CANDIDATES = (
    os.environ.get("ODA_CONVERTER", ""),
    "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
    "ODAFileConverter",
)


def find_oda() -> Optional[str]:
    for c in ODA_CANDIDATES:
        if not c:
            continue
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
        w = shutil.which(c)
        if w:
            return w
    return None


def find_converter() -> Optional[tuple[str, str]]:
    """Kullanılabilir DWG→DXF dönüştürücü: ("oda", yol) | ("libredwg", yol) | None.
    ODA daha eksiksiz; LibreDWG (brew install libredwg) açık kaynak yedek."""
    oda = find_oda()
    if oda:
        return ("oda", oda)
    d2d = os.environ.get("DWG2DXF") or shutil.which("dwg2dxf")
    if d2d:
        return ("libredwg", d2d)
    return None


def convert_dwg_dir(in_dir: str, out_dir: str, oda: str, version: str = "ACAD2018") -> None:
    """ODA File Converter ile klasördeki tüm DWG'leri DXF'e çevirir (özyinelemeli)."""
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run([oda, in_dir, out_dir, version, "DXF", "1", "1", "*.DWG"],
                   check=False, capture_output=True, timeout=1800)


def convert_dwg_files(files: list, out_dir: str, dwg2dxf: str) -> list[str]:
    """LibreDWG dwg2dxf ile dosya dosya çevirir; dönüştürülemeyenlerin adını döndürür."""
    os.makedirs(out_dir, exist_ok=True)
    failed = []
    for f in files:
        f = Path(f)
        out = Path(out_dir) / (f.stem + ".dxf")
        try:
            r = subprocess.run([dwg2dxf, "-o", str(out), str(f)],
                               check=False, capture_output=True, timeout=600)
            if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
                failed.append(str(f))
        except Exception:
            failed.append(str(f))
    return failed


_UNITS = {0: "?", 1: "inch", 4: "mm", 5: "cm", 6: "m"}


def render_report(profiles: list[FileProfile], families: list[list[FileProfile]],
                  skipped_dwg: list[str] = ()) -> str:
    ok = [p for p in profiles if p.ok]
    cands = [p for p in ok if p.verdict == "ADAY"]
    cand_fams = [f for f in families if any(p.verdict == "ADAY" for p in f)]
    L = []
    L.append("# Veri Seti Tarama Raporu\n")
    L.append(f"- Taranan dosya: **{len(profiles)}**  (okunabilen: {len(ok)}, hatalı: {len(profiles) - len(ok)})")
    L.append(f"- ADAY kat planı (≥3 oda metni + çizgi geometrisi): **{len(cands)}**")
    L.append(f"- Katman ailesi (≈ farklı mimar/şablon): **{len(families)}**, aday içeren aile: **{len(cand_fams)}**")
    if skipped_dwg:
        L.append(f"- Dönüştürülemeyen DWG: {len(skipped_dwg)}")
    L.append("")
    L.append("## Aileler\n")
    for i, fam in enumerate(families, 1):
        common = set.intersection(*[{l for l in p.layers} for p in fam]) if fam else set()
        n_c = sum(1 for p in fam if p.verdict == "ADAY")
        L.append(f"### Aile {i} — {len(fam)} dosya, {n_c} aday")
        L.append(f"Ortak katmanlar ({len(common)}): " + ", ".join(sorted(common)[:20]) + ("…" if len(common) > 20 else ""))
        L.append("")
        L.append("| Dosya | Karar | Oda metni | Çizgi | Yay | INSERT | HATCH | Katman | Birim | Boyut | Oda eşleşmeleri |")
        L.append("|---|---|---:|---:|---:|---:|---:|---:|---|---|---|")
        for p in sorted(fam, key=lambda q: (q.verdict != "ADAY", q.name)):
            w, h = p.extent
            hits = ", ".join(f"{k}:{v}" for k, v in sorted(p.room_hits.items(), key=lambda kv: -kv[1])[:6])
            L.append(f"| {p.name} | {p.verdict} | {p.n_room_texts} | {p.n_lines} | {p.n_arcs} | {p.n_inserts} | {p.n_hatch} | {len(p.layers)} | {_UNITS.get(p.units, str(p.units))} | {w:.0f}×{h:.0f} | {hits} |")
        L.append("")
    bad = [p for p in profiles if not p.ok]
    if bad:
        L.append("## Okunamayan dosyalar\n")
        for p in bad:
            L.append(f"- {p.name}: {p.error}")
        L.append("")
    if skipped_dwg:
        L.append("## Dönüştürülmeyen DWG dosyaları\n")
        L.append("Dönüştürücü yoksa `brew install libredwg` (açık kaynak, dwg2dxf) kurun ya da "
                 "ODA File Converter'ı `ODA_CONVERTER=/yol/ODAFileConverter` ile gösterin. "
                 "Dönüştürücü varsa bu dosyalar bozuk/desteklenmeyen sürüm olabilir.\n")
        for s in skipped_dwg:
            L.append(f"- {s}")
        L.append("")
    return "\n".join(L)
