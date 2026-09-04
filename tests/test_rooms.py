# tests/test_rooms.py
import ezdxf
import pytest


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
    from core.perception.pipeline import reconstruct
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
    from core.perception.pipeline import reconstruct
    path = _two_label_dxf(tmp_path, "Merdiven")
    b = parse_dxf(path, target_floor=0, gap=2000)
    b = reconstruct(b, path, res=3.0, seal=18, margin=300, units_per_meter=100)
    rooms = b.floors[0].rooms
    assert len(rooms) == 2 and all(r.geometry_ok for r in rooms) and all(not r.aliases for r in rooms)


def test_outside_label_does_not_flood_background(tmp_path):
    """Bina dışındaki etiket (ör. korkuluk notu) raster kenarına akar → oda olmamalı."""
    import ezdxf
    from core.perception.parse import parse_dxf
    from core.perception.pipeline import reconstruct
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
