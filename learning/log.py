# learning/log.py
"""Learning log (ARCHITECTURE §8): her HITL cevabı bir JSONL satırı, output/learning/<tarih>.jsonl."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "output" / "learning"


def append(record: dict, log_dir: Path | None = None) -> Path:
    """Kaydı günün dosyasına ekler; `ts` yoksa ekler. Dönen değer dosya yolu. log_dir None → LOG_DIR (çağrı anında)."""
    log_dir = Path(log_dir or LOG_DIR); log_dir.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    path = log_dir / f"{rec['ts'][:10]}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def read(log_dir: Path | None = None) -> list[dict]:
    log_dir = Path(log_dir or LOG_DIR)
    out = []
    for p in sorted(Path(log_dir).glob("*.jsonl")) if Path(log_dir).is_dir() else []:
        out += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return out
