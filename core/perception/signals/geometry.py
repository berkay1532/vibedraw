# core/perception/signals/geometry.py
"""Geometri sinyalleri: kapı yayı imzası, menteşe ↔ duvar boşluğu."""
from __future__ import annotations

from core.perception.openings import _seg_dist


def arc_signature(has_door_arc: bool) -> float:
    """0/1: adayda kapı-genişliğinde ve 55–125° süpürmeli yay var mı (openings._door_like_arc)."""
    return 1.0 if has_door_arc else 0.0


def wall_gap(hinge, walls, max_dist: float) -> float | None:
    """Menteşe bir duvar yüzüne ≤ max_dist ise 1, değilse 0. Duvar yoksa değerlendirilemez → None
    (kapı sinyali olarak None elemez; mevcut davranış: duvar yoksa filtre uygulanmaz)."""
    if not walls:
        return None
    return 1.0 if _seg_dist(hinge, walls) <= max_dist else 0.0
