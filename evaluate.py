#!/usr/bin/env python3
"""Ground truth ↔ pipeline çıktısı ölçümü.

Kullanım: python3 evaluate.py [--gt data/ground_truth] [--pred output/baseline] [--out output/eval_report.md]
Her GT dosyası için aynı adlı pred JSON'u (floors[0]) alınır; per-dosya + toplam tablo yazılır.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core.perception.metrics import evaluate_floor
from core.perception.ir_compat import load_floor_for_eval


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default="data/ground_truth")
    ap.add_argument("--pred", default="output/baseline")
    ap.add_argument("--out", default="output/eval_report.md")
    args = ap.parse_args(argv)
    rows, agg = [], {"rooms": [0, 0, 0], "doors": [0, 0, 0], "windows": [0, 0, 0]}
    ious, names, derr, conn = [], [], [], []
    cal = {"rooms": [], "doors": [], "windows": []}
    cal_src = {"rooms": [], "doors": [], "windows": []}
    pair_acc = []
    for gp in sorted(Path(args.gt).glob("*.json")):
        gt = json.loads(gp.read_text(encoding="utf-8"))
        pp = Path(args.pred) / gp.name
        if not pp.exists():
            rows.append((gp.stem, None)); continue
        pred = load_floor_for_eval(json.loads(pp.read_text(encoding="utf-8")))   # v1 veya v2 JSON
        r = evaluate_floor(gt, pred)
        rows.append((gp.stem, r))
        for k in ("rooms", "doors", "windows"):
            cal[k] += r["calibration"][k]
            cal_src[k] += r["calibration"]["sources"][k]
        if r["doors"].get("pair_acc") is not None:
            pair_acc.append((r["doors"]["pair_acc"], r["doors"]["pair_n"]))
        for k in agg:
            agg[k][0] += r[k]["tp"]; agg[k][1] += r[k]["fp"]; agg[k][2] += r[k]["fn"]
        if r["rooms"]["mean_iou"] is not None: ious.append(r["rooms"]["mean_iou"])
        if r["rooms"]["name_acc"] is not None: names.append(r["rooms"]["name_acc"])
        if r["doors"]["mean_err_m"] is not None: derr.append(r["doors"]["mean_err_m"])
        if r["doors"]["connect_acc"] is not None: conn.append(r["doors"]["connect_acc"])

    def prf(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        return p, rc, (2 * p * rc / (p + rc) if p + rc else 0.0)

    L = ["# Building IR Ölçüm Raporu\n", f"- GT dosyası: **{len(rows)}** (pred bulunan: {sum(1 for _, r in rows if r)})\n"]
    L.append("## Toplam (mikro)\n")
    L.append("| Varlık | TP | FP | FN | Precision | Recall | F1 | Ek |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---|")
    mean = lambda xs: (round(sum(xs) / len(xs), 3) if xs else "-")
    extras = {"rooms": f"IoU={mean(ious)}, ad doğruluğu={mean(names)}",
              "doors": f"konum hatası={mean(derr)} m, bağlantı doğruluğu={mean(conn)}", "windows": ""}
    for k, (tp, fp, fn) in agg.items():
        p, rc, f1 = prf(tp, fp, fn)
        L.append(f"| {k} | {tp} | {fp} | {fn} | {p:.3f} | {rc:.3f} | {f1:.3f} | {extras[k]} |")
    if pair_acc:
        n = sum(k for _, k in pair_acc); ok = sum(a * k for a, k in pair_acc)
        L.append(f"\nKapı çift doğruluğu (yalnız rapor): {ok / n:.3f} ({n} kapı)")
    else:
        L.append("\nKapı çift doğruluğu (yalnız rapor): — (tahminde ikinci oda yok)")
    # Güven kalibrasyonu: dilim başına gerçek doğruluk (TP oranı). Yüksek dilim > düşük dilim olmalı.
    bins = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
    L.append("\n## Güven kalibrasyonu (dilim → eşleşme oranı, n)\n")
    L.append("| Varlık | 0–0.5 | 0.5–0.7 | 0.7–0.9 | 0.9–1 |")
    L.append("|---|---|---|---|---|")
    for k in ("rooms", "doors", "windows"):
        cells = []
        for lo, hi in bins:
            xs = [m for c, m in cal[k] if c is not None and lo <= c < hi]
            cells.append(f"{sum(xs) / len(xs):.2f} (n={len(xs)})" if xs else "— (n=0)")
        L.append(f"| {k} | " + " | ".join(cells) + " |")
    L.append("\n## Kaynağa göre doğruluk\n")
    L.append("| Varlık | Kaynak | n | Eşleşme oranı |")
    L.append("|---|---|---:|---:|")
    for k in ("rooms", "doors", "windows"):
        by = {}
        for src, m in cal_src[k]:
            by.setdefault(src, []).append(m)
        for src, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
            L.append(f"| {k} | {src} | {len(xs)} | {sum(xs) / len(xs):.2f} |")
    L.append("\n## Dosya bazında\n")
    L.append("| Dosya | Oda F1 | Oda IoU | Ad | Kapı F1 | Kapı hata (m) | Bağlantı | Pencere F1 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, r in rows:
        if not r:
            L.append(f"| {name} | pred yok | | | | | | |"); continue
        L.append(f"| {name} | {r['rooms']['f1']} | {r['rooms']['mean_iou']} | {r['rooms']['name_acc']} | "
                 f"{r['doors']['f1']} | {r['doors']['mean_err_m']} | {r['doors']['connect_acc']} | {r['windows']['f1']} |")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(json.dumps(dict(rows), ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L[:12])); print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
