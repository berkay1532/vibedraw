#!/usr/bin/env python3
"""Pafta anlama taraması: her ADAY dosyada görünümleri ayır, sınıfla, dağılımı raporla.

Kullanım: python3 experiments/survey_views.py [--triage output/dataset_triage.json] [--out output/views_report.md]
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.perception.sheets import analyze_sheet


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--triage", default="output/dataset_triage.json")
    ap.add_argument("--results", default="output/baseline/results.json")
    ap.add_argument("--out", default="output/views_report.md")
    ap.add_argument("--only", default=None)
    a = ap.parse_args(argv)
    tri = json.loads(Path(a.triage).read_text(encoding="utf-8"))
    upms = {}
    if Path(a.results).exists():
        for r in json.loads(Path(a.results).read_text(encoding="utf-8")):
            upms[unicodedata.normalize("NFC", r["file"])] = r["stages"].get("labels_generic", {}).get("upm", 100.0)
    rows, kinds, conf = [], Counter(), Counter()
    L = ["# Pafta Anlama Raporu\n"]
    for p in tri["profiles"]:
        if p["verdict"] != "ADAY":
            continue
        name = Path(p["path"]).stem
        if a.only and not any(k in name for k in a.only.split(",")):
            continue
        upm = float(upms.get(unicodedata.normalize("NFC", name), 100.0) or 100.0)
        try:
            msp = ezdxf.readfile(p["path"]).modelspace()
            vs = analyze_sheet(msp, upm)
        except Exception as ex:
            L.append(f"## {name}\n- HATA: {ex}\n"); continue
        L.append(f"## {name}  (upm {upm:.0f}, {len(vs)} görünüm)\n")
        L.append("| # | tür | güven | kat | blok | ölçek | etiket | kapı yayı | entity | boyut (m) | başlık |")
        L.append("|---|---|---:|---|---|---|---:|---:|---:|---|---|")
        for v in vs:
            kinds[v.kind] += 1
            conf["yüksek" if v.confidence >= 0.7 else ("orta" if v.confidence >= 0.4 else "düşük")] += 1
            L.append(f"| {v.index} | {v.kind} | {v.confidence:.2f} | {v.floor_name or ''} | {v.block or ''} | {v.scale or ''} | "
                     f"{v.n_room_labels} | {v.n_door_arcs} | {v.n_entities} | {v.width/upm:.0f}×{v.height/upm:.0f} | {(v.title or '')[:40]} |")
        L.append("")
        print(f"{name[:40]:40s} görünüm={len(vs):2d} plan={sum(1 for v in vs if v.kind=='floor_plan')} "
              f"kesit={sum(1 for v in vs if v.kind=='section')} görünüş={sum(1 for v in vs if v.kind=='elevation')} "
              f"çatı={sum(1 for v in vs if v.kind=='roof_plan')} bilinmeyen={sum(1 for v in vs if v.kind=='unknown')}", flush=True)
    head = [f"- Görünüm türleri: {dict(kinds)}", f"- Güven: {dict(conf)}", ""]
    Path(a.out).write_text("\n".join(L[:1] + head + L[1:]) + "\n", encoding="utf-8")
    print("türler:", dict(kinds)); print("güven:", dict(conf)); print("→", a.out)


if __name__ == "__main__":
    main()
