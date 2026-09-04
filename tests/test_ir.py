# tests/test_ir.py
from core.perception.ir import Room, Floor, BuildingIR
from core.electrical.ir import Symbol, RoomDesign, Circuit, DesignIR


def test_room_defaults():
    r = Room(raw_name="Salon", label_xy=(10.0, 20.0))
    assert r.area_m2 is None
    assert r.room_type is None


def test_building_holds_floors_and_rooms():
    r = Room(raw_name="Salon", label_xy=(1.0, 2.0), area_m2=14.12, room_type="living")
    f = Floor(index=0, rooms=[r])
    b = BuildingIR(floors=[f], source_path="x.dxf")
    assert b.floors[0].rooms[0].room_type == "living"


def test_design_holds_symbols_and_circuits():
    sym = Symbol(kind="light", xy=(1.0, 2.0), circuit_id="A1")
    rd = RoomDesign(room=Room(raw_name="Salon", label_xy=(1.0, 2.0)),
                    fixtures=[sym], sockets=[], circuit_id="A1", rationale="...")
    c = Circuit(id="A1", kind="lighting", room_names=["Salon"])
    d = DesignIR(rooms=[rd], circuits=[c])
    assert d.rooms[0].fixtures[0].kind == "light"
    assert d.circuits[0].id == "A1"
