# tests/conftest.py
import ezdxf
import pytest


@pytest.fixture
def synthetic_dxf(tmp_path):
    """İki kat planı içeren küçük DXF: KAT 0 (x~0), KAT 1 (x~500).
    Her odada isim MTEXT + alan MTEXT (YAZI layer'ında)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("YAZI")

    def room(name, area, x, y):
        msp.add_mtext(name, dxfattribs={"layer": "YAZI", "insert": (x, y)})
        msp.add_mtext(f"A: {area}m²", dxfattribs={"layer": "YAZI", "insert": (x, y - 5)})

    # KAT 0 (x ~ 0..100)
    room("Salon", "14.12", 10, 100)
    room("Mutfak", "12.50", 60, 100)
    room("Banyo", "5.69", 10, 50)
    # KAT 1 (x ~ 500..600) — büyük x boşluğu ile ayrı küme
    room("Yatak Odası", "17.97", 510, 100)
    room("Hol", "4.41", 560, 100)

    path = tmp_path / "synthetic.dxf"
    doc.saveas(path)
    return str(path)


@pytest.fixture
def synthetic_walled_dxf(tmp_path):
    """Duvarlı küçük plan: 100x50 dış duvar, x=50'de kapı boşluklu bölme duvarı.
    İki oda (Salon solda, Mutfak sağda) + kapı boşluğunda bir 'kapi' entity'si.
    M1 geometri testleri için (flood-fill ile ayrışmalı)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for lyr in ("YAZI", "duv", "kapi"):
        doc.layers.add(lyr)

    # Dış duvar (kapalı dikdörtgen) 0,0 - 100,50
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)],
                       close=True, dxfattribs={"layer": "duv"})
    # Bölme duvarı x=50, y=20..30 arası kapı boşluğu (iki parça)
    msp.add_line((50, 0), (50, 20), dxfattribs={"layer": "duv"})
    msp.add_line((50, 30), (50, 50), dxfattribs={"layer": "duv"})
    # Kapı boşluğunda kapı entity'si (tespit için)
    msp.add_lwpolyline([(50, 20), (50, 30)], dxfattribs={"layer": "kapi"})

    def room(name, x, y):
        msp.add_mtext(name, dxfattribs={"layer": "YAZI", "insert": (x, y)})

    room("Salon", 25, 25)
    room("Mutfak", 75, 25)

    path = tmp_path / "walled.dxf"
    doc.saveas(path)
    return str(path)
