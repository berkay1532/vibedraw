#!/usr/bin/env python3
"""HITL CLI (Adım 7, ilk sürüm): pred JSON'daki issue'ları önem sırasına göre gösterir, hedefin crop PNG'sini
üretir, seçenekleri basar; cevabı learning/log.py'ye (JSONL) yazar ve IR JSON'a uygular.

Kullanım:
  python3 hitl/cli.py output/baseline/<ad>.json --list
  python3 hitl/cli.py output/baseline/<ad>.json --issue 0                # crop PNG + soru
  python3 hitl/cli.py output/baseline/<ad>.json --issue 0 --answer kapı  # cevabı kaydet + IR'a uygula
Cevap IR'a uygulama: hedef elemanın `status` alanı human_confirmed / human_rejected, `data.answer` issue'da;
katman cevabı params.extra.hitl_layer_overrides, birim cevabı params.extra.hitl_units. "İlgili aşamadan
yeniden koş" henüz yok (aday: run_baseline --only ile yeniden koşu bu override'ları okur).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.perception.validate import PRIORITY  # noqa: E402
from learning import log as learning_log  # noqa: E402

CLASS_BY_ANSWER = {"duvar": "wall", "kapı": "door", "pencere": "window", "mobilya": "furniture", "yazı": "text",
                   "açıklama-yazı": "text", "yoksay": "ignore"}
UPM_BY_ANSWER = {"m": 1.0, "dm": 10.0, "cm": 100.0, "mm": 1000.0, "inç": 39.37}


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def issues(pred: dict) -> list[dict]:
    iss = list((pred.get("validation") or {}).get("issues") or [])
    iss.sort(key=lambda i: PRIORITY.index(i["kind"]) if i["kind"] in PRIORITY else len(PRIORITY))
    return iss


def _find(fl: dict, target_id: str):
    for r in fl.get("rooms", []):
        if r["id"] == target_id:
            return "room", r
    for o in fl.get("openings", []):
        if o["id"] == target_id:
            return "opening", o
    for w in fl.get("walls", []):
        if w["id"] == target_id:
            return "wall", w
    return None, None


def target_bbox(pred: dict, iss: dict, margin_m: float = 1.5):
    fl = pred["floors"][0]; upm = fl["params"]["units_per_meter"]
    tid = iss.get("target_id") or "file"
    kind, el = _find(fl, tid)
    if kind == "room" and el.get("polygon"):
        xs = [p[0] for p in el["polygon"]]; ys = [p[1] for p in el["polygon"]]
    elif kind == "opening":
        c = el.get("hinge") or el["center"]; xs, ys = [c[0]], [c[1]]
    elif kind == "wall":
        xs = [el["a"][0], el["b"][0]]; ys = [el["a"][1], el["b"][1]]
    else:                                                     # layer:* / file → tüm kat
        pts = [p for r in fl["rooms"] for p in (r.get("polygon") or ([r["label_xy"]] if r.get("label_xy") else []))]
        xs = [p[0] for p in pts] or [0.0]; ys = [p[1] for p in pts] or [0.0]
        margin_m = 3.0
    m = margin_m * upm
    return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m), kind, el


def render_crop(pred: dict, iss: dict, out_png: Path) -> Path:
    """Hedefin çevresi: DXF çizgileri gri, hedef kırmızı, diğer oda poligonları soluk, kapılar magenta."""
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    (x0, y0, x1, y1), kind, el = target_bbox(pred, iss)
    fl = pred["floors"][0]
    doc = ezdxf.readfile(pred["source_path"]); msp = doc.modelspace()
    layer_target = iss["target_id"][6:] if (iss.get("target_id") or "").startswith("layer:") else None
    fig, ax = plt.subplots(figsize=(10, max(4.0, 10 * (y1 - y0) / max(1e-6, x1 - x0))))

    def inb(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

    def draw(e, col, lw):
        t = e.dxftype()
        try:
            if t == "LINE":
                p, q = e.dxf.start, e.dxf.end
                if inb(p) or inb(q):
                    ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=lw)
            elif t in ("LWPOLYLINE", "ARC", "CIRCLE"):
                for ve in (list(e.virtual_entities()) if t == "LWPOLYLINE" else [e]):
                    vt = ve.dxftype()
                    if vt == "LINE":
                        p, q = ve.dxf.start, ve.dxf.end
                        if inb(p) or inb(q):
                            ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=lw)
                    elif vt in ("ARC", "CIRCLE"):
                        c = ve.dxf.center
                        if not inb(c):
                            continue
                        r = ve.dxf.radius
                        a0, a1 = ((math.radians(ve.dxf.start_angle), math.radians(ve.dxf.end_angle)) if vt == "ARC" else (0.0, 2 * math.pi))
                        if a1 < a0:
                            a1 += 2 * math.pi
                        P = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / 24), c[1] + r * math.sin(a0 + (a1 - a0) * k / 24)) for k in range(25)]
                        ax.plot([p[0] for p in P], [p[1] for p in P], color=col, lw=lw)
            elif t == "INSERT" and inb(e.dxf.insert):
                for ve in e.virtual_entities():
                    draw(ve, col, lw)
        except Exception:
            pass

    for e in msp:
        lay = getattr(e.dxf, "layer", "")
        if layer_target and lay == layer_target:
            draw(e, "red", 1.2)
        else:
            draw(e, "0.75", 0.4)
    for r in fl["rooms"]:
        if r.get("polygon"):
            P = r["polygon"] + [r["polygon"][0]]
            col = "red" if (kind == "room" and r is el) else "green"
            ax.plot([p[0] for p in P], [p[1] for p in P], color=col, lw=1.4 if col == "red" else 0.7, ls="--")
            if r.get("label_xy"):
                ax.text(r["label_xy"][0], r["label_xy"][1], r["raw_name"], fontsize=7)
    for o in fl["openings"]:
        c = o.get("hinge") or o["center"]
        if o["kind"] == "door":
            ax.plot(c[0], c[1], "o", mfc="none", mec=("red" if o is el else "magenta"), ms=(12 if o is el else 8), mew=1.5)
        elif o is el:
            ax.plot(c[0], c[1], "s", mfc="none", mec="red", ms=12, mew=1.5)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{iss['kind']} — {iss.get('target_id')}", fontsize=9)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=110, bbox_inches="tight"); plt.close(fig)
    return out_png


def apply_answer(pred: dict, iss: dict, answer: str) -> dict:
    """Cevabı IR'a uygular; learning kaydı için 'predicted' bilgisini döndürür."""
    fl = pred["floors"][0]; extra = fl["params"].setdefault("extra", {})
    kind, el = _find(fl, iss.get("target_id") or "")
    predicted = {"kind": iss["kind"]}
    if iss["kind"] in ("unknown_layer", "conflicting_layer"):
        layer = iss["target_id"][6:]
        extra.setdefault("hitl_layer_overrides", {})[layer] = CLASS_BY_ANSWER.get(answer, answer)
        predicted["layer_class"] = iss.get("data", {}).get("class_vote", "unknown")
    elif iss["kind"] == "unit_suspect":
        extra["hitl_units"] = {"answer": answer, "upm": UPM_BY_ANSWER.get(answer)}
        predicted["upm"] = fl["params"]["units_per_meter"]
    elif el is not None:
        confirms = {"room_no_door": {"kapı eksik", "açık geçiş", "sürgülü kapı"}, "ambiguous_opening": {el.get("kind") == "door" and "kapı" or "pencere"},
                    "open_room": set(), "area_mismatch": {"geometri"}}.get(iss["kind"], set())
        el["status"] = "human_confirmed" if answer in confirms else "human_rejected"
        el.setdefault("hitl", {})["answer"] = answer
        predicted["confidence"] = el.get("confidence"); predicted["source"] = (el.get("evidence") or {}).get("source")
    iss.setdefault("data", {})["answer"] = answer
    return predicted


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pred"); ap.add_argument("--list", action="store_true")
    ap.add_argument("--issue", type=int, default=None); ap.add_argument("--answer", default=None)
    ap.add_argument("--png", default=None, help="crop PNG yolu (varsayılan output/hitl/<ad>/<i>_<tip>.png)")
    ap.add_argument("--no-write", action="store_true", help="IR JSON'u ve learning log'u yazma")
    a = ap.parse_args(argv)
    pred = load(Path(a.pred)); iss = issues(pred); stem = Path(a.pred).stem
    if a.list or a.issue is None:
        print(f"{stem}: {len(iss)} issue (hedef ≤ 5/dosya)")
        for i, it in enumerate(iss):
            print(f"  [{i}] {it['kind']:18s} {str(it.get('target_id')):24s} {it['message'][:90]}")
        return 0
    it = iss[a.issue]
    png = Path(a.png) if a.png else ROOT / "output" / "hitl" / stem / f"{a.issue}_{it['kind']}.png"
    render_crop(pred, it, png)
    print(f"[{a.issue}] {it['kind']} — {it.get('target_id')}\n{it['message']}\nPNG: {png}\nSeçenekler: " + " / ".join(it["options"]))
    ans = a.answer
    if ans is None and sys.stdin.isatty():
        ans = input("Cevap (boş = atla): ").strip() or None
    if ans is None:
        print("atlandı"); return 0
    if ans not in it["options"]:
        print(f"UYARI: '{ans}' seçeneklerde yok, serbest metin olarak kaydediliyor")
    predicted = apply_answer(pred, it, ans)
    rec = {"file": stem, "fingerprint": pred.get("source_fingerprint", ""), "issue": it["kind"], "target_id": it.get("target_id"),
           "signals": (_find(pred["floors"][0], it.get("target_id") or "")[1] or {}).get("evidence", {}).get("signals", {}),
           "predicted": predicted, "answer": ans, "answered_by": "human", "skipped": False}
    if not a.no_write:
        p = learning_log.append(rec)
        Path(a.pred).write_text(json.dumps(pred, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"kaydedildi → {p}; IR güncellendi ({a.pred})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
