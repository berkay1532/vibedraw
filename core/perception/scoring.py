# core/perception/scoring.py
"""Sinyal → güven birleşimi (Adım 6). Ağırlıklar config/weights.yaml'dan.

score(kind, signals): signals = {ad: 0..1}. Kapı (gate) sinyalleri 0 ise aday elenir (None döner).
conf = max(w_i × s_i) + agreement_bonus × (pozitif ağırlıklı sinyal sayısı − 1), cap ile sınırlı.
Evidence.signals'a ağırlıklı katkılar ve kapı değerleri yazılır."""
from __future__ import annotations

from typing import Optional

from core.perception.config import weights
from core.perception.ir import Evidence


def score(kind: str, signals: dict, source: str = "") -> Optional[tuple[float, Evidence]]:
    cfg = weights()[kind]
    w = cfg.get("weights", {})
    contrib: dict = {}
    for name, val in signals.items():
        if name in cfg.get("gates", []):
            if val is not None and float(val) <= 0.0:
                return None                       # kapı: aday elendi
            contrib[f"gate:{name}"] = None if val is None else float(val)
            continue
        if name in w and val:
            contrib[name] = round(w[name] * float(val), 4)
    pos = [v for k, v in contrib.items() if not k.startswith("gate:") and v]
    if not pos:
        return None
    conf = max(pos) + cfg.get("agreement_bonus", 0.0) * (len(pos) - 1)
    conf = min(conf, cfg.get("cap", 1.0))
    return round(conf, 4), Evidence(signals=contrib, source=source)
