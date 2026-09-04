#!/usr/bin/env python3
"""Veri seti tarama CLI.

Kullanım:
    python3 triage_dataset.py <klasör> [--out output/dataset_triage.md] [--threshold 0.5]

Klasördeki (özyinelemeli) DWG/DXF dosyalarını profiller, katman parmak izine göre
mimar ailelerine gruplar ve Markdown + JSON rapor yazar.
DWG dosyaları ODA File Converter veya LibreDWG (dwg2dxf) ile <klasör>/_dxf/ altına çevrilir; dönüştürücü yoksa raporda listelenir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from core.perception.triage import (
    scan_files, profile_dxf, group_families, render_report, pair_candidates,
    find_converter, convert_dwg_dir, convert_dwg_files,
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="DWG/DXF klasörü")
    ap.add_argument("--out", default="output/dataset_triage.md")
    ap.add_argument("--threshold", type=float, default=0.5, help="Aile Jaccard eşiği")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    files = scan_files(root)
    dwgs = [f for f in files if f.suffix.lower() == ".dwg"]
    dxfs = [f for f in files if f.suffix.lower() == ".dxf"]
    skipped = []

    if dwgs:
        conv = find_converter()
        if conv:
            kind, exe = conv
            conv_dir = os.path.join(root, "_dxf")
            print(f"[triage] {len(dwgs)} DWG → DXF ({kind}: {exe}) → {conv_dir}", file=sys.stderr)
            if kind == "oda":
                convert_dwg_dir(root, conv_dir, exe)
            else:
                convert_dwg_files(dwgs, conv_dir, exe)
            converted = [f for f in scan_files(conv_dir) if f.suffix.lower() == ".dxf"]
            have = {f.stem.lower() for f in converted}
            skipped = [str(f.relative_to(root)) for f in dwgs if f.stem.lower() not in have]
            # aynı isimli DXF zaten varsa (AutoCAD'den çıkmış) onu tercih et, çift saymayı önle
            existing = {f.stem.lower() for f in dxfs}
            dxfs = sorted(set(dxfs) | {f for f in converted if f.stem.lower() not in existing})
        else:
            skipped = [str(f.relative_to(root)) for f in dwgs]
            print(f"[triage] DWG dönüştürücü yok (brew install libredwg); {len(dwgs)} DWG atlandı", file=sys.stderr)

    profiles = []
    for i, f in enumerate(dxfs, 1):
        print(f"[triage] {i}/{len(dxfs)} {f.name}", file=sys.stderr)
        profiles.append(profile_dxf(str(f)))

    fams = group_families(profiles, threshold=args.threshold)
    md = render_report(profiles, fams, skipped_dwg=skipped)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps({"profiles": [asdict(p) for p in profiles],
                    "families": [[p.path for p in f] for f in fams],
                    "electrical_pairs": pair_candidates(profiles),
                    "skipped_dwg": skipped}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    n_e = sum(1 for p in profiles if p.verdict == "ELEKTRİK")
    n_c = sum(1 for p in profiles if p.verdict == "ADAY")
    n_cf = sum(1 for f in fams if any(p.verdict == "ADAY" for p in f))
    print(f"\n{len(profiles)} dosya | {n_c} ADAY | {n_e} ELEKTRİK | {len(fams)} aile ({n_cf} aday içeren) → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
