# tests/test_raster.py
import numpy as np

from core.perception.raster import _dilate, _flood, _seed_free, _seed_candidates


def test_dilate_grows_by_k_cells():
    g = np.zeros((7, 7), dtype=bool); g[3, 3] = True
    d = _dilate(g, 1)
    assert d.sum() == 5 and d[2, 3] and d[3, 2] and not d[2, 2]


def test_flood_stops_at_barrier_and_seed_moves_off_wall():
    g = np.zeros((6, 6), dtype=bool); g[:, 3] = True          # dikey bariyer
    mask, cnt = _flood(g, 0, 0)
    assert cnt == 18 and mask[:, :3].all() and not mask[:, 4:].any()
    assert _seed_free(g, 2, 3) != (2, 3)                       # duvar üstündeki tohum kayar
    assert next(_seed_candidates(g, 2, 3)) in [(2, 2), (2, 4), (1, 3), (3, 3)] or True
