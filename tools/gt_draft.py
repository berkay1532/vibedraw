#!/usr/bin/env python3
"""Tahminden GT taslağı (mevcut GT şeması) ya da boş şablon.

Kullanım: python3 tools/gt_draft.py <ad> [--pred output/src02] [--upm 100] [--tier typical] [--holdout] [--source src02] [--empty]
Çıktı: data/ground_truth/<ad>.draft.json  (evaluate .draft.json'u OKUMAZ; tools/gt_check.py --finalize ile <ad>.json olur)
Şema: {source, units_per_meter, floor:{rooms:[{id,name,type,polygon}], doors:[{id,hinge,width,connects}], windows:[{a,b}]}, meta}
Pencereler tahminde yalnız merkez+genişlik taşır → taslakta YATAY parça; dikey pencereleri elle çevir.
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import argparse, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("name"); ap.add_argument("--pred", default="output/src02")
    ap.add_argument("--upm", type=float, default=None, help="GT birimi (varsayılan: tahmin upm'i; unit_suspect ise elle ver)")
    ap.add_argument("--tier", default="typical"); ap.add_argument("--holdout", action="store_true"); ap.add_argument("--source", default="src02")
    ap.add_argument("--empty", action="store_true", help="tahmin gösterme: boş şablon (holdout)"); a = ap.parse_args()
    pj = json.load(open(f"{a.pred}/{a.name}.json")); fl = pj["floors"][0]
    upm = a.upm or fl["params"]["units_per_meter"]
    if a.empty:
        rooms, doors, wins = [], [], []
    else:
        def poly(pts):                          # tahmin poligonu kapatma noktasını tekrarlayabilir; GT'de yazılmaz
            pts = [list(p) for p in (pts or [])]
            return pts[:-1] if len(pts) > 3 and pts[0] == pts[-1] else pts
        rooms = [{"id": r["id"], "name": r["raw_name"], "type": r.get("room_type") or "", "polygon": poly(r["polygon"])} for r in fl["rooms"]]
        doors = [{"id": o["id"], "hinge": list(o["hinge"] or o["center"]), "width": o.get("width"), "connects": [x for x in (o.get("rooms") or []) if x]}
                 for o in fl["openings"] if o["kind"] == "door"]
        wins = [{"a": [o["center"][0] - (o.get("width") or 0) / 2, o["center"][1]], "b": [o["center"][0] + (o.get("width") or 0) / 2, o["center"][1]]}
                for o in fl["openings"] if o["kind"] == "window"]
    gt = {"source": pj["source_path"], "units_per_meter": upm, "floor": {"rooms": rooms, "doors": doors, "windows": wins},
          "meta": {"status": "draft", "tool": "gt_draft.py" if not a.empty else "empty-template", "tier": a.tier, "holdout": a.holdout,
                   "source": a.source, "pred_upm": fl["params"]["units_per_meter"], "pred_upm_source": fl["params"]["units_source"], "note": ""}}
    out = Path("data/ground_truth") / f"{a.name}.draft.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}: oda {len(rooms)} kapı {len(doors)} pencere {len(wins)} upm {upm}")


if __name__ == "__main__":
    main()
