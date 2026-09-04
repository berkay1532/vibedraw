# tests/test_blocks.py
import ezdxf
import pytest


def test_walls_and_doors_inside_big_block(tmp_path):
    """Kat planı BLOK olarak yerleştirilmiş: duvar çifti ve kapı yayı blok içinde."""
    import ezdxf
    from core.perception.walls import _wall_segments
    from core.perception.openings import _swing_dirs
    doc = ezdxf.new("R2010")
    blk = doc.blocks.new("KAT_PLANI")
    blk.add_line((0, 0), (800, 0)); blk.add_line((0, 15), (800, 15))          # 8 m duvar çifti (15 cm)
    blk.add_line((0, 0), (0, 500)); blk.add_line((15, 0), (15, 500))
    blk.add_arc((400, 15), 85, 0, 90)                                           # kapı yayı
    msp = doc.modelspace(); msp.add_blockref("KAT_PLANI", (1000, 1000))
    p = tmp_path / "blok.dxf"; doc.saveas(p); doc2 = ezdxf.readfile(str(p)); msp2 = doc2.modelspace()
    bbox = (900, 900, 2000, 1700)
    walls = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18, big_blocks=True)
    assert len(walls) == 4
    sw = _swing_dirs(msp2, bbox, 55, 130, big_blocks=True)
    assert len(sw) == 1 and abs(sw[0][0][0] - 1400) < 1e-6 and abs(sw[0][0][1] - 1015) < 1e-6
