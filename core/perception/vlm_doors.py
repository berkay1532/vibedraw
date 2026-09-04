# core/vlm_doors.py
"""VLM-destekli kapı doğrulama.

Mantık: deterministik kapı kümeleri (kesin konum, ama gürültülü/fazla) ADAY'dır.
Kat planı görüntüsünü görme modeline (Claude) gönderip "gerçek kapılar nerede"
diye sorarız; VLM yaklaşık konum verir (TANIMA). Her adayı, VLM'in işaret ettiği
bir kapıya yakınsa KORUR, değilse (balkon ortası, merdiven gibi sahteler) ELER.

VLM yargılar (hangi konum kapı), geometri kesinleştirir (tam koordinat).
Mimari ilkeyle uyumlu: LLM koordinat üretmez, sadece doğrular.
"""
from __future__ import annotations
import base64
import json
import math
import os
import re


def _load_api_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def render_floor_png(dxf_path: str, bbox, out_path: str, width_in: float = 10.0,
                     dpi: int = 120):
    """Hedef kat bbox'ını PNG'ye render eder; (png, W_px, H_px, bbox) döner.

    Eksen figürü tam doldurur -> dünya<->piksel eşlemesi lineer ve kesin.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    x0, y0, x1, y1 = bbox
    h_in = width_in * (y1 - y0) / (x1 - x0)
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    fig = plt.figure(figsize=(width_in, h_in), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(msp, finalize=False)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_axis_off()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=dpi, facecolor="white", pad_inches=0)
    plt.close(fig)
    return out_path, int(width_in * dpi), int(h_in * dpi), bbox


def _pixel_to_world(px, py, W, H, bbox):
    x0, y0, x1, y1 = bbox
    wx = x0 + (px / W) * (x1 - x0)
    wy = y0 + (1 - py / H) * (y1 - y0)   # görüntü y'si yukarıdan aşağı
    return wx, wy


def vlm_door_points(png_path: str, W: int, H: int, bbox,
                    model: str = "claude-sonnet-4-6") -> list[tuple[float, float]]:
    """Görme modeline planı gönderir, kapı konumlarını (dünya koordinatı) döner.

    Dönen liste VLM'in YAKLAŞIK kapı konumlarıdır; çağıran taraf adaylara snap'ler.
    """
    key = _load_api_key()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY yok (.env veya ortam değişkeni)")
    from anthropic import Anthropic

    with open(png_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    prompt = (
        "Bu bir mimari kat planı (tek daire). Görseldeki KAPI'ları (oda girişleri, "
        "duvardaki kapı açıklıkları — kapı kanadı/açılış işareti olan yerler) bul. "
        "Pencere, merdiven, baca, mobilya KAPI DEĞİLDİR; onları dahil etme. "
        "Her kapı için açıklığın ORTASINI, görüntüye göre normalize edilmiş "
        "koordinatla ver (x: soldan 0..1, y: yukarıdan 0..1). "
        "SADECE şu formatta JSON dizi döndür, başka metin yazma: "
        '[{"x":0.12,"y":0.34}, ...]'
    )
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    text = resp.content[0].text.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    pts = json.loads(m.group(0))
    out = []
    for p in pts:
        px, py = float(p["x"]) * W, float(p["y"]) * H
        out.append(_pixel_to_world(px, py, W, H, bbox))
    return out


def validate_doors(candidates: list[tuple[float, float]],
                   vlm_points: list[tuple[float, float]],
                   tol: float = 25.0) -> list[tuple[float, float]]:
    """Adayları VLM kapılarıyla doğrula: bir VLM kapısına 'tol' içinde olan adayları
    KORU. Hiç adayı olmayan VLM kapısını da (ham) ekle."""
    confirmed = []
    used = set()
    for vx, vy in vlm_points:
        # bu VLM kapısına en yakın KULLANILMAMIŞ aday (tol içinde)
        best, bd, bi = None, tol, -1
        for i, (cx, cy) in enumerate(candidates):
            if i in used:
                continue
            d = math.hypot(cx - vx, cy - vy)
            if d < bd:
                bd, best, bi = d, (cx, cy), i
        if best is not None:
            confirmed.append(best)       # adaya snap (kesin konum)
            used.add(bi)
        else:
            confirmed.append((vx, vy))   # uygun aday yok -> ham VLM noktası (kayıp olmasın)
    return confirmed
