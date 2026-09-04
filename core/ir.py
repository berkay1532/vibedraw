# core/ir.py
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
class Device:
    """M2 cihazı: aydınlatma/anahtar/priz/buat/beyaz eşya."""
    kind: str                          # "light"|"switch"|"socket"|"junction"|"appliance"
    xy: tuple[float, float]
    room_name: Optional[str] = None
    circuit: Optional[str] = None      # "aydinlatma"|"priz"|"<beyaz-esya>"
    covered: bool = False              # ıslak hacim: kapaklı priz
    label: Optional[str] = None        # beyaz eşya adı vb.


@dataclass
class Floor:
    index: int
    rooms: list[Room] = field(default_factory=list)
    doors: list[Door] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)   # M2 cihazları
    # Gerçek duvar parçaları (M1'de doldurulur) — cihazları duvara snap için
    walls: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    # Pencere/cam parçaları — cihaz konmaz (yasak bölge)
    windows: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    # Tespit edilen beyaz eşya konumları (ad -> xy), M1'de doldurulur (ör. ocak)
    appliance_pts: dict = field(default_factory=dict)
    big_blocks: bool = False           # plan blok içindeydi, bloklar açılarak işlendi


@dataclass
class BuildingIR:
    floors: list[Floor] = field(default_factory=list)
    source_path: str = ""


@dataclass
class Symbol:
    kind: str                          # "light" | "socket"
    xy: tuple[float, float]
    circuit_id: str


@dataclass
class RoomDesign:
    room: Room
    fixtures: list[Symbol] = field(default_factory=list)   # aydınlatma
    sockets: list[Symbol] = field(default_factory=list)    # priz
    circuit_id: Optional[str] = None
    rationale: Optional[str] = None


@dataclass
class Circuit:
    id: str
    kind: str                          # "lighting" | "socket"
    room_names: list[str] = field(default_factory=list)


@dataclass
class DesignIR:
    rooms: list[RoomDesign] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
