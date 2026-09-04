# core/perception/signals/layer.py
"""Katman sınıfı sinyali: adayın geldiği katman NameMap'te hedef sınıfta mı (güvenle çarpılmış)."""
from __future__ import annotations

from core.perception.names import EMPTY, NameMap


def layer_class(layer: str | None, classes, names: NameMap = EMPTY) -> float:
    """0..1: katman hedef sınıfta ise sınıf güveni (profil 0,9 / sözlük 0,6), değilse 0."""
    if not layer:
        return 0.0
    c, conf, _ = names.classes.get(layer, (None, 0.0, "none"))
    return float(conf) if c in classes else 0.0


def layer_raw(from_door_layer: bool) -> float:
    """Adım 6 geçiş sinyali: aday ham kapı-katmanı kümelemesinden (layer_raw yolu) geliyorsa 1."""
    return 1.0 if from_door_layer else 0.0


def layer_class_vote(layer: str | None, classes, names: NameMap = EMPTY) -> float | None:
    """Duvar için katman oyu: hedef sınıfta → 1; başka BİLİNEN sınıfta (yazı/ölçü/mobilya…) → 0;
    sınıfı bilinmiyorsa None (değerlendirilemez; çelişki sayılmaz). Değer ikili (geçiş sinyali)."""
    if not layer:
        return None
    c, conf, _ = names.classes.get(layer, (None, 0.0, "none"))
    if c is None or getattr(c, "value", c) == "unknown":
        return None
    return 1.0 if c in classes else 0.0
