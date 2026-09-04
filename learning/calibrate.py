#!/usr/bin/env python3
"""Ağırlık ayarı aracı (iskelet, Adım 6). Holdout dosyalarını okumayı REDDEDER (config/holdout.yaml).

Kullanım (ileride): python3 learning/calibrate.py --gt data/ground_truth --pred output/baseline
Şimdilik yalnız ayar kümesini listeler; lojistik regresyon/holdout değerlendirmesi yeni kaynak + fam00 GT
geldikten sonra (docs/REFACTOR_PLAN.md Adım 6, kullanıcı kararı).
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def holdout_files(path: Path = ROOT / "config" / "holdout.yaml") -> set[str]:
    d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {unicodedata.normalize("NFC", str(f)) for f in (d.get("files") or [])}


def is_holdout(stem: str, holdout: set[str] | None = None) -> bool:
    return unicodedata.normalize("NFC", stem) in (holdout_files() if holdout is None else holdout)


class HoldoutError(ValueError):
    """Ağırlık ayarı holdout dosyasına dokunamaz."""


def tuning_set(gt_dir: Path, requested: list[str] | None = None) -> list[Path]:
    """Ayar kümesi = GT dosyaları − holdout. `requested` içinde holdout dosyası varsa HoldoutError."""
    hold = holdout_files()
    if requested:
        bad = [r for r in requested if is_holdout(Path(r).stem, hold)]
        if bad:
            raise HoldoutError(f"holdout dosyası ayar kümesine alınamaz: {bad}")
        return [Path(gt_dir) / (Path(r).stem + ".json") for r in requested]
    return [p for p in sorted(Path(gt_dir).glob("*.json")) if not is_holdout(p.stem, hold)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gt", default="data/ground_truth")
    ap.add_argument("--only", nargs="*", default=None, help="ayar kümesini bu dosyalarla sınırla (holdout reddedilir)")
    a = ap.parse_args(argv)
    try:
        files = tuning_set(Path(a.gt), a.only)
    except HoldoutError as ex:
        print(f"REDDEDİLDİ: {ex}", file=sys.stderr); return 2
    print(f"ayar kümesi ({len(files)} dosya, holdout hariç): " + ", ".join(p.stem for p in files))
    print("ağırlık ayarı henüz uygulanmadı (yeni kaynak + fam00 GT sonrası holdout ile).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
