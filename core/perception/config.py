# core/perception/config.py
"""config/thresholds.yaml ve config/weights.yaml yükleyicisi (önbellekli). Sabitler koda yazılmaz."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"


@lru_cache(maxsize=None)
def thresholds() -> dict:
    return yaml.safe_load((CONFIG_DIR / "thresholds.yaml").read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=None)
def weights() -> dict:
    return yaml.safe_load((CONFIG_DIR / "weights.yaml").read_text(encoding="utf-8")) or {}


def T(*path):
    """thresholds()['a']['b'] kısa yolu; eksik anahtar KeyError verir (sessiz varsayılan yok)."""
    d = thresholds()
    for k in path:
        d = d[k]
    return d
