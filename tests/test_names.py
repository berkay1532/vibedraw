# tests/test_names.py — katman sınıflandırma: profil, sözlük, aile eşleştirme
import textwrap

from core.perception.names import (BARRIER_CLASSES, WALL_EXCLUDE_CLASSES, LayerClass, SourceProfile,
                                   classify_layers, keyword_class, load_profiles, match_profile)


def test_keyword_class_generic_words():
    assert keyword_class("DUVAR")[0] is LayerClass.wall
    assert keyword_class("A_WALL_HID")[0] is LayerClass.wall
    assert keyword_class("kapi")[0] is LayerClass.door
    assert keyword_class("PENCERE")[0] is LayerClass.window
    assert keyword_class("YAZI")[0] is LayerClass.text
    assert keyword_class("OLCU")[0] is LayerClass.dim
    assert keyword_class("AKS")[0] is LayerClass.grid
    assert keyword_class("merdiven")[0] is LayerClass.stair
    assert keyword_class("Defpoints")[0] is LayerClass.ignore
    assert keyword_class("12mm levha")[0] is LayerClass.unknown


def test_keyword_annotation_beats_structural_and_door_window_conflict():
    assert keyword_class("KAPIPENCEREYAZISI")[0] is LayerClass.text      # yazı kelimesi yapısalı yener
    assert keyword_class("CAMTARAMA")[0] is LayerClass.hatch
    assert keyword_class("MERDİVEN YAZI")[0] is LayerClass.text
    c, conf = keyword_class("KAPI___PENCERE")
    assert c is LayerClass.window and conf < 0.6                          # kapı+pencere → window, düşük güven


def _profile(tmp_path):
    (tmp_path / "famXX.yaml").write_text(textwrap.dedent("""
        family_id: famXX
        label: test
        fingerprints: [deadbeef]
        layers:
          OFIS-DUV: wall
          OFIS-KAP: door
          ince: furniture
        layer_union: [OFIS-DUV, OFIS-KAP, ince, 0, YAZI, OLCU]
    """), encoding="utf-8")
    return load_profiles(tmp_path)


def test_match_profile_three_tiers(tmp_path):
    profs = _profile(tmp_path)
    assert match_profile(["x"], profs, fingerprint="deadbeef")[1] == "fingerprint"
    assert match_profile(["OFIS-DUV", "OFIS-KAP", "Z"], profs)[1] == "structural"        # 2/3 kayıtlı ad
    assert match_profile(["OFIS-DUV", "0", "YAZI", "OLCU", "Q"], profs)[1] == "jaccard"   # 4/6 ≥ 0.5
    assert match_profile(["A", "B", "C"], profs)[0] is None


def test_classify_profile_over_keyword(tmp_path):
    profs = _profile(tmp_path)
    prof, how, sc = match_profile(["OFIS-DUV", "OFIS-KAP", "ince", "DUVAR"], profs)
    nm = classify_layers(["OFIS-DUV", "ince", "DUVAR", "0"], prof, how, sc)
    assert nm.cls("OFIS-DUV") is LayerClass.wall and nm.classes["OFIS-DUV"][2] == "profile"
    assert nm.cls("ince") is LayerClass.furniture
    assert nm.cls("DUVAR") is LayerClass.wall and nm.classes["DUVAR"][2] == "keyword"
    assert nm.cls("0") is LayerClass.unknown and nm.family_id == "famXX"
    assert nm.has("OFIS-DUV", BARRIER_CLASSES) and not nm.has("ince", BARRIER_CLASSES)
    assert not nm.has("ince", WALL_EXCLUDE_CLASSES)      # mobilya duvar taramasından çıkarılmaz (eski davranış)


def test_repo_profiles_load_and_have_classes():
    profs = load_profiles()
    assert profs, "source_profiles/ boş"
    for p in profs:
        assert p.family_id and p.fingerprints and p.layers
        assert all(isinstance(v, LayerClass) for v in p.layers.values())


def test_has_min_conf_gates_keyword_classes(tmp_path):
    from core.perception.names import GATED_MIN_CONF, WALL_EXCLUDE_CLASSES
    profs = _profile(tmp_path)
    prof, how, sc = match_profile(["OFIS-KAP", "OFIS-DUV"], profs)
    nm = classify_layers(["OFIS-KAP", "YAZI"], prof, how, sc)
    assert nm.has("YAZI", WALL_EXCLUDE_CLASSES)                          # sözlük: ekleyici tüketiciler için yeter
    assert not nm.has("YAZI", WALL_EXCLUDE_CLASSES, GATED_MIN_CONF)      # hariç tutma profil güveni ister
    assert nm.has("OFIS-KAP", {LayerClass.door}, GATED_MIN_CONF)


def test_union_side_file_used_for_jaccard(tmp_path):
    (tmp_path / "famYY.yaml").write_text("family_id: famYY\nfingerprints: [ab]\nlayers:\n  X-DUV: wall\n", encoding="utf-8")
    (tmp_path / "unions").mkdir(); (tmp_path / "unions" / "famYY.json").write_text('["X-DUV", "A", "B", "C"]', encoding="utf-8")
    profs = load_profiles(tmp_path)
    assert profs[0].layer_union == ["X-DUV", "A", "B", "C"]
    assert match_profile(["A", "B", "C", "Q"], profs)[1] == "jaccard"      # 3/5 ≥ 0.5, yapısal ad yok


def test_english_uppercase_layers_classified():
    """Türkçe katlama I→ı: 'WINDOW'→'wındow' sözlüğe uymuyordu (2026-09-04). İki katlama birden denenir."""
    assert keyword_class("WINDOW")[0] is LayerClass.window and keyword_class("WIN")[0] is LayerClass.unknown
    assert keyword_class("DIM")[0] is LayerClass.dim and keyword_class("PUB_DIM")[0] is LayerClass.dim
    assert keyword_class("STAIR")[0] is LayerClass.stair and keyword_class("AXIS")[0] is LayerClass.grid
    assert keyword_class("A_STAIR_STR")[0] is LayerClass.stair
