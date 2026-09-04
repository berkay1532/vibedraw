# tests/test_polygons.py
import ezdxf
import pytest


def test_staircase_polygon_survives_large_coordinates():
    """UTM benzeri büyük koordinatlarda (4.4 milyon) maske→poligon boş dönmemeli."""
    import numpy as np
    from core.perception.polygons import _staircase_polygon

    class R:  # asgari raster taklidi
        res = 2.74
        x0, y0 = 314700.0, 4430000.0
    mask = np.zeros((60, 80), dtype=bool); mask[10:50, 15:70] = True
    poly = _staircase_polygon(mask, R)
    assert poly is not None and poly.area > 0
    exp = (40 * 2.74) * (55 * 2.74)
    assert abs(poly.area - exp) / exp < 0.02
    minx, miny, maxx, maxy = poly.bounds
    assert abs(minx - (R.x0 + 15 * 2.74 - 1.37)) < 0.01 and abs(miny - (R.y0 + 10 * 2.74 - 1.37)) < 0.01
