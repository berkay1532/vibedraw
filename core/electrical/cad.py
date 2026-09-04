# core/cad.py
from __future__ import annotations
import os

import ezdxf

from core.electrical.ir import DesignIR

LAYER_LIGHT = "EL-AYDINLATMA"
LAYER_SOCKET = "EL-PRIZ"
LAYER_LINYE = "EL-LINYE"
SYM_SIZE = 8.0  # sembol yarıçapı (çizim birimi)


def _ensure_layers(doc):
    for name, color in ((LAYER_LIGHT, 2), (LAYER_SOCKET, 4), (LAYER_LINYE, 3)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def _define_blocks(doc):
    """Basit sembol blokları: lamba = daire + çarpı, priz = yarım daire benzeri."""
    if "EL_LIGHT" not in doc.blocks:
        blk = doc.blocks.new(name="EL_LIGHT")
        blk.add_circle((0, 0), SYM_SIZE)
        blk.add_line((-SYM_SIZE, 0), (SYM_SIZE, 0))
        blk.add_line((0, -SYM_SIZE), (0, SYM_SIZE))
    if "EL_SOCKET" not in doc.blocks:
        blk = doc.blocks.new(name="EL_SOCKET")
        blk.add_circle((0, 0), SYM_SIZE)
        blk.add_line((0, 0), (0, SYM_SIZE * 1.5))


def write_dxf(design: DesignIR, source_path: str, out_path: str) -> str:
    """Aşama 5: kaynak DXF'i koru, yeni layer'lara semboller + linye ekle, yaz."""
    doc = ezdxf.readfile(source_path)
    msp = doc.modelspace()
    _ensure_layers(doc)
    _define_blocks(doc)

    # Linye grubuna göre sembol konumlarını topla (sıralı polyline için)
    circuit_points: dict[str, list[tuple[float, float]]] = {}

    for rd in design.rooms:
        for f in rd.fixtures:
            msp.add_blockref("EL_LIGHT", f.xy, dxfattribs={"layer": LAYER_LIGHT})
            circuit_points.setdefault(f.circuit_id, []).append(f.xy)
        for s in rd.sockets:
            msp.add_blockref("EL_SOCKET", s.xy, dxfattribs={"layer": LAYER_SOCKET})
            circuit_points.setdefault(s.circuit_id, []).append(s.xy)

    # Her linye için sembolleri birbirine bağlayan basit polyline
    for cid, pts in circuit_points.items():
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs={"layer": LAYER_LINYE})

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    doc.saveas(out_path)
    return out_path
