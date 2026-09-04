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


def test_wall_signals():
    from core.perception.signals.geometry import parallel_pair, thickness_mode
    from core.perception.signals.layer import layer_class_vote
    from core.perception.signals.topology import graph_connectivity
    from core.perception.names import WALL_SCAN_CLASSES
    assert parallel_pair(True) == 1.0
    assert thickness_mode(0.21, [0.205, 0.105], 0.02) == 1.0 and thickness_mode(0.30, [0.205], 0.02) == 0.0
    assert thickness_mode(None, [0.2], 0.02) is None and thickness_mode(0.2, [], 0.02) is None
    nm = NameMap(classes={"DUVAR": (LayerClass.wall, 0.6, "keyword"), "YAZI": (LayerClass.text, 0.6, "keyword"),
                          "0": (LayerClass.unknown, 0.0, "none")})
    assert layer_class_vote("DUVAR", WALL_SCAN_CLASSES, nm) == 1.0
    assert layer_class_vote("YAZI", WALL_SCAN_CLASSES, nm) == 0.0
    assert layer_class_vote("0", WALL_SCAN_CLASSES, nm) is None and layer_class_vote("X", WALL_SCAN_CLASSES, nm) is None
    assert graph_connectivity(((0, 0), (1, 1))) is None


def test_thickness_modes_histogram():
    from core.perception.calibration import thickness_modes
    th = [20.0] * 10 + [21.0] * 5 + [10.5] * 6 + [33.0] * 1     # cm; upm 100
    modes = thickness_modes(th, 100.0)
    assert any(abs(m - 0.205) < 0.011 for m in modes) and any(abs(m - 0.105) < 0.011 for m in modes)
    assert not any(abs(m - 0.335) < 0.011 for m in modes)         # tek örnek: pay eşiği altında
