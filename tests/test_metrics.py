# tests/test_metrics.py
from core.perception.metrics import (
    match_rooms, match_points, evaluate_floor, room_iou,
)

SQ = lambda x, y, s: [[x, y], [x + s, y], [x + s, y + s], [x, y + s]]


def test_room_iou_and_matching():
    gt = [{"id": "a", "name": "Salon", "polygon": SQ(0, 0, 100)},
          {"id": "b", "name": "Mutfak", "polygon": SQ(200, 0, 100)}]
    pred = [{"raw_name": "SALON", "polygon": SQ(5, 5, 100)},   # ~%82 IoU
            {"raw_name": "Banyo", "polygon": SQ(500, 500, 50)}]  # sahte
    assert 0.8 < room_iou(gt[0]["polygon"], pred[0]["polygon"]) < 0.85
    m = match_rooms(gt, pred, iou_thr=0.5)
    assert m.tp == 1 and m.fp == 1 and m.fn == 1
    assert abs(m.f1 - 0.5) < 1e-9
    assert m.name_acc == 1.0          # SALON ~ Salon (casefold)


def test_point_matching_with_tolerance():
    gt = [{"hinge": [0, 0], "connects": ["a", "b"]}, {"hinge": [100, 0], "connects": ["b", "c"]}]
    pred = [{"xy": [3, 4], "room_name": "b"}, {"xy": [500, 500], "room_name": "x"}]
    m = match_points(gt, pred, gt_key="hinge", pred_key="xy", tol=10.0)
    assert m.tp == 1 and m.fp == 1 and m.fn == 1
    assert abs(m.mean_err - 5.0) < 1e-9


def test_evaluate_floor_end_to_end():
    gt = {"units_per_meter": 100.0, "floor": {
        "rooms": [{"id": "a", "name": "Salon", "polygon": SQ(0, 0, 400)},
                  {"id": "b", "name": "Hol", "polygon": SQ(400, 0, 200)}],
        "doors": [{"hinge": [400, 100], "width": 90, "connects": ["a", "b"]}],
        "windows": [{"a": [0, 0], "b": [200, 0]}]}}
    pred = {"rooms": [{"raw_name": "SALON", "polygon": SQ(2, 2, 400)},
                      {"raw_name": "HOL", "polygon": SQ(402, 0, 200)}],
            "doors": [{"xy": [405, 105], "room_name": "HOL"}],
            "windows": [[[0, 0], [190, 0]]]}
    r = evaluate_floor(gt, pred)
    assert r["rooms"]["tp"] == 2 and r["rooms"]["f1"] == 1.0
    assert r["doors"]["tp"] == 1 and r["doors"]["connect_acc"] == 1.0
    assert r["doors"]["mean_err_m"] < 0.1
    assert r["windows"]["tp"] == 1


def test_name_fold_ignores_area_suffix():
    from core.perception.metrics import _tr_fold
    assert _tr_fold("HOL\nA:6.60 M²") == _tr_fold("HOL") == "hol"
    assert _tr_fold("Yatak Odası  A: 11.30 m2") == "yatak odası"
