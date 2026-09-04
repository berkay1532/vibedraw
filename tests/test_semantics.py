# tests/test_semantics.py
from core.ir import Room, Floor, BuildingIR
from core import semantics


def _building(*names):
    rooms = [Room(raw_name=n, label_xy=(0.0, 0.0), area_m2=10.0) for n in names]
    return BuildingIR(floors=[Floor(index=0, rooms=rooms)])


def test_known_names_mapped_by_dictionary(monkeypatch):
    # Sözlük yeterse LLM ASLA çağrılmamalı
    def boom(*a, **k):
        raise AssertionError("LLM çağrılmamalıydı")
    monkeypatch.setattr(semantics.llm, "normalize_room_name", boom)

    b = semantics.classify(_building("Salon", "Mutfak", "Yatak Odası", "WC", "Kat Holü"))
    types = [r.room_type for r in b.floors[0].rooms]
    assert types == ["living", "kitchen", "bedroom", "wc", "circulation"]


def test_unknown_name_falls_back_to_llm(monkeypatch):
    monkeypatch.setattr(semantics.llm, "normalize_room_name", lambda raw: "bedroom")
    b = semantics.classify(_building("Ebeveyn Suiti"))
    assert b.floors[0].rooms[0].room_type == "bedroom"


def test_unknown_name_degrades_to_other_when_llm_fails(monkeypatch):
    def boom(raw):
        raise RuntimeError("LLM yok / ağ hatası")
    monkeypatch.setattr(semantics.llm, "normalize_room_name", boom)
    b = semantics.classify(_building("Ebeveyn Suiti"))
    assert b.floors[0].rooms[0].room_type == "other"
