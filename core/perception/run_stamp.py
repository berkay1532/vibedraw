# core/perception/run_stamp.py
"""Koşu damgası: pred JSON'ların hangi kodla ve ne zaman üretildiğini kaydeder; `evaluate.py`
karşılaştırmadan önce tazeliği doğrular (docs/DECISIONS.md "eval taze çıktı şartı", Adım 4).

Damga = perception kaynak dosyalarının içerik hash'i + git commit + koşu başlangıç zamanı.
`evaluate.py` her GT dosyası için: results.json kaydı var mı, koşu hatasız mı, hash şimdiki kodla
aynı mı, JSON koşudan sonra mı yazılmış — biri tutmazsa rapor üretmeden hata verir.
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
# Tahmini etkileyen dosyalar: kod + eşik/ağırlık config'i + profiller. config/holdout.yaml yalnız raporlamayı
# etkiler, hash'e girmez.
CODE_GLOBS = ("core/perception/*.py", "core/perception/signals/*.py", "config/thresholds.yaml", "config/weights.yaml",
              "source_profiles/*.yaml", "source_profiles/unions/*.json", "experiments/run_baseline.py")
EXCLUDE = {"core/perception/metrics.py"}          # yalnız ölçüm; tahmini etkilemez


def code_files(root: Path = ROOT, globs=CODE_GLOBS) -> list[Path]:
    out: list[Path] = []
    for g in globs:
        out += sorted(p for p in root.glob(g) if str(p.relative_to(root)) not in EXCLUDE)
    return out


def code_hash(root: Path = ROOT, globs=CODE_GLOBS) -> str:
    """Kaynak dosyaların (göreli yol + içerik) sha256'sının ilk 12 karakteri."""
    h = hashlib.sha256()
    for p in code_files(root, globs):
        h.update(str(p.relative_to(root)).encode("utf-8")); h.update(b"\0")
        h.update(p.read_bytes()); h.update(b"\0")
    return h.hexdigest()[:12]


def git_info(root: Path = ROOT) -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                                text=True, timeout=10).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "core", "experiments"], cwd=root,
                                    capture_output=True, text=True, timeout=10).stdout.strip())
    except Exception:
        commit, dirty = None, None
    return {"commit": commit, "dirty": dirty}


def make_stamp(root: Path = ROOT) -> dict:
    g = git_info(root)
    return {"code_hash": code_hash(root), "git_commit": g["commit"], "git_dirty": g["dirty"],
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def check_fresh(entry: Optional[dict], json_path: Path, current_hash: str) -> Optional[str]:
    """Bir pred JSON'un taze olmama nedeni; tazeyse None."""
    if entry is None:
        return "results.json'da kayıt yok"
    if entry.get("fail_stage"):
        return f"koşu hatalı ({entry['fail_stage']}): JSON eski koşudan kalma olabilir"
    st = entry.get("stamp")
    if not st:
        return "damgasız kayıt (Adım 4 öncesi koşu)"
    if st.get("code_hash") != current_hash:
        return f"kod değişmiş (koşu {st.get('code_hash')} ≠ şimdi {current_hash})"
    if not json_path.exists():
        return "pred JSON yok"
    started = datetime.fromisoformat(st["started_at"]).timestamp()
    if json_path.stat().st_mtime < started:
        return "pred JSON koşu başlangıcından eski"
    return None
