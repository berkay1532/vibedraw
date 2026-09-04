# core/perception/validate.py
"""Perception sözleşme kontrolleri (v1). Adım 7'de ValidationReport/issue üretimi buraya gelir."""
from __future__ import annotations

from core.perception.ir_v1 import BuildingIR


class PipelineError(Exception):
    """Aşama kontratı ihlal edildiğinde fırlatılır; pipeline durur."""


def validate_building(building: BuildingIR) -> None:
    if not building.floors:
        raise PipelineError("BuildingIR boş: hiç kat yok")
    for floor in building.floors:
        for room in floor.rooms:
            if not room.room_type:
                raise PipelineError(f"Oda room_type eksik: {room.raw_name!r}")
