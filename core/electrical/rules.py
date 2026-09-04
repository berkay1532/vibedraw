# core/rules.py
from __future__ import annotations
import math

import yaml

from core.perception.ir_v1 import BuildingIR
from core.electrical.ir import DesignIR, RoomDesign, Symbol, Circuit
from core.perception import llm


def load_rules(path: str = "rules/residential.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _rationale(room_type: str, circuit_group: str, area: float):
    """LLM gerekçe metni (opsiyonel). Sayı üretmez."""
    try:
        return llm.explain_decision(
            f"{room_type} odası '{circuit_group}' linye grubuna atandı",
            {"area_m2": area},
        )
    except Exception:
        return None  # LLM yoksa pipeline yine de çalışır


def _lighting_count(area: float | None, rule: dict) -> int:
    minimum = rule["lighting"]["min"]
    per = rule["lighting"].get("per_m2")
    if area is not None and per:
        return max(minimum, math.ceil(area / per))
    return minimum


def decide(building: BuildingIR, rules: dict) -> DesignIR:
    """Aşama 3: her odaya armatür/priz adedi ve linye atar. Konumlar Aşama 4'te."""
    design = DesignIR()
    circuits: dict[str, Circuit] = {}

    for floor in building.floors:
        for room in floor.rooms:
            rule = rules.get(room.room_type, rules["other"])
            group = rule["circuit"]

            light_cid = f"{group}-L"
            socket_cid = f"{group}-P"
            for cid, kind in ((light_cid, "lighting"), (socket_cid, "socket")):
                c = circuits.setdefault(cid, Circuit(id=cid, kind=kind))
                if room.raw_name not in c.room_names:
                    c.room_names.append(room.raw_name)

            n_light = _lighting_count(room.area_m2, rule)
            n_socket = rule["sockets"]["min"]

            rd = RoomDesign(
                room=room,
                fixtures=[Symbol(kind="light", xy=(0.0, 0.0), circuit_id=light_cid)
                          for _ in range(n_light)],
                sockets=[Symbol(kind="socket", xy=(0.0, 0.0), circuit_id=socket_cid)
                         for _ in range(n_socket)],
                circuit_id=light_cid,
                rationale=_rationale(room.room_type, group, room.area_m2 or 0.0),
            )
            design.rooms.append(rd)

    design.circuits = list(circuits.values())
    return design
