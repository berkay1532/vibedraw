#!/usr/bin/env python3
"""Boş altlık görseli: tahminsiz, sadece mimarın çizgileri. Yaylar (ARC + bulge'lu
polyline) doğru çizilir; kapı/pencere benzeri katmanlar kırmızı vurgulanır.

Kullanım: python3 render_raw.py <ad> [--pred output/baseline] [--open]
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))          # tools/ (kardeş araçlar)
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))  # repo kökü (core/)

import argparse
import glob
import json
import math
import subprocess
import unicodedata

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--pred", default="output/baseline")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    nf = unicodedata.normalize("NFC", a.name)
    pj = [p for p in glob.glob(f"{a.pred}/*.json") if unicodedata.normalize("NFC", p).find(nf) >= 0 and not p.endswith("results.json")][0]
    pr = json.load(open(pj)); f = pr["floors"][0]
    upm = 100.0
    for r in json.load(open(f"{a.pred}/results.json")):
        if unicodedata.normalize("NFC", r["file"]) in unicodedata.normalize("NFC", pj):
            upm = float(r["stages"].get("labels_generic", {}).get("upm", upm))
    xs = [p[0] for r in f["rooms"] for p in (r["polygon"] or [r["label_xy"]])]
    ys = [p[1] for r in f["rooms"] for p in (r["polygon"] or [r["label_xy"]])]
    m = 3 * upm
    x0, y0, x1, y1 = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
    doc = ezdxf.readfile(pr["source_path"]); msp = doc.modelspace()

    def inb(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1

    fig, ax = plt.subplots(figsize=(16, 16 * (y1 - y0) / (x1 - x0)))

    def draw(e, col, lw):
        t = e.dxftype()
        try:
            if t == "LINE":
                p, q = e.dxf.start, e.dxf.end
                if inb(p) or inb(q):
                    ax.plot([p[0], q[0]], [p[1], q[1]], color=col, lw=lw)
            elif t in ("LWPOLYLINE", "ARC", "CIRCLE"):
                ents = list(e.virtual_entities()) if t == "LWPOLYLINE" else [e]
                for ve in ents:
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
                        a0, a1 = ((math.radians(ve.dxf.start_angle), math.radians(ve.dxf.end_angle))
                                  if vt == "ARC" else (0.0, 2 * math.pi))
                        if a1 < a0:
                            a1 += 2 * math.pi
                        P = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / 24), c[1] + r * math.sin(a0 + (a1 - a0) * k / 24)) for k in range(25)]
                        ax.plot([p[0] for p in P], [p[1] for p in P], color=col, lw=lw)
            elif t == "INSERT":
                if inb(e.dxf.insert):
                    for ve in e.virtual_entities():
                        draw(ve, col, lw)
        except Exception:
            pass

    door_layers = {l.dxf.name for l in doc.layers if "KAPI" in l.dxf.name.upper() or "DOOR" in l.dxf.name.upper()}
    print("kapı benzeri katmanlar:", door_layers)
    for e in msp:
        if e.dxf.layer not in door_layers:
            draw(e, "0.6", 0.3)
    for e in msp:
        if e.dxf.layer in door_layers:
            draw(e, "red", 1.4)
    for r in f["rooms"]:
        ax.text(r["label_xy"][0], r["label_xy"][1], r["raw_name"].split("\n")[0], fontsize=5, color="darkblue", ha="center")
    ax.set_aspect("equal"); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    out = f"output/raw/{nf}_bos_altlik.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(out)
    if a.open:
        subprocess.run(["open", out])


if __name__ == "__main__":
    main()
