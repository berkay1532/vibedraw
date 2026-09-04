# tests/test_signals.py — saf sinyal fonksiyonları
from core.perception.signals.block import block_class
from core.perception.signals.geometry import arc_signature, wall_gap
from core.perception.signals.layer import layer_class, layer_raw
from core.perception.signals.topology import room_boundary
from core.perception.names import LayerClass, NameMap


def test_geometry_signals():
    walls = [((0.0, 0.0), (100.0, 0.0))]
    assert wall_gap((50.0, 10.0), walls, 25.0) == 1.0
    assert wall_gap((50.0, 40.0), walls, 25.0) == 0.0
    assert wall_gap((50.0, 40.0), [], 25.0) is None                # duvar yok → değerlendirilemez
    assert arc_signature(True) == 1.0 and arc_signature(False) == 0.0


def test_block_layer_topology_signals():
    assert block_class(True) == 1.0 and layer_raw(False) == 0.0
    nm = NameMap(classes={"KAPI": (LayerClass.door, 0.6, "keyword")})
    assert layer_class("KAPI", {LayerClass.door}, nm) == 0.6 and layer_class("X", {LayerClass.door}, nm) == 0.0
    from shapely.geometry import Polygon
    polys = [(None, Polygon([(0, 0), (100, 0), (100, 100), (0, 100)]))]
    assert room_boundary((100.0, 50.0), polys, 15.0) == 1.0
    assert room_boundary((150.0, 50.0), polys, 15.0) == 0.0
    assert room_boundary((150.0, 50.0), polys, 15.0, enabled=False) is None and room_boundary((1, 1), [], 15.0) is None
