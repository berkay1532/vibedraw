# tests/test_openings.py
import ezdxf
import pytest

from core.perception.openings import _cluster_doors


def test_door_barriers_pick_closed_leaf():
    from core.perception.openings import _door_barriers
    walls = [((0, 0), (300, 0))]                       # yatay duvar y=0
    # menteşe (100,0); uç1 (190,0) duvar üstünde (kapalı), uç2 (100,90) odaya açık
    sw = [((100.0, 0.0), (0.7, 0.7), (190.0, 0.0), (100.0, 90.0))]
    b = _door_barriers(sw, walls)
    assert b == [((100.0, 0.0), (190.0, 0.0))]
    assert _door_barriers(sw, []) == []


def test_cluster_doors_merges_near_points():
    pts = [(0, 0), (2, 1), (50, 50), (51, 49)]
    clusters = _cluster_doors(pts, radius=15.0)
    assert len(clusters) == 2


def test_cluster_doors_tags_sources():
    from core.perception.openings import _cluster_doors
    out = _cluster_doors([(0, 0), (5, 0), (100, 0)], radius=25.0, tags=["block", "arc", "arc"])
    assert len(out) == 2 and out[0][1] == {"block", "arc"} and out[1][1] == {"arc"}
