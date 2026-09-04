# core/perception/semantics.py
from __future__ import annotations

from core.perception.ir_v1 import BuildingIR
from core.perception import llm
from core.perception.vocab import ROOM_TYPE_MAP   # ham isim (casefold) → kanonik tip


def map_name(raw_name: str) -> str | None:
    """Sözlükten kanonik tip döndürür; yoksa None."""
    return ROOM_TYPE_MAP.get(raw_name.strip().casefold())


def classify(building: BuildingIR) -> BuildingIR:
    """Aşama 2: her odaya room_type atar. Sözlük tutmazsa LLM'e sorar."""
    for floor in building.floors:
        for room in floor.rooms:
            mapped = map_name(room.raw_name)
            if mapped is None:
                # LLM yoksa/başarısızsa pipeline çökmesin: "other"'a düş.
                try:
                    mapped = llm.normalize_room_name(room.raw_name)
                except Exception:
                    mapped = "other"
            room.room_type = mapped
    return building
