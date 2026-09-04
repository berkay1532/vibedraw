# core/validate.py
from __future__ import annotations

from core.ir import BuildingIR, DesignIR


class PipelineError(Exception):
    """Aşama kontratı ihlal edildiğinde fırlatılır; pipeline durur."""


def validate_building(building: BuildingIR) -> None:
    if not building.floors:
        raise PipelineError("BuildingIR boş: hiç kat yok")
    for floor in building.floors:
        for room in floor.rooms:
            if not room.room_type:
                raise PipelineError(f"Oda room_type eksik: {room.raw_name!r}")


def validate_design(design: DesignIR) -> None:
    if not design.rooms:
        raise PipelineError("DesignIR boş: hiç oda yok")
    for rd in design.rooms:
        for sym in (*rd.fixtures, *rd.sockets):
            if not sym.circuit_id:
                raise PipelineError(f"Sembol circuit_id eksik: {rd.room.raw_name!r}")
