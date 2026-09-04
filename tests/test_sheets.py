# tests/test_sheets.py
import ezdxf

from core.sheets import analyze_sheet, segment_views


def _sheet(tmp_path):
    """İki görünüm: solda kat planı (oda etiketleri + kapı yayları + başlık), 8 m sağda
    kesit (başlık, etiket yok). Birim cm (upm=100)."""
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    # plan: 800x500 dış duvar, 3 oda etiketi, 3 kapı yayı, altında büyük başlık
    msp.add_lwpolyline([(0, 0), (800, 0), (800, 500), (0, 500)], close=True)
    for i in range(30):
        msp.add_line((i * 25, 0), (i * 25, 500))
    for name, x in (("SALON", 100), ("MUTFAK", 400), ("BANYO", 700)):
        msp.add_text(name, dxfattribs={"height": 15, "insert": (x, 250)})
    for x in (200, 500, 650):
        msp.add_arc((x, 0), 85, 0, 90)
    msp.add_text("ZEMİN KAT PLANI 1/50", dxfattribs={"height": 40, "insert": (300, -80)})
    msp.add_text("not: kiremit çatı", dxfattribs={"height": 10, "insert": (300, 520)})
    # kesit: 800 br sağda (boşluk 800 cm = 8 m)
    ox = 1700
    msp.add_lwpolyline([(ox, 0), (ox + 800, 0), (ox + 800, 600), (ox, 600)], close=True)
    for i in range(40):
        msp.add_line((ox + i * 20, 0), (ox + i * 20, 600))
    msp.add_text("A-A KESİTİ 1/50", dxfattribs={"height": 40, "insert": (ox + 300, -80)})
    p = tmp_path / "sheet.dxf"; doc.saveas(p)
    return str(p)


def test_segment_two_views(tmp_path):
    path = _sheet(tmp_path)
    msp = ezdxf.readfile(path).modelspace()
    views, ents = segment_views(msp, upm=100)
    assert len(views) == 2


def test_classify_plan_and_section(tmp_path):
    path = _sheet(tmp_path)
    msp = ezdxf.readfile(path).modelspace()
    vs = analyze_sheet(msp, upm=100)
    kinds = {v.kind: v for v in vs}
    assert set(kinds) == {"floor_plan", "section"}
    plan = kinds["floor_plan"]
    assert plan.floor_name == "ZEMİN KAT" and plan.scale == 50 and plan.n_room_labels == 3 and plan.n_door_arcs == 3
    assert plan.confidence >= 0.8
    assert kinds["section"].title.startswith("A-A KESİTİ") and kinds["section"].n_room_labels == 0
