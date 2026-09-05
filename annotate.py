#!/usr/bin/env python3
"""Ground truth etiketleme aracı üretici.

Kullanım: python3 annotate.py <dosya_adı> [--pred output/baseline] [--gt data/ground_truth] [--open]
Örn:      python3 annotate.py <dosya_adı> --open

Pipeline çıktısını (veya varsa mevcut GT'yi) altlık çizgileriyle birlikte tek dosyalık bir
HTML'e gömer: output/annotate/<ad>.html. Tarayıcıda düzeltip "Kaydet" → <ad>.json iner;
dosyayı data/ground_truth/ altına koyun, sonra `python3 evaluate.py`.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parent


def base_segments(dxf_path, bbox, max_segs=80000):
    x0, y0, x1, y1 = bbox
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    segs = []

    def inb(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

    m = 0.15 * max(x1 - x0, y1 - y0) + 300.0

    def near(p):
        return x0 - m <= p[0] <= x1 + m and y0 - m <= p[1] <= y1 + m

    def add(a, b):
        if inb(a) or inb(b):
            segs.append([round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2)])

    def handle(e):
        t = e.dxftype()
        try:
            if t == "LINE":
                add(e.dxf.start, e.dxf.end)
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if e.closed and pts: pts.append(pts[0])
                for i in range(len(pts) - 1): add(pts[i], pts[i + 1])
            elif t == "POLYLINE":
                pts = [(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]
                for i in range(len(pts) - 1): add(pts[i], pts[i + 1])
            elif t in ("ARC", "CIRCLE"):
                c = e.dxf.center; r = e.dxf.radius
                if t == "ARC":
                    a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
                    if a1 < a0: a1 += 2 * math.pi
                else:
                    a0, a1 = 0.0, 2 * math.pi
                n = 12 if t == "ARC" else 24
                P = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
                for i in range(n): add(P[i], P[i + 1])
            elif t == "INSERT":
                ip = e.dxf.insert                      # blok geometrisi insert noktasından uzak olabilir (kapı/pencere
                if inb(ip) or near(ip):                # blokları): geniş komşulukta da aç
                    for ve in e.virtual_entities():
                        handle(ve)
        except Exception:
            pass

    for e in msp:
        if len(segs) > max_segs:
            break
        handle(e)
    return segs


def build(name, pred_dir, gt_dir, view=None):
    """view: (x0,y0,x1,y1) — altlık ve başlangıç görünümü bu kutuya kırpılır; tüm oda/kapı/pencere yine yüklenir
    (Kaydet dosyanın tamamını yazar)."""
    pred_path = Path(pred_dir) / f"{name}.json"
    if not pred_path.exists():
        sys.exit(f"pred bulunamadı: {pred_path} (önce experiments/run_baseline.py)")
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    from core.perception.ir_compat import load_floor_for_eval
    floor = load_floor_for_eval(pred)             # v1 veya v2 JSON
    dxf_path = pred["source_path"]
    upm = 100.0
    res_path = Path(pred_dir) / "results.json"
    if res_path.exists():
        import unicodedata
        nf = unicodedata.normalize("NFC", name)
        for r in json.loads(res_path.read_text(encoding="utf-8")):
            if unicodedata.normalize("NFC", r["file"]) == nf:
                upm = float(r["stages"].get("labels_generic", {}).get("upm", upm))
    gt_path = Path(gt_dir) / f"{name}.draft.json"           # taslak varsa o (Kaydet de buraya yazar)
    if not gt_path.exists():
        gt_path = Path(gt_dir) / f"{name}.json"
    gt = json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else None
    if gt:
        upm = float(gt.get("units_per_meter") or upm)
        rooms = [{"id": r.get("id", f"r{i+1}"), "name": r.get("name", ""), "type": r.get("type", ""), "polygon": r["polygon"]}
                 for i, r in enumerate(gt["floor"].get("rooms", []))]
        doors = [{"id": d.get("id", f"d{i+1}"), "hinge": d["hinge"], "width": d.get("width"), "connects": d.get("connects", [])}
                 for i, d in enumerate(gt["floor"].get("doors", []))]
        windows = [[w["a"], w["b"]] for w in gt["floor"].get("windows", [])]
    else:
        rooms = [{"id": f"r{i+1}", "name": r["raw_name"], "type": r.get("room_type") or "",
                  "polygon": r["polygon"] or _square(r["label_xy"], 1.5 * upm)} for i, r in enumerate(floor["rooms"])]
        # tahmin edilen kapı: room_name → id (yalnız tek taraf biliniyor)
        name2id = {}
        for r in rooms:
            name2id.setdefault(r["name"], r["id"])
        doors = [{"id": f"d{i+1}", "hinge": d["xy"], "width": None,
                  "connects": [name2id[d["room_name"]]] if d.get("room_name") in name2id else []}
                 for i, d in enumerate(floor["doors"])]
        windows = [[w[0], w[1]] for w in floor["windows"]]
    xs = [p[0] for r in rooms for p in r["polygon"]]; ys = [p[1] for r in rooms for p in r["polygon"]]
    m = 3.0 * upm
    bbox = tuple(view) if view else (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
    segs = base_segments(dxf_path, bbox)
    data = {"name": name, "source": dxf_path, "units_per_meter": upm, "bbox": bbox, "segments": segs,
            "rooms": rooms, "doors": doors, "windows": windows,
            "meta": (gt or {}).get("meta", {"status": "draft", "note": ""})}
    tpl = (ROOT / "templates" / "annotate.html").read_text(encoding="utf-8")
    html = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = ROOT / "output" / "annotate" / f"{name}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out, len(segs)


def serve(html_path: Path, save_path: Path, port: int, open_browser: bool):
    """Tek dosyalık HTTP sunucu: GET / → etiketleme sayfası, POST /save → JSON'u save_path'e yaz (tarayıcı indirmesi yok)."""
    import http.server, json as _json
    html = html_path.read_bytes()

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(html)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
            try:
                data = _json.loads(body.decode("utf-8"))
                save_path.write_text(_json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                msg = f"{save_path} (oda {len(data['floor']['rooms'])}, kapı {len(data['floor']['doors'])}, pencere {len(data['floor']['windows'])})"
                self.send_response(200)
            except Exception as ex:
                msg = f"HATA {ex}"; self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(msg.encode("utf-8"))
            print("[annotate] kaydedildi:", msg, flush=True)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    print(f"[annotate] http://127.0.0.1:{port}/  (Ctrl-C ile kapat)", flush=True)
    if open_browser:
        subprocess.run(["open", f"http://127.0.0.1:{port}/"])
    srv.serve_forever()


def _square(c, h):
    return [[c[0] - h, c[1] - h], [c[0] + h, c[1] - h], [c[0] + h, c[1] + h], [c[0] - h, c[1] + h]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--pred", default="output/baseline")
    ap.add_argument("--gt", default="data/ground_truth")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--view", default=None, help="x0,y0,x1,y1 — yalnız bu bölgeyi göster (kırpılmış etiketleme)")
    ap.add_argument("--serve", type=int, default=None, help="port: sayfayı http://localhost:PORT/ üzerinden sun; Kaydet → <gt>/<ad>.draft.json (indirme yok)")
    a = ap.parse_args(argv)
    view = tuple(float(v) for v in a.view.split(",")) if a.view else None
    out, n = build(a.name, a.pred, a.gt, view)
    if a.serve:
        serve(out, Path(a.gt) / f"{a.name}.draft.json", a.serve, a.open)
        return
    print(f"→ {out}  ({n} altlık parçası)")
    if a.open:
        subprocess.run(["open", str(out)])


if __name__ == "__main__":
    main()
