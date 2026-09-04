# tests/test_pipeline.py — orkestratör: run_floor, select_plan, run_file
from shapely.geometry import Polygon, Point

from core.perception.ir_v1 import BuildingIR
from core.perception.pipeline import label_floors, run_file, run_floor, select_plan


def _building(path, gap=200.0, index=0):
    return BuildingIR(floors=[label_floors(path, gap)[index]], source_path=path)


def test_reconstruct_separates_two_rooms(synthetic_walled_dxf):
    # Tek kat: Salon (x~25) ve Mutfak (x~75), kapı boşluklu bölme duvarı.
    b = _building(synthetic_walled_dxf)
    b = run_floor(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    rooms = {r.raw_name: r for r in b.floors[0].rooms}

    assert rooms["Salon"].geometry_ok
    assert rooms["Mutfak"].geometry_ok
    # Bölme duvarı + kapama sayesinde odalar AYRI: merkezler kendi yarısında
    assert rooms["Salon"].center[0] < 50
    assert rooms["Mutfak"].center[0] > 50


def test_reconstruct_center_inside_polygon(synthetic_walled_dxf):
    b = _building(synthetic_walled_dxf)
    b = run_floor(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    for r in b.floors[0].rooms:
        assert r.polygon is not None
        assert Polygon(r.polygon).buffer(0).contains(Point(r.center))


def test_reconstruct_detects_door(synthetic_walled_dxf):
    b = _building(synthetic_walled_dxf)
    b = run_floor(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    doors = b.floors[0].doors
    assert len(doors) >= 1
    # Kapı, x=50 boşluğunun yakınında olmalı
    assert any(abs(d.xy[0] - 50) < 10 for d in doors)


def test_fallback_when_no_walls(synthetic_dxf):
    # Duvarsız dosya: flood-fill tüm bbox'ı doldurur -> sızma -> fallback.
    b = _building(synthetic_dxf)
    b = run_floor(b, synthetic_dxf, res=1.0, seal=4, margin=25.0)
    # Geometri güvenilir değil; center label_xy'ye düşmeli (çökmeden).
    for r in b.floors[0].rooms:
        assert r.center is not None
        if not r.geometry_ok:
            assert r.center == r.label_xy



def test_run_file_reads_dxf_once(synthetic_dxf, monkeypatch):
    """DXF tek okuma: select_plan → calibration → run_floor → parmak izi aynı belgeyi paylaşır."""
    import ezdxf
    import core.perception.pipeline as P
    import core.perception.parse as PARSE
    calls = []
    real = ezdxf.readfile
    def counting(path, *a, **k):
        calls.append(path); return real(path, *a, **k)
    monkeypatch.setattr(P.ezdxf, "readfile", counting)
    monkeypatch.setattr(PARSE.ezdxf, "readfile", counting)
    import core.perception.calibration as C
    monkeypatch.setattr(C.ezdxf, "readfile", counting)
    P.run_file(synthetic_dxf)
    assert len(calls) == 1
