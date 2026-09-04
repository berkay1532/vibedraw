# tests/test_pipeline.py — run_floor (reconstruct) orkestratörü
from shapely.geometry import Polygon, Point

from core.perception.parse import parse_dxf
from core.perception.pipeline import reconstruct, run_floor


def test_reconstruct_separates_two_rooms(synthetic_walled_dxf):
    # Tek kat: Salon (x~25) ve Mutfak (x~75), kapı boşluklu bölme duvarı.
    b = parse_dxf(synthetic_walled_dxf, target_floor=0, gap=200.0)
    b = reconstruct(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    rooms = {r.raw_name: r for r in b.floors[0].rooms}

    assert rooms["Salon"].geometry_ok
    assert rooms["Mutfak"].geometry_ok
    # Bölme duvarı + kapama sayesinde odalar AYRI: merkezler kendi yarısında
    assert rooms["Salon"].center[0] < 50
    assert rooms["Mutfak"].center[0] > 50


def test_reconstruct_center_inside_polygon(synthetic_walled_dxf):
    b = parse_dxf(synthetic_walled_dxf, target_floor=0, gap=200.0)
    b = reconstruct(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    for r in b.floors[0].rooms:
        assert r.polygon is not None
        assert Polygon(r.polygon).buffer(0).contains(Point(r.center))


def test_reconstruct_detects_door(synthetic_walled_dxf):
    b = parse_dxf(synthetic_walled_dxf, target_floor=0, gap=200.0)
    b = reconstruct(b, synthetic_walled_dxf, res=1.0, seal=8, margin=25.0)
    doors = b.floors[0].doors
    assert len(doors) >= 1
    # Kapı, x=50 boşluğunun yakınında olmalı
    assert any(abs(d.xy[0] - 50) < 10 for d in doors)


def test_fallback_when_no_walls(synthetic_dxf):
    # Duvarsız dosya: flood-fill tüm bbox'ı doldurur -> sızma -> fallback.
    b = parse_dxf(synthetic_dxf, target_floor=0, gap=200.0)
    b = reconstruct(b, synthetic_dxf, res=1.0, seal=4, margin=25.0)
    # Geometri güvenilir değil; center label_xy'ye düşmeli (çökmeden).
    for r in b.floors[0].rooms:
        assert r.center is not None
        if not r.geometry_ok:
            assert r.center == r.label_xy


def test_run_floor_is_reconstruct():
    assert run_floor is reconstruct
