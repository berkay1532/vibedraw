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
from core.perception.calibration import estimate_units_from_doors, estimate_units_per_meter, scaled_params
from core.perception.ir_compat import to_v2
from core.perception.parse import (cluster_floors_2d, dedupe_labels, extract_room_labels, grid_likeness,
                                   pick_plan_floor)
from core.perception.triage import layer_fingerprint
from core.perception.openings import _cluster_doors, _door_barriers, _seg_dist, _swing_dirs
from core.perception.polygons import _mask_polygon
from core.perception.raster import _Raster
from core.perception.rooms import _floor_bbox, _segment_rooms
from core.perception.walls import _wall_lines, _wall_segments
from core.perception.windows import _window_segments


def run_floor(building: BuildingIR, dxf_path: str, *,
                res: float = 1.0, seal: int = 8, margin: float = 25.0,
                leak_fraction: float = 0.45, door_max_boundary_dist: float = 15.0,
                vlm_door_points: list | None = None,
                door_arc_radius: tuple = (50.0, 130.0),
                door_wall_dist: float = 25.0,
                units_per_meter: float | None = None) -> BuildingIR:
    """M1 giriş noktası: her kat için oda merkezi/poligonu doldur, kapıları tespit et.

    geometry_ok=False olan odalar (sızma/boş) için center=label_xy fallback uygulanır.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    for floor in building.floors:
        if not floor.rooms:
            continue
        bbox = _floor_bbox(floor, margin)
        # Katman-bağımsız duvar/pencere tespiti ÖNCE: raster bariyeri bunlardan da beslenir.
        if units_per_meter:   # duvar kalınlığı 4-45 cm, boyuna örtüşme ≥18 cm (metre-tabanlı)
            # tmin 6 cm: 4 cm'lik "duvar" yapıda yok (duş kabini camı, cam bölme, çift çizgi
            # kaplama 2-4 cm → duvar sayılmaz); en ince bölme duvarı 7-8 cm.
            wk = dict(tmin=0.06 * units_per_meter, tmax=0.45 * units_per_meter,
                      min_overlap=0.18 * units_per_meter)
        else:
            wk = {}
        label_pts = [rm.label_xy for rm in floor.rooms]
        wk["label_pts"] = label_pts
        floor.walls, floor.wall_sources = _wall_segments(msp, bbox, min_len=8.0 * res, with_sources=True, **wk)
        # ADAPTİF: modelspace'te oda başına <8 duvar parçası bulunduysa plan büyük ihtimalle
        # BLOK içinde yerleştirilmiş → ≥3 m'lik blokların içine de bakılır.
        # (Koşulsuz açmak Revit export'larında sahte duvar üretip IoU'yu düşürdü.)
        big = False
        if len(floor.walls) < 8 * len(floor.rooms):
            walls_b, srcs_b = _wall_segments(msp, bbox, min_len=8.0 * res, big_blocks=True, with_sources=True, **wk)
            if len(walls_b) > len(floor.walls):
                floor.walls, floor.wall_sources = walls_b, srcs_b
                big = True
        floor.big_blocks = big
        floor.windows, floor.window_sources = _window_segments(
            msp, bbox, min_len=8.0 * res, upm=units_per_meter, walls=floor.walls, big_blocks=big,
            with_sources=True)
        # Kapı yayları (katman-bağımsız) → kapalı kanat bariyeri: açıklık mühürlenir,
        # böylece genel mühür küçük tutulabilir (dar odalar/WC kaybolmaz).
        amin, amax = door_arc_radius
        swing = _swing_dirs(msp, bbox, amin, amax, big_blocks=big)
        barriers = _door_barriers(swing, floor.walls)
        extra = floor.walls + floor.windows + barriers
        seal_small = max(3, int(round(0.25 * units_per_meter / res))) if units_per_meter else max(3, seal // 2)
        seals = sorted({seal_small, seal})
        rasters = [_Raster(msp, bbox, res, sl, extra_segs=extra, door_arc_radius=door_arc_radius, big_blocks=big)
                   for sl in seals]
        raster = rasters[-1]                      # kapı adayları vb. için (büyük mühür = tam bariyer)
        seed_rad = int(round(0.7 * units_per_meter / res)) if units_per_meter else 12
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
            msp, bbox, angled_min_len=15.0 * res, cluster_tol=3.0 * res, extra_segs=floor.walls)

        for room in floor.rooms:
            idx = next((i for i, r in idx_room.items() if r is room), None)
            if idx is None or int(recovered[idx].sum()) < 30:
                # Fallback: güvenilir geometri yok, etiket noktasını kullan.
                room.geometry_ok = False
                room.center = room.label_xy
                room.polygon = None
                room.source = "fallback"
                continue
            room.source = room_sources.get(idx, "exclusive")
            mask = recovered[idx]
            ys, xs = np.where(mask)
            cx, cy = raster.to_world(float(xs.mean()), float(ys.mean()))
            room.geometry_ok = True
            room.center = (cx, cy)
            room.polygon = _mask_polygon(mask, raster, wall_xs, wall_ys, angled_walls)

        # Kapı konumlarını belirle:
        #  - vlm_door_points verildiyse: adayları VLM kapılarıyla DOĞRULA (manuel/VLM mod)
        #  - verilmediyse: deterministik filtre (oda sınırına uzak sahteleri ele)
        from shapely.geometry import Polygon as _P, Point as _Pt
        room_polys = [(r, _P(r.polygon).buffer(0))
                      for r in floor.rooms if r.polygon]
        # Kapı adayları: kapı BLOKLARI (kesin) + kapı-genişliği YAYLARI (kesin).
        # İkisi de yeterince yoksa ham kapı-katmanı kümelemesine düş.
        swing_arcs = [(x, y) for (x, y, rr) in raster.arcs if amin <= rr <= amax]
        primary = list(raster.door_blocks) + swing_arcs
        used_primary = len(primary) >= 2
        cand_src: dict = {}                       # aday merkezi → kaynak (block+arc | arc | block | layer_raw)
        if used_primary:
            tagged = _cluster_doors(primary, radius=max(20.0, amin * 0.5),
                                    tags=["block"] * len(raster.door_blocks) + ["arc"] * len(swing_arcs))
            candidates = [c for c, _ in tagged]
            for c, t in tagged:
                cand_src[c] = "block+arc" if t == {"block", "arc"} else next(iter(t))
        else:
            candidates = _cluster_doors(raster.door_raw)
            cand_src = {c: "layer_raw" for c in candidates}

        if vlm_door_points:
            from core.perception.vlm_doors import validate_doors
            # tol=10: yalnızca çok yakın aday varsa ince-ayar snap; yoksa VLM noktası korunur
            door_pts = validate_doors(candidates, vlm_door_points, tol=10.0)
        elif used_primary:
            # Blok + yay = yüksek güven; gürültü filtresi gerekmez.
            door_pts = candidates
        else:
            # Fallback (ham kapı-katmanı): oda sınırına uzak sahteleri ele.
            door_pts = []
            for (dx, dy) in candidates:
                if room_polys:
                    bd = min(poly.exterior.distance(_Pt(dx, dy))
                             for _, poly in room_polys)
                    if bd > door_max_boundary_dist:
                        continue
                door_pts.append((dx, dy))

        # Fikstür yaylarını (klozet/lavabo vb.) ELE: gerçek kapı menteşesi bir DUVARIN
        # üstündedir (~5-10 br); fikstür yayı merkezi oda ortasında (>30 br). Geniş
        # margin'de bbox'a giren fikstürlerin sahte-kapı olmasını engeller.
        def _dist_walls(p):
            best = float("inf")
            for a, b in floor.walls:
                ax, ay = a
                ex, ey = b[0] - a[0], b[1] - a[1]
                L2 = ex * ex + ey * ey or 1.0
                t = max(0.0, min(1.0, ((p[0] - ax) * ex + (p[1] - ay) * ey) / L2))
                d = math.hypot(ax + t * ex - p[0], ay + t * ey - p[1])
                if d < best:
                    best = d
            return best
        if floor.walls:   # duvar yoksa filtre uygulanmaz (_dist_walls yine tanımlı: inf döner)
            door_pts = [p for p in door_pts if _dist_walls(p) <= door_wall_dist]

        # Kapı = menteşe (blok matrix44 / yay merkezi). Standart: tüm kapılar menteşede.
        # room_name = AÇILIŞ YAYI YÖNÜ ile (etiket-mesafesi değil): menteşeye en yakın
        # yayı bul, bisektör yönündeki odayı seç. Yay eşleşmezse merkez-mesafesi fallback.
        floor.doors = []
        for (dx, dy) in door_pts:
            sd = min(swing, key=lambda s: math.hypot(s[0][0] - dx, s[0][1] - dy),
                     default=None)
            room, strike = None, None
            if sd is not None and math.hypot(sd[0][0] - dx, sd[0][1] - dy) <= door_wall_dist * 1.6:
                room = _room_by_swing((dx, dy), sd[1], floor.rooms)
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
            floor.doors.append(Door(xy=(dx, dy), source=cand_src.get((dx, dy), "vlm" if vlm_door_points else None),
                                    room_name=room.raw_name if room else None,
                                    strike_xy=strike))

    return building


# --- Plan seçimi ve dosya koşusu -------------------------------------------------------
MAX_CELLS = 30_000_000   # raster hücre üst sınırı; aşılırsa res büyütülür (config/ adayı, Adım 6)


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


def label_floors(dxf_path: str, gap: float) -> list[Floor]:
    """Yardımcı (test/araç): etiket → ad↔alan → 2B kümeleme. Ölçek tahmini ve plan seçimi yok."""
    return cluster_floors_2d(pair_names_with_areas(extract_room_labels(dxf_path)), gap=gap)


def select_plan(dxf_path: str) -> PlanSelection:
    """Genel etiket çıkarımı + ölçek + kat seçimi (tek yol)."""
    labels = extract_room_labels(dxf_path)
    upm0 = estimate_units_per_meter(labels)
    labels = dedupe_labels(labels, tol=0.5 * upm0)      # 50 cm içindeki tekrarlar
    upm = estimate_units_per_meter(labels)
    rooms = pair_names_with_areas(labels)
    floors = cluster_floors_2d(rooms, gap=7.0 * upm)    # 7 m'den yakın etiketler aynı çizim
    floors = [f for f in floors if len(f.rooms) >= 3]
    stats = {"labels": len(labels), "rooms": len(rooms), "upm": round(upm, 1),
             "floors": [len(f.rooms) for f in floors]}
    sel = PlanSelection(labels=labels, rooms=rooms, floors=floors, upm=upm, stats=stats)
    if not floors:
        return sel
    floor = pick_plan_floor(floors, upm); floor.index = 0
    stats["grid"] = [round(grid_likeness(f.rooms, 0.3 * upm), 2) for f in floors]
    # Kapı-yayı kanıtı: mahal listesi tabloları (döndürülmüş olsa bile) kapı yayı içermez.
    # Kapı yayı bulunan en kalabalık kümeyi tercih et.
    with_doors = []
    for f in sorted(floors, key=lambda f: -len(f.rooms))[:8]:
        if len(f.rooms) < 3:
            continue
        if estimate_units_from_doors(dxf_path, _floor_bbox(f, 2.5 * upm), upm) is not None:
            with_doors.append(f)
    if with_doors and floor not in with_doors:
        floor = with_doors[0]; floor.index = 0
        stats["pick"] = "doors"
    # Ölçeği kapı yaylarından düzelt (etiket-mesafesi tahmini kaba)
    upm_doors = estimate_units_from_doors(dxf_path, _floor_bbox(floor, 2.5 * upm), upm)
    stats["upm_labels"] = round(upm, 1)
    if upm_doors and 0.25 * upm <= upm_doors <= 4.0 * upm:   # etiket öncülü kaba; kapı kümesi güçlü kanıt
        upm = upm_doors
        stats["upm"] = round(upm, 1)
        stats["upm_source"] = "doors"
        # Düzeltilmiş ölçekle YENİDEN kümele: kaba ölçekle 7 m eşiği büyük salon
        # etiketini kümenin dışında bırakabiliyor.
        floors2 = [f for f in cluster_floors_2d(rooms, gap=8.0 * upm) if len(f.rooms) >= 3]
        if floors2:
            # yeniden kümelemede: önceki seçimin etiketlerini içeren kümeyi koru
            prev = {id(rm) for rm in floor.rooms}
            same = [f for f in floors2 if any(id(rm) in prev for rm in f.rooms)]
            floor = max(same, key=lambda f: len(f.rooms)) if same else pick_plan_floor(floors2, upm)
            floor.index = 0
            stats["floors"] = [len(f.rooms) for f in floors2]
            sel.floors = floors2
    sel.floor, sel.upm = floor, upm
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
    b = BuildingIR(floors=[floor], source_path=dxf_path)
    b = run_floor(b, dxf_path, units_per_meter=upm, **p)
    f = b.floors[0]
    # v2 çıktı: güven + kanıt (ir_compat). Koordinatlar çizim biriminde, ölçek params'ta.
    try:
        fp = layer_fingerprint(l.dxf.name for l in ezdxf.readfile(dxf_path).layers)
    except Exception:
        fp = ""
    extra = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
    extra["big_blocks"] = bool(getattr(f, "big_blocks", False))
    b2 = to_v2(b, units_per_meter=upm, units_source=sel.stats.get("upm_source", "labels"),
               fingerprint=fp, params_extra=extra)
    return p, f, b2


def run_file(dxf_path: str, *, max_cells: int = MAX_CELLS):
    """Tek dosya, tek yol: select_plan + run_selected. ≥3 odalı kat kümesi yoksa ValueError."""
    sel = select_plan(dxf_path)
    if sel.floor is None:
        raise ValueError("≥3 odalı kat kümesi yok")
    return run_selected(dxf_path, sel, max_cells=max_cells)
