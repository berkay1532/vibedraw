# core/perception/calibration.py
"""Dosyadan türetilen parametreler: birim/metre (etiket mesafesi, kapı yayı), ölçekli koşu parametreleri.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

import ezdxf

from core.perception.ir import FileParams  # noqa: F401 (yeniden dışa aktarım)
from core.perception.openings import _swing_dirs
from core.perception.parse import YaziText, is_area_text


def estimate_units_from_doors(dxf_path: str, bbox, upm_prior: float, door_m: float = 0.875,
                              min_doors: int = 3, msp=None):
    """Kapı yayı yarıçaplarından birim/metre.

    Yarıçaplar karışık: fikstür yayları (~45 cm), dar banyo kapıları (60-70), ana kapılar
    (80-95), semboller (2-3 cm). Etiket öncülü (upm_prior) kaba olabilir (tablo/lejant
    etiketleri) → birden çok öncül denenir (etiket, 10, 100, 1000 birim/m) ve en çok yay
    içeren EN BÜYÜK küme (max'ın %85'i ve üstü) alınır; ortalaması ≈ ana kapı kanadı
    (≈0.875 m). Kümede ≥min_doors yay yoksa None.
    """
    if msp is None:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    # Öncül sırası: etiket tahmini; başarısızsa cm (100) ve mm (1000). Küçük öncüller
    # (10) sembol yaylarını kapı sanıp yanlış ölçek veriyor → denenmez; "en çok yay"
    # seçimi de aynı tuzağa düşüyordu → ilk başarılı öncül alınır.
    for prior in (upm_prior, 100.0, 1000.0):
        sw = _swing_dirs(msp, bbox, 0.3 * prior, 2.0 * prior)
        radii = sorted(math.hypot(e1[0] - h[0], e1[1] - h[1]) for h, _b, e1, _e2 in sw)
        if len(radii) < min_doors:
            continue
        # Yukarıdan aşağı: birkaç büyük aykırı yay (merdiven/eğri duvar) tepede tek
        # kalabilir → ≥min_doors üyeli ilk %85-kümesi ana kapı kanadı sayılır.
        for k in range(len(radii) - 1, -1, -1):
            rmax = radii[k]
            top = [r for r in radii[:k + 1] if r >= 0.85 * rmax]
            if len(top) >= min_doors:
                return (sum(top) / len(top)) / door_m
    return None


def estimate_units_per_meter(labels: list[YaziText], typical_room_m: float = 3.5) -> float:
    """Oda etiketleri arası en-yakın-komşu mesafesinin medyanı ≈ tipik oda boyu varsayımıyla
    çizim birimi/metre tahmini. Etiket azsa 100 (cm) döner."""
    pts = [t.xy for t in labels if not is_area_text(t.content)]
    if len(pts) < 2:
        return 100.0
    nn = []
    for i, p in enumerate(pts):
        d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for j, q in enumerate(pts) if j != i)
        if d > 0:
            nn.append(d)
    if not nn:
        return 100.0
    nn.sort()
    return nn[len(nn) // 2] / typical_room_m


# Ölçek-100 (1 birim = 1 cm) referans parametreleri — ilk referans dosyada elle ayarlandı
BASE_UPM = 100.0
BASE = dict(res=3.0, seal=18, margin=250.0, door_arc_radius=(55.0, 130.0),
            door_wall_dist=25.0, door_max_boundary_dist=15.0)
def scaled_params(upm: float) -> dict:
    k = upm / BASE_UPM
    return dict(res=BASE["res"] * k, seal=BASE["seal"], margin=BASE["margin"] * k,
                door_arc_radius=(BASE["door_arc_radius"][0] * k, BASE["door_arc_radius"][1] * k),
                door_wall_dist=BASE["door_wall_dist"] * k,
                door_max_boundary_dist=BASE["door_max_boundary_dist"] * k)
