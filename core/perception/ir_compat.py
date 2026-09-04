# core/perception/ir_compat.py
"""v1 (ir_v1) ↔ v2 (ir) köprüsü.

- `to_v2(building_v1, ...)`: pipeline içi v1 sonucunu v2 şemasına çevirir; güven değerleri
  tespitin KAYNAĞINDAN türetilir (docs/REFACTOR_PLAN.md Adım 2 tablosu + DECISIONS).
- `floor_v2_to_eval(floor_v2_dict)`: v2 JSON katını `evaluate.py` / `annotate.py` / araçların
  beklediği v1 benzeri sözlüğe indirger (rooms/doors/windows + confidence).
- `load_floor_for_eval(pred_json)`: sürümü tanır (v1 alan adları da desteklenir).
"""
from __future__ import annotations

import math
from typing import Optional

from core.perception.ir import (BuildingIR, Evidence, FileParams, Floor, Opening, Room,
                                ValidationReport, Wall)

# Adım 2 güven tablosu (kaba ama dürüst): kaynak → güven
DOOR_CONF = {"block+arc": 0.95, "arc": 0.75, "block": 0.7, "layer_raw": 0.4, "vlm": 0.8}
ROOM_CONF = {"exclusive": 0.85, "voronoi": 0.5, "alias_merge": 0.6, "edge_fragment": 0.4, "fallback": 0.2}
WALL_CONF = {"pair+layer": 0.9, "pair": 0.6}
WINDOW_CONF = {"layer": 0.85, "block_keyword": 0.85, "block_geometry": 0.7, "thin_lines": 0.3}  # thin_lines: 0/9 sahte (DECISIONS)


def _ev(source: str, conf: float, **signals) -> Evidence:
    sig = {k: v for k, v in signals.items()}
    sig.setdefault(source, conf)
    return Evidence(signals=sig, source=source)


def _poly_area(poly) -> float:
    if not poly or len(poly) < 3:
        return 0.0
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def to_v2(b1, units_per_meter: float = 100.0, units_source: str = "labels",
          fingerprint: str = "", params_extra: Optional[dict] = None,
          floor_names: Optional[dict] = None, file_params: Optional[FileParams] = None) -> BuildingIR:
    """v1 BuildingIR → v2 BuildingIR. Koordinatlar çizim biriminde kalır."""
    out = BuildingIR(source_path=getattr(b1, "source_path", "") or "", source_fingerprint=fingerprint)
    for f1 in b1.floors:
        params = file_params if file_params is not None else FileParams(
            units_per_meter=float(units_per_meter), units_source=units_source)
        params.extra = {**params.extra, **dict(params_extra or {})}
        fl = Floor(index=f1.index, name=(floor_names or {}).get(f1.index), params=params)
        # --- odalar
        id_by_room = {}
        for i, r in enumerate(f1.rooms):
            rid = f"r{i + 1}"
            id_by_room[id(r)] = rid
            src = getattr(r, "source", None) or ("exclusive" if r.geometry_ok else "fallback")
            if not r.polygon:
                src = "fallback"
            conf = ROOM_CONF.get(src, 0.5)
            poly = [(float(x), float(y)) for x, y in (r.polygon or [])]
            geom = _poly_area(poly) / (units_per_meter ** 2) if poly else None
            fl.rooms.append(Room(
                id=rid, confidence=conf, evidence=_ev(f"flood:{src}", conf),
                polygon=poly, raw_name=r.raw_name, room_type=r.room_type,
                area_m2_text=r.area_m2, area_m2_geom=(round(geom, 2) if geom is not None else None),
                aliases=list(getattr(r, "aliases", []) or []), alias_xy=[tuple(p) for p in (getattr(r, "alias_xy", []) or [])],
                label_xy=tuple(r.label_xy) if r.label_xy else None))
        # --- kapılar: room_name → aynı adlı odalardan menteşeye en yakın olanın id'si
        def room_id_for(name, xy):
            best, bd = None, None
            for r in f1.rooms:
                if (r.raw_name or "") != (name or ""):
                    continue
                ref = r.center or r.label_xy
                d = math.hypot(ref[0] - xy[0], ref[1] - xy[1]) if ref else 0.0
                if bd is None or d < bd:
                    best, bd = id_by_room[id(r)], d
            return best
        n_op = 0
        for d in f1.doors:
            n_op += 1
            src = getattr(d, "source", None) or "arc"
            conf = DOOR_CONF.get(src, 0.5)
            sig = dict(getattr(d, "signals", None) or {})
            if getattr(d, "confidence", None) is not None:      # Adım 6: scoring.score (weights.yaml)
                conf = float(d.confidence)
            hinge = (float(d.xy[0]), float(d.xy[1]))
            strike = tuple(map(float, d.strike_xy)) if getattr(d, "strike_xy", None) else None
            center = ((hinge[0] + strike[0]) / 2, (hinge[1] + strike[1]) / 2) if strike else hinge
            width = math.hypot(strike[0] - hinge[0], strike[1] - hinge[1]) if strike else None
            fl.openings.append(Opening(
                id=f"op{n_op}", confidence=conf, evidence=(Evidence(signals=sig, source=src) if sig else _ev(src, conf)), kind="door",
                center=center, width=width, hinge=hinge,
                rooms=(room_id_for(d.room_name, hinge) if d.room_name else None, None)))
        # --- pencereler
        wsrc = list(getattr(f1, "window_sources", []) or [])
        for i, w in enumerate(f1.windows):
            n_op += 1
            src = wsrc[i] if i < len(wsrc) else "layer"
            conf = WINDOW_CONF.get(src, 0.6)
            a, b = (float(w[0][0]), float(w[0][1])), (float(w[1][0]), float(w[1][1]))
            fl.openings.append(Opening(
                id=f"op{n_op}", confidence=conf, evidence=_ev(f"window:{src}", conf), kind="window",
                center=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), width=math.hypot(b[0] - a[0], b[1] - a[1])))
        # --- duvarlar (yüz parçaları)
        wsrcs = list(getattr(f1, "wall_sources", []) or [])
        wsig = list(getattr(f1, "wall_signals", []) or [])
        wthk = list(getattr(f1, "wall_thickness", []) or [])
        for i, (a, b) in enumerate(f1.walls):
            src = wsrcs[i] if i < len(wsrcs) else "pair"
            conf = WALL_CONF.get(src, 0.6)
            ev = _ev(src, conf)
            if i < len(wsig) and wsig[i] is not None:         # Adım 6: scoring.score (weights.yaml wall)
                conf, ev = wsig[i]
            thk = float(wthk[i]) if i < len(wthk) and wthk[i] is not None else None
            fl.walls.append(Wall(id=f"w{i + 1}", confidence=conf, evidence=ev, thickness=thk,
                                 a=(float(a[0]), float(a[1])), b=(float(b[0]), float(b[1]))))
        out.floors.append(fl)
    out.validation = ValidationReport()
    return out


def floor_v2_to_eval(fl: dict) -> dict:
    """v2 kat sözlüğü → v1 benzeri {rooms, doors, windows} (+ confidence alanları)."""
    id2name = {r["id"]: r.get("raw_name") for r in fl.get("rooms", [])}
    rooms = [{"raw_name": r.get("raw_name"), "polygon": r.get("polygon") or None,
              "label_xy": r.get("label_xy"), "geometry_ok": bool(r.get("polygon")),
              "confidence": r.get("confidence"), "source": (r.get("evidence") or {}).get("source"),
              "aliases": r.get("aliases", []), "room_type": r.get("room_type")} for r in fl.get("rooms", [])]
    doors, windows, win_conf = [], [], []
    for op in fl.get("openings", []):
        if op.get("kind") == "door":
            a, b = (op.get("rooms") or (None, None))[:2]
            doors.append({"xy": op.get("hinge") or op.get("center"), "room_name": id2name.get(a),
                          "room_name_2": id2name.get(b), "rooms": (a, b),
                          "confidence": op.get("confidence"), "source": (op.get("evidence") or {}).get("source"),
                          "strike_xy": None})
        elif op.get("kind") == "window":
            c, w = op.get("center"), op.get("width") or 0.0
            # yön bilgisi yok: orta noktadan simetrik yatay parça (ölçüm orta noktayı kullanır)
            windows.append([[c[0] - w / 2, c[1]], [c[0] + w / 2, c[1]]])
            win_conf.append({"confidence": op.get("confidence"), "source": (op.get("evidence") or {}).get("source")})
    walls = [[w["a"], w["b"]] for w in fl.get("walls", [])]
    return {"rooms": rooms, "doors": doors, "windows": windows, "window_meta": win_conf, "walls": walls,
            "big_blocks": (fl.get("params") or {}).get("extra", {}).get("big_blocks")}


def load_floor_for_eval(pred: dict, floor_index: int = 0) -> dict:
    """pred JSON (v1 veya v2) → ölçüm/araçların beklediği kat sözlüğü."""
    fl = pred["floors"][floor_index]
    if str(pred.get("version", "1")) == "2":
        return floor_v2_to_eval(fl)
    return fl
