# core/perception/calibration.py
"""Dosyadan türetilen parametreler: birim/metre (etiket mesafesi, kapı yayı), ölçekli koşu parametreleri.

Adım 3: core/perception/geometry.py'den taşındı; mantık değişmedi."""
from __future__ import annotations

import math

import ezdxf

from core.perception.config import T
from core.perception.ir import FileParams
from core.perception.names import EMPTY
from core.perception.openings import _swing_dirs
from core.perception.parse import YaziText, is_area_text


def estimate_units_from_doors(dxf_path: str, bbox, upm_prior: float, door_m: float | None = None,
                              min_doors: int | None = None, msp=None, names=EMPTY):
    """Kapı yayı yarıçaplarından birim/metre.

    Yarıçaplar karışık: fikstür yayları (~45 cm), dar banyo kapıları (60-70), ana kapılar
    (80-95), semboller (2-3 cm). Etiket öncülü (upm_prior) kaba olabilir (tablo/lejant
    etiketleri) → birden çok öncül denenir (etiket, 10, 100, 1000 birim/m) ve en çok yay
    içeren EN BÜYÜK küme (max'ın %85'i ve üstü) alınır; ortalaması ≈ ana kapı kanadı
    (≈0.875 m). Kümede ≥min_doors yay yoksa None.
    """
    door_m = T("door", "leaf_m") if door_m is None else door_m
    min_doors = T("door", "calib_min_doors") if min_doors is None else min_doors
    top_frac = T("door", "calib_top_frac"); rf = T("door", "calib_radius_frac")
    if msp is None:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    # Öncül sırası: etiket tahmini; başarısızsa cm (100) ve mm (1000). Küçük öncüller
    # (10) sembol yaylarını kapı sanıp yanlış ölçek veriyor → denenmez; "en çok yay"
    # seçimi de aynı tuzağa düşüyordu → ilk başarılı öncül alınır.
    for prior in (upm_prior, *T("door", "calib_priors")):
        sw = _swing_dirs(msp, bbox, rf[0] * prior, rf[1] * prior, names=names)
        radii = sorted(math.hypot(e1[0] - h[0], e1[1] - h[1]) for h, _b, e1, _e2 in sw)
        if len(radii) < min_doors:
            continue
        # Yukarıdan aşağı: birkaç büyük aykırı yay (merdiven/eğri duvar) tepede tek
        # kalabilir → ≥min_doors üyeli ilk %85-kümesi ana kapı kanadı sayılır.
        for k in range(len(radii) - 1, -1, -1):
            rmax = radii[k]
            top = [r for r in radii[:k + 1] if r >= top_frac * rmax]
            if len(top) >= min_doors:
                return (sum(top) / len(top)) / door_m
    return None


def estimate_units_per_meter(labels: list[YaziText], typical_room_m: float | None = None) -> float:
    """Oda etiketleri arası en-yakın-komşu mesafesinin medyanı ≈ tipik oda boyu varsayımıyla
    çizim birimi/metre tahmini. Etiket azsa 100 (cm) döner."""
    typical_room_m = T("labels", "typical_room_m") if typical_room_m is None else typical_room_m
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


# Ölçek-100 (1 birim = 1 cm) referans parametreleri config/thresholds.yaml'da (base_upm / base.*)
BASE_UPM = float(T("base_upm"))
BASE = {k: (tuple(v) if isinstance(v, list) else v) for k, v in T("base").items()}


def scaled_params(upm: float) -> dict:
    """upm'e ölçeklenmiş koşu parametreleri (dosyadan türeyen). İfade biçimi korunur (bit-bit aynı eval)."""
    k = upm / BASE_UPM
    return dict(res=BASE["res"] * k, seal=BASE["seal"], margin=BASE["margin"] * k,
                door_arc_radius=(BASE["door_arc_radius"][0] * k, BASE["door_arc_radius"][1] * k),
                door_wall_dist=BASE["door_wall_dist"] * k,
                door_max_boundary_dist=BASE["door_max_boundary_dist"] * k)


def file_params(upm: float, units_source: str = "labels", extra: dict | None = None) -> FileParams:
    """Dosyadan türeyen tüm koşu parametreleri tek nesnede (FileParams)."""
    p = scaled_params(upm)
    th = T("wall", "thickness_m")
    return FileParams(units_per_meter=float(upm), units_source=units_source, res=p["res"], seal=p["seal"],
                      margin=p["margin"], door_arc_radius=p["door_arc_radius"], door_wall_dist=p["door_wall_dist"],
                      door_max_boundary_dist=p["door_max_boundary_dist"],
                      wall_thickness=(th[0] * upm, th[1] * upm), wall_min_overlap=T("wall", "min_overlap_m") * upm,
                      extra=dict(extra or {}))


def thickness_modes(thicknesses, upm: float) -> list[float]:
    """Duvar çifti kalınlıklarının histogram modları (metre). Kutu genişliği ve pay eşiği thresholds
    wall.thickness_bin_m / thickness_mode_min_share. FileParams.wall_thickness_modes'a yazılır."""
    vals = [float(t) / upm for t in thicknesses if t is not None and upm]
    if not vals:
        return []
    b = T("wall", "thickness_bin_m"); share = T("wall", "thickness_mode_min_share")
    hist: dict = {}
    for v in vals:
        hist[int(v / b)] = hist.get(int(v / b), 0) + 1
    n = len(vals)
    peaks = [k for k, c in hist.items() if c / n >= share and c >= hist.get(k - 1, 0) and c >= hist.get(k + 1, 0)]
    return sorted(round((k + 0.5) * b, 4) for k in peaks)


def label_upm_confidence(labels: list[YaziText]) -> float:
    """Etiket-mesafesi kestiriminin güveni (0,1..1): az etiket, dar (tablo benzeri) ya da tekrarlı en-yakın-komşu
    dağılımı güveni düşürür (thresholds labels.conf_*). Kullanıcı kararı 2026-09-05."""
    L = T("labels")
    pts = [t.xy for t in labels if not is_area_text(t.content)]
    if len(pts) < 2:
        return 0.1
    nn = []
    for i, p in enumerate(pts):
        d = min(math.hypot(p[0] - q[0], p[1] - q[1]) for j, q in enumerate(pts) if j != i)
        if d > 0:
            nn.append(d)
    if len(nn) < L["conf_min_n"]:
        return 0.3
    nn.sort(); med = nn[len(nn) // 2]
    q1, q3 = nn[len(nn) // 4], nn[(3 * len(nn)) // 4]
    conf = 1.0
    if med and (q3 - q1) / med < L["conf_narrow_iqr"]:
        conf -= 0.4
    rounded = [round(d / med, 1) for d in nn] if med else []
    if rounded:
        top = max(set(rounded), key=rounded.count)
        if rounded.count(top) / len(rounded) > L["conf_repeat_share"]:
            conf -= 0.4
    return max(0.1, round(conf, 2))
