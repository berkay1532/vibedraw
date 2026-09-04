#!/usr/bin/env python3
"""Deney A temel çizgisi: mevcut çıkarım pipeline'ını (etiket → kat → geometri) tüm ADAY
dosyalarda koşturur, her dosya için IR JSON + overlay PNG üretir ve başarısızlık kataloğu yazar.

Kullanım: python3 experiments/run_baseline.py [--triage output/dataset_triage.json] [--out output/baseline] [--timeout 180]
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAX_CELLS = 30_000_000
from core.perception.calibration import scaled_params, BASE, BASE_UPM  # noqa: E402
from core.perception.run_stamp import make_stamp  # noqa: E402


def _render(dxf_path, floor, out_png, margin):
    import ezdxf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [r.label_xy[0] for r in floor.rooms]; ys = [r.label_xy[1] for r in floor.rooms]
    x0, y0, x1, y1 = min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin
    doc = ezdxf.readfile(dxf_path); msp = doc.modelspace()
    fig, ax = plt.subplots(figsize=(14, 14 * max(0.3, (y1 - y0) / max(1e-6, x1 - x0))))
    for e in msp:
        t = e.dxftype()
        try:
            if t == "LINE":
                a, b = e.dxf.start, e.dxf.end
                if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
                    ax.plot([a[0], b[0]], [a[1], b[1]], color="0.75", lw=0.4)
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if pts and x0 <= pts[0][0] <= x1 and y0 <= pts[0][1] <= y1:
                    if e.closed: pts.append(pts[0])
                    ax.plot([p[0] for p in pts], [p[1] for p in pts], color="0.75", lw=0.4)
            elif t == "ARC":
                c = e.dxf.center
                if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
                    a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
                    if a1 < a0: a1 += 2 * math.pi
                    r = e.dxf.radius
                    P = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / 16), c[1] + r * math.sin(a0 + (a1 - a0) * k / 16)) for k in range(17)]
                    ax.plot([p[0] for p in P], [p[1] for p in P], color="0.75", lw=0.4)
        except Exception:
            pass
    for (a, b) in floor.walls:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="red", lw=1.0)
    for (a, b) in floor.windows:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="deepskyblue", lw=1.5)
    for r in floor.rooms:
        if r.polygon:
            P = r.polygon + [r.polygon[0]]
            col = "green" if r.geometry_ok else "orange"
            ax.fill([p[0] for p in P], [p[1] for p in P], color=col, alpha=0.18, lw=0)
            ax.plot([p[0] for p in P], [p[1] for p in P], color=col, lw=0.8, ls="--")
        ax.plot(r.label_xy[0], r.label_xy[1], "k+", ms=8)
        ax.text(r.label_xy[0], r.label_xy[1], r.raw_name, fontsize=6, color="black")
    for d in floor.doors:
        ax.plot(d.xy[0], d.xy[1], "o", mfc="none", mec="magenta", ms=9, mew=1.5)
    ax.set_aspect("equal"); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    fig.savefig(out_png, dpi=110, bbox_inches="tight"); plt.close(fig)


def run_one(dxf_path: str, out_dir: str, q):
    """Alt süreçte koşar; sonucu kuyruğa yazar."""
    from core.perception.parse import (parse_dxf, extract_room_labels, cluster_floors_2d, dedupe_labels,
                                       pick_plan_floor, grid_likeness)
    from core.perception.binding import pair_names_with_areas
    from core.perception.calibration import estimate_units_per_meter
    from core.perception.pipeline import reconstruct
    from core.perception.ir_v1 import BuildingIR
    name = Path(dxf_path).stem
    r = {"file": name, "path": dxf_path, "stages": {}, "error": None, "fail_stage": None}
    t0 = time.time()
    # 1) stok parse (YAZI katmanı)
    try:
        b = parse_dxf(dxf_path)
        r["stages"]["parse_stock"] = {"rooms": len(b.floors[0].rooms)}
    except Exception as ex:
        r["stages"]["parse_stock"] = {"rooms": 0, "error": f"{type(ex).__name__}: {ex}"[:120]}
    # 2) genel etiket çıkarımı + ölçek + kat
    try:
        labels = extract_room_labels(dxf_path)
        upm0 = estimate_units_per_meter(labels)
        labels = dedupe_labels(labels, tol=0.5 * upm0)      # 50 cm içindeki tekrarlar
        upm = estimate_units_per_meter(labels)
        rooms = pair_names_with_areas(labels)
        floors = cluster_floors_2d(rooms, gap=7.0 * upm)    # 7 m'den yakın etiketler aynı çizim
        floors = [f for f in floors if len(f.rooms) >= 3]
        r["stages"]["labels_generic"] = {"labels": len(labels), "rooms": len(rooms), "upm": round(upm, 1),
                                         "floors": [len(f.rooms) for f in floors]}
        if not floors:
            r["fail_stage"] = "labels_generic"; r["error"] = "≥3 odalı kat kümesi yok"
            r["elapsed"] = round(time.time() - t0, 1); q.put(r); return
        floor = pick_plan_floor(floors, upm); floor.index = 0
        r["stages"]["labels_generic"]["grid"] = [round(grid_likeness(f.rooms, 0.3 * upm), 2) for f in floors]
        # Kapı-yayı kanıtı: mahal listesi tabloları (döndürülmüş olsa bile) kapı yayı içermez.
        # Kapı yayı bulunan en kalabalık kümeyi tercih et.
        from core.perception.calibration import estimate_units_from_doors as _eud
        from core.perception.rooms import _floor_bbox as _fb
        with_doors = []
        for f in sorted(floors, key=lambda f: -len(f.rooms))[:8]:
            if len(f.rooms) < 3:
                continue
            if _eud(dxf_path, _fb(f, 2.5 * upm), upm) is not None:
                with_doors.append(f)
        if with_doors and floor not in with_doors:
            floor = with_doors[0]; floor.index = 0
            r["stages"]["labels_generic"]["pick"] = "doors"
    except Exception as ex:
        r["fail_stage"] = "labels_generic"; r["error"] = f"{type(ex).__name__}: {ex}"[:200]
        r["trace"] = traceback.format_exc()[-800:]; r["elapsed"] = round(time.time() - t0, 1); q.put(r); return
    # 3) geometri
    try:
        # Ölçeği kapı yaylarından düzelt (etiket-mesafesi tahmini kaba)
        from core.perception.calibration import estimate_units_from_doors
        from core.perception.rooms import _floor_bbox
        xs = [rm.label_xy[0] for rm in floor.rooms]; ys = [rm.label_xy[1] for rm in floor.rooms]
        upm_doors = estimate_units_from_doors(dxf_path, _floor_bbox(floor, 2.5 * upm), upm)
        r["stages"]["labels_generic"]["upm_labels"] = round(upm, 1)
        if upm_doors and 0.25 * upm <= upm_doors <= 4.0 * upm:   # etiket öncülü kaba; kapı kümesi güçlü kanıt
            upm = upm_doors
            r["stages"]["labels_generic"]["upm"] = round(upm, 1)
            r["stages"]["labels_generic"]["upm_source"] = "doors"
            # Düzeltilmiş ölçekle YENİDEN kümele: kaba ölçekle 7 m eşiği büyük salon
            # etiketini kümenin dışında bırakabiliyor.
            floors2 = [f for f in cluster_floors_2d(rooms, gap=8.0 * upm) if len(f.rooms) >= 3]
            if floors2:
                # yeniden kümelemede: önceki seçimin etiketlerini içeren kümeyi koru
                prev = {id(rm) for rm in floor.rooms}
                same = [f for f in floors2 if any(id(rm) in prev for rm in f.rooms)]
                floor = max(same, key=lambda f: len(f.rooms)) if same else pick_plan_floor(floors2, upm)
                floor.index = 0
                r["stages"]["labels_generic"]["floors"] = [len(f.rooms) for f in floors2]
                xs = [rm.label_xy[0] for rm in floor.rooms]; ys = [rm.label_xy[1] for rm in floor.rooms]
        p = scaled_params(upm)
        w = max(xs) - min(xs) + 2 * p["margin"]; h = max(ys) - min(ys) + 2 * p["margin"]
        cells = (w / p["res"]) * (h / p["res"])
        if cells > MAX_CELLS:
            p["res"] *= math.sqrt(cells / MAX_CELLS)
        b = BuildingIR(floors=[floor], source_path=dxf_path)
        b = reconstruct(b, dxf_path, units_per_meter=upm, **p)
        f = b.floors[0]
        # v2 çıktı: güven + kanıt (ir_compat). Koordinatlar çizim biriminde, ölçek params'ta.
        from core.perception.ir_compat import to_v2
        from core.perception.triage import layer_fingerprint
        try:
            import ezdxf as _ez
            fp = layer_fingerprint(l.dxf.name for l in _ez.readfile(dxf_path).layers)
        except Exception:
            fp = ""
        extra = {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
        extra["big_blocks"] = bool(getattr(f, "big_blocks", False))
        b2 = to_v2(b, units_per_meter=upm, units_source=r["stages"]["labels_generic"].get("upm_source", "labels"),
                   fingerprint=fp, params_extra=extra)
        r["stages"]["geometry"] = {
            "params": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in p.items()},
            "rooms": len(f.rooms), "geometry_ok": sum(1 for rm in f.rooms if rm.geometry_ok),
            "walls": len(f.walls), "windows": len(f.windows), "doors": len(f.doors),
            "doors_with_room": sum(1 for d in f.doors if d.room_name),
        }
        Path(out_dir, f"{name}.json").write_text(json.dumps(asdict(b2), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        try:
            _render(dxf_path, f, str(Path(out_dir, f"{name}.png")), p["margin"])
        except Exception as ex:
            r["stages"]["geometry"]["render_error"] = f"{type(ex).__name__}: {ex}"[:120]
    except Exception as ex:
        r["fail_stage"] = "geometry"; r["error"] = f"{type(ex).__name__}: {ex}"[:200]
        r["trace"] = traceback.format_exc()[-800:]
    r["elapsed"] = round(time.time() - t0, 1)
    q.put(r)


def run_with_timeout(dxf_path, out_dir, timeout):
    q = mp.Queue()
    pr = mp.Process(target=run_one, args=(dxf_path, out_dir, q))
    pr.start(); pr.join(timeout)
    if pr.is_alive():
        pr.terminate(); pr.join()
        return {"file": Path(dxf_path).stem, "path": dxf_path, "stages": {}, "fail_stage": "timeout",
                "error": f"{timeout}s aşıldı", "elapsed": timeout}
    try:
        return q.get(timeout=5)
    except Exception:
        return {"file": Path(dxf_path).stem, "path": dxf_path, "stages": {}, "fail_stage": "crash",
                "error": f"alt süreç çıktı vermeden bitti (exit {pr.exitcode})", "elapsed": None}


def report(results, out_md):
    L = ["# Deney A — Temel Çizgi Raporu\n"]
    n = len(results)
    ok_geo = [r for r in results if r["stages"].get("geometry") and not r["fail_stage"]]
    L.append(f"- Koşulan ADAY dosya: **{n}**")
    L.append(f"- Stok parse (YAZI katmanı) oda bulan: **{sum(1 for r in results if r['stages'].get('parse_stock', {}).get('rooms', 0) >= 3)}**")
    L.append(f"- Genel etiket ile ≥3 odalı kat bulunan: **{sum(1 for r in results if r['stages'].get('labels_generic', {}).get('floors'))}**")
    L.append(f"- Geometri aşaması hatasız biten: **{len(ok_geo)}**")
    if ok_geo:
        tot_r = sum(r["stages"]["geometry"]["rooms"] for r in ok_geo)
        tot_ok = sum(r["stages"]["geometry"]["geometry_ok"] for r in ok_geo)
        L.append(f"- Oda poligonu çıkan / toplam oda (geometri biten dosyalarda): **{tot_ok}/{tot_r}**")
    L.append("")
    L.append("| Dosya | Stok oda | Etiket | Oda | upm | Kat(oda) | Poligon ok | Duvar | Pencere | Kapı | Kapı→oda | Süre | Hata |")
    L.append("|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for r in results:
        ps = r["stages"].get("parse_stock", {}); lg = r["stages"].get("labels_generic", {}); g = r["stages"].get("geometry", {})
        err = f"{r['fail_stage']}: {r['error']}" if r["fail_stage"] else (g.get("render_error", "") and "render: " + g["render_error"])
        L.append(f"| {r['file']} | {ps.get('rooms', 0)} | {lg.get('labels', '')} | {lg.get('rooms', '')} | {lg.get('upm', '')} | "
                 f"{'/'.join(str(x) for x in lg.get('floors', []))} | "
                 f"{(str(g['geometry_ok']) + '/' + str(g['rooms'])) if g else ''} | {g.get('walls', '')} | {g.get('windows', '')} | "
                 f"{g.get('doors', '')} | {g.get('doors_with_room', '')} | {r.get('elapsed', '')} | {err} |")
    L.append("\n## Başarısızlık kataloğu\n")
    cats = {}
    for r in results:
        if r["fail_stage"]:
            cats.setdefault(f"{r['fail_stage']} — {r['error'].split(':')[0]}", []).append(r["file"])
    for r in results:
        ps = r["stages"].get("parse_stock", {})
        if ps.get("rooms", 0) < 3:
            cats.setdefault("stok parse oda bulamadı (YAZI katmanı yok / etiket ATTRIB'de)", []).append(r["file"])
        g = r["stages"].get("geometry")
        if g and g["rooms"] and g["geometry_ok"] < g["rooms"] * 0.5:
            cats.setdefault("geometri: odaların yarısından azı poligonlandı", []).append(r["file"])
        if g and g["doors"] == 0:
            cats.setdefault("geometri: hiç kapı bulunamadı", []).append(r["file"])
        if g and g["walls"] < 10:
            cats.setdefault("geometri: <10 duvar parçası", []).append(r["file"])
    for k, v in sorted(cats.items(), key=lambda kv: -len(kv[1])):
        L.append(f"- **{k}** ({len(v)}): " + ", ".join(v))
    Path(out_md).write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--triage", default="output/dataset_triage.json")
    ap.add_argument("--out", default="output/baseline")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--only", default=None, help="sadece adı bu alt-dizgiyi içeren dosyalar")
    args = ap.parse_args(argv)
    tri = json.loads(Path(args.triage).read_text(encoding="utf-8"))
    paths = [p["path"] for p in tri["profiles"] if p["verdict"] == "ADAY"]
    if args.only:
        keys = [k for k in args.only.split(",") if k]
        paths = [p for p in paths if any(k in p for k in keys)]
    os.makedirs(args.out, exist_ok=True)
    # results.json: önceki koşuların kayıtlarını koru, aynı dosya adını güncelle (--only için).
    # Her dosyadan SONRA yazılır → kesintide emek kaybolmaz.
    rp = Path(args.out, "results.json")
    merged = {}
    if rp.exists():
        try:
            merged = {r["file"]: r for r in json.loads(rp.read_text(encoding="utf-8"))}
        except Exception:
            merged = {}
    results = []
    stamp = make_stamp()                       # kod hash + commit + başlangıç: evaluate tazelik kapısı
    print(f"koşu damgası: {stamp}", file=sys.stderr, flush=True)
    for i, p in enumerate(paths, 1):
        print(f"[{i}/{len(paths)}] {Path(p).name}", file=sys.stderr, flush=True)
        r = run_with_timeout(p, args.out, args.timeout)
        r["stamp"] = stamp
        results.append(r)
        merged[r["file"]] = r
        rp.write_text(json.dumps(sorted(merged.values(), key=lambda x: x["file"]), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"    → {r['fail_stage'] or 'ok'} {r.get('error') or r['stages'].get('geometry', '')}", file=sys.stderr, flush=True)
    all_results = sorted(merged.values(), key=lambda r: r["file"])
    report(all_results if not args.only else results, Path(args.out).parent / "baseline_report.md")
    print(f"→ {Path(args.out).parent / 'baseline_report.md'}")


if __name__ == "__main__":
    main()
