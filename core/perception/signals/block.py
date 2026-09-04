# core/perception/signals/block.py
"""Blok sinyali: aday bir INSERT'ten (kapı katmanı bloğu ya da içinde kapı yayı olan blok) mı geldi."""
from __future__ import annotations


def block_class(from_block: bool) -> float:
    return 1.0 if from_block else 0.0
