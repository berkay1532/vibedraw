# tests/test_triage.py
import ezdxf

from core.perception.triage import (
    FileProfile,
    profile_dxf,
    layer_fingerprint,
    group_families,
    render_report,
    scan_files,
    room_hits,
)


def test_room_hits_turkish_casefold():
    hits = room_hits(["SALON", "Yatak Odası", "GİRİŞ", "A: 14.12m²", "Ölçek 1/50"])
    assert hits["salon"] == 1
    assert hits["yatak"] == 1
    assert hits["giriş"] == 1
    assert sum(hits.values()) == 3


def test_profile_dxf_detects_rooms_and_layers(synthetic_dxf):
    p = profile_dxf(synthetic_dxf)
    assert p.ok
    assert p.n_room_texts >= 3
    assert "salon" in p.room_hits
    assert "YAZI" in p.layers
    assert len(p.fingerprint) == 8
    assert p.n_entities > 0
    assert p.verdict == "ZAYIF"  # metin var ama çizgi geometrisi yok


def test_profile_plan_dxf_is_candidate(tmp_path):
    """3 oda etiketi + 20'den fazla duvar çizgisi olan plan ADAY sayılmalı."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for i in range(25):
        msp.add_line((i * 10, 0), (i * 10, 50), dxfattribs={"layer": "DUVAR"})
    for name, x in (("Salon", 10), ("Mutfak", 60), ("Banyo", 110)):
        msp.add_text(name, dxfattribs={"layer": "MAHAL", "insert": (x, 25)})
    path = tmp_path / "plan.dxf"
    doc.saveas(path)
    p = profile_dxf(str(path))
    assert p.ok
    assert p.n_lines == 25
    assert p.verdict == "ADAY"


def test_profile_bad_file(tmp_path):
    bad = tmp_path / "bad.dxf"
    bad.write_text("bu bir dxf değil")
    p = profile_dxf(str(bad))
    assert not p.ok
    assert p.verdict == "HATA"
    assert p.error


def test_layer_fingerprint_stable_and_case_insensitive():
    a = layer_fingerprint(["A-WALL", "A-DOOR", "0"])
    b = layer_fingerprint(["a-door", "0", "A-Wall"])
    c = layer_fingerprint(["Layer1", "Layer2"])
    assert a == b
    assert a != c


def _fake(name, layers):
    p = FileProfile(path=name, ok=True)
    p.layers = sorted(layers)
    p.fingerprint = layer_fingerprint(layers)
    return p


def test_group_families_by_layer_similarity():
    a = _fake("a.dxf", {"A-WALL", "A-DOOR", "A-WIND", "0"})
    b = _fake("b.dxf", {"A-WALL", "A-DOOR", "A-TEXT", "0"})
    c = _fake("c.dxf", {"duvar", "kapi", "yazi"})
    fams = group_families([a, b, c], threshold=0.5)
    assert len(fams) == 2
    names = [sorted(p.path for p in f) for f in fams]
    assert ["a.dxf", "b.dxf"] in names
    assert ["c.dxf"] in names


def test_scan_files_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "x.DXF").write_text("")
    (tmp_path / "sub" / "y.dwg").write_text("")
    (tmp_path / "z.txt").write_text("")
    found = scan_files(str(tmp_path))
    names = sorted(f.name for f in found)
    assert names == ["x.DXF", "y.dwg"]


def test_render_report_mentions_files_and_families(synthetic_dxf, synthetic_walled_dxf):
    ps = [profile_dxf(synthetic_dxf), profile_dxf(synthetic_walled_dxf)]
    fams = group_families(ps)
    md = render_report(ps, fams, skipped_dwg=["foo.dwg"])
    assert "synthetic.dxf" in md
    assert "walled.dxf" in md
    assert "Aile" in md
    assert "foo.dwg" in md


def test_find_converter_shape():
    from core.perception.triage import find_converter
    c = find_converter()
    assert c is None or (c[0] in ("oda", "libredwg") and c[1])


def test_convert_dwg_files_reports_failures(tmp_path):
    """Bozuk DWG dönüştürülemez → failed listesinde; gerçek dönüştürücü yoksa test atlanır."""
    import pytest
    from core.perception.triage import find_converter, convert_dwg_files
    c = find_converter()
    if not c or c[0] != "libredwg":
        pytest.skip("dwg2dxf yok")
    bad = tmp_path / "bozuk.dwg"
    bad.write_bytes(b"not a dwg")
    failed = convert_dwg_files([bad], str(tmp_path / "_dxf"), c[1])
    assert failed == [str(bad)]


def test_profile_reads_room_names_from_block_attribs(tmp_path):
    """Revit-tarzı dosyalar: oda adı INSERT üzerindeki ATTRIB'de (tag=MAHAL)."""
    doc = ezdxf.new("R2010")
    blk = doc.blocks.new("MAHAL_ETIKET")
    blk.add_attdef("MAHAL", (0, 0), dxfattribs={"height": 2.5})
    msp = doc.modelspace()
    for i in range(25):
        msp.add_line((i * 10, 0), (i * 10, 50), dxfattribs={"layer": "A_WALL"})
    for name, x in (("SALON", 10), ("MUTFAK", 60), ("BANYO", 110)):
        ref = msp.add_blockref("MAHAL_ETIKET", (x, 25))
        ref.add_auto_attribs({"MAHAL": name})
    path = tmp_path / "attrib.dxf"
    doc.saveas(path)
    p = profile_dxf(str(path))
    assert p.n_room_texts == 3
    assert p.verdict == "ADAY"


def test_electrical_detection_and_pairs(tmp_path):
    from core.perception.triage import electrical_hits, pair_candidates, ELECTRICAL_MIN
    hits = electrical_hits(["linye", "linyee", "DUVAR"], ["_anahtardinamik", "buat", "etanj", "KOT"])
    assert len(hits) >= ELECTRICAL_MIN and "katman:linye" in hits and "blok:buat" in hits
    assert electrical_hits(["ELE", "DUVAR"], ["KOT"]) == []                     # "ELE" ipucu değil; mimari altlık kalır
    e = FileProfile(path="/x/2510-9_ELK.dxf", ok=True, verdict="ELEKTRİK")
    a = FileProfile(path="/x/2510_912.05.2023.dxf", ok=True, verdict="ADAY")
    b = FileProfile(path="/x/290-10_KOLDERE.dxf", ok=True, verdict="ADAY")
    assert pair_candidates([e, a, b]) == [("2510-9_ELK.dxf", ["2510_912.05.2023.dxf"])]
