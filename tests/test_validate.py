# tests/test_validate.py
import pytest
from core.perception.ir_v1 import Room, Floor, BuildingIR
from core.electrical.ir import RoomDesign, Symbol, DesignIR
from core.perception.validate import validate_building, PipelineError
from core.electrical.validate import validate_design


def test_validate_building_requires_room_type():
    b = BuildingIR(floors=[Floor(0, [Room("Salon", (0, 0), 10.0, room_type=None)])])
    with pytest.raises(PipelineError, match="room_type"):
        validate_building(b)


def test_validate_building_passes_when_typed():
    b = BuildingIR(floors=[Floor(0, [Room("Salon", (0, 0), 10.0, room_type="living")])])
    validate_building(b)  # raise etmemeli


def test_validate_design_requires_symbol_circuit():
    rd = RoomDesign(room=Room("Salon", (0, 0)), fixtures=[Symbol("light", (1, 1), "")])
    with pytest.raises(PipelineError, match="circuit"):
        validate_design(DesignIR(rooms=[rd]))


def test_validate_building_rejects_empty():
    with pytest.raises(PipelineError):
        validate_building(BuildingIR())


def test_validate_design_rejects_empty():
    with pytest.raises(PipelineError):
        validate_design(DesignIR())
