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


def test_wall_weights_reproduce_table_and_conflict():
    from core.perception.ir_compat import WALL_CONF
    from core.perception.scoring import is_conflicting
    pair = {"parallel_pair": 1.0, "layer_class": None, "thickness_mode": 0.0, "graph_connectivity": None}
    both = {**pair, "layer_class": 1.0}
    assert score("wall", pair, "pair")[0] == WALL_CONF["pair"]
    assert score("wall", both, "pair+layer")[0] == WALL_CONF["pair+layer"]
    assert not is_conflicting("wall", pair)                       # None ve ağırlığı 0 olan sinyal sayılmaz
    assert is_conflicting("wall", {**pair, "layer_class": 0.0})   # geometri duvar der, katman yazı der
    assert score("wall", {**pair, "layer_class": 0.0}, "pair")[1].note == "conflicting_signal"
    assert is_conflicting("door", {"block_class": 1.0, "arc_signature": 0.0})
    assert not is_conflicting("door", {"block_class": 1.0, "arc_signature": 1.0, "wall_gap": 0.0})  # kapı sinyali ağırlıksız
