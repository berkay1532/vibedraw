# tests/test_hitl.py — validator issue üretimi, learning log, HITL CLI (liste/cevap/uygulama)
import json
from pathlib import Path

from core.perception.ir import BuildingIR, Evidence, FileParams, Floor, Opening, Room, Wall
from core.perception.names import LayerClass, NameMap
from core.perception.validate import issue_counts, issues_for_floor, validate_building_v2


def _floor():
    fl = Floor(index=0, params=FileParams(units_per_meter=42.0, units_source="labels"))
    sq = [(0.0, 0.0), (400.0, 0.0), (400.0, 500.0), (0.0, 500.0)]
    fl.rooms = [Room("r1", 0.85, Evidence(source="flood:exclusive"), polygon=sq, raw_name="SALON", area_m2_text=30.0, area_m2_geom=20.0, label_xy=(200.0, 250.0)),
                Room("r2", 0.2, Evidence(source="flood:fallback"), polygon=[], raw_name="WC", label_xy=(600.0, 100.0)),
                Room("r3", 0.85, Evidence(source="flood:exclusive"), polygon=sq, raw_name="MERDİVEN", label_xy=(50.0, 50.0))]
    fl.openings = [Opening("op1", 0.95, Evidence(source="block+arc"), kind="door", center=(400.0, 100.0), hinge=(400.0, 100.0), rooms=("r1", None)),
                   Opening("op2", 0.3, Evidence(source="window:thin_lines"), kind="window", center=(100.0, 500.0))]
    fl.walls = [Wall(f"w{i}", 0.6, Evidence(source="pair", note="conflicting_signal"), a=(0, i), b=(100, i), layer="A_ANNO") for i in range(25)]
    fl.walls += [Wall("w99", 0.9, Evidence(source="pair+layer"), a=(0, 0), b=(10, 0), layer="DUVAR")]
    return fl


def test_issues_types_and_priority():
    nm = NameMap(classes={"A_ANNO": (LayerClass.text, 0.6, "keyword"), "DUVAR": (LayerClass.wall, 0.6, "keyword")})
    iss = issues_for_floor(_floor(), nm, layer_counts={"A_ANNO": 300, "GIZEMLI": 120, "DUVAR": 80})
    kinds = [i.kind for i in iss]
    assert kinds[0] == "unknown_layer" and iss[0].target_id == "layer:GIZEMLI"
    assert "conflicting_layer" in kinds and next(i for i in iss if i.kind == "conflicting_layer").data["count"] == 25
    assert "unit_suspect" in kinds                                  # 42 birim/m standart değil
    assert "open_room" in kinds and "ambiguous_opening" in kinds
    amb = next(i for i in iss if i.kind == "ambiguous_opening")
    assert amb.target_id == "openings" and amb.data["targets"] == ["op2"]   # toplu; penceresiz odaya değiyor
    assert "area_mismatch" not in kinds                             # tek oda: medyan kendisi → sapma 0
    assert not any(i.kind == "room_no_door" and i.target_id == "r3" for i in iss)   # merdiven muaf
    assert not any(i.kind == "room_no_door" and i.target_id == "r1" for i in iss)   # kapısı var
    from core.perception.validate import PRIORITY
    assert kinds == sorted(kinds, key=PRIORITY.index)
    rep = validate_building_v2(BuildingIR(floors=[_floor()]), nm, {"GIZEMLI": 120})
    assert issue_counts(rep.issues)["unknown_layer"] == 1


def test_cli_list_answer_and_log(tmp_path, monkeypatch):
    from dataclasses import asdict
    import hitl.cli as cli
    from learning import log as L
    fl = _floor(); b = BuildingIR(source_path="x.dxf", floors=[fl])
    b.validation = validate_building_v2(b, NameMap(), {})
    pj = tmp_path / "t.json"; pj.write_text(json.dumps(asdict(b), default=str), encoding="utf-8")
    monkeypatch.setattr(L, "LOG_DIR", tmp_path / "learning")
    monkeypatch.setattr(cli, "render_crop", lambda pred, iss, out: out)          # DXF yok: crop atla
    assert cli.main([str(pj), "--list"]) == 0
    pred = cli.load(pj); iss = cli.issues(pred)
    idx = next(i for i, it in enumerate(iss) if it["kind"] == "ambiguous_opening")
    assert cli.main([str(pj), "--issue", str(idx), "--answer", "hiçbiri"]) == 0
    pred = cli.load(pj)
    op = next(o for o in pred["floors"][0]["openings"] if o["id"] == "op2")
    assert op["status"] == "human_rejected" and op["hitl"]["answer"] == "hiçbiri"
    recs = L.read(tmp_path / "learning")
    assert len(recs) == 1 and recs[0]["issue"] == "ambiguous_opening" and recs[0]["answer"] == "hiçbiri" and recs[0]["ts"]
    uidx = next(i for i, it in enumerate(cli.issues(pred)) if it["kind"] == "unit_suspect")
    assert cli.main([str(pj), "--issue", str(uidx), "--answer", "cm"]) == 0
    assert cli.load(pj)["floors"][0]["params"]["extra"]["hitl_units"]["upm"] == 100.0



def test_policy_exemptions_area_convention_and_budget():
    from core.perception.validate import exempt_room_type
    assert exempt_room_type("BALKON") == "balcony" and exempt_room_type("TERAS") == "terrace" and exempt_room_type("ŞAFT") == "shaft"
    assert exempt_room_type("ASANSÖR") == "elevator" and exempt_room_type("AYDINLIK") == "light_well" and exempt_room_type("SALON") is None
    fl = _floor()
    sq = [(0.0, 0.0), (400.0, 0.0), (400.0, 500.0), (0.0, 500.0)]
    # üç oda oran 1.5 (konvansiyon), biri 3.0 → yalnız o issue
    fl.rooms = [Room(f"r{i}", 0.85, Evidence(source="flood:exclusive"), polygon=sq, raw_name="ODA", area_m2_text=t, area_m2_geom=20.0, label_xy=(1, 1))
                for i, t in enumerate((30.0, 30.0, 30.0, 60.0))]
    iss = issues_for_floor(fl, NameMap(), {})
    am = [i for i in iss if i.kind == "area_mismatch"]
    assert len(am) == 1 and am[0].target_id == "r3" and fl.params.area_convention == 1.5
    fl.params.extra["heavy"] = True                      # üretim sınırı yok: heavy dosyada da tüm issue'lar üretilir
    iss2 = issues_for_floor(fl, NameMap(), {f"L{k}": 100 for k in range(5)})
    assert len(iss2) >= len(iss)


def test_unknown_layer_ranked_and_capped():
    from core.perception.names import stats_class
    nm = NameMap(); nm.stats = {f"L{k}": {"n": 100, "line": 50, "long": k * 10, "short": 0, "arc": 0, "small_arc": 0, "text": 0, "dim": 0, "hatch": 0, "insert": 0} for k in range(6)}
    iss = issues_for_floor(_floor(), nm, {f"L{k}": 100 for k in range(6)})
    ul = [i for i in iss if i.kind == "unknown_layer"]
    assert len(ul) == 3 and ul[0].target_id == "layer:L5" and ul[0].data["wall_like_ratio"] == 1.0
    assert stats_class({"n": 40, "line": 40, "long": 0, "short": 35, "arc": 0, "small_arc": 0, "text": 0, "dim": 0, "hatch": 0, "insert": 0})[0].value == "furniture"
    assert stats_class({"n": 40, "line": 0, "long": 0, "short": 0, "arc": 0, "small_arc": 0, "text": 36, "dim": 2, "hatch": 0, "insert": 0})[0].value == "text"
    assert stats_class({"n": 40, "line": 10, "long": 0, "short": 2, "arc": 5, "small_arc": 1, "text": 0, "dim": 0, "hatch": 0, "insert": 20})[0].value == "ignore"
    assert stats_class({"n": 40, "line": 40, "long": 20, "short": 0, "arc": 0, "small_arc": 0, "text": 0, "dim": 0, "hatch": 0, "insert": 0})[0].value == "unknown"


def test_window_missing_door_side_and_absolute_area():
    from core.perception.validate import window_expected_type
    assert window_expected_type("YATAK ODASI") == "bedroom" and window_expected_type("ODA") == "bedroom"
    assert window_expected_type("SALON+MUTFAK") in ("living", "kitchen") and window_expected_type("BANYO") is None
    fl = _floor()
    sq = [(0.0, 0.0), (400.0, 0.0), (400.0, 500.0), (0.0, 500.0)]
    inner = [(100.0, 100.0), (300.0, 100.0), (300.0, 400.0), (100.0, 400.0)]
    fl.rooms = [Room("r1", 0.85, Evidence(source="flood:exclusive"), polygon=sq, raw_name="YATAK ODASI", label_xy=(50, 50), area_m2_text=8.0, area_m2_geom=20.0),
                Room("r2", 0.85, Evidence(source="flood:exclusive"), polygon=inner, raw_name="YATAK ODASI", label_xy=(200, 250), area_m2_text=30.0, area_m2_geom=20.0),
                Room("r3", 0.85, Evidence(source="flood:exclusive"), polygon=sq, raw_name="BANYO", label_xy=(60, 60), area_m2_text=30.0, area_m2_geom=20.0)]
    fl.openings = [Opening("op1", 0.95, Evidence(source="block+arc", signals={"swing_margin": 0.05}), kind="door", center=(400, 100), hinge=(400, 100), width=90.0, rooms=("r1", None)),
                   Opening("op2", 0.7, Evidence(source="block"), kind="door", center=(0, 100), hinge=(0, 100), width=None, rooms=("r3", None))]
    fl.walls = []
    iss = issues_for_floor(fl, NameMap(), {})
    kinds = {(i.kind, i.target_id) for i in iss}
    assert ("window_missing", "r1") in kinds                     # yatak odası, dış sınıra değiyor, pencere yok
    assert ("window_missing", "r2") not in kinds                 # iç oda (dış sınıra değmiyor)
    assert ("window_missing", "r3") not in kinds                 # banyo: pencere beklenmez
    assert ("door_side_ambiguous", "op1") in kinds and ("door_side_ambiguous", "op2") in kinds
    am = {i.target_id for i in iss if i.kind == "area_mismatch"}
    assert "r1" in am                                            # oran 0.4 < 0.5: mutlak kural (medyan 1.5'ten sapma da var)
    sub = issues_for_floor(fl, NameMap(), {}, enabled={"open_room"})
    assert all(i.kind == "open_room" for i in sub)


def test_room_merged_issue_and_no_budget_truncation():
    fl = _floor()
    sq = [(0.0, 0.0), (400.0, 0.0), (400.0, 500.0), (0.0, 500.0)]
    fl.rooms = [Room("r1", 0.6, Evidence(source="flood:alias_merge"), polygon=sq, raw_name="ANTRE", aliases=["HOL"], label_xy=(1, 1))]
    fl.openings = []; fl.walls = []
    iss = issues_for_floor(fl, NameMap(), {})
    rm = [i for i in iss if i.kind == "room_merged"]
    assert len(rm) == 1 and rm[0].target_id == "r1" and rm[0].data["aliases"] == ["HOL"]
    fl.params.extra["heavy"] = True
    many = issues_for_floor(fl, NameMap(), {f"L{k}": 100 for k in range(12)})
    assert len(many) >= 1 and not any("budget_dropped" in i.data for i in many)     # üretim sınırı yok
