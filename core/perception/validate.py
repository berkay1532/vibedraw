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
from core.perception.vocab import EXEMPT_ROOM_WORDS, WINDOW_EXPECTED_ROOM_WORDS, WINDOW_EXPECTED_SHORT, fold, has_word

PRIORITY = ("unknown_layer", "conflicting_layer", "unit_suspect", "open_room", "room_merged", "room_no_door", "window_missing",
            "door_side_ambiguous", "ambiguous_opening", "area_mismatch")
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


def exempt_room_type(name: Optional[str]) -> Optional[str]:
    """room_no_door muafiyeti: balkon/teras/şaft/merdiven/asansör/aydınlık (vocab.EXEMPT_ROOM_WORDS)."""
    for t, words in EXEMPT_ROOM_WORDS.items():
        if name and has_word(name, words):
            return t
    return None


def _is_stair_name(name: Optional[str]) -> bool:
    return exempt_room_type(name) == "stair"


def window_expected_type(name: Optional[str]) -> Optional[str]:
    """window_missing: yalnız bedroom/living/kitchen/study (vocab.WINDOW_EXPECTED_ROOM_WORDS; 'ODA' tam kelime → bedroom)."""
    if not name:
        return None
    for t, words in WINDOW_EXPECTED_ROOM_WORDS.items():
        if has_word(name, words):
            return t
    import re as _re
    toks = set(_re.findall(r"[a-zçğıöşü]+", fold(name)))
    if any(w in toks for w in WINDOW_EXPECTED_SHORT):
        return "bedroom"
    return None


def issues_for_floor(fl: Floor, names: NameMap = EMPTY, layer_counts: Optional[dict] = None,
                     enabled: Optional[set] = None) -> list[Issue]:
    """enabled: yalnız bu tipler üretilir (None = hepsi); kapsama ölçümü için."""
    V = T("validate")
    out: list[Issue] = []
    on = (lambda k: enabled is None or k in enabled)
    # --- unknown_layer: sınıfı bilinmeyen kalabalık katmanlar; entity × duvar-benzeri geometri oranına göre ilk N
    from core.perception.names import wall_like_ratio
    cands = []
    for layer, n in (layer_counts or {}).items():
        if on("unknown_layer") and n >= V["unknown_layer_min_entities"] and names.cls(layer) is LayerClass.unknown:
            st = (names.stats or {}).get(layer, {})
            ratio = wall_like_ratio(st) if st else 0.0
            cands.append((n * ratio, n, ratio, layer))
    for scorev, n, ratio, layer in sorted(cands, reverse=True)[:V["unknown_layer_max_per_file"]]:
        out.append(Issue("unknown_layer", f"layer:{layer}",
                         f"'{layer}' katmanı sınıflanamadı ({n} entity, uzun düz çizgi oranı {ratio:.2f}). Bu katman ne?",
                         LAYER_OPTIONS, {"entities": n, "wall_like_ratio": round(ratio, 3), "rank_score": round(scorev, 1)}))
    # --- conflicting_layer: dosya × katman çelişkili duvar segment oranı
    by_layer: dict = {}
    for w in fl.walls:
        lay = w.layer or "?"
        tot, con = by_layer.get(lay, (0, 0))
        by_layer[lay] = (tot + 1, con + (1 if w.evidence.note == "conflicting_signal" else 0))
    for lay, (tot, con) in sorted(by_layer.items(), key=lambda kv: -kv[1][1]):
        ratio = con / tot if tot else 0.0
        if on("conflicting_layer") and con >= V["conflicting_layer_min_count"] and ratio >= V["conflicting_layer_min_ratio"]:
            vote = names.cls(lay).value if lay != "?" else "unknown"
            out.append(Issue("conflicting_layer", f"layer:{lay}",
                             f"'{lay}' katmanı: geometri {con}/{tot} segmentte duvar çifti diyor, katman sınıfı '{vote}' diyor. Bu çizgiler ne?",
                             ["duvar", "açıklama-yazı", "mobilya", "yoksay"],
                             {"class_vote": vote, "ratio": round(ratio, 3), "count": con, "total": tot}))
    # --- unit_suspect: upm standart değerlerden uzak
    upm = fl.params.units_per_meter
    std = V["unit_standard_upm"]; tol = V["unit_tol_frac"]
    nonstd = bool(upm) and not any(abs(upm - s) <= tol * s for s in std)
    lowconf = fl.params.units_confidence < T("labels", "conf_min")
    if on("unit_suspect") and (nonstd or lowconf):
        why = []
        if nonstd: why.append("standart değerlere (m/dm/cm/mm) uzak")
        if lowconf: why.append(f"kestirim güveni düşük ({fl.params.units_confidence:.2f}: {fl.params.units_source})")
        out.append(Issue("unit_suspect", "file",
                         f"Birim kestirimi {upm:.1f} birim/m ({fl.params.units_source}); " + "; ".join(why) + ". Çizim birimi ne?",
                         ["m", "dm", "cm", "mm", "inç"], {"upm": round(upm, 2), "source": fl.params.units_source,
                                                          "confidence": fl.params.units_confidence}))
    # --- odalar. area_convention: dosya medyanı (yazı/geometri); yalnız medyandan ±dev sapan odalar issue
    ratios = sorted(r.area_m2_text / r.area_m2_geom for r in fl.rooms if r.area_m2_text and r.area_m2_geom)
    conv = ratios[len(ratios) // 2] if ratios else None
    fl.params.area_convention = round(conv, 3) if conv else None
    door_rooms = {op.rooms[0] for op in fl.openings if op.kind == "door" and op.rooms and op.rooms[0]}
    for r in fl.rooms:
        if not r.polygon:
            if on("open_room"):
                out.append(Issue("open_room", r.id, f"'{r.raw_name}' odasının poligonu kapanmıyor (sızma/boşluk). Boşluk ne?",
                             ["kapı", "geçiş", "pencere", "duvar eksik", "yoksay"], {"name": r.raw_name}))
            continue
        if on("room_merged") and r.aliases and (r.evidence.source or "").endswith("alias_merge"):
            out.append(Issue("room_merged", r.id,
                             f"'{r.raw_name}' ile {', '.join(repr(a) for a in r.aliases)} etiketleri tek bölgeye düştü (takma ad birleşmesi, HITL #8). Aynı oda mı?",
                             ["aynı oda", "ayrı odalar (bölme eksik)", "yoksay"], {"name": r.raw_name, "aliases": list(r.aliases)}))
        ex = exempt_room_type(r.raw_name)
        if on("room_no_door") and r.id not in door_rooms and not ex:
            out.append(Issue("room_no_door", r.id, f"'{r.raw_name}' odasına açılan kapı yok. Giriş nerede?",
                             ["kapı eksik", "açık geçiş", "sürgülü kapı", "yoksay"], {"name": r.raw_name}))
        if r.area_m2_text and r.area_m2_geom and conv and on("area_mismatch"):
            ratio = r.area_m2_text / r.area_m2_geom
            dev = abs(ratio / conv - 1.0)
            absolute = ratio < V["area_abs_low"] or ratio > V["area_abs_high"]     # mutlak aykırılık her zaman issue
            if dev > V["area_convention_dev"] or absolute:
                out.append(Issue("area_mismatch", r.id,
                                 f"'{r.raw_name}': yazı {r.area_m2_text} m², geometri {r.area_m2_geom} m²; oran dosya medyanından %{dev * 100:.0f} sapıyor. Hangisi doğru?",
                                 ["yazı", "geometri", "ikisi de yanlış"],
                                 {"text": r.area_m2_text, "geom": r.area_m2_geom, "dev": round(dev, 3), "convention": fl.params.area_convention}))
    # --- açıklıklar: düşük güvenli adaylar; yalnız PENCERESİZ odaya değenler, dosya başına TEK toplu soru
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    upm = fl.params.units_per_meter or 100.0
    polys = []
    for r in fl.rooms:
        if r.polygon:
            try:
                polys.append((r, Polygon(r.polygon).buffer(0)))
            except Exception:
                pass
    # --- window_missing: penceresi beklenen tip, dış duvara değiyor, pencere adayı (her güvende) sıfır
    if on("window_missing") and polys:
        try:
            outer = unary_union([P for _, P in polys]).buffer(0)
            ext = outer.boundary
        except Exception:
            ext = None
        win_pts = [Point(op.center[0], op.center[1]) for op in fl.openings if op.kind == "window"]
        for r, P in polys:
            wt = window_expected_type(r.raw_name)
            if not wt or ext is None:
                continue
            if P.boundary.distance(ext) > V["exterior_touch_m"] * upm:
                continue                                       # iç oda: dış duvara değmiyor
            Pb = P.buffer(V["ambiguous_touch_m"] * upm)
            if any(Pb.contains(pt) for pt in win_pts):
                continue
            out.append(Issue("window_missing", r.id,
                             f"'{r.raw_name}' ({wt}) dış duvara değiyor ama hiç pencere adayı yok. Pencere nerede?",
                             ["pencere var (çizilmemiş)", "pencere yok", "yoksay"], {"name": r.raw_name, "type": wt}))
    # --- door_side_ambiguous: açılış yayı eşleşmedi (width yok) ya da yön skoru marjı küçük
    if on("door_side_ambiguous"):
        id2name = {r.id: r.raw_name for r in fl.rooms}
        for op in fl.openings:
            if op.kind != "door":
                continue
            margin = (op.evidence.signals or {}).get("swing_margin")
            no_swing = op.width is None
            if no_swing or (margin is not None and margin < V["swing_margin_min"]):
                why = "açılış yayı eşleşmedi (merkez-mesafesi fallback)" if no_swing else f"yön skoru marjı {margin:.2f}"
                out.append(Issue("door_side_ambiguous", op.id,
                                 f"Kapı {op.id}: '{id2name.get(op.rooms[0]) if op.rooms else None}' odasına atandı; {why}. Hangi odaya açılıyor?",
                                 ["atanan oda doğru", "diğer oda", "bilinmiyor"],
                                 {"room": op.rooms[0] if op.rooms else None, "margin": margin, "no_swing": no_swing}))
    conf_win_rooms = set()
    for op in fl.openings:
        if op.kind == "window" and op.confidence >= V["ambiguous_opening_conf"]:
            pt = Point(op.center[0], op.center[1])
            for r, P in polys:
                if P.buffer(V["ambiguous_touch_m"] * upm).contains(pt):
                    conf_win_rooms.add(r.id)
    grouped, rooms_hit = [], set()
    for op in fl.openings:
        if op.confidence >= V["ambiguous_opening_conf"]:
            continue
        pt = Point(op.center[0], op.center[1])
        touch = [r for r, P in polys if P.buffer(V["ambiguous_touch_m"] * upm).contains(pt)]
        if touch and all(r.id not in conf_win_rooms for r in touch):
            grouped.append(op.id); rooms_hit |= {r.id for r in touch}
    if grouped and on("ambiguous_opening"):
        out.append(Issue("ambiguous_opening", "openings",
                         f"{len(grouped)} düşük güvenli açıklık adayı penceresiz {len(rooms_hit)} odaya değiyor. Bunlar pencere mi?",
                         ["pencere", "kapı", "geçiş", "hiçbiri"],
                         {"targets": grouped, "rooms": sorted(rooms_hit), "count": len(grouped)}))
    out.sort(key=lambda i: PRIORITY.index(i.kind) if i.kind in PRIORITY else len(PRIORITY))
    # Üretim sınırı yok (kullanıcı kararı 2026-09-05): bütçe ölçütü issue/oda (evaluate), CLI etki sıralı ilk 10 + devam.
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


def issues_per_room(issues, n_rooms: int) -> float | None:
    """Bütçe ölçütü: issue sayısı / oda sayısı (hedef typical dosyada ≤ thresholds validate.issues_per_room_target)."""
    return round(len(issues) / n_rooms, 3) if n_rooms else None
