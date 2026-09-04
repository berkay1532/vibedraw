# core/electrical/validate.py
"""Elektrik prototipi (v1) DesignIR kontrolleri."""
from __future__ import annotations

from core.electrical.ir import DesignIR
from core.perception.validate import PipelineError


def validate_design(design: DesignIR) -> None:
    if not design.rooms:
        raise PipelineError("DesignIR boş: hiç oda yok")
    for rd in design.rooms:
        for sym in (*rd.fixtures, *rd.sockets):
            if not sym.circuit_id:
                raise PipelineError(f"Sembol circuit_id eksik: {rd.room.raw_name!r}")
