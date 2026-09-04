# core/layout.py
from __future__ import annotations
import math

from core.ir import DesignIR, Symbol

SOCKET_RADIUS = 30.0   # etiket çevresinde priz dağıtım yarıçapı (çizim birimi)
LIGHT_GAP = 25.0       # birden fazla armatür arası yatay aralık


def _ring(cx: float, cy: float, n: int, r: float) -> list[tuple[float, float]]:
    """Merkez etrafında n noktayı çembersel dağıtır."""
    if n <= 0:
        return []
    return [
        (cx + r * math.cos(2 * math.pi * i / n),
         cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def place(design: DesignIR) -> DesignIR:
    """Aşama 4: armatür ve prizlere etiket-merkezli konum verir."""
    for rd in design.rooms:
        cx, cy = rd.room.label_xy

        # Armatürler: tek ise merkeze, çok ise yatay sırada
        n = len(rd.fixtures)
        start = cx - (n - 1) * LIGHT_GAP / 2
        for i, f in enumerate(rd.fixtures):
            rd.fixtures[i] = Symbol("light", (start + i * LIGHT_GAP, cy), f.circuit_id)

        # Prizler: etiket çevresinde çembersel
        ring = _ring(cx, cy, len(rd.sockets), SOCKET_RADIUS)
        for i, s in enumerate(rd.sockets):
            rd.sockets[i] = Symbol("socket", ring[i], s.circuit_id)

    return design
