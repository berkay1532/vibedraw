# tests/test_rules.py
import core.electrical.rules as R
from core.perception.ir_v1 import Room, Floor, BuildingIR
from core.electrical.rules import load_rules, decide


def test_load_rules_has_expected_types():
    rules = load_rules("rules/residential.yaml")
    assert "living" in rules
    assert rules["kitchen"]["circuit"] == "kitchen"
    assert rules["bedroom"]["sockets"]["min"] >= 1


def _b(name, rtype, area):
    r = Room(raw_name=name, label_xy=(0.0, 0.0), area_m2=area, room_type=rtype)
    return BuildingIR(floors=[Floor(index=0, rooms=[r])])


def test_decide_counts_lighting_by_area(monkeypatch):
    # LLM gerekçesini devre dışı bırak (deterministik sayıyı test ediyoruz)
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: None)
    rules = R.load_rules("rules/residential.yaml")
    design = decide(_b("Salon", "living", 25.0), rules)
    rd = design.rooms[0]
    # 25 m² / 12 per_m2 -> ceil = 3 armatür
    assert len(rd.fixtures) == 3
    assert len(rd.sockets) == 4          # living min 4
    assert all(s.kind == "light" for s in rd.fixtures)


def test_decide_assigns_kitchen_separate_circuit(monkeypatch):
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: None)
    rules = R.load_rules("rules/residential.yaml")
    design = decide(_b("Mutfak", "kitchen", 14.5), rules)
    assert design.rooms[0].circuit_id.startswith("kitchen")
    kinds = {c.id: c.kind for c in design.circuits}
    assert design.rooms[0].circuit_id in kinds
