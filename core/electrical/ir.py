# core/electrical/ir.py
# Elektrik prototipinin IR'ı (v1). Room perception IR'ından gelir.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from core.perception.ir import Room


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
