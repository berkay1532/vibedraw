# tests/test_ir_compat.py
import json
from dataclasses import asdict

from core.perception.ir_v1 import BuildingIR as B1, Floor as F1, Room as R1, Door as D1
from core.perception.ir import FileParams
from core.perception.ir_compat import to_v2, load_floor_for_eval, ROOM_CONF, DOOR_CONF


def _v1():
    salon = R1(raw_name="Salon", label_xy=(100.0, 100.0), area_m2=20.0, center=(100.0, 100.0),
               polygon=[(0.0, 0.0), (400.0, 0.0), (400.0, 500.0), (0.0, 500.0)], geometry_ok=True, source="exclusive")
    hol = R1(raw_name="Hol", label_xy=(500.0, 100.0), center=(500.0, 100.0),
             polygon=[(400.0, 0.0), (600.0, 0.0), (600.0, 500.0), (400.0, 500.0)], geometry_ok=True, source="voronoi")
    kayip = R1(raw_name="WC", label_xy=(700.0, 100.0), geometry_ok=False, polygon=None, source="fallback")
    f = F1(index=0, rooms=[salon, hol, kayip],
           doors=[D1(xy=(400.0, 100.0), room_name="Salon", strike_xy=(400.0, 190.0), source="block+arc"),
                  D1(xy=(600.0, 300.0), room_name="Hol", source="layer_raw")],
           walls=[((0.0, 0.0), (400.0, 0.0)), ((0.0, 15.0), (400.0, 15.0))], wall_sources=["pair+layer", "pair"],
           windows=[((100.0, 500.0), (200.0, 500.0))], window_sources=["thin_lines"])
    return B1(floors=[f], source_path="x.dxf")


def test_to_v2_confidence_and_evidence():
    b2 = to_v2(_v1(), units_per_meter=100.0, units_source="doors", fingerprint="abcd1234", params_extra={"res": 3.0})
    assert b2.version == "2" and b2.source_fingerprint == "abcd1234"
    fl = b2.floors[0]
    assert isinstance(fl.params, FileParams) and fl.params.units_per_meter == 100.0 and fl.params.units_source == "doors"
    by = {r.raw_name: r for r in fl.rooms}
    assert by["Salon"].confidence == ROOM_CONF["exclusive"] and by["Salon"].evidence.source == "flood:exclusive"
    assert by["Hol"].confidence == ROOM_CONF["voronoi"]
    assert by["WC"].confidence == ROOM_CONF["fallback"] and by["WC"].polygon == []
    assert abs(by["Salon"].area_m2_geom - 20.0) < 1e-6 and by["Salon"].area_m2_text == 20.0
    doors = [o for o in fl.openings if o.kind == "door"]
    assert doors[0].confidence == DOOR_CONF["block+arc"] and doors[0].rooms[0] == by["Salon"].id
    assert abs(doors[0].width - 90.0) < 1e-6 and doors[0].center == (400.0, 145.0)
    assert doors[1].confidence == DOOR_CONF["layer_raw"]
    wins = [o for o in fl.openings if o.kind == "window"]
    assert len(wins) == 1 and wins[0].confidence == 0.3 and abs(wins[0].width - 100.0) < 1e-6
    assert [w.confidence for w in fl.walls] == [0.9, 0.6] and fl.walls[0].thickness is None
    # her tespit güven + kanıt taşır
    for det in fl.rooms + fl.openings + fl.walls:
        assert 0.0 <= det.confidence <= 1.0 and det.evidence.source
    # to_mm yardımcısı
    assert fl.params.to_mm((100.0, 50.0)) == (1000.0, 500.0)


def test_v2_json_round_trip_to_eval_dict():
    b2 = to_v2(_v1(), units_per_meter=100.0)
    pred = json.loads(json.dumps(asdict(b2), default=str))
    fl = load_floor_for_eval(pred)
    assert [r["raw_name"] for r in fl["rooms"]] == ["Salon", "Hol", "WC"]
    assert fl["rooms"][0]["polygon"][0] == [0.0, 0.0] and fl["rooms"][2]["polygon"] is None
    assert fl["doors"][0]["xy"] == [400.0, 100.0] and fl["doors"][0]["room_name"] == "Salon"
    assert fl["doors"][0]["confidence"] == 0.95 and fl["doors"][1]["room_name"] == "Hol"
    assert len(fl["windows"]) == 1 and abs(fl["windows"][0][0][0] - 100.0) < 1e-6
    # v1 JSON de tanınır
    v1 = {"floors": [{"rooms": [], "doors": [], "windows": []}]}
    assert load_floor_for_eval(v1) == v1["floors"][0]
