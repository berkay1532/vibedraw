# tests/test_config.py — thresholds/weights yüklenir; kod içinde başvurulan anahtarlar vardır
import re, pathlib
from core.perception.config import T, thresholds, weights


def test_thresholds_and_weights_load():
    th = thresholds(); w = weights()
    assert th["base_upm"] == 100.0 and th["base"]["res"] == 3.0 and w["door"]["weights"]["block_class"] == 0.7


def test_every_T_reference_exists():
    root = pathlib.Path("core/perception")
    refs = set()
    for f in list(root.glob("*.py")) + list(root.glob("signals/*.py")):
        for m in re.finditer(r'T\(("[^"]+")(?:,\s*("[^"]+"))?\)', f.read_text(encoding="utf-8")):
            refs.add(tuple(x.strip('"') for x in m.groups() if x))
    assert refs, "T() başvurusu bulunamadı"
    for path in refs:
        T(*path)                       # eksik anahtar KeyError verir
