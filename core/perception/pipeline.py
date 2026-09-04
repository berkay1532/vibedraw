# core/perception/pipeline.py
"""Orkestratör.

- `select_plan(dxf)`: etiket → ölçek → 2B kat kümeleme → plan seçimi (kapı-yayı kanıtı) → ölçek
  düzeltme. Adım 4'te `experiments/run_baseline.run_one`'dan taşındı; mantık değişmedi.
- `run_floor(building, dxf)`: seçilen kat için duvar → açıklık → oda → bağlama (eski reconstruct;
  Adım 3'te geometry.py'den taşındı).
- `run_selected` / `run_file`: seçim + ölçekli parametreler + run_floor + v2 IR.
Deney scriptleri (experiments/) yalnızca bunları çağırır, mantık taşımaz."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import ezdxf
import numpy as np

from core.perception.ir_v1 import BuildingIR, Door, Floor, Room
from core.perception.binding import _room_by_swing, pair_names_with_areas
from core.perception.calibration import (estimate_units_from_doors, estimate_units_per_meter, file_params,
                                         scaled_params)
from core.perception.config import T
from core.perception.ir_compat import to_v2
from core.perception.names import NameMap, apply_overrides, layer_stats, names_for, refine_with_stats
from core.perception.triage import HEAVY_BLOCK_ENTITIES, HEAVY_ENTITIES
from core.perception.scoring import score
from core.perception.signals.block import block_class, window_source
from core.perception.calibration import thickness_modes
from core.perception.names import WALL_SCAN_CLASSES
from core.perception.signals.geometry import arc_signature, parallel_pair, thickness_mode, wall_gap
from core.perception.signals.layer import layer_class_vote, layer_raw
from core.perception.signals.topology import flood_outcome, graph_connectivity, room_boundary
from core.perception.parse import (cluster_floors_2d, dedupe_labels, extract_room_labels, grid_likeness,
                                   pick_plan_floor)
from core.perception.triage import layer_fingerprint
from core.perception.validate import validate_building_v2
from core.perception.openings import _cluster_doors, _door_barriers, _seg_dist, _swing_dirs
from core.perception.polygons import _mask_polygon
from core.perception.raster import _Raster
from core.perception.rooms import _floor_bbox, _segment_rooms
from core.perception.walls import _wall_lines, _wall_segments
from core.perception.windows import _window_segments


def run_floor(building: BuildingIR, dxf_path: str, *,
                res: float = 1.0, seal: int = 8, margin: float = 25.0,
                leak_fraction: float | None = None, door_max_boundary_dist: float = 15.0,
                vlm_door_points: list | None = None,
                door_arc_radius: tuple = (50.0, 130.0),
                door_wall_dist: float = 25.0,
                units_per_meter: float | None = None,
                doc=None, names: NameMap | None = None) -> BuildingIR:
    """M1 giriş noktası: her kat için oda merkezi/poligonu doldur, kapıları tespit et.

    geometry_ok=False olan odalar (sızma/boş) için center=label_xy fallback uygulanır.
    doc verilirse dosya yeniden okunmaz (DXF tek okuma). names: katman sınıfları (profil +
    sözlük); verilmezse belgeden türetilir.
    """
    if doc is None:
        doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    if names is None:
        names = names_for(doc)
    TW, TR, TD = T("wall"), T("raster"), T("door")          # adlandırılmış sabitler (config/thresholds.yaml)
    if leak_fraction is None:
        leak_fraction = TW["leak_fraction"]

    for floor in building.floors:
        if not floor.rooms:
            continue
        bbox = _floor_bbox(floor, margin)
        # Katman-bağımsız duvar/pencere tespiti ÖNCE: raster bariyeri bunlardan da beslenir.
        if units_per_meter:   # duvar kalınlığı 6-45 cm, boyuna örtüşme ≥18 cm (metre-tabanlı, thresholds wall.*)
            # tmin 6 cm: 4 cm'lik "duvar" yapıda yok (duş kabini camı, cam bölme, çift çizgi
            # kaplama 2-4 cm → duvar sayılmaz); en ince bölme duvarı 7-8 cm.
            th = TW["thickness_m"]
            wk = dict(tmin=th[0] * units_per_meter, tmax=th[1] * units_per_meter,
                      min_overlap=TW["min_overlap_m"] * units_per_meter)
        else:
            wk = {}
        label_pts = [rm.label_xy for rm in floor.rooms]
        wk["label_pts"] = label_pts
        min_len = TW["min_len_res"] * res
        floor.walls, floor.wall_sources, w_lays, w_thick = _wall_segments(
            msp, bbox, min_len=min_len, with_signals=True, names=names, **wk)
        # ADAPTİF: modelspace'te oda başına <N duvar parçası bulunduysa plan büyük ihtimalle
        # BLOK içinde yerleştirilmiş → ≥3 m'lik blokların içine de bakılır.
        # (Koşulsuz açmak Revit export'larında sahte duvar üretip IoU'yu düşürdü.)
        big = False
        if len(floor.walls) < TW["adaptive_walls_per_room"] * len(floor.rooms):
            walls_b, srcs_b, lays_b, thick_b = _wall_segments(
                msp, bbox, min_len=min_len, big_blocks=True, with_signals=True, names=names, **wk)
            if len(walls_b) > len(floor.walls):
                floor.walls, floor.wall_sources, w_lays, w_thick = walls_b, srcs_b, lays_b, thick_b
                big = True
        floor.big_blocks = big
        # Duvar sinyalleri (Adım 6): parallel_pair (katman bağımsız), layer_class (oy: 1 / 0 / None),
        # thickness_mode (kalibrasyon histogramı; ağırlık 0), graph_connectivity (iskelet, None).
        modes = thickness_modes(w_thick, units_per_meter) if units_per_meter else []
        floor.wall_thickness_modes = modes
        tol = TW["thickness_mode_tol_m"]
        floor.wall_thickness, floor.wall_signals, floor.wall_layers = list(w_thick), [], list(w_lays)
        for (a, b), src, lay, thk in zip(floor.walls, floor.wall_sources, w_lays, w_thick):
            sig = {"parallel_pair": parallel_pair(True),
                   "layer_class": layer_class_vote(lay, WALL_SCAN_CLASSES, names),
                   "thickness_mode": thickness_mode(thk / units_per_meter if (thk is not None and units_per_meter) else None, modes, tol),
                   "graph_connectivity": graph_connectivity((a, b))}
            floor.wall_signals.append(score("wall", sig, src))
        floor.windows, floor.window_sources = _window_segments(
            msp, bbox, min_len=min_len, upm=units_per_meter, walls=floor.walls, big_blocks=big,
            with_sources=True, names=names)
        floor.window_signals = [score("window", window_source(src), f"window:{src}") for src in floor.window_sources]
        # Kapı yayları (katman-bağımsız) → kapalı kanat bariyeri: açıklık mühürlenir,
        # böylece genel mühür küçük tutulabilir (dar odalar/WC kaybolmaz).
        amin, amax = door_arc_radius
        swing = _swing_dirs(msp, bbox, amin, amax, big_blocks=big, names=names)
        barriers = _door_barriers(swing, floor.walls)
        extra = floor.walls + floor.windows + barriers
        seal_small = (max(TR["seal_small_min_px"], int(round(TR["seal_small_m"] * units_per_meter / res)))
                      if units_per_meter else max(TR["seal_small_min_px"], seal // TR["seal_fallback_div"]))
        seals = sorted({seal_small, seal})
        rasters = [_Raster(msp, bbox, res, sl, extra_segs=extra, door_arc_radius=door_arc_radius, big_blocks=big,
                           names=names)
                   for sl in seals]
        raster = rasters[-1]                      # kapı adayları vb. için (büyük mühür = tam bariyer)
        seed_rad = int(round(TR["seed_radius_m"] * units_per_meter / res)) if units_per_meter else TR["seed_radius_fallback_px"]
        labels, idx_room, merged, room_sources = _segment_rooms(rasters, floor.rooms, leak_fraction, seed_rad=seed_rad)
        # Takma ad birleştirme: birleşen etiketler oda listesinden çıkar, birincile eklenir.
        alias_rooms = set()
        for prim, others in merged.items():
            primary = floor.rooms[prim - 1]
            for o in others:
                primary.aliases.append(o.raw_name)
                primary.alias_xy.append(o.label_xy)
                alias_rooms.add(id(o))
        if alias_rooms:
            floor.rooms = [rm for rm in floor.rooms if id(rm) not in alias_rooms]
        recovered = {i: (labels == i) for i in idx_room}
        wall_xs, wall_ys, angled_walls = _wall_lines(
            msp, bbox, angled_min_len=TW["angled_min_len_res"] * res, cluster_tol=TW["cluster_tol_res"] * res,
            extra_segs=floor.walls, names=names)

        for room in floor.rooms:
            idx = next((i for i, r in idx_room.items() if r is room), None)
            if idx is None or int(recovered[idx].sum()) < TR["min_room_px"]:
                # Fallback: güvenilir geometri yok, etiket noktasını kullan.
                room.geometry_ok = False
                room.center = room.label_xy
                room.polygon = None
                room.source = "fallback"
                room.confidence, ev = score("room", flood_outcome("fallback"), "flood:fallback"); room.signals = ev.signals
                continue
            room.source = room_sources.get(idx, "exclusive")
            room.confidence, ev = score("room", flood_outcome(room.source), f"flood:{room.source}"); room.signals = ev.signals
            mask = recovered[idx]
            ys, xs = np.where(mask)
            cx, cy = raster.to_world(float(xs.mean()), float(ys.mean()))
            room.geometry_ok = True
            room.center = (cx, cy)
            room.polygon = _mask_polygon(mask, raster, wall_xs, wall_ys, angled_walls)

        # Kapı adayları ve sinyaller (Adım 6): block_class / arc_signature / layer_class / vlm, kapı (gate)
        # sinyalleri wall_gap ve room_boundary. Adaylar: kapı BLOKLARI + kapı-genişliği YAYLARI; ikisi de
        # yeterince yoksa ham kapı-katmanı kümelemesine (layer_raw) düşülür. Güven scoring.score'dan.
        from shapely.geometry import Polygon as _P
        room_polys = [(r, _P(r.polygon).buffer(0))
                      for r in floor.rooms if r.polygon]
        swing_arcs = [(x, y) for (x, y, rr) in raster.arcs if amin <= rr <= amax]
        primary = list(raster.door_blocks) + swing_arcs
        used_primary = len(primary) >= TD["primary_min"]
        cand_sig: dict = {}                       # aday merkezi → ham sinyaller
        if used_primary:
            tagged = _cluster_doors(primary, radius=max(TD["cluster_radius_min_units"], amin * TD["cluster_radius_frac"]),
                                    tags=["block"] * len(raster.door_blocks) + ["arc"] * len(swing_arcs))
            candidates = [c for c, _ in tagged]
            for c, t in tagged:
                cand_sig[c] = {"block_class": block_class("block" in t), "arc_signature": arc_signature("arc" in t)}
        else:
            candidates = _cluster_doors(raster.door_raw)
            cand_sig = {c: {"layer_class": layer_raw(True)} for c in candidates}

        if vlm_door_points:
            from core.perception.vlm_doors import validate_doors
            # tol: yalnızca çok yakın aday varsa ince-ayar snap; yoksa VLM noktası korunur
            door_pts = validate_doors(candidates, vlm_door_points, tol=TD["vlm_snap_tol_units"])
        else:
            door_pts = candidates

        def _dist_walls(p):
            return _seg_dist(p, floor.walls) if floor.walls else float("inf")

        # Kapı = menteşe (blok matrix44 / yay merkezi). Standart: tüm kapılar menteşede.
        # room_name = AÇILIŞ YAYI YÖNÜ ile (etiket-mesafesi değil): menteşeye en yakın
        # yayı bul, bisektör yönündeki odayı seç. Yay eşleşmezse merkez-mesafesi fallback.
        floor.doors = []
        for (dx, dy) in door_pts:
            is_vlm_pt = bool(vlm_door_points) and (dx, dy) not in cand_sig
            sig = dict(cand_sig.get((dx, dy), {"vlm": 1.0} if is_vlm_pt else {}))
            # Kapı sinyalleri: fikstür yayları (klozet/lavabo) ELE: gerçek menteşe bir DUVARIN üstündedir;
            # layer_raw yolunda ayrıca oda sınırına uzak sahteler elenir (VLM yolunda uygulanmaz).
            sig["wall_gap"] = wall_gap((dx, dy), floor.walls, door_wall_dist)
            sig["room_boundary"] = room_boundary((dx, dy), room_polys, door_max_boundary_dist,
                                                 enabled=(not used_primary and not vlm_door_points))
            src = ("vlm" if is_vlm_pt else
                   "layer_raw" if "layer_class" in sig else
                   "block+arc" if sig.get("block_class") and sig.get("arc_signature") else
                   "arc" if sig.get("arc_signature") else "block")
            scored = score("door", sig, src)
            if scored is None:                    # bir kapı sinyali 0 → aday elendi
                continue
            conf, ev = scored
            sd = min(swing, key=lambda s_: math.hypot(s_[0][0] - dx, s_[0][1] - dy),
                     default=None)
            room, strike = None, None
            if sd is not None and math.hypot(sd[0][0] - dx, sd[0][1] - dy) <= door_wall_dist * TD["swing_match_factor"]:
                room, margin = _room_by_swing((dx, dy), sd[1], floor.rooms, with_margin=True,
                                              max_dist=(T("swing", "max_dist_m") * units_per_meter) if units_per_meter else None)
                if margin is not None:
                    sig["swing_margin"] = round(margin, 3)      # ağırlıksız bilgi sinyali (door_side_ambiguous)
                # kilit sövesi = KAPALI kanat ucu = kanat ortası bir duvara YASLI olan
                # uç (açık kanat oda boşluğuna gider, duvara uzak). Köşe menteşelerde
                # 'en yakın duvara paralel' testi yanılıyordu; bu test kapının asıl
                # duvarını doğru bulur.
                def _leaf_mid_wall(ep):
                    return _dist_walls(((dx + ep[0]) / 2, (dy + ep[1]) / 2))
                strike = sd[2] if _leaf_mid_wall(sd[2]) <= _leaf_mid_wall(sd[3]) else sd[3]
            if room is None:                       # yay yok → eski merkez-mesafesi
                room = min(floor.rooms,
                           key=lambda r: math.hypot((r.center or r.label_xy)[0] - dx,
                                                    (r.center or r.label_xy)[1] - dy),
                           default=None)
            sigs = dict(ev.signals)
            if "swing_margin" in sig:
                sigs["swing_margin"] = sig["swing_margin"]
            floor.doors.append(Door(xy=(dx, dy), source=src, room_name=room.raw_name if room else None,
                                    strike_xy=strike, confidence=conf, signals=sigs))

    return building


# --- Plan seçimi ve dosya koşusu -------------------------------------------------------
MAX_CELLS = int(T("raster", "max_cells"))   # raster hücre üst sınırı; aşılırsa res büyütülür


@dataclass
class PlanSelection:
    """Etiket → ölçek → kat kümeleme → plan seçimi sonucu. `floor` None ise ≥3 odalı küme yok.
    `stats` results.json'daki "labels_generic" aşaması ile birebir aynı anahtarları taşır."""
    labels: list = field(default_factory=list)
    rooms: list = field(default_factory=list)
    floors: list = field(default_factory=list)
    floor: Floor | None = None
    upm: float = 100.0
    stats: dict = field(default_factory=dict)
    doc: object = field(default=None, repr=False)   # okunmuş ezdxf belgesi (tek okuma; run_selected paylaşır)
    names: NameMap = field(default_factory=NameMap, repr=False)   # katman sınıfları (profil + sözlük)
    fingerprint: str = ""
    layer_counts: dict = field(default_factory=dict)   # katman → modelspace entity sayısı (unknown_layer issue)


def label_floors(dxf_path: str, gap: float) -> list[Floor]:
    """Yardımcı (test/araç): etiket → ad↔alan → 2B kümeleme. Ölçek tahmini ve plan seçimi yok."""
    return cluster_floors_2d(pair_names_with_areas(extract_room_labels(dxf_path)), gap=gap)


def select_plan(dxf_path: str, doc=None, overrides: dict | None = None) -> PlanSelection:
    """Genel etiket çıkarımı + ölçek + kat seçimi (tek yol). DXF bir kez okunur; belge
    PlanSelection.doc ile run_selected/run_floor'a taşınır (AVİDA: 12 okuma → 1, DECISIONS)."""
    if doc is None:
        doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    try:
        fingerprint = layer_fingerprint(l.dxf.name for l in doc.layers)
    except Exception:
        fingerprint = ""
    names = names_for(doc, fingerprint=fingerprint)      # kaynak profili + sözlük → katman sınıfları
    overrides = overrides or {}
    apply_overrides(names, overrides.get("layers"))      # HITL katman cevapları (run_baseline yeniden koşu)
    layer_counts: dict = {}
    for e in msp:
        try:
            layer_counts[e.dxf.layer] = layer_counts.get(e.dxf.layer, 0) + 1
        except Exception:
            pass
    TL, TD = T("labels"), T("door")
    labels = extract_room_labels(dxf_path, msp=msp)
    upm0 = estimate_units_per_meter(labels)
    labels = dedupe_labels(labels, tol=TL["dedupe_m"] * upm0)      # 50 cm içindeki tekrarlar
    upm = estimate_units_per_meter(labels)
    if overrides.get("upm"):                                        # HITL birim cevabı: kestirim atlanır
        upm0 = upm = float(overrides["upm"])
    rooms = pair_names_with_areas(labels)
    floors = cluster_floors_2d(rooms, gap=TL["cluster_gap_m"] * upm)    # 7 m'den yakın etiketler aynı çizim
    floors = [f for f in floors if len(f.rooms) >= TL["min_rooms"]]
    stats = {"labels": len(labels), "rooms": len(rooms), "upm": round(upm, 1),
             "floors": [len(f.rooms) for f in floors],
             "family": names.family_id, "family_match": f"{names.match}:{names.match_score:.2f}"}
    if overrides.get("upm"):
        stats["upm_source"] = "hitl"
    sel = PlanSelection(labels=labels, rooms=rooms, floors=floors, upm=upm, stats=stats, doc=doc,
                        names=names, fingerprint=fingerprint, layer_counts=layer_counts)
    if not floors:
        return sel
    floor = pick_plan_floor(floors, upm); floor.index = 0
    stats["grid"] = [round(grid_likeness(f.rooms, TL["grid_tol_m"] * upm), 2) for f in floors]
    # Kapı-yayı kanıtı: mahal listesi tabloları (döndürülmüş olsa bile) kapı yayı içermez.
    # Kapı yayı bulunan en kalabalık kümeyi tercih et.
    with_doors = []
    for f in sorted(floors, key=lambda f: -len(f.rooms))[:TL["door_evidence_top"]]:
        if len(f.rooms) < TL["min_rooms"]:
            continue
        if estimate_units_from_doors(dxf_path, _floor_bbox(f, TL["bbox_margin_m"] * upm), upm, msp=msp, names=names) is not None:
            with_doors.append(f)
    if with_doors and floor not in with_doors:
        floor = with_doors[0]; floor.index = 0
        stats["pick"] = "doors"
    # Ölçeği kapı yaylarından düzelt (etiket-mesafesi tahmini kaba)
    upm_doors = None if overrides.get("upm") else estimate_units_from_doors(dxf_path, _floor_bbox(floor, TL["bbox_margin_m"] * upm), upm, msp=msp, names=names)
    stats["upm_labels"] = round(upm, 1)
    acc = TD["upm_ratio_accept"]
    if upm_doors and acc[0] * upm <= upm_doors <= acc[1] * upm:   # etiket öncülü kaba; kapı kümesi güçlü kanıt
        upm = upm_doors
        stats["upm"] = round(upm, 1)
        stats["upm_source"] = "doors"
        # Düzeltilmiş ölçekle YENİDEN kümele: kaba ölçekle 7 m eşiği büyük salon
        # etiketini kümenin dışında bırakabiliyor.
        floors2 = [f for f in cluster_floors_2d(rooms, gap=TL["recluster_gap_m"] * upm) if len(f.rooms) >= TL["min_rooms"]]
        if floors2:
            # yeniden kümelemede: önceki seçimin etiketlerini içeren kümeyi koru
            prev = {id(rm) for rm in floor.rooms}
            same = [f for f in floors2 if any(id(rm) in prev for rm in f.rooms)]
            floor = max(same, key=lambda f: len(f.rooms)) if same else pick_plan_floor(floors2, upm)
            floor.index = 0
            stats["floors"] = [len(f.rooms) for f in floors2]
            sel.floors = floors2
    sel.floor, sel.upm = floor, upm
    # 3. kademe: içerik istatistiği (upm bilinince); bilinmeyen katmanlar text/dim/hatch/furniture/ignore olabilir
    refine_with_stats(names, layer_stats(doc, upm))
    n_ent = sum(layer_counts.values())
    try:
        n_blk = sum(len(b) for b in doc.blocks if not b.name.lower().startswith(("*model_space", "*paper_space")))
    except Exception:
        n_blk = 0
    stats["heavy"] = bool(n_ent >= HEAVY_ENTITIES or n_blk >= HEAVY_BLOCK_ENTITIES)
    return sel


def run_selected(dxf_path: str, sel: PlanSelection, *, max_cells: int = MAX_CELLS):
    """Seçilen kat için ölçekli parametreler + run_floor + v2 IR. (params, kat_v1, building_v2) döner."""
    floor, upm = sel.floor, sel.upm
    xs = [rm.label_xy[0] for rm in floor.rooms]; ys = [rm.label_xy[1] for rm in floor.rooms]
    p = scaled_params(upm)
    w = max(xs) - min(xs) + 2 * p["margin"]; h = max(ys) - min(ys) + 2 * p["margin"]
    cells = (w / p["res"]) * (h / p["res"])
    if cells > max_cells:
        p["res"] *= math.sqrt(cells / max_cells)
    doc = sel.doc if sel.doc is not None else ezdxf.readfile(dxf_path)
    b = BuildingIR(floors=[floor], source_path=dxf_path)
    b = run_floor(b, dxf_path, units_per_meter=upm, doc=doc, names=sel.names, **p)
    f = b.floors[0]
    # v2 çıktı: güven + kanıt (ir_compat). Koordinatlar çizim biriminde, ölçek params'ta.
    fp = sel.fingerprint
    extra = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
    extra["big_blocks"] = bool(getattr(f, "big_blocks", False))
    extra["family_id"] = sel.names.family_id
    extra["family_match"] = sel.names.match
    extra["layer_classes"] = sel.names.summary()
    extra["heavy"] = bool(sel.stats.get("heavy"))
    fparams = file_params(upm, sel.stats.get("upm_source", "labels"), extra)   # dosyadan türeyenler tek nesnede
    fparams.res = p["res"]                                                    # hücre sınırı düzeltmesi dahil
    fparams.wall_thickness_modes = list(getattr(f, "wall_thickness_modes", []) or [])
    b2 = to_v2(b, units_per_meter=upm, units_source=sel.stats.get("upm_source", "labels"),
               fingerprint=fp, file_params=fparams)
    b2.validation = validate_building_v2(b2, sel.names, sel.layer_counts)      # Adım 7 issue üretimi
    return p, f, b2


def run_file(dxf_path: str, *, max_cells: int = MAX_CELLS, overrides: dict | None = None):
    """Tek dosya, tek yol: select_plan + run_selected. ≥3 odalı kat kümesi yoksa ValueError."""
    sel = select_plan(dxf_path, overrides=overrides)
    if sel.floor is None:
        raise ValueError("≥3 odalı kat kümesi yok")
    return run_selected(dxf_path, sel, max_cells=max_cells)
