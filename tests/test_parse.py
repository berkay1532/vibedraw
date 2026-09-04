# tests/test_parse.py
from core.perception.parse import (
    extract_room_labels,
    is_area_text,
    parse_area,
    cluster_floors_2d,
)
from core.perception.binding import pair_names_with_areas


def test_extract_room_labels_includes_area_texts(synthetic_dxf):
    texts = extract_room_labels(synthetic_dxf)
    contents = [t.content for t in texts]
    assert "Salon" in contents
    assert any(c.startswith("A:") for c in contents)
    # her metnin konumu var
    assert all(isinstance(t.xy, tuple) and len(t.xy) == 2 for t in texts)


def test_is_area_text():
    assert is_area_text("A: 14.12m²") is True
    assert is_area_text("Salon") is False


def test_parse_area():
    assert parse_area("A: 14.12m²") == 14.12
    assert parse_area("A: 5m²") == 5.0


def test_pair_names_with_areas(synthetic_dxf):
    texts = extract_room_labels(synthetic_dxf)
    rooms = pair_names_with_areas(texts)
    by_name = {r.raw_name: r for r in rooms}
    assert "Salon" in by_name
    assert abs(by_name["Salon"].area_m2 - 14.12) < 1e-6
    # alan yazıları oda olarak sayılmamalı
    assert all(not r.raw_name.startswith("A:") for r in rooms)


def test_cluster_floors_2d_separates_by_gap(synthetic_dxf):
    rooms = pair_names_with_areas(extract_room_labels(synthetic_dxf))
    floors = cluster_floors_2d(rooms, gap=200.0)
    assert len(floors) == 2
    # ilk küme (küçük x) Salon/Mutfak/Banyo içerir
    assert {r.raw_name for r in floors[0].rooms} == {"Salon", "Mutfak", "Banyo"}


def test_label_floors_helper_indexes_clusters(synthetic_dxf):
    from core.perception.pipeline import label_floors
    floors = label_floors(synthetic_dxf, gap=200.0)
    assert {r.raw_name for r in floors[1].rooms} == {"Yatak Odası", "Hol"}


def test_extract_room_labels_layer_independent_and_attribs(tmp_path):
    """Herhangi bir katmandaki TEXT/MTEXT + INSERT ATTRIB'lerinden oda etiketleri."""
    import ezdxf
    from core.perception.parse import extract_room_labels
    doc = ezdxf.new("R2010")
    blk = doc.blocks.new("TAG")
    blk.add_attdef("MAHAL", (0, 0))
    msp = doc.modelspace()
    msp.add_text("SALON", dxfattribs={"layer": "Layer 7", "insert": (10, 10)})
    msp.add_mtext("Yatak Odası", dxfattribs={"layer": "0", "insert": (50, 10)})
    msp.add_text("1/50", dxfattribs={"layer": "0", "insert": (90, 10)})       # gürültü
    msp.add_text("K1-90/220", dxfattribs={"layer": "0", "insert": (90, 20)})  # kapı kodu, gürültü
    ref = msp.add_blockref("TAG", (30, 40)); ref.add_auto_attribs({"MAHAL": "BANYO"})
    p = tmp_path / "labels.dxf"; doc.saveas(p)
    labels = extract_room_labels(str(p))
    names = sorted(t.content for t in labels)
    assert names == ["BANYO", "SALON", "Yatak Odası"]
    banyo = next(t for t in labels if t.content == "BANYO")
    assert banyo.xy == (30.0, 40.0)



def test_dedupe_labels_and_cluster_floors_2d():
    from core.perception.parse import dedupe_labels, cluster_floors_2d, YaziText
    from core.perception.binding import pair_names_with_areas
    labels = [YaziText("HALL", (-3000, -3000)), YaziText("HALL", (-2998, -2999)), YaziText("Hall", (-2999, -2998)),  # lejant tekrarı
              YaziText("Salon", (100, 100)), YaziText("Mutfak", (400, 100)), YaziText("Banyo", (100, 400)),
              YaziText("Salon", (100, 1500)), YaziText("Mutfak", (400, 1500))]  # üstteki kesit
    d = dedupe_labels(labels, tol=5)
    assert sum(1 for t in d if t.content.lower() == "hall") == 1
    floors = cluster_floors_2d(pair_names_with_areas(d), gap=500)
    sizes = sorted(len(f.rooms) for f in floors)
    assert sizes == [1, 2, 3]   # hall tek, kesit 2, plan 3 → x-only kümeleme bunları birleştirirdi


def test_non_room_sublabels_excluded():
    from core.perception.parse import looks_like_room_label
    assert looks_like_room_label("BANYO")
    assert not looks_like_room_label("ÇAMAŞIR MAK.YERİ")
    assert not looks_like_room_label("MUTFAK DOLABI")
    assert not looks_like_room_label("ZEMİN KAT PLANI 1/50")


def test_grid_likeness_and_plan_pick():
    from core.perception.parse import grid_likeness, pick_plan_floor, Room, Floor
    table = [Room(n, (x, y)) for y in (0, 300, 600, 900, 1200) for x, n in ((0, "ODA"), (500, "SALON"))]
    plan = [Room("Salon", (100, 120)), Room("Mutfak", (450, 90)), Room("Yatak", (130, 520)),
            Room("Banyo", (420, 470)), Room("Hol", (300, 300)), Room("WC", (600, 380))]
    assert grid_likeness(table, 30) >= 0.85
    assert grid_likeness(plan, 30) < 0.6
    fl = pick_plan_floor([Floor(0, table), Floor(1, plan)], upm=100)
    assert [r.raw_name for r in fl.rooms][0] == "Salon"   # 10 etiketli tablo değil, 6 etiketli plan


def test_room_label_rejects_cover_sheet_texts():
    from core.perception.parse import looks_like_room_label
    assert not looks_like_room_label("ODA SİCİL NO            :")
    assert not looks_like_room_label("SIĞINAK HESABI")          # 'sığınak' değil, hesap yazısı → 4 kelime altı ama...
    assert looks_like_room_label("ODA")
    assert looks_like_room_label("YATAK ODASI")
    assert looks_like_room_label("SALON+ MUTFAK")
    assert not looks_like_room_label("P1-90/140 ODA")            # rakam ağırlıklı kod


def test_label_with_area_suffix_split(tmp_path):
    import ezdxf
    from core.perception.parse import extract_room_labels
    from core.perception.binding import pair_names_with_areas
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    msp.add_mtext("SALON+ MUTFAK\nA:19.50 M²", dxfattribs={"insert": (10, 10)})
    msp.add_text("YATAK ODASI A: 11.30 M2", dxfattribs={"insert": (300, 10)})
    p = tmp_path / "a.dxf"; doc.saveas(p)
    L = extract_room_labels(str(p)); rooms = pair_names_with_areas(L)
    names = {r.raw_name: r.area_m2 for r in rooms}
    assert names == {"SALON+ MUTFAK": 19.5, "YATAK ODASI": 11.3}


def test_decode_dxf_unicode_escapes():
    from core.perception.parse import decode_dxf_text, looks_like_room_label, AREA_RE
    assert decode_dxf_text("\\U+00C7OCUK ODASI") == "ÇOCUK ODASI"
    assert decode_dxf_text("A:13.20 M\\U+00B2") == "A:13.20 M²"
    assert looks_like_room_label(decode_dxf_text("\\U+00C7OCUK ODASI"))
    assert AREA_RE.search(decode_dxf_text("MUTFAK\\PA:13.20 M\\U+00B2")).group(1) == "13.20"
