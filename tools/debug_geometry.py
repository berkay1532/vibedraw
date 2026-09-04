# debug_geometry.py
"""M1 görsel doğrulama: oda poligonu + merkez + kapıları mimari altlığın
üstüne çizer. AutoCAD'de açıp geometri temelinin doğruluğunu gözle kontrol et.

Kullanım:
    python3 debug_geometry.py ornekler/empty-structure.dxf -o output/debug_m1.dxf --floor 1
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)
import argparse
import os

import ezdxf

from core.perception.ir_v1 import BuildingIR
from core.perception.pipeline import label_floors, run_floor

L_POLY = "DBG-ODA-SINIR"
L_CENTER = "DBG-ODA-MERKEZ"
L_DOOR = "DBG-KAPI"


def main() -> None:
    p = argparse.ArgumentParser(description="M1 geometri temelini altlık üstüne çiz")
    p.add_argument("dxf")
    p.add_argument("-o", "--out", default="output/debug_m1.dxf")
    p.add_argument("--floor", type=int, default=1)
    p.add_argument("--gap", type=float, default=80.0)
    args = p.parse_args()

    # Manuel VLM ile bu dosya için doğrulanmış kapı konumları (dünya koordinatı).
    # GİRİŞ(KatHolü↔Hol), SALON, MUTFAK (Hol sol), BANYO (Hol sağ-alt), BALKON.
    # (İleride API anahtarıyla otomatik VLM bu listeyi üretir.)
    # Kapı sövesi (jamb) çiftlerinin ortasından alınan KESİN konumlar.
    MANUAL_VLM_DOORS = [
        (4604, 3815),   # GİRİŞ — Kat Holü <-> Hol (üst duvar)
        (4594, 3795),   # SALON — Hol sol-üst
        (4594, 3772),   # MUTFAK — Hol sol-alt
        (4622, 3755),   # YATAK — Hol sağ duvar -> Yatak Odası
        (4604, 3744),   # BANYO — Hol alt -> Banyo
        (4646, 3723),   # Banyo <-> Yatak (ensuite)
        (4719, 3750),   # BALKON — Yatak <-> Balkon
    ]

    building = BuildingIR(floors=[label_floors(args.dxf, args.gap)[args.floor]], source_path=args.dxf)
    building = run_floor(building, args.dxf, vlm_door_points=MANUAL_VLM_DOORS)

    doc = ezdxf.readfile(args.dxf)
    msp = doc.modelspace()
    for name, color in ((L_POLY, 3), (L_CENTER, 1), (L_DOOR, 5)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    ok = 0
    floor = building.floors[0]
    for r in floor.rooms:
        if r.polygon:
            msp.add_lwpolyline(r.polygon, close=True, dxfattribs={"layer": L_POLY})
        if r.center:
            msp.add_circle(r.center, 2, dxfattribs={"layer": L_CENTER})
            tag = r.raw_name + ("" if r.geometry_ok else " [FALLBACK]")
            msp.add_text(tag, dxfattribs={"layer": L_CENTER, "height": 3}
                         ).set_placement((r.center[0] + 2, r.center[1] + 2))
        ok += int(r.geometry_ok)

    for d in floor.doors:
        msp.add_circle(d.xy, 2.5, dxfattribs={"layer": L_DOOR})

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    doc.saveas(args.out)
    print(f"Tamam → {args.out} | geometry_ok {ok}/{len(floor.rooms)} | kapı {len(floor.doors)}")


if __name__ == "__main__":
    main()
