# tests/test_devices.py
"""M2 cihaz yerleşimi (core.devices) — poligonsuz: duvara snap + etiket temelli."""
from core.perception.ir_v1 import BuildingIR, Floor, Room, Door
from core.electrical.devices import (
    place_devices, is_wet, switch_outside, _covered,
)


def _square_walls(cx, cy, h=100.0):
    """Merkez (cx,cy), yarı-genişlik h olan kare odanın 4 duvar parçası."""
    c = [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]
    return [(c[i], c[(i + 1) % 4]) for i in range(4)]


def _building():
    salon = Room(raw_name="Salon", label_xy=(0.0, 0.0), center=(0.0, 0.0), geometry_ok=True)
    mutfak = Room(raw_name="Mutfak", label_xy=(300.0, 0.0), center=(300.0, 0.0), geometry_ok=True)
    banyo = Room(raw_name="Banyo", label_xy=(0.0, 300.0), center=(0.0, 300.0), geometry_ok=True)
    balkon = Room(raw_name="Balkon", label_xy=(300.0, 300.0), center=(300.0, 300.0), geometry_ok=True)
    walls = (_square_walls(0, 0) + _square_walls(300, 0)
             + _square_walls(0, 300) + _square_walls(300, 300))
    # Her odanın alt duvarında bir kapı; room_name = açıldığı oda (M1 yay yönüyle atar)
    doors = [
        Door(xy=(0.0, -100.0), room_name="Salon"),
        Door(xy=(300.0, -100.0), room_name="Mutfak"),
        Door(xy=(0.0, 200.0), room_name="Banyo"),
        Door(xy=(300.0, 200.0), room_name="Balkon"),
    ]
    floor = Floor(index=1, rooms=[salon, mutfak, banyo, balkon],
                  doors=doors, walls=walls)
    return BuildingIR(floors=[floor])


def test_classification_helpers():
    assert is_wet("Banyo") and is_wet("Mutfak") and is_wet("WC")
    assert not is_wet("Salon")
    assert switch_outside("Banyo") and not switch_outside("Mutfak")
    assert _covered("Balkon")            # dış mekân da kapaklı


def test_one_light_per_room_at_center():
    b = place_devices(_building())
    lights = [d for d in b.floors[0].devices if d.kind == "light"]
    assert len(lights) == 4
    salon = next(d for d in lights if d.room_name == "Salon")
    assert salon.xy == (0.0, 0.0) and salon.circuit == "aydinlatma"


def test_switch_snapped_to_wall_inside_except_wet():
    b = place_devices(_building())
    sw = {d.room_name: d for d in b.floors[0].devices if d.kind == "switch"}
    assert len(sw) == 4
    # Salon: kapı alt duvarda (y=-100), anahtar duvara snap + oda içine (y>-100)
    assert sw["Salon"].xy[1] > -100.0
    assert abs(abs(sw["Salon"].xy[1]) - 100.0) < 30.0     # alt duvara yakın (snap)
    # Banyo (ıslak): kapı y=200 alt duvarda, anahtar DIŞARI (y<200)
    assert sw["Banyo"].xy[1] < 200.0


def test_two_sockets_per_room_wet_covered():
    b = place_devices(_building())
    socks = [d for d in b.floors[0].devices if d.kind == "socket"]
    assert len([s for s in socks if s.room_name == "Salon"]) == 2
    assert all(s.covered for s in socks if s.room_name == "Mutfak")
    assert all(not s.covered for s in socks if s.room_name == "Salon")


def test_appliances_each_separate_circuit():
    b = place_devices(_building())
    apps = [d for d in b.floors[0].devices if d.kind == "appliance"]
    labels = {a.label for a in apps}
    assert {"Ocak/Fırın", "Bulaşık Mak.", "Buzdolabı",
            "Çamaşır Mak.", "Kombi", "Klima"} <= labels
    assert len({a.circuit for a in apps}) == len(apps)   # her biri ayrı linye
    assert all(a.covered for a in apps)                  # hepsi kapaklı (su koruması)


def test_devices_snap_onto_walls():
    """Her cihaz bir duvar parçasına çok yakın olmalı (yüzmemeli)."""
    from core.electrical.devices import _nearest_wall
    b = place_devices(_building())
    f = b.floors[0]
    for d in f.devices:
        if d.kind == "light":
            continue                          # armatür merkezde, duvarda değil
        nw = _nearest_wall(d.xy, f.walls)
        assert nw is not None and nw[3] <= 20.0, (d.kind, d.room_name, nw[3])
