# tests/test_scoring.py — weights.yaml Adım 2 güven tablosunu birebir üretir; kapılar eler
from core.perception.ir_compat import DOOR_CONF
from core.perception.scoring import score


def test_door_weights_reproduce_confidence_table():
    cases = {"block": {"block_class": 1}, "arc": {"arc_signature": 1}, "block+arc": {"block_class": 1, "arc_signature": 1},
             "layer_raw": {"layer_class": 1}, "vlm": {"vlm": 1}}
    for src, sig in cases.items():
        conf, ev = score("door", {**sig, "wall_gap": None, "room_boundary": None}, src)
        assert conf == DOOR_CONF[src], (src, conf)
        assert ev.source == src and all(k in ev.signals for k in sig)


def test_gates_drop_candidate_and_none_passes():
    assert score("door", {"block_class": 1, "wall_gap": 0.0}) is None
    assert score("door", {"block_class": 1, "room_boundary": 0.0}) is None
    assert score("door", {"block_class": 1, "wall_gap": None, "room_boundary": 1.0})[0] == 0.7
    assert score("door", {"wall_gap": 1.0}) is None                       # pozitif sinyal yok
