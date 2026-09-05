#!/usr/bin/env python3
"""GT şema/tutarlılık kontrolü ve taslak → GT.

Kullanım: python3 tools/gt_check.py data/ground_truth/<ad>.draft.json [--finalize]
Kontroller: kapalı/geçerli poligon (≥3 nokta, self-intersection yok, alan > 0), tekil id'ler, her kapının connects'i
var ve odalara/outside'a çözülüyor, kapı genişliği birimle uyumlu (0,6–1,5 m; None uyarı), menteşe bir odanın
≤ 0,5 m yakınında, pencere a≠b, birim standart (1/10/100/1000; değilse meta.note'ta gerekçe), meta alanları.
--finalize: sorun yoksa meta.status=verified yazıp <ad>.json olarak kaydeder (evaluate bunu okur).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from shapely.geometry import Point, Polygon


def check(d: dict) -> tuple[list[str], list[str]]:
    err, warn = [], []
    f = d.get("floor") or {}; upm = float(d.get("units_per_meter") or 0)
    if upm not in (1.0, 10.0, 100.0, 1000.0):
        (warn if (d.get("meta") or {}).get("note") else err).append(f"birim {upm} standart değil (bilinçliyse meta.note'a gerekçe yaz)")
    ids = set(); polys = {}
    for r in f.get("rooms", []):
        rid = r.get("id")
        if not rid or rid in ids: err.append(f"oda id tekil değil/boş: {rid}")
        ids.add(rid)
        pts = r.get("polygon") or []
        if len(pts) < 3: err.append(f"{rid} ({r.get('name')}): poligon < 3 nokta"); continue
        if pts[0] == pts[-1]: warn.append(f"{rid}: son nokta ilkin tekrarı (kapatma noktası yazılmaz)")
        P = Polygon(pts)
        if not P.is_valid: err.append(f"{rid} ({r.get('name')}): poligon geçersiz (kendini kesiyor?)")
        elif P.area <= 0: err.append(f"{rid}: alan 0")
        elif P.area / upm ** 2 < 0.5: warn.append(f"{rid} ({r.get('name')}): alan {P.area / upm ** 2:.2f} m² çok küçük")
        polys[rid] = P
        if not r.get("name"): warn.append(f"{rid}: name boş")
        if (d.get("meta") or {}).get("source", "").startswith("src02"):                # src02 standardı: kind zorunlu
            if r.get("kind") not in ("daire içi", "ortak", "teknik", "dış"): err.append(f"{rid} ({r.get('name')}): kind eksik/geçersiz (daire içi|ortak|teknik|dış)")
    dids = set()
    for o in f.get("doors", []):
        did = o.get("id")
        if not did or did in dids: err.append(f"kapı id tekil değil/boş: {did}")
        dids.add(did)
        con = [c for c in (o.get("connects") or []) if c]
        if not con: err.append(f"{did}: connects boş (en az bir oda ya da 'outside')")
        for c in con:
            if c != "outside" and c not in ids: err.append(f"{did}: connects '{c}' odası yok")
        h = o.get("hinge")
        if not h or len(h) != 2: err.append(f"{did}: hinge eksik"); continue
        w = o.get("width")
        if w is None: warn.append(f"{did}: width yok (ölçüm için gerekmez)")
        elif not (0.6 * upm <= w <= 1.5 * upm): warn.append(f"{did}: width {w} birimle uyumsuz (0.6–1.5 m beklenir)")
        near = [rid for rid, P in polys.items() if P.buffer(0.5 * upm).contains(Point(h))]
        if not near: err.append(f"{did}: menteşe hiçbir odanın 0.5 m yakınında değil")
        elif any(c not in near and c != "outside" for c in con): warn.append(f"{did}: connects {con} ama menteşeye yakın odalar {near}")
    for i, w in enumerate(f.get("windows", [])):
        if not w.get("a") or not w.get("b") or w["a"] == w["b"]: err.append(f"pencere #{i}: a/b eksik ya da eşit")
    meta = d.get("meta") or {}
    for k in ("tier", "holdout", "source", "status"):
        if k not in meta: err.append(f"meta.{k} eksik")
    if meta.get("tier") not in ("clean", "typical", "hard", "easy", "normal"): warn.append(f"meta.tier '{meta.get('tier')}' beklenmedik")
    return err, warn


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("path"); ap.add_argument("--finalize", action="store_true"); a = ap.parse_args()
    p = Path(a.path); d = json.loads(p.read_text(encoding="utf-8")); err, warn = check(d)
    for w in warn: print("UYARI:", w)
    for e in err: print("HATA:", e)
    f = d["floor"]; print(f"özet: oda {len(f.get('rooms', []))} kapı {len(f.get('doors', []))} pencere {len(f.get('windows', []))} upm {d.get('units_per_meter')} | {len(err)} hata, {len(warn)} uyarı")
    if err: sys.exit(2)
    if a.finalize:
        d.setdefault("meta", {})["status"] = "verified"
        out = p.with_name(p.name.replace(".draft.json", ".json"))
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8"); print("→", out)
    print("OK")


if __name__ == "__main__":
    main()
