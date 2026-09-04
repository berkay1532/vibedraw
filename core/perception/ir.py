# core/perception/ir.py
"""Building IR v2 — ARCHITECTURE §3 şeması. Perception katmanının ÇIKTI sözleşmesi.

Her tespit `Detected` tabanından türer: `confidence` (0..1) ve `evidence` (hangi sinyaller,
hangi kaynak) olmadan hiçbir eleman listeye giremez. Elektrik alanı yoktur.

Koordinatlar ÇİZİM BİRİMİNDE (dosyanın kendi orijini); ölçek `FileParams.units_per_meter`
ile taşınır ve `FileParams.to_mm()` yardımcısı vardır — Adım 2'de pipeline'da kullanılmaz,
mm normalizasyonu Adım 3'te `calibration.py` ile gelir (docs/DECISIONS.md, 2026-09-04).

Pipeline içi hesap hâlâ v1 (`ir_v1.py`) ile yapılır; `ir_compat.to_v2` v1 → v2 çevirir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Point = tuple  # (x, y) çizim birimi


@dataclass
class Evidence:
    signals: dict = field(default_factory=dict)   # {"arc_signature": 0.9, "block_class": 0.8, ...}
    source: str = ""                               # "block+arc" | "arc" | "flood:exclusive" | "hitl" ...
    note: str = ""


@dataclass
class Detected:
    id: str
    confidence: float                              # 0..1 (Adım 2: kaba, kaynaktan türetilmiş)
    evidence: Evidence
    status: str = "auto"                           # auto | vlm_confirmed | human_confirmed | human_rejected


@dataclass
class Wall(Detected):
    """v1 duvarları YÜZ parçalarıdır: a-b bir duvar yüzü; merkez hattı + kalınlık Adım 9'da."""
    a: Point = (0.0, 0.0)
    b: Point = (0.0, 0.0)
    thickness: Optional[float] = None              # çizim birimi; v1'den bilinmiyor
    kind: str = "unknown"                          # exterior | interior | partition | unknown


@dataclass
class Opening(Detected):
    kind: str = "door"                             # door | window | passage
    wall_id: Optional[str] = None
    center: Point = (0.0, 0.0)
    width: Optional[float] = None                  # çizim birimi
    hinge: Optional[Point] = None                  # kapı için (menteşe)
    swing_dir: Optional[Point] = None              # birim vektör (menteşe→kanat ortası)
    rooms: tuple = (None, None)                    # (a, b) oda id'leri; a = yayın açıldığı oda


@dataclass
class Room(Detected):
    polygon: list = field(default_factory=list)    # [(x, y), ...] çizim birimi; boş = poligon yok
    raw_name: Optional[str] = None
    room_type: Optional[str] = None                # RoomType (sözlük/LLM normalizasyonu)
    area_m2_text: Optional[float] = None           # çizimdeki "A: 14.12m²" yazısı
    area_m2_geom: Optional[float] = None           # poligondan (units_per_meter ile)
    aliases: list = field(default_factory=list)    # aynı alandaki diğer etiketler
    alias_xy: list = field(default_factory=list)
    label_xy: Optional[Point] = None               # etiket konumu (v1 uyumluluk / bağlama)
    unit_id: Optional[str] = None


@dataclass
class Unit:
    """Daire: kapı grafında ortak alanlar çıkarılınca kalan bağlı bileşen (Adım 5d)."""
    id: str
    room_ids: list = field(default_factory=list)
    entry_opening_id: Optional[str] = None


@dataclass
class FileParams:
    """Dosyadan türetilen parametreler (calibration.file_params doldurur, Adım 6).

    upm'e bağlı koşu parametreleri çizim birimindedir; dosyadan türetilemeyen sabitler
    config/thresholds.yaml'dadır (oraya bakan kod bu alanları kullanmaz)."""
    units_per_meter: float = 100.0
    units_source: str = "labels"                   # labels | doors | header | hitl
    res: Optional[float] = None                    # raster hücre boyu (birim)
    seal: Optional[int] = None                     # morfolojik kapama (piksel)
    margin: Optional[float] = None                 # kat bbox marjı (birim)
    door_arc_radius: Optional[tuple] = None        # kapı yayı yarıçap aralığı (birim)
    door_wall_dist: Optional[float] = None         # menteşe ↔ duvar (birim)
    door_max_boundary_dist: Optional[float] = None # layer_raw adayı ↔ oda sınırı (birim)
    wall_thickness: Optional[tuple] = None         # duvar kalınlık aralığı (birim)
    wall_min_overlap: Optional[float] = None
    extra: dict = field(default_factory=dict)      # big_blocks, family_id, layer_classes vb.

    def to_mm(self, p: Point) -> Point:
        """Çizim birimi → mm. Pipeline'da kullanılmaz (Adım 3'e kadar), yardımcı."""
        k = 1000.0 / self.units_per_meter
        return (p[0] * k, p[1] * k)


@dataclass
class Issue:
    kind: str                                      # unknown_layer | open_room | room_no_door | ...
    target_id: Optional[str] = None
    message: str = ""
    options: list = field(default_factory=list)


@dataclass
class ValidationReport:
    issues: list = field(default_factory=list)     # Issue listesi (Adım 7'de dolar)


@dataclass
class Floor:
    index: int
    name: Optional[str] = None                     # "ZEMİN KAT" (pafta anlama bağlanınca)
    walls: list = field(default_factory=list)      # Wall
    openings: list = field(default_factory=list)   # Opening
    rooms: list = field(default_factory=list)      # Room
    units: list = field(default_factory=list)      # Unit
    params: FileParams = field(default_factory=FileParams)


@dataclass
class BuildingIR:
    source_path: str = ""
    source_fingerprint: str = ""                   # triage.layer_fingerprint
    floors: list = field(default_factory=list)     # Floor
    validation: ValidationReport = field(default_factory=ValidationReport)
    version: str = "2"
