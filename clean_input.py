# clean_input.py
"""input-2.dxf (tam mimar üretim seti) -> sadece kat planları, gürültü temizlenmiş.

Tutar: 3 kat planı bölgesi (Zemin/1.kat/Çatı, x~2700-9200) içinde, işe yarar
katmanlardaki geometri + oda isim/alan yazıları. Atar: kesitler, cepheler,
detaylar, vaziyet/yerleşim, ölçüler, tablolar, mobilya, akslar, malzeme notları.
"""
from __future__ import annotations
import argparse
import re

import ezdxf

# Kat planı bölgesi (haritalamadan: 3 plan yan yana)
REGION = (2700, 300, 9200, 3300)

KEEP_LAYERS = {
    # duvar / strüktür  (NOT: .ABM-KİRİŞ=kiriş bilinçli ÇIKARILDI — tavan elemanı,
    # oda ortasından geçer, mimari altlıkta olmamalı; duvar tespitini bozuyordu)
    "PislikMimar.com - duvar", ".ABM-DUVAR", "duv", "ince", ".ABM-SIVA",
    "KOLON",
    # kapı / pencere
    "kapi", ".KAPI", ".ABM-KAPI", "pencere", "cam", "KAPEN",
    # oda yazıları / mahal
    "YAZI", "MAHAL ADI",
    # merdiven / baca / çatı
    "merdiven", "MERDİVEN YAZI", "BACA", "RPD-CATI_1",
    # kapı açılış yayları ve genel geometri (kapı tespiti için gerekli)
    "0",
}

AREA_RE = re.compile(r"A:\s*[\d.]+\s*m²")
# YAZI/MAHAL ADI içinde at: malzeme/teknik notları
NOISE_TEXT = ("DÖŞ:", "DUV:", "TAV:", "ISITMA", "ölçek", "Ölçek", "Kotu", "kotu",
              "pencere açılış", "Süzgeç", "küpeşte", "korkuluk", "PAYI", "SAÇAK",
              "doğrama", "DÖŞEME", "---YOL---", "ALAN", "Plan", "PLAN",
              "KOMBİ", "ELEKTRİKLİ", "Kotu", "CEPHE", "KESİT", "asansör", "Asansör")


def _pos(e):
    t = e.dxftype()
    try:
        if t == "INSERT":
            return e.dxf.insert[0], e.dxf.insert[1]
        if t == "LINE":
            return (e.dxf.start[0] + e.dxf.end[0]) / 2, (e.dxf.start[1] + e.dxf.end[1]) / 2
        if t == "LWPOLYLINE":
            pts = e.get_points()
            return pts[0][0], pts[0][1]
        if t == "POLYLINE":
            v = list(e.vertices)
            return (v[0].dxf.location[0], v[0].dxf.location[1]) if v else None
        if t in ("ARC", "CIRCLE", "ELLIPSE"):
            return e.dxf.center[0], e.dxf.center[1]
        if t in ("MTEXT", "TEXT"):
            return e.dxf.insert[0], e.dxf.insert[1]
        if t == "HATCH":
            # kaba: ilk path noktası
            for p in e.paths.paths:
                try:
                    return p.vertices[0][0], p.vertices[0][1]
                except Exception:
                    pass
    except Exception:
        return None
    return None


def _is_room_text(e) -> bool:
    """YAZI/MAHAL ADI metni gerçek oda ismi/alanı mı (malzeme notu değil)?"""
    t = (e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text).strip()
    if not t:
        return False
    if AREA_RE.search(t):
        return True                      # "A: 14.12m²" -> tut
    if ":" in t:
        return False                     # "DÖŞ:..." gibi notlar -> at
    if any(n.lower() in t.lower() for n in NOISE_TEXT):
        return False
    return len(t) <= 20                   # kısa oda ismi -> tut


def clean(in_path: str, out_path: str) -> None:
    x0, y0, x1, y1 = REGION
    doc = ezdxf.readfile(in_path)
    msp = doc.modelspace()
    drop = []
    for e in list(msp):
        p = _pos(e)
        keep = True
        if p is None or not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1):
            keep = False                  # bölge dışı
        elif e.dxf.layer not in KEEP_LAYERS:
            keep = False                  # istenmeyen katman
        elif e.dxftype() in ("MTEXT", "TEXT"):
            # SADECE oda ismi/alanı kalsın; diğer tüm metinler (layer 0 notları,
            # merdiven basamak no, korkuluk/küpeşte notları vb.) silinsin.
            keep = e.dxf.layer in ("YAZI", "MAHAL ADI") and _is_room_text(e)
        if not keep:
            drop.append(e)
    for e in drop:
        msp.delete_entity(e)
    doc.saveas(out_path)
    print(f"Temizlendi -> {out_path} | silinen {len(drop)} entity, kalan {len(list(msp))}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("inp", nargs="?", default="ornekler/input-2.dxf")
    p.add_argument("-o", "--out", default="ornekler/input-2-clean.dxf")
    a = p.parse_args()
    clean(a.inp, a.out)
