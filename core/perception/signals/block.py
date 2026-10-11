# core/perception/signals/block.py
"""Blok sinyali: aday bir INSERT'ten (kapı katmanı bloğu ya da içinde kapı yayı olan blok) mı geldi."""
from __future__ import annotations

NAME_ONLY_CONF = 0.6      # v0.2-1: kanıt yalnız blok ADI/profili (yay yok) → kademeli sinyal değeri


def block_class(from_block: bool, name_only: bool = False) -> float:
    """1,0: blok geometrisi kapı kanıtı taşıyor (kapı katmanı INSERT'i ya da içinde kapı yayı olan blok).
    NAME_ONLY_CONF: kanıt yalnız blok adı/profili (v0.2-1, yaysız blok kapı). 0: blok değil."""
    if from_block:
        return 1.0
    return NAME_ONLY_CONF if name_only else 0.0


WINDOW_SOURCE_SIGNALS = ("layer_class", "block_keyword", "block_geometry", "thin_lines")


def window_source(source: str) -> dict:
    """Pencere kaynağı → tek-sıcak sinyaller (geçiş): layer → layer_class, block_keyword (blok adı/katmanında
    pencere kelimesi), block_geometry (ince-uzun cam geometrisi + duvar yakınlığı), thin_lines (duvar bandı)."""
    key = "layer_class" if source == "layer" else source
    return {k: (1.0 if k == key else None) for k in WINDOW_SOURCE_SIGNALS}
