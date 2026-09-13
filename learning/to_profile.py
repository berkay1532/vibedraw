# learning/to_profile.py
"""Learning log → kaynak profili (Adım 10). Yalnız AKTARILABİLİR cevaplar profile yazılır:

  aktarılabilir (aileye ait bilgi):
    unknown_layer / conflicting_layer  → profile.layers[katman] = sınıf (katman adı ofise özgü, sınıfı aile geneli)
    unit_suspect                       → profile.units = {upm, answer, learned_from} (ofis çizim birimi; pipeline'da
                                          yalnız hipotez yolunda öncül adayı — dosyanın kendi kapı kestirimi öncelikli)
    (blok cevabı: henüz issue tipi yok — unknown_block adayı; geldiğinde profile.blocks)
  aktarılamayan (dosyanın geometrisine özgü, sonraki dosyaya taşınmaz):
    unlabeled_region, room_merged, room_no_door, window_missing, door_side_ambiguous, area_mismatch, open_room,
    ambiguous_opening → yalnız o dosyanın IR'ında (hitl/cli.py apply_answer) ve learning log'da kalır; ağırlık turu verisi.

Kullanım: python3 learning/to_profile.py [--pred output/baseline] [--log output/learning] [--dry-run]
Dosya → aile eşlemesi koşu JSON'undan (params.extra.family_id, source_fingerprint). Profilde zaten farklı sınıf varsa
mevcut korunur ve uyarı basılır (insan/GT cevabı profil kaydını sessizce ezmez)."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.perception.names import PROFILE_DIR, LayerClass  # noqa: E402
from learning import log as learning_log  # noqa: E402

TRANSFERABLE = ("unknown_layer", "conflicting_layer", "unit_suspect")
NOT_TRANSFERABLE = ("unlabeled_region", "room_merged", "room_no_door", "window_missing", "door_side_ambiguous",
                    "area_mismatch", "open_room", "ambiguous_opening")
# cevap kelimesi → LayerClass (hitl/cli.py CLASS_BY_ANSWER ile aynı; sınıf adı doğrudan da kabul edilir)
CLASS_BY_ANSWER = {"duvar": "wall", "kapı": "door", "pencere": "window", "mobilya": "furniture", "yazı": "text",
                   "açıklama-yazı": "text", "yoksay": "ignore", "merdiven": "stair", "kiriş": "beam", "kolon": "column",
                   "korkuluk": "railing", "baca": "chimney", "aks": "grid", "tarama": "hatch", "ölçü": "dim"}
UPM_BY_ANSWER = {"m": 1.0, "dm": 10.0, "cm": 100.0, "mm": 1000.0, "inç": 39.37}


def _layer_class(answer: str):
    v = CLASS_BY_ANSWER.get(answer, answer)
    try:
        return LayerClass(v)
    except ValueError:
        return None


def _family_of(pred_dir: Path, stem: str):
    p = pred_dir / f"{stem}.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text(encoding="utf-8"))
    ex = ((d.get("floors") or [{}])[0].get("params") or {}).get("extra") or {}
    return ex.get("family_id"), d.get("source_fingerprint")


def _load_yaml_with_header(path: Path):
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    header = "".join(l for l in text.splitlines(keepends=True) if l.startswith("#"))
    return header, (yaml.safe_load(text) or {})


def plan(records: list, pred_dir: Path) -> dict:
    """Kayıtlar → {family_id: {layers:{name:(cls, src)}, units:{...}, files:set, fingerprints:set}}, ayrıca tip sayımı."""
    by_fam: dict = defaultdict(lambda: {"layers": {}, "units": None, "files": set(), "fingerprints": set(), "skipped": []})
    counts = Counter()
    for r in records:
        if r.get("skipped"):
            continue
        kind = r.get("issue"); counts[kind] += 1
        if kind not in TRANSFERABLE:
            continue
        fam, fp = _family_of(pred_dir, r["file"])
        if not fam:
            by_fam["?"]["skipped"].append((r["file"], kind, "koşu JSON yok → aile bilinmiyor")); continue
        e = by_fam[fam]; e["files"].add(r["file"])
        if fp:
            e["fingerprints"].add(fp)
        if kind in ("unknown_layer", "conflicting_layer"):
            layer = (r.get("target_id") or "")[6:]
            cls = _layer_class(r.get("answer", ""))
            if layer and cls is not None:
                e["layers"][layer] = (cls, f"hitl {r['file']} ({r.get('answered_by', '?')})")
            else:
                e["skipped"].append((r["file"], kind, f"cevap sınıfa çevrilemedi: {r.get('answer')!r}"))
        elif kind == "unit_suspect":
            upm = UPM_BY_ANSWER.get(r.get("answer", ""))
            if upm:
                e["units"] = {"upm": upm, "answer": r["answer"], "learned_from": r["file"], "answered_by": r.get("answered_by", "?")}
            else:
                e["skipped"].append((r["file"], kind, f"birim cevabı tanınmadı: {r.get('answer')!r}"))
    return {"families": by_fam, "counts": counts}


def apply(p: dict, profile_dir: Path, dry_run: bool) -> list:
    lines = []
    for fam, e in p["families"].items():
        if fam == "?":
            continue
        path = profile_dir / f"{fam}.yaml"
        header, d = _load_yaml_with_header(path)
        d.setdefault("family_id", fam); d.setdefault("layers", {}); d.setdefault("notes", {})
        d.setdefault("learned_from", []); d.setdefault("fingerprints", [])
        for layer, (cls, src) in sorted(e["layers"].items()):
            cur = d["layers"].get(layer)
            if cur and cur != cls.value:
                lines.append(f"  UYARI {fam}: '{layer}' profilde '{cur}', cevap '{cls.value}' ({src}) — mevcut korundu"); continue
            if cur == cls.value:
                lines.append(f"  {fam}: '{layer}' zaten {cls.value}"); continue
            d["layers"][layer] = cls.value; d["notes"][layer] = src
            lines.append(f"  {fam}: layers['{layer}'] = {cls.value}  ← {src}")
        if e["units"]:
            u = e["units"]; cur = d.get("units")
            if cur and cur.get("upm") != u["upm"]:
                lines.append(f"  UYARI {fam}: units profilde {cur}, cevap {u} — mevcut korundu")
            else:
                d["units"] = {"upm": u["upm"], "answer": u["answer"], "source": f"hitl {u['learned_from']} ({u['answered_by']})"}
                lines.append(f"  {fam}: units = {d['units']}")
        for f in sorted(e["files"]):
            if f not in d["learned_from"]:
                d["learned_from"].append(f); lines.append(f"  {fam}: learned_from += {f}")
        for fp in sorted(e["fingerprints"]):
            if fp not in d["fingerprints"]:
                d["fingerprints"].append(fp); lines.append(f"  {fam}: fingerprints += {fp}")
        for f, kind, why in e["skipped"]:
            lines.append(f"  ATLANDI {fam} {f} {kind}: {why}")
        if not dry_run:
            path.write_text(header + yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            lines.append(f"  → {path}")
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred", default="output/baseline"); ap.add_argument("--log", default=None)
    ap.add_argument("--profiles", default=str(PROFILE_DIR)); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    recs = learning_log.read(Path(a.log) if a.log else None)
    p = plan(recs, Path(a.pred))
    print(f"learning log: {len(recs)} kayıt")
    print("aktarılabilir tipler:   " + ", ".join(f"{k}={p['counts'].get(k, 0)}" for k in TRANSFERABLE))
    print("aktarılamayan tipler:   " + ", ".join(f"{k}={p['counts'].get(k, 0)}" for k in NOT_TRANSFERABLE if p["counts"].get(k)))
    for l in apply(p, Path(a.profiles), a.dry_run):
        print(l)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
