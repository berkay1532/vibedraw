# core/metrics.py
"""Building IR ölçümü: ground truth (data/ground_truth/<ad>.json) ↔ pipeline çıktısı
(output/baseline/<ad>.json). Saf fonksiyonlar; CLI için evaluate.py.

Ground truth şeması:
{
  "source": "...dxf", "units_per_meter": 73.1,
  "floor": {
    "rooms":   [{"id":"r1","name":"SALON","type":"living","polygon":[[x,y],...]}],
    "doors":   [{"id":"d1","hinge":[x,y],"width":90,"connects":["r1","r2"|"outside"]}],
    "windows": [{"a":[x,y],"b":[x,y]}],
    "walls":   [{"a":[x,y],"b":[x,y]}]          # isteğe bağlı
  },
  "meta": {"status":"draft|verified","note":""}
}
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from shapely.geometry import Point, Polygon

from core.perception.vocab import fold


_AREA_SUFFIX = re.compile(r"A\s*[:=]?\s*\d+(?:[.,]\d+)?\s*m\s*[²2]", re.IGNORECASE)


def _tr_fold(s: str) -> str:
    """Ad karşılaştırması: vocab.fold + alan eki ("A:6.60 M²") ve fazla boşluk atılır."""
    s = _AREA_SUFFIX.sub("", s or "")
    return " ".join(fold(s).split()).strip(" -")


def _poly(pts):
    try:
        p = Polygon([(float(x), float(y)) for x, y in pts])
        if not p.is_valid:
            p = p.buffer(0)
        return p if not p.is_empty else None
    except Exception:
        return None


def room_iou(a, b) -> float:
    pa, pb = _poly(a), _poly(b)
    if pa is None or pb is None:
        return 0.0
    u = pa.union(pb).area
    return pa.intersection(pb).area / u if u > 0 else 0.0


@dataclass
class Match:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    pairs: list = field(default_factory=list)      # (gt_idx, pred_idx, score)
    name_acc: float | None = None
    mean_iou: float | None = None
    mean_err: float | None = None

    @property
    def precision(self):
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self):
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self):
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _greedy(scores, better):
    """scores: [(gt_i, pred_j, s)] → eşleşme listesi; her gt/pred en fazla bir kez."""
    used_g, used_p, out = set(), set(), []
    for gi, pj, s in sorted(scores, key=better):
        if gi in used_g or pj in used_p:
            continue
        used_g.add(gi); used_p.add(pj); out.append((gi, pj, s))
    return out


def match_rooms(gt_rooms, pred_rooms, iou_thr=0.5) -> Match:
    cands = []
    for i, g in enumerate(gt_rooms):
        for j, p in enumerate(pred_rooms):
            if not p.get("polygon"):
                continue
            iou = room_iou(g["polygon"], p["polygon"])
            if iou >= iou_thr:
                cands.append((i, j, iou))
    pairs = _greedy(cands, better=lambda t: -t[2])
    m = Match(tp=len(pairs), fp=len(pred_rooms) - len(pairs), fn=len(gt_rooms) - len(pairs), pairs=pairs)
    if pairs:
        m.mean_iou = sum(s for _, _, s in pairs) / len(pairs)
        ok = sum(1 for gi, pj, _ in pairs
                 if _tr_fold(gt_rooms[gi].get("name")) == _tr_fold(pred_rooms[pj].get("raw_name")))
        m.name_acc = ok / len(pairs)
    return m


def match_points(gt_items, pred_items, gt_key, pred_key, tol) -> Match:
    cands = []
    for i, g in enumerate(gt_items):
        gx, gy = g[gt_key]
        for j, p in enumerate(pred_items):
            px, py = p[pred_key]
            d = math.hypot(gx - px, gy - py)
            if d <= tol:
                cands.append((i, j, d))
    pairs = _greedy(cands, better=lambda t: t[2])
    m = Match(tp=len(pairs), fp=len(pred_items) - len(pairs), fn=len(gt_items) - len(pairs), pairs=pairs)
    if pairs:
        m.mean_err = sum(s for _, _, s in pairs) / len(pairs)
    return m


def _mid(seg):
    (ax, ay), (bx, by) = seg
    return [(ax + bx) / 2, (ay + by) / 2]


def evaluate_floor(gt: dict, pred: dict, iou_thr=0.5, door_tol_m=0.5, window_tol_m=0.6) -> dict:
    """gt: ground truth dosyası (dict); pred: pipeline Floor dict'i (rooms/doors/windows)."""
    upm = float(gt.get("units_per_meter") or 100.0)
    gf = gt["floor"]
    gt_rooms, pr_rooms = gf.get("rooms", []), pred.get("rooms", [])
    rm = match_rooms(gt_rooms, pr_rooms, iou_thr)

    # Kapılar: konum + bağlantı. Tahmin edilen kapının room_name'i, GT kapının
    # bağladığı odalardan birinin adıyla eşleşiyorsa bağlantı doğru sayılır.
    gt_doors, pr_doors = gf.get("doors", []), pred.get("doors", [])
    dm = match_points(gt_doors, pr_doors, "hinge", "xy", tol=door_tol_m * upm)
    id2name = {r.get("id"): r.get("name") for r in gt_rooms}
    conn_ok = 0
    for gi, pj, _ in dm.pairs:
        names = {_tr_fold(id2name.get(c, c)) for c in gt_doors[gi].get("connects", [])}
        if _tr_fold(pr_doors[pj].get("room_name")) in names:
            conn_ok += 1
    connect_acc = conn_ok / dm.tp if dm.tp else None

    gt_win = [{"m": _mid((w["a"], w["b"]))} for w in gf.get("windows", [])]
    pr_win = [{"m": _mid(w)} for w in pred.get("windows", [])]
    wm = match_points(gt_win, pr_win, "m", "m", tol=window_tol_m * upm)

    # Çift doğruluğu (v2 rooms=(a,b)): iki oda da tahminde varsa GT connects kümesiyle karşılaştır.
    # Yalnız raporlanır; GT'de ikinci oda alanı olana kadar çoğunlukla boş kalır (DECISIONS).
    pair_n = pair_ok = 0
    for gi, pj, _ in dm.pairs:
        p = pr_doors[pj]
        n2 = p.get("room_name_2")
        if p.get("room_name") and n2:
            pair_n += 1
            names = {_tr_fold(id2name.get(c, c)) for c in gt_doors[gi].get("connects", [])}
            if {_tr_fold(p["room_name"]), _tr_fold(n2)} <= names:
                pair_ok += 1
    pair_acc = pair_ok / pair_n if pair_n else None

    # Güven kalibrasyonu için: her tahminin (güven, eşleşti mi) çifti
    def _cal(items, pairs, key="confidence"):
        matched = {pj for _, pj, _ in pairs}
        return [(it.get(key), j in matched) for j, it in enumerate(items) if it.get(key) is not None]
    win_meta = pred.get("window_meta") or []
    calibration = {
        "rooms": _cal(pr_rooms, rm.pairs),
        "doors": _cal(pr_doors, dm.pairs),
        "windows": [(m.get("confidence"), j in {pj for _, pj, _ in wm.pairs}) for j, m in enumerate(win_meta)
                    if m.get("confidence") is not None],
        "sources": {"rooms": [(r.get("source"), j in {pj for _, pj, _ in rm.pairs}) for j, r in enumerate(pr_rooms) if r.get("source")],
                    "doors": [(d.get("source"), j in {pj for _, pj, _ in dm.pairs}) for j, d in enumerate(pr_doors) if d.get("source")],
                    "windows": [(m.get("source"), j in {pj for _, pj, _ in wm.pairs}) for j, m in enumerate(win_meta) if m.get("source")]},
    }

    def block(m: Match, **extra):
        d = {"tp": m.tp, "fp": m.fp, "fn": m.fn, "precision": round(m.precision, 3),
             "recall": round(m.recall, 3), "f1": round(m.f1, 3)}
        d.update(extra)
        return d

    errors = {
        "room_fp": [j for j in range(len(pr_rooms)) if j not in {pj for _, pj, _ in rm.pairs}],
        "room_fn": [i for i in range(len(gt_rooms)) if i not in {gi for gi, _, _ in rm.pairs}],
        "room_name": [pj for gi, pj, _ in rm.pairs if _tr_fold(gt_rooms[gi].get("name")) != _tr_fold(pr_rooms[pj].get("raw_name"))],
        "door_fp": [j for j in range(len(pr_doors)) if j not in {pj for _, pj, _ in dm.pairs}],
        "door_fn": [i for i in range(len(gt_doors)) if i not in {gi for gi, _, _ in dm.pairs}],
        "door_connect": [pj for gi, pj, _ in dm.pairs
                         if _tr_fold(pr_doors[pj].get("room_name")) not in {_tr_fold(id2name.get(c, c)) for c in gt_doors[gi].get("connects", [])}],
        "window_fp": [j for j in range(len(pr_win)) if j not in {pj for _, pj, _ in wm.pairs}],
        "window_fn": [i for i in range(len(gt_win)) if i not in {gi for gi, _, _ in wm.pairs}],
    }
    return {
        "errors": errors,
        "rooms": block(rm, mean_iou=(round(rm.mean_iou, 3) if rm.mean_iou is not None else None),
                       name_acc=(round(rm.name_acc, 3) if rm.name_acc is not None else None)),
        "doors": block(dm, mean_err_m=(round(dm.mean_err / upm, 3) if dm.mean_err is not None else None),
                       connect_acc=(round(connect_acc, 3) if connect_acc is not None else None),
                       pair_acc=(round(pair_acc, 3) if pair_acc is not None else None), pair_n=pair_n),
        "windows": block(wm, mean_err_m=(round(wm.mean_err / upm, 3) if wm.mean_err is not None else None)),
        "calibration": calibration,
    }


# --- Issue kapsama (Adım 7 politika ölçütü) ---------------------------------------------------
ROOM_ISSUES = {"open_room", "room_no_door", "area_mismatch"}


def _issue_targets(issues) -> dict:
    """target_id → issue tipleri; toplu issue'larda data.targets de açılır."""
    out: dict = {}
    for i in issues:
        kinds = out.setdefault(i.get("target_id"), set()); kinds.add(i.get("kind"))
        for t in (i.get("data") or {}).get("targets") or []:
            out.setdefault(t, set()).add(i.get("kind"))
    return out


def _room_containing(pt, rooms, upm):
    best = None
    for r in rooms:
        if not r.get("polygon"):
            continue
        try:
            P = Polygon([(float(x), float(y)) for x, y in r["polygon"]]).buffer(0)
        except Exception:
            continue
        if P.buffer(0.5 * upm).contains(Point(pt[0], pt[1])):
            return r
    return best


def issue_coverage(gt: dict, pred: dict, issues: list, errors: dict) -> dict:
    """GT-7 hata varlıkları için "onu işaret eden issue var mı": tip → (kapsanan, toplam).

    Kurallar: FP oda/kapı/pencere → o tahmine hedefli issue (toplu issue'larda data.targets); FN oda → GT
    odayı içeren tahmin odasına hedefli oda issue'su; FN kapı/pencere → GT konumunu içeren tahmin odasına
    issue (room_no_door / toplu ambiguous_opening); yanlış ad ve yanlış bağlantı → kapsanmaz (issue tipi yok)."""
    from shapely.geometry import Point  # noqa: F401 (yerel kullanım)
    upm = float(gt.get("units_per_meter") or 100.0)
    gf = gt["floor"]; pr_rooms = pred.get("rooms", []); pr_doors = pred.get("doors", []); win_meta = pred.get("window_meta") or []
    tg = _issue_targets(issues)
    cov: dict = {}

    def add(kind, ok):
        c, t = cov.get(kind, (0, 0)); cov[kind] = (c + (1 if ok else 0), t + 1)

    for j in errors["room_fp"]:
        add("room_fp", bool(tg.get(pr_rooms[j].get("id"), set()) & ROOM_ISSUES))
    for i in errors["room_fn"]:
        g = gf["rooms"][i]; poly = g.get("polygon") or []
        c = ([sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)] if poly else None)
        r = _room_containing(c, pr_rooms, upm) if c else None
        add("room_fn", bool(r and tg.get(r.get("id"), set()) & ROOM_ISSUES))
    for j in errors["door_fp"]:
        add("door_fp", "ambiguous_opening" in tg.get(pr_doors[j].get("id"), set()))
    for i in errors["door_fn"]:
        r = _room_containing(gf["doors"][i]["hinge"], pr_rooms, upm)
        add("door_fn", bool(r and tg.get(r.get("id"), set()) & {"room_no_door", "open_room", "ambiguous_opening"}))
    for j in errors["window_fp"]:
        wid = win_meta[j].get("id") if j < len(win_meta) else None
        add("window_fp", "ambiguous_opening" in tg.get(wid, set()))
    for i in errors["window_fn"]:
        w = gf["windows"][i]; m = _mid((w["a"], w["b"]))
        r = _room_containing(m, pr_rooms, upm)
        add("window_fn", bool(r and tg.get(r.get("id"), set()) & {"ambiguous_opening", "open_room"}))
    for j in errors["room_name"]:
        add("room_name", False)
    for j in errors["door_connect"]:
        add("door_connect", False)
    return cov
