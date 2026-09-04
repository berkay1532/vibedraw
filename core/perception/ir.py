# core/perception/ir.py
# Perception IR (v1). Elektrik alanları core/electrical/ir.py'de; Adım 2'de v2 şeması gelecek.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Room:
    raw_name: str                      # Çizimdeki ham isim, örn. "Yatak Odası"
    label_xy: tuple[float, float]      # Oda etiketinin konumu (≈oda merkezi)
    area_m2: Optional[float] = None    # "A: 14.12m²" yazısından okunur
    room_type: Optional[str] = None    # Kanonik tip, mahallendirmede doldurulur
    # v2 geometri (M1'de doldurulur):
    center: Optional[tuple[float, float]] = None       # temsilî iç nokta (armatür için)
    polygon: Optional[list[tuple[float, float]]] = None  # oda sınır poligonu
    geometry_ok: bool = False          # False ise center=label_xy (fallback)
    # Aynı kapalı alanda (duvarsız/kapısız) bulunan diğer etiketler: bölge adları.
    # Örn. açık mutfaklı salon → raw_name="SALON", aliases=["MUTFAK"].
    aliases: list = field(default_factory=list)
    alias_xy: list = field(default_factory=list)


@dataclass
class Door:
    xy: tuple[float, float]            # menteşe konumu
    room_name: Optional[str] = None    # açıldığı oda (yay yönü)
    strike_xy: Optional[tuple[float, float]] = None  # kilit sövesi (anahtar bu tarafa)


@dataclass
class Floor:
    index: int
    rooms: list[Room] = field(default_factory=list)
    doors: list[Door] = field(default_factory=list)
    devices: list = field(default_factory=list)   # elektrik motoru doldurur (v1 uyumluluk; bkz. docs/DECISIONS.md)
    # Gerçek duvar parçaları (M1'de doldurulur) — cihazları duvara snap için
    walls: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    # Pencere/cam parçaları — cihaz konmaz (yasak bölge)
    windows: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    big_blocks: bool = False           # plan blok içindeydi, bloklar açılarak işlendi


@dataclass
class BuildingIR:
    floors: list[Floor] = field(default_factory=list)
    source_path: str = ""


