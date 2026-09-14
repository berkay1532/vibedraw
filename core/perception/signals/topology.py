# core/perception/signals/topology.py
"""Topoloji sinyalleri: aday ↔ oda sınırı. (Komşuluk/kapı grafı Adım 5d/7'de.)"""
from __future__ import annotations


def room_boundary(pt, room_polys, max_dist: float, enabled: bool = True) -> float | None:
    """Aday bir oda poligonu sınırına ≤ max_dist ise 1, değilse 0. Değerlendirilemiyorsa
    (oda poligonu yok ya da bu yol için kapalı) None."""
    if not enabled or not room_polys:
        return None
    from shapely.geometry import Point
    bd = min(poly.exterior.distance(Point(pt[0], pt[1])) for _, poly in room_polys)
    return 1.0 if bd <= max_dist else 0.0


def graph_connectivity(segment, wall_graph=None) -> float | None:
    """İskelet (Adım 6): duvar grafı (5a WallGraph) gelince segmentin düğüm bağlantı derecesi → 0..1.
    Şimdilik değerlendirilemez (None); ağırlığı weights.yaml'da 0."""
    return None


ROOM_FLOOD_SIGNALS = ("flood_exclusive", "alias_merge", "voronoi", "edge_fragment", "fallback")


def area_polyline(hit: bool) -> float | None:
    """Ağırlık turu 7: odanın etiketi alan-polyline katmanındaki kapalı bir poligonun içinde ve poligon yalnız bu etiketi
    içeriyor → 1 (poligon oda geometrisi olur). Alan katmanı yoksa None."""
    return 1.0 if hit else None


def flood_outcome(source: str) -> dict:
    """Oda ayrıştırma sonucu → tek-sıcak sinyaller (geçiş, Adım 6): kaynak sinyali 1, diğerleri None
    (değerlendirilmedi; çelişki sayılmaz). Kaynaklar: exclusive | alias_merge | voronoi | edge_fragment | fallback."""
    key = "flood_exclusive" if source == "exclusive" else source
    return {k: (1.0 if k == key else None) for k in ROOM_FLOOD_SIGNALS}
