# tests/test_walls.py
import ezdxf
import pytest


def test_ladder_filter_removes_stair_steps_keeps_door_leaf():
    from core.perception.walls import _ladder_filter
    steps = [((0, y), (100, y)) for y in range(0, 150, 28)]          # 6 basamak, 28 cm aralık
    leaf = [((500, 0), (590, 0))]                                     # tek kapı kanadı
    out = _ladder_filter(steps + leaf, dmin=15, dmax=100)
    assert out == leaf


def test_label_frame_not_a_wall(tmp_path):
    """Etiketi saran 120x40 cm kapalı çerçeve duvar çifti sayılmamalı."""
    import ezdxf
    from core.perception.walls import _wall_segments
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    msp.add_lwpolyline([(100, 100), (220, 100), (220, 140), (100, 140)], close=True, dxfattribs={"layer": "ZONE"})
    msp.add_line((0, 0), (800, 0)); msp.add_line((0, 15), (800, 15))          # gerçek duvar
    p = tmp_path / "frame.dxf"; doc.saveas(p); msp2 = ezdxf.readfile(str(p)).modelspace()
    bbox = (-50, -50, 900, 300)
    w_all = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18)
    w_lab = _wall_segments(msp2, bbox, min_len=10, tmin=6, tmax=45, min_overlap=18, label_pts=[(160, 120)])
    assert len(w_all) == 4 and len(w_lab) == 2
