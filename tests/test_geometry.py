# tests/test_geometry.py
from shapely.geometry import Polygon, Point

from core.perception.parse import parse_dxf
from core.perception.geometry import reconstruct, _cluster_doors


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


def test_cluster_doors_merges_near_points():
    pts = [(0, 0), (2, 1), (50, 50), (51, 49)]
    clusters = _cluster_doors(pts, radius=15.0)
    assert len(clusters) == 2


def test_staircase_polygon_survives_large_coordinates():
    """UTM benzeri büyük koordinatlarda (4.4 milyon) maske→poligon boş dönmemeli."""
    import numpy as np
    from core.perception.geometry import _staircase_polygon

    class R:  # asgari raster taklidi
        res = 2.74
        x0, y0 = 314700.0, 4430000.0
    mask = np.zeros((60, 80), dtype=bool); mask[10:50, 15:70] = True
    poly = _staircase_polygon(mask, R)
    assert poly is not None and poly.area > 0
    exp = (40 * 2.74) * (55 * 2.74)
    assert abs(poly.area - exp) / exp < 0.02
    minx, miny, maxx, maxy = poly.bounds
    assert abs(minx - (R.x0 + 15 * 2.74 - 1.37)) < 0.01 and abs(miny - (R.y0 + 10 * 2.74 - 1.37)) < 0.01


def test_door_barriers_pick_closed_leaf():
    from core.perception.geometry import _door_barriers
    walls = [((0, 0), (300, 0))]                       # yatay duvar y=0
    # menteşe (100,0); uç1 (190,0) duvar üstünde (kapalı), uç2 (100,90) odaya açık
    sw = [((100.0, 0.0), (0.7, 0.7), (190.0, 0.0), (100.0, 90.0))]
    b = _door_barriers(sw, walls)
    assert b == [((100.0, 0.0), (190.0, 0.0))]
    assert _door_barriers(sw, []) == []


def test_window_detection_layer_independent(tmp_path):
    """(a) 'PENCERE' adlı blok, (b) duvar bandında 3 ince paralel cam çizgisi → 2 pencere."""
    import ezdxf
    from core.perception.geometry import _window_segments
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    blk = doc.blocks.new("90LIK PENCERE")
    blk.add_line((0, 0), (90, 0)); blk.add_line((0, 4), (90, 4)); blk.add_line((0, 0), (0, 4)); blk.add_line((90, 0), (90, 4))
    msp.add_blockref("90LIK PENCERE", (100, 500), dxfattribs={"layer": "Layer 3"})
    # duvar bandı: y=0 ve y=20 yüzleri (walls listesi), boşlukta 3 cam çizgisi x=300..420
    walls = [((0, 0), (300, 0)), ((0, 20), (300, 20)), ((420, 0), (800, 0)), ((420, 20), (800, 20))]
    for y in (8, 10, 12):
        msp.add_line((300, y), (420, y), dxfattribs={"layer": "0"})
    # gürültü: oda ortasında tek çizgi, kısa çizgiler
    msp.add_line((100, 300), (250, 300), dxfattribs={"layer": "0"})
    p = tmp_path / "w.dxf"; doc.saveas(p)
    doc2 = ezdxf.readfile(str(p)); wins = _window_segments(doc2.modelspace(), (-50, -50, 900, 600), upm=100, walls=walls)
    mids = sorted(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in wins)
    assert len(mids) == 2
    assert abs(mids[0][0] - 145) < 2 and abs(mids[0][1] - 502) < 3     # blok
    assert abs(mids[1][0] - 360) < 2 and abs(mids[1][1] - 10) < 3      # cam çizgileri


def test_ladder_filter_removes_stair_steps_keeps_door_leaf():
    from core.perception.geometry import _ladder_filter
    steps = [((0, y), (100, y)) for y in range(0, 150, 28)]          # 6 basamak, 28 cm aralık
    leaf = [((500, 0), (590, 0))]                                     # tek kapı kanadı
    out = _ladder_filter(steps + leaf, dmin=15, dmax=100)
    assert out == leaf


def _two_label_dxf(tmp_path, second_name):
    """Tek kapalı dikdörtgen (600x300), içinde iki etiket; ikinci etiketin adı parametre."""
    import ezdxf
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for lyr in ("YAZI", "duv"):
        doc.layers.add(lyr)
    msp.add_lwpolyline([(0, 0), (600, 0), (600, 300), (0, 300)], close=True, dxfattribs={"layer": "duv"})
    msp.add_lwpolyline([(-12, -12), (612, -12), (612, 312), (-12, 312)], close=True, dxfattribs={"layer": "duv"})
    msp.add_mtext("Salon", dxfattribs={"layer": "YAZI", "insert": (150, 150)})
    msp.add_mtext(second_name, dxfattribs={"layer": "YAZI", "insert": (450, 150)})
    p = tmp_path / f"two_{second_name}.dxf"; doc.saveas(p); return str(p)


def test_alias_merge_two_labels_one_space(tmp_path):
    from core.perception.parse import parse_dxf
    from core.perception.geometry import reconstruct
    path = _two_label_dxf(tmp_path, "Mutfak")
    b = parse_dxf(path, target_floor=0, gap=2000)
    b = reconstruct(b, path, res=3.0, seal=18, margin=300, units_per_meter=100)
    rooms = b.floors[0].rooms
    assert len(rooms) == 1 and rooms[0].geometry_ok
    assert rooms[0].aliases == ["Mutfak"] and len(rooms[0].alias_xy) == 1
    from shapely.geometry import Polygon
    assert Polygon(rooms[0].polygon).area > 0.8 * 600 * 300


def test_stair_label_not_merged(tmp_path):
    from core.perception.parse import parse_dxf
    from core.perception.geometry import reconstruct
    path = _two_label_dxf(tmp_path, "Merdiven")
    b = parse_dxf(path, target_floor=0, gap=2000)
    b = reconstruct(b, path, res=3.0, seal=18, margin=300, units_per_meter=100)
    rooms = b.floors[0].rooms
    assert len(rooms) == 2 and all(r.geometry_ok for r in rooms) and all(not r.aliases for r in rooms)


def test_walls_and_doors_inside_big_block(tmp_path):
    """Kat planı BLOK olarak yerleştirilmiş: duvar çifti ve kapı yayı blok içinde."""
    import ezdxf
    from core.perception.geometry import _wall_segments, _swing_dirs
    doc = ezdxf.new("R2010")
    blk = doc.blocks.new("KAT_PLANI")
    blk.add_line((0, 0), (800, 0)); blk.add_line((0, 15), (800, 15))          # 8 m duvar çifti (15 cm)
    blk.add_line((0, 0), (0, 500)); blk.add_line((15, 0), (15, 500))
    blk.add_arc((400, 15), 85, 0, 90)                                           # kapı yayı
    msp = doc.modelspace(); msp.add_blockref("KAT_PLANI", (1000, 1000))
    p = tmp_path / "blok.dxf"; doc.saveas(p); doc2 = ezdxf.readfile(str(p)); msp2 = doc2.modelspace()
    bbox = (900, 900, 2000, 1700)
    walls = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18, big_blocks=True)
    assert len(walls) == 4
    sw = _swing_dirs(msp2, bbox, 55, 130, big_blocks=True)
    assert len(sw) == 1 and abs(sw[0][0][0] - 1400) < 1e-6 and abs(sw[0][0][1] - 1015) < 1e-6


def test_label_frame_not_a_wall(tmp_path):
    """Etiketi saran 120x40 cm kapalı çerçeve duvar çifti sayılmamalı."""
    import ezdxf
    from core.perception.geometry import _wall_segments
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    msp.add_lwpolyline([(100, 100), (220, 100), (220, 140), (100, 140)], close=True, dxfattribs={"layer": "ZONE"})
    msp.add_line((0, 0), (800, 0)); msp.add_line((0, 15), (800, 15))          # gerçek duvar
    p = tmp_path / "frame.dxf"; doc.saveas(p); msp2 = ezdxf.readfile(str(p)).modelspace()
    bbox = (-50, -50, 900, 300)
    w_all = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18)
    w_lab = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18, label_pts=[(160, 120)])
    assert len(w_all) == 4 and len(w_lab) == 2


def test_outside_label_does_not_flood_background(tmp_path):
    """Bina dışındaki etiket (ör. korkuluk notu) raster kenarına akar → oda olmamalı."""
    import ezdxf
    from core.perception.parse import parse_dxf
    from core.perception.geometry import reconstruct
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for lyr in ("YAZI", "duv"):
        doc.layers.add(lyr)
    msp.add_lwpolyline([(0, 0), (400, 0), (400, 300), (0, 300)], close=True, dxfattribs={"layer": "duv"})
    msp.add_lwpolyline([(-12, -12), (412, -12), (412, 312), (-12, 312)], close=True, dxfattribs={"layer": "duv"})
    msp.add_mtext("Salon", dxfattribs={"layer": "YAZI", "insert": (200, 150)})
    msp.add_mtext("Balkon", dxfattribs={"layer": "YAZI", "insert": (200, 420)})   # dışarıda, duvarsız
    msp.add_mtext("Hol", dxfattribs={"layer": "YAZI", "insert": (200, 450)})      # dışarıda
    p = tmp_path / "out.dxf"; doc.saveas(p)
    b = parse_dxf(str(p), target_floor=0, gap=2000)
    b = reconstruct(b, str(p), res=3.0, seal=18, margin=300, units_per_meter=100)
    by = {r.raw_name: r for r in b.floors[0].rooms}
    assert by["Salon"].geometry_ok and by["Salon"].polygon
    assert not by["Balkon"].geometry_ok and by["Balkon"].polygon is None

