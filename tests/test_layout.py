# tests/test_layout.py
from core.perception.ir import Room
from core.electrical.ir import RoomDesign, Symbol, DesignIR
from core.electrical.layout import place


def _design():
    room = Room(raw_name="Salon", label_xy=(100.0, 200.0), area_m2=14.0, room_type="living")
    rd = RoomDesign(
        room=room,
        fixtures=[Symbol("light", (0.0, 0.0), "general-L")],
        sockets=[Symbol("socket", (0.0, 0.0), "general-P") for _ in range(3)],
        circuit_id="general-L",
    )
    return DesignIR(rooms=[rd])


def test_single_light_placed_at_label():
    d = place(_design())
    light = d.rooms[0].fixtures[0]
    assert light.xy == (100.0, 200.0)


def test_sockets_distributed_around_label_uniquely():
    d = place(_design())
    coords = [s.xy for s in d.rooms[0].sockets]
    # her priz ayrı konumda ve hiçbiri etiket noktasıyla çakışmıyor
    assert len(set(coords)) == len(coords)
    assert (100.0, 200.0) not in coords
