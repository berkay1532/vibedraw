# main.py
from __future__ import annotations
import argparse

from graph import run_pipeline


def cli() -> None:
    p = argparse.ArgumentParser(description="DXF mimari altlıktan aydınlatma+priz elektrik projesi üret")
    p.add_argument("dxf", help="Girdi DXF yolu")
    p.add_argument("-o", "--out", default="output/elektrik.dxf", help="Çıktı DXF yolu")
    p.add_argument("--floor", type=int, default=1, help="Hedef kat indeksi (soldan, 0 tabanlı)")
    p.add_argument("--gap", type=float, default=80.0, help="Kat kümeleme x-boşluğu eşiği")
    p.add_argument("--rules", default="rules/residential.yaml", help="Kural tablosu yolu")
    args = p.parse_args()

    run_pipeline(args.dxf, out_path=args.out, target_floor=args.floor,
                 gap=args.gap, rules_path=args.rules)
    print(f"Tamam → {args.out}")


if __name__ == "__main__":
    cli()
