# tests/test_graph_rooms.py — Adım 9: duvar grafı (walls.build_wall_graph) ve polygonize odalar (rooms.graph_faces)
import math

from shapely.geometry import Polygon

from core.perception.config import T
from core.perception.ir_v1 import BuildingIR, Room
from core.perception.rooms import graph_faces, reconcile_rooms
from core.perception.walls import WallGraph, build_wall_graph, centerlines, passage_closures

UPM = 100.0


def _double_rect(x0, y0, x1, y1, t):
    """Dış+iç yüzlerden kapalı dikdörtgen duvar (kalınlık t, dışa doğru)."""
    outer = [((x0 - t, y0 - t), (x1 + t, y0 - t)), ((x1 + t, y0 - t), (x1 + t, y1 + t)),
             ((x1 + t, y1 + t), (x0 - t, y1 + t)), ((x0 - t, y1 + t), (x0 - t, y0 - t))]
    inner = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return outer + inner


def _plan(door_gap=True):
    """600×400 cm plan, x=300'de 10 cm bölme; y 100..190 kapı boşluğu."""
    t = 10.0
    segs = _double_rect(0, 0, 600, 400, t)
    if door_gap:
        for x in (295, 305):
            segs += [((x, 0), (x, 100)), ((x, 190), (x, 400))]
    else:
        for x in (295, 305):
            segs += [((x, 0), (x, 400))]
    return segs, t


def test_centerlines_from_pair():
    cl = centerlines([((0, 0), (100, 0)), ((0, 10), (100, 10))], tmin=5, tmax=20, min_overlap=18)
    assert len(cl) == 1
    (a, b, thick) = cl[0]
    assert abs(a[1] - 5.0) < 1e-6 and abs(b[1] - 5.0) < 1e-6 and abs(thick - 10.0) < 1e-6


def test_graph_faces_two_rooms_with_door_closure():
    segs, t = _plan(door_gap=True)
    G = T("graph")
    # kapatma olmadan: bölmedeki boşluk iki odayı birleştirir → tek yüz
    wg0 = build_wall_graph(segs, t, UPM, G)
    faces0 = graph_faces(wg0, UPM, G, seal_units=4.0)
    assert len(faces0) == 1
    # kapı kanadı (menteşe (300,100) → uç (300,190)) → kapatma → iki yüz
    leaves = [((300.0, 100.0), (300.0, 190.0))]
    wg = build_wall_graph(segs, t, UPM, G, door_leaves=leaves)
    assert wg.stats["door_closures"] == 1
    faces = graph_faces(wg, UPM, G, seal_units=4.0)
    assert len(faces) == 2
    areas = sorted(f.area / UPM ** 2 for f, _ in faces)
    assert all(11.0 < a < 12.6 for a in areas)              # 295×400 / 1e4 = 11.8 m² (iç yüzler)


def test_passage_closure_closes_gap_without_door():
    segs, t = _plan(door_gap=True)
    G = T("graph")
    wg = build_wall_graph(segs, t, UPM, G)
    pc = passage_closures(wg.face_edges, G, UPM)
    assert len(pc) == 2                                       # 90 cm boşluk, iki yüzde de doğrultudaş uçlar
    wg.closures += pc
    assert len(graph_faces(wg, UPM, G, seal_units=4.0)) == 2


def test_thin_and_small_faces_dropped():
    G = T("graph")
    # 30 cm genişliğinde 5 m koridor yüzü (ince) + 0.5 m² kutu (küçük) + 3×3 m oda
    edges = [((0, 0), (300, 0)), ((300, 0), (300, 300)), ((300, 300), (0, 300)), ((0, 300), (0, 0)),
             ((400, 0), (430, 0)), ((430, 0), (430, 500)), ((430, 500), (400, 500)), ((400, 500), (400, 0)),
             ((600, 0), (670, 0)), ((670, 0), (670, 70)), ((670, 70), (600, 70)), ((600, 70), (600, 0))]
    wg = WallGraph(edges=edges, thickness=0.0)
    faces = graph_faces(wg, UPM, G, seal_units=2.0)
    assert len(faces) == 1 and abs(faces[0][0].area / UPM ** 2 - 9.0) < 0.1   # yuvarlak köşe payı


def test_reconcile_matched_and_new():
    G = T("graph")
    room = Room(raw_name="SALON", label_xy=(150, 200), polygon=[(0, 0), (300, 0), (300, 400), (0, 400)], geometry_ok=True)
    faces = [(Polygon([(2, 2), (298, 2), (298, 398), (2, 398)]), {"stair": False}),
             (Polygon([(700, 0), (900, 0), (900, 200), (700, 200)]), {"stair": True})]
    matched, unmatched, new = reconcile_rooms([room], faces, G["iou_match"], G["candidate_max_overlap"])
    assert id(room) in matched and matched[id(room)][0] == 0 and matched[id(room)][1] > 0.9
    assert unmatched == [] and new == [1]


def test_pipeline_single_line_walls_unchanged(synthetic_walled_dxf):
    """Tek çizgili duvarlar (çift yok) → graf boş; flood-fill sonucu değişmez, çökme yok."""
    from core.perception.pipeline import label_floors, run_floor
    path = synthetic_walled_dxf
    b = BuildingIR(floors=[label_floors(path, gap=2000)[0]], source_path=path)
    b = run_floor(b, path, res=1.0, seal=2, margin=10, units_per_meter=None)
    fl = b.floors[0]
    assert {r.raw_name for r in fl.rooms} == {"Salon", "Mutfak"}
    assert getattr(fl, "graph_faces", []) == []


def test_merge_split_faces_thin_line_inside_room():
    """İnce çizgiyle (duvar boşluğu yok) bölünmüş iki yüz birleşir; kalın duvarla ya da iki etiketle ayrılanlar birleşmez."""
    from shapely.geometry import LineString
    from core.perception.rooms import merge_split_faces
    G = T("graph")
    room = Room(raw_name="HOL", label_xy=(150, 200), polygon=[(0, 0), (300, 0), (300, 400), (0, 400)], geometry_ok=True)
    thin = [(Polygon([(0, 0), (300, 0), (300, 200), (0, 200)]), {"stair": False}),
            (Polygon([(0, 200), (300, 200), (300, 400), (0, 400)]), {"stair": False})]
    kw = dict(gap_max=G["merge_gap_max_m"] * UPM, min_shared=G["merge_min_shared_m"] * UPM)
    out, n = merge_split_faces(thin, [room], [], G["merge_thin_cavity_max_frac"], G["merge_eps_m"] * UPM, G["merge_max_labels"], **kw)
    assert n == 1 and len(out) == 1 and abs(out[0][0].area - 300 * 400) < 300 * 400 * 0.01
    # aynı bölme, ama ortak sınır bir duvar boşluğunun (merkez hattı × 20 birim) içinde → birleşmez
    cav = [LineString([(0, 200), (300, 200)]).buffer(10, cap_style=2)]
    out2, n2 = merge_split_faces(thin, [room], cav, G["merge_thin_cavity_max_frac"], G["merge_eps_m"] * UPM, G["merge_max_labels"], **kw)
    assert n2 == 0 and len(out2) == 2
    # iki etiketli bileşen (salon + mutfak ince çizgiyle ayrı) → birleşmez
    room2 = Room(raw_name="MUTFAK", label_xy=(150, 300), polygon=[(0, 200), (300, 200), (300, 400), (0, 400)], geometry_ok=True)
    room.label_xy = (150, 100)
    out3, n3 = merge_split_faces(thin, [room, room2], [], G["merge_thin_cavity_max_frac"], G["merge_eps_m"] * UPM, G["merge_max_labels"], **kw)
    assert n3 == 0 and len(out3) == 2
    # 25 birimlik kiriş bandıyla ayrık iki yüz (polygonize bandı yüz yapmaz) → aralık ≤ gap_max, boşluk yok → birleşir, şerit dolar
    apart = [(Polygon([(0, 0), (300, 0), (300, 190), (0, 190)]), {"stair": False}),
             (Polygon([(0, 215), (300, 215), (300, 400), (0, 400)]), {"stair": False})]
    out4, n4 = merge_split_faces(apart, [room], [], G["merge_thin_cavity_max_frac"], G["merge_eps_m"] * UPM, G["merge_max_labels"], **kw)
    assert n4 == 1 and abs(out4[0][0].area - 300 * 400) < 300 * 400 * 0.02


def test_candidate_overlap_gate():
    """Mevcut flood odasıyla > candidate_max_overlap örtüşen yüz aday olmaz."""
    G = T("graph")
    room = Room(raw_name="SALON", label_xy=(150, 200), polygon=[(0, 0), (300, 0), (300, 400), (0, 400)], geometry_ok=True)
    faces = [(Polygon([(200, 0), (500, 0), (500, 400), (200, 400)]), {"stair": False}),    # %33 oda içinde
             (Polygon([(250, 0), (550, 0), (550, 400), (250, 400)]), {"stair": False})]    # %17 oda içinde
    _, _, new = reconcile_rooms([room], faces, G["iou_match"], G["candidate_max_overlap"])
    assert new == [1]


def test_graph_edge_classes_and_railing():
    """hatch/furniture/unknown katman çizgisi kenar üretmez; korkuluk (railing) üretir; pencere kapı gibi mühürlenir."""
    from core.perception.names import GRAPH_EDGE_CLASSES, LayerClass, NameMap, keyword_class
    from core.perception.walls import barrier_segments, build_wall_graph
    assert keyword_class("korkuluk")[0] is LayerClass.railing and keyword_class("Railing-1")[0] is LayerClass.railing
    assert LayerClass.railing in GRAPH_EDGE_CLASSES and LayerClass.hatch not in GRAPH_EDGE_CLASSES
    assert LayerClass.window not in GRAPH_EDGE_CLASSES and LayerClass.unknown not in GRAPH_EDGE_CLASSES
    segs, t = _plan(door_gap=False)
    G = T("graph")
    wg = build_wall_graph(segs, t, UPM, G, windows=[((100, 0), (200, 0))], face_walls=[])
    assert wg.stats["window_closures"] == 1 and wg.stats["faces_in"] == 0 and len(wg.closures) == 1
