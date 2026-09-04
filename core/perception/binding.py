# core/perception/binding.py
"""Bağlama: kapı ↔ oda (açılış yönü), oda adı ↔ alan yazısı eşleştirme.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

from core.perception.config import T
from core.perception.ir_v1 import Room
from core.perception.parse import YaziText, is_area_text, parse_area


def _room_by_swing(hinge, bdir, rooms, max_dist=None, with_margin=False):
    """Kapının açıldığı oda: yay yönündeki (cos>0.2) odalar arası score=cos-0.4·(d/D) max.

    'En yakın etiket' değil 'yay YÖNÜ'; merkezi oda etiketi (Banyo) fazla sahiplenmez,
    bitişik kapılar (Salon/Mutfak) açılış yönüyle ayrışır.
    """
    max_dist = T("swing", "max_dist_units_fallback") if max_dist is None else max_dist
    cos_min, pen = T("swing", "cos_min"), T("swing", "dist_penalty")
    bx, by = bdir
    best, bscore, second = None, -9.0, -9.0
    for r in rooms:
        lx, ly = r.label_xy
        dx, dy = lx - hinge[0], ly - hinge[1]
        d = math.hypot(dx, dy)
        if d < 1e-6:
            continue
        cos = (bx * dx + by * dy) / d            # bdir birim
        if cos < cos_min:
            continue
        score = cos - pen * (d / max_dist)
        if score > bscore:
            second, bscore, best = bscore, score, r
        elif score > second:
            second = score
    if with_margin:                            # (oda, en iyi − ikinci skor); ikinci yoksa None
        return best, (bscore - second if second > -9.0 else None)
    return best


def pair_names_with_areas(texts: list[YaziText]) -> list[Room]:
    names = [t for t in texts if not is_area_text(t.content)]
    areas = [t for t in texts if is_area_text(t.content)]
    rooms: list[Room] = []
    for nt in names:
        area_val = None
        if areas:
            nearest = min(
                areas,
                key=lambda at: math.hypot(at.xy[0] - nt.xy[0], at.xy[1] - nt.xy[1]),
            )
            area_val = parse_area(nearest.content)
        rooms.append(Room(raw_name=nt.content, label_xy=nt.xy, area_m2=area_val))
    return rooms
