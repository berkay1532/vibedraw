# core/perception/validate.py
"""Perception doğrulama (Adım 7): v2 BuildingIR → ValidationReport (issue listesi, HITL soruları).

Issue tipleri (ARCHITECTURE §7 + kullanıcı kararı 2026-09-04): unknown_layer, conflicting_layer,
unit_suspect, open_room, room_no_door, ambiguous_opening, area_mismatch. Henüz yok: unlabeled_region
(duvar grafı, Adım 9), unit_split (Adım 5d). Eşikler config/thresholds.yaml `validate.*`.
Sıralama: etkisi en yüksek önce (PRIORITY). Eski v1 sözleşme kontrolü `validate_building` kaldı."""
from __future__ import annotations

from typing import Optional

from core.perception.config import T
from core.perception.ir import BuildingIR, Floor, Issue, ValidationReport
from core.perception.ir_v1 import BuildingIR as BuildingIRv1
from core.perception.names import EMPTY, LayerClass, NameMap
from core.perception.vocab import ROOM_TYPE_MAP, fold

PRIORITY = ("unknown_layer", "conflicting_layer", "unit_suspect", "open_room", "room_no_door",
            "ambiguous_opening", "area_mismatch")
LAYER_OPTIONS = ["duvar", "kapı", "pencere", "mobilya", "yazı", "yoksay"]


class PipelineError(Exception):
    """Aşama kontratı ihlal edildiğinde fırlatılır; pipeline durur."""


def validate_building(building: BuildingIRv1) -> None:
    """v1 sözleşme kontrolü (elektrik prototipi kullanır)."""
    if not building.floors:
        raise PipelineError("BuildingIR boş: hiç kat yok")
    for floor in building.floors:
        for room in floor.rooms:
            if not room.room_type:
                raise PipelineError(f"Oda room_type eksik: {room.raw_name!r}")


def _is_stair_name(name: Optional[str]) -> bool:
    f = fold(name)
    return any(w in f for w in ("merdiven", "stair"))


def issues_for_floor(fl: Floor, names: NameMap = EMPTY, layer_counts: Optional[dict] = None) -> list[Issue]:
    V = T("validate")
    out: list[Issue] = []
    # --- unknown_layer: sınıfı bilinmeyen ve kalabalık katmanlar
    for layer, n in sorted((layer_counts or {}).items(), key=lambda kv: -kv[1]):
        if n >= V["unknown_layer_min_entities"] and names.cls(layer) is LayerClass.unknown:
            out.append(Issue("unknown_layer", f"layer:{layer}", f"'{layer}' katmanı sınıflanamadı ({n} entity). Bu katman ne?",
                             LAYER_OPTIONS, {"entities": n}))
    # --- conflicting_layer: dosya × katman çelişkili duvar segment oranı
    by_layer: dict = {}
    for w in fl.walls:
        lay = w.layer or "?"
        tot, con = by_layer.get(lay, (0, 0))
        by_layer[lay] = (tot + 1, con + (1 if w.evidence.note == "conflicting_signal" else 0))
    for lay, (tot, con) in sorted(by_layer.items(), key=lambda kv: -kv[1][1]):
        ratio = con / tot if tot else 0.0
        if con >= V["conflicting_layer_min_count"] and ratio >= V["conflicting_layer_min_ratio"]:
            vote = names.cls(lay).value if lay != "?" else "unknown"
            out.append(Issue("conflicting_layer", f"layer:{lay}",
                             f"'{lay}' katmanı: geometri {con}/{tot} segmentte duvar çifti diyor, katman sınıfı '{vote}' diyor. Bu çizgiler ne?",
                             ["duvar", "açıklama-yazı", "mobilya", "yoksay"],
                             {"class_vote": vote, "ratio": round(ratio, 3), "count": con, "total": tot}))
    # --- unit_suspect: upm standart değerlerden uzak
    upm = fl.params.units_per_meter
    std = V["unit_standard_upm"]; tol = V["unit_tol_frac"]
    if upm and not any(abs(upm - s) <= tol * s for s in std):
        out.append(Issue("unit_suspect", "file",
                         f"Birim kestirimi {upm:.1f} birim/m ({fl.params.units_source}); standart değerlere (m/dm/cm/mm) uzak. Çizim birimi ne?",
                         ["m", "dm", "cm", "mm", "inç"], {"upm": round(upm, 2), "source": fl.params.units_source}))
    # --- odalar
    door_rooms = {op.rooms[0] for op in fl.openings if op.kind == "door" and op.rooms and op.rooms[0]}
    for r in fl.rooms:
        if not r.polygon:
            out.append(Issue("open_room", r.id, f"'{r.raw_name}' odasının poligonu kapanmıyor (sızma/boşluk). Boşluk ne?",
                             ["kapı", "geçiş", "pencere", "duvar eksik", "yoksay"], {"name": r.raw_name}))
            continue
        if r.id not in door_rooms and not _is_stair_name(r.raw_name):
            out.append(Issue("room_no_door", r.id, f"'{r.raw_name}' odasına açılan kapı yok. Giriş nerede?",
                             ["kapı eksik", "açık geçiş", "sürgülü kapı", "yoksay"], {"name": r.raw_name}))
        if r.area_m2_text and r.area_m2_geom:
            frac = abs(r.area_m2_text - r.area_m2_geom) / r.area_m2_text
            if frac > V["area_mismatch_frac"]:
                out.append(Issue("area_mismatch", r.id,
                                 f"'{r.raw_name}': yazı {r.area_m2_text} m², geometri {r.area_m2_geom} m² (fark %{frac * 100:.0f}). Hangisi doğru?",
                                 ["yazı", "geometri", "ikisi de yanlış"], {"text": r.area_m2_text, "geom": r.area_m2_geom, "frac": round(frac, 3)}))
    # --- açıklıklar
    for op in fl.openings:
        if op.confidence < V["ambiguous_opening_conf"]:
            out.append(Issue("ambiguous_opening", op.id,
                             f"{op.kind} adayı güven {op.confidence:.2f} (kaynak {op.evidence.source}). Bu ne?",
                             ["kapı", "pencere", "geçiş", "hiçbiri"], {"kind": op.kind, "confidence": op.confidence, "source": op.evidence.source}))
    out.sort(key=lambda i: PRIORITY.index(i.kind) if i.kind in PRIORITY else len(PRIORITY))
    return out


def validate_building_v2(b: BuildingIR, names: NameMap = EMPTY, layer_counts: Optional[dict] = None) -> ValidationReport:
    issues: list[Issue] = []
    for fl in b.floors:
        issues += issues_for_floor(fl, names, layer_counts)
    return ValidationReport(issues=issues)


def issue_counts(issues) -> dict:
    """Tip → sayı (rapor)."""
    out: dict = {}
    for i in issues:
        k = i.kind if hasattr(i, "kind") else i.get("kind")
        out[k] = out.get(k, 0) + 1
    return out
