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


def test_unknown_block_issue_and_cap():
    """v0.2-1: sınıfsız, yaysız bloklar → unknown_block (kapı/pencere katmanı ya da ≥5 yerleşim; dosya başına ≤3)."""
    from core.perception.ir import FileParams, Floor
    from core.perception.names import NameMap, classify_blocks
    from core.perception.validate import BLOCK_OPTIONS, issues_for_floor
    nm = NameMap(classes={"KAPI": (__import__("core.perception.names", fromlist=["LayerClass"]).LayerClass.door, 0.6, "keyword")},
                 blocks=classify_blocks(["A$C001", "A$C002", "A$C003", "A$C004", "SUZGEC", "95 KAPI"], None))
    nm.block_stats = {
        "A$C001": {"n": 2, "arc": 0, "arc_door": 0, "w": 0.9, "h": 0.1, "layers": {"KAPI": 2}, "xy": [(0, 0)]},
        "A$C002": {"n": 9, "arc": 0, "arc_door": 0, "w": 1.2, "h": 0.2, "layers": {"0": 9}, "xy": [(1, 1)]},
        "A$C003": {"n": 7, "arc": 0, "arc_door": 0, "w": 8.0, "h": 4.0, "layers": {"0": 7}, "xy": [(2, 2)]},
        "A$C004": {"n": 6, "arc": 0, "arc_door": 0, "w": 1.0, "h": 0.3, "layers": {"0": 6}, "xy": [(3, 3)]},
        "SUZGEC": {"n": 2, "arc": 0, "arc_door": 0, "w": 0.2, "h": 0.2, "layers": {"0": 2}, "xy": [(4, 4)]},
        "95 KAPI": {"n": 30, "arc": 0, "arc_door": 0, "w": 0.9, "h": 0.1, "layers": {"0": 30}, "xy": [(5, 5)]},
    }
    fl = Floor(index=0, name="t", params=FileParams(units_per_meter=100.0))
    iss = issues_for_floor(fl, nm, {}, enabled={"unknown_block"})
    ids = [i.target_id for i in iss]
    assert len(ids) == 3                                  # dosya başına en fazla 3
    assert "block:95 KAPI" not in ids                     # sözlük tuttu (kapı) → sorulmaz
    assert "block:SUZGEC" not in ids                      # 2 yerleşim, kapı katmanı değil → eşik altı
    assert ids[0] == "block:A$C002"                       # yerleşim × boyut bandı sıralaması
    assert "block:A$C001" in ids                          # kapı katmanında → yerleşim eşiği aranmaz
    assert iss[0].options == BLOCK_OPTIONS and iss[0].data["placements"] == 9


def test_unknown_block_skips_arc_blocks():
    """İçinde kapı yayı olan blok sorulmaz (yay yolu zaten kapı üretiyor)."""
    from core.perception.ir import FileParams, Floor
    from core.perception.names import NameMap, classify_blocks
    from core.perception.validate import issues_for_floor
    nm = NameMap(blocks=classify_blocks(["A$C009"], None))
    nm.block_stats = {"A$C009": {"n": 20, "arc": 1, "arc_door": 1, "w": 0.9, "h": 0.9, "layers": {"0": 20}, "xy": [(0, 0)]}}
    fl = Floor(index=0, name="t", params=FileParams(units_per_meter=100.0))
    assert issues_for_floor(fl, nm, {}, enabled={"unknown_block"}) == []
