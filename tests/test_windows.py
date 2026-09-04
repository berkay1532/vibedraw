# tests/test_windows.py
import ezdxf
import pytest


def test_window_detection_layer_independent(tmp_path):
    """(a) 'PENCERE' adlı blok, (b) duvar bandında 3 ince paralel cam çizgisi → 2 pencere."""
    import ezdxf
    from core.perception.windows import _window_segments
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    blk = doc.blocks.new("90LIK PENCERE")
    blk.add_line((0, 0), (90, 0)); blk.add_line((0, 4), (90, 4)); blk.add_line((0, 0), (0, 4)); blk.add_line((90, 0), (90, 4))
    msp.add_blockref("90LIK PENCERE", (100, 500), dxfattribs={"layer": "Layer 3"})
    # duvar bandı: y=0 ve y=20 yüzleri (walls listesi), boşlukta 3 cam çizgisi x=300..420
    walls = [((0, 0), (300, 0)), ((0, 20), (300, 20)), ((420, 0), (800, 0)), ((420, 20), (800, 20))]
    for y in (8, 10, 12):
        msp.add_line((300, y), (420, y), dxfattribs={"layer": "0"})
    # gürültü: oda ortasında tek çizgi, kısa çizgiler
    msp.add_line((100, 300), (250, 300), dxfattribs={"layer": "0"})
    p = tmp_path / "w.dxf"; doc.saveas(p)
    doc2 = ezdxf.readfile(str(p)); wins = _window_segments(doc2.modelspace(), (-50, -50, 900, 600), upm=100, walls=walls)
    mids = sorted(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in wins)
    assert len(mids) == 2
    assert abs(mids[0][0] - 145) < 2 and abs(mids[0][1] - 502) < 3     # blok
    assert abs(mids[1][0] - 360) < 2 and abs(mids[1][1] - 10) < 3      # cam çizgileri
