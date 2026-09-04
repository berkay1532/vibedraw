# Elektrik Projesi Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bir DXF mimari altlıktan tek konut katı için aydınlatma + priz sembolleri ve linyeleri üreten, uçtan uca çalışan deterministik Python pipeline prototipi.

**Architecture:** 5 saf (framework-bağımsız) aşama fonksiyonu — Parse → Mahallendirme → Karar Motoru → Yerleşim → DXF Üretim — aralarında doğrulama. LangGraph yalnızca ince orkestrasyon kabuğudur. Mühendislik kararları deterministik YAML kural tablosundan gelir; LLM yalnızca bilinmeyen oda ismi normalizasyonu ve gerekçe metni üretir, asla sayı üretmez.

**Tech Stack:** Python 3.9, ezdxf (DXF oku/yaz), PyYAML (kural tablosu), langgraph (orkestrasyon), anthropic (LLM), pytest (test).

> **Git notu:** Kullanıcı şimdilik git deposu istemedi. Her görevin son adımı "Checkpoint: tüm testler yeşil" olarak yazıldı. Git başlatılınca her görev sonunda commit önerilir.

> **Test stratejisi:** Testler büyük örnek dosyaya bağımlı değildir — her test ezdxf ile kendi küçük sentetik DXF'ini üretir. Böylece testler hızlı ve deterministiktir. LLM çağrıları monkeypatch ile mock'lanır (API'ye gidilmez).

---

## File Structure

```
core/
  ir.py          # Veri modelleri: Room, Floor, BuildingIR, Symbol, RoomDesign, Circuit, DesignIR
  parse.py       # Aşama 1: DXF oku → BuildingIR
  semantics.py   # Aşama 2: oda ismi → kanonik tip (sözlük + LLM fallback)
  rules.py       # Aşama 3: YAML kural tablosu yükle + karar motoru
  layout.py      # Aşama 4: etiket-merkezli sembol yerleşimi
  cad.py         # Aşama 5: blok tanımları + DXF üretimi
  llm.py         # İnce LLM arayüzü (mock'lanabilir)
  validate.py    # Aşamalar arası doğrulama + PipelineError
rules/
  residential.yaml   # Oda tipi başına aydınlatma/priz/linye kuralları
graph.py         # LangGraph kablolama (node = stage sarmalayıcı)
main.py          # CLI giriş noktası: DXF yolu al, pipeline çalıştır, output yaz
ornekler/
  empty-structure.dxf   # (mevcut) örnek girdi
output/          # üretilen DXF (gitignore'lanacak ileride)
tests/
  conftest.py    # ortak sentetik DXF fixture'ları
  test_parse.py
  test_semantics.py
  test_rules.py
  test_layout.py
  test_cad.py
  test_validate.py
  test_graph.py
```

---

## Task 1: Proje kurulumu ve bağımlılıklar

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `core/__init__.py` (boş)
- Create: `tests/__init__.py` (boş)

- [ ] **Step 1: requirements.txt yaz**

```
ezdxf==1.4.2
PyYAML>=6.0
langgraph>=0.2
anthropic>=0.40
pytest>=8.0
```

- [ ] **Step 2: pytest.ini yaz**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v
```

- [ ] **Step 3: Boş paket dosyalarını oluştur**

`core/__init__.py` ve `tests/__init__.py` boş dosyalar olarak oluşturulur.

- [ ] **Step 4: Bağımlılıkları kur**

Run: `python3 -m pip install --user -r requirements.txt`
Expected: ezdxf, pyyaml, langgraph, anthropic, pytest kurulu.

- [ ] **Step 5: Checkpoint**

Run: `python3 -c "import ezdxf, yaml, langgraph, anthropic; print('ok')"`
Expected: `ok`

---

## Task 2: IR veri modelleri

**Files:**
- Create: `core/ir.py`
- Test: `tests/test_ir.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_ir.py
from core.ir import Room, Floor, BuildingIR, Symbol, RoomDesign, Circuit, DesignIR


def test_room_defaults():
    r = Room(raw_name="Salon", label_xy=(10.0, 20.0))
    assert r.area_m2 is None
    assert r.room_type is None


def test_building_holds_floors_and_rooms():
    r = Room(raw_name="Salon", label_xy=(1.0, 2.0), area_m2=14.12, room_type="living")
    f = Floor(index=0, rooms=[r])
    b = BuildingIR(floors=[f], source_path="x.dxf")
    assert b.floors[0].rooms[0].room_type == "living"


def test_design_holds_symbols_and_circuits():
    sym = Symbol(kind="light", xy=(1.0, 2.0), circuit_id="A1")
    rd = RoomDesign(room=Room(raw_name="Salon", label_xy=(1.0, 2.0)),
                    fixtures=[sym], sockets=[], circuit_id="A1", rationale="...")
    c = Circuit(id="A1", kind="lighting", room_names=["Salon"])
    d = DesignIR(rooms=[rd], circuits=[c])
    assert d.rooms[0].fixtures[0].kind == "light"
    assert d.circuits[0].id == "A1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ir.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.ir'`

- [ ] **Step 3: core/ir.py yaz**

```python
# core/ir.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Room:
    raw_name: str                      # Çizimdeki ham isim, örn. "Yatak Odası"
    label_xy: tuple[float, float]      # Oda etiketinin konumu (≈oda merkezi)
    area_m2: Optional[float] = None    # "A: 14.12m²" yazısından okunur
    room_type: Optional[str] = None    # Kanonik tip, mahallendirmede doldurulur


@dataclass
class Floor:
    index: int
    rooms: list[Room] = field(default_factory=list)


@dataclass
class BuildingIR:
    floors: list[Floor] = field(default_factory=list)
    source_path: str = ""


@dataclass
class Symbol:
    kind: str                          # "light" | "socket"
    xy: tuple[float, float]
    circuit_id: str


@dataclass
class RoomDesign:
    room: Room
    fixtures: list[Symbol] = field(default_factory=list)   # aydınlatma
    sockets: list[Symbol] = field(default_factory=list)    # priz
    circuit_id: Optional[str] = None
    rationale: Optional[str] = None


@dataclass
class Circuit:
    id: str
    kind: str                          # "lighting" | "socket"
    room_names: list[str] = field(default_factory=list)


@dataclass
class DesignIR:
    rooms: list[RoomDesign] = field(default_factory=list)
    circuits: list[Circuit] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ir.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 3: Ortak test fixture'ı (sentetik DXF)

**Files:**
- Create: `tests/conftest.py`

Bu fixture, parse ve cad testlerinin kullanacağı küçük, kontrollü bir DXF üretir. Gerçek örnek dosyaya bağımlılığı ortadan kaldırır.

- [ ] **Step 1: conftest.py yaz**

```python
# tests/conftest.py
import ezdxf
import pytest


@pytest.fixture
def synthetic_dxf(tmp_path):
    """İki kat planı içeren küçük DXF: KAT 0 (x~0), KAT 1 (x~500).
    Her odada isim MTEXT + alan MTEXT (YAZI layer'ında)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("YAZI")

    def room(name, area, x, y):
        msp.add_mtext(name, dxfattribs={"layer": "YAZI", "insert": (x, y)})
        msp.add_mtext(f"A: {area}m²", dxfattribs={"layer": "YAZI", "insert": (x, y - 5)})

    # KAT 0 (x ~ 0..100)
    room("Salon", "14.12", 10, 100)
    room("Mutfak", "12.50", 60, 100)
    room("Banyo", "5.69", 10, 50)
    # KAT 1 (x ~ 500..600) — büyük x boşluğu ile ayrı küme
    room("Yatak Odası", "17.97", 510, 100)
    room("Hol", "4.41", 560, 100)

    path = tmp_path / "synthetic.dxf"
    doc.saveas(path)
    return str(path)
```

- [ ] **Step 2: Fixture'ın yüklendiğini doğrula**

Run: `python3 -m pytest tests/conftest.py -v`
Expected: collect edilir, hata yok (test yok ama import temiz).

- [ ] **Step 3: Checkpoint** — import hatası yok.

---

## Task 4: Parse — metin çıkarma ve temizleme

**Files:**
- Create: `core/parse.py`
- Test: `tests/test_parse.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_parse.py
from core.parse import extract_yazi_texts, is_area_text, parse_area


def test_extract_yazi_texts(synthetic_dxf):
    texts = extract_yazi_texts(synthetic_dxf)
    contents = [t.content for t in texts]
    assert "Salon" in contents
    assert any(c.startswith("A:") for c in contents)
    # her metnin konumu var
    assert all(isinstance(t.xy, tuple) and len(t.xy) == 2 for t in texts)


def test_is_area_text():
    assert is_area_text("A: 14.12m²") is True
    assert is_area_text("Salon") is False


def test_parse_area():
    assert parse_area("A: 14.12m²") == 14.12
    assert parse_area("A: 5m²") == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parse.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.parse'`

- [ ] **Step 3: core/parse.py yaz (bu kısım)**

```python
# core/parse.py
from __future__ import annotations
import re
from dataclasses import dataclass

import ezdxf

AREA_RE = re.compile(r"A:\s*([\d]+(?:\.[\d]+)?)\s*m²")


@dataclass
class YaziText:
    content: str
    xy: tuple[float, float]


def _plain(entity) -> str:
    """MTEXT/TEXT içeriğini biçim kodlarından arındır."""
    if entity.dxftype() == "MTEXT":
        return entity.plain_text().strip()
    return entity.dxf.text.strip()


def extract_yazi_texts(dxf_path: str, layer: str = "YAZI") -> list[YaziText]:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    out: list[YaziText] = []
    for e in msp:
        if e.dxftype() in ("MTEXT", "TEXT") and e.dxf.layer == layer:
            content = _plain(e)
            if not content:
                continue
            x, y, *_ = e.dxf.insert
            out.append(YaziText(content=content, xy=(float(x), float(y))))
    return out


def is_area_text(content: str) -> bool:
    return AREA_RE.search(content) is not None


def parse_area(content: str) -> float:
    m = AREA_RE.search(content)
    if not m:
        raise ValueError(f"Alan yazısı değil: {content!r}")
    return float(m.group(1))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parse.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 5: Parse — isim/alan eşleştirme

**Files:**
- Modify: `core/parse.py`
- Test: `tests/test_parse.py` (ek test)

- [ ] **Step 1: Failing test ekle**

```python
# tests/test_parse.py (append)
from core.parse import extract_yazi_texts, pair_names_with_areas


def test_pair_names_with_areas(synthetic_dxf):
    texts = extract_yazi_texts(synthetic_dxf)
    rooms = pair_names_with_areas(texts)
    by_name = {r.raw_name: r for r in rooms}
    assert "Salon" in by_name
    assert abs(by_name["Salon"].area_m2 - 14.12) < 1e-6
    # alan yazıları oda olarak sayılmamalı
    assert all(not r.raw_name.startswith("A:") for r in rooms)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parse.py::test_pair_names_with_areas -v`
Expected: FAIL with `ImportError: cannot import name 'pair_names_with_areas'`

- [ ] **Step 3: core/parse.py'a ekle**

```python
# core/parse.py (append)
import math
from core.ir import Room


def pair_names_with_areas(texts: list[YaziText]) -> list[Room]:
    names = [t for t in texts if not is_area_text(t.content)]
    areas = [t for t in texts if is_area_text(t.content)]
    rooms: list[Room] = []
    for nt in names:
        area_val = None
        if areas:
            nearest = min(
                areas,
                key=lambda at: math.hypot(at.xy[0] - nt.xy[0], at.xy[1] - nt.xy[1]),
            )
            area_val = parse_area(nearest.content)
        rooms.append(Room(raw_name=nt.content, label_xy=nt.xy, area_m2=area_val))
    return rooms
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parse.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 6: Parse — kat kümeleme ve BuildingIR

**Files:**
- Modify: `core/parse.py`
- Test: `tests/test_parse.py` (ek test)

- [ ] **Step 1: Failing test ekle**

```python
# tests/test_parse.py (append)
from core.parse import cluster_floors, parse_dxf


def test_cluster_floors_separates_by_x_gap(synthetic_dxf):
    from core.parse import extract_yazi_texts, pair_names_with_areas
    rooms = pair_names_with_areas(extract_yazi_texts(synthetic_dxf))
    floors = cluster_floors(rooms, gap=200.0)
    assert len(floors) == 2
    # ilk küme (küçük x) Salon/Mutfak/Banyo içerir
    assert {r.raw_name for r in floors[0].rooms} == {"Salon", "Mutfak", "Banyo"}


def test_parse_dxf_selects_target_floor(synthetic_dxf):
    building = parse_dxf(synthetic_dxf, target_floor=1, gap=200.0)
    assert len(building.floors) == 1
    names = {r.raw_name for r in building.floors[0].rooms}
    assert names == {"Yatak Odası", "Hol"}
    assert building.source_path == synthetic_dxf
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parse.py::test_cluster_floors_separates_by_x_gap -v`
Expected: FAIL with `ImportError: cannot import name 'cluster_floors'`

- [ ] **Step 3: core/parse.py'a ekle**

```python
# core/parse.py (append)
from core.ir import Floor, BuildingIR


def cluster_floors(rooms: list[Room], gap: float = 80.0) -> list[Floor]:
    """Odaları x-ekseni boşluğuna göre kümeler; soldan sağa sıralı Floor listesi döner."""
    if not rooms:
        return []
    ordered = sorted(rooms, key=lambda r: r.label_xy[0])
    clusters: list[list[Room]] = [[ordered[0]]]
    for r in ordered[1:]:
        if r.label_xy[0] - clusters[-1][-1].label_xy[0] > gap:
            clusters.append([r])
        else:
            clusters[-1].append(r)
    return [Floor(index=i, rooms=c) for i, c in enumerate(clusters)]


def parse_dxf(dxf_path: str, target_floor: int = 1, gap: float = 80.0) -> BuildingIR:
    """Aşama 1 giriş noktası: DXF → seçili katı içeren BuildingIR."""
    texts = extract_yazi_texts(dxf_path)
    rooms = pair_names_with_areas(texts)
    floors = cluster_floors(rooms, gap=gap)
    if not floors:
        raise ValueError("DXF'te oda etiketi bulunamadı")
    idx = min(target_floor, len(floors) - 1)
    return BuildingIR(floors=[floors[idx]], source_path=dxf_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parse.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Gerçek örnek dosyada elle doğrula (regresyon değil, gözlem)**

Run:
```bash
python3 -c "from core.parse import parse_dxf; b=parse_dxf('ornekler/empty-structure.dxf', target_floor=1); print([r.raw_name for r in b.floors[0].rooms])"
```
Expected: KAT 2 odaları listelenir (Salon, Mutfak, Yatak Odası, Banyo, Hol, Kat Holü, Balkon civarı).

- [ ] **Step 6: Checkpoint** — tüm testler yeşil + örnek dosya çıktısı makul.

---

## Task 7: LLM arayüzü (mock'lanabilir)

**Files:**
- Create: `core/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_llm.py
from core import llm


def test_normalize_room_name_uses_client(monkeypatch):
    captured = {}

    def fake_call(prompt, model):
        captured["prompt"] = prompt
        captured["model"] = model
        return "bedroom"

    monkeypatch.setattr(llm, "_call_text", fake_call)
    result = llm.normalize_room_name("Ebeveyn Yatak")
    assert result == "bedroom"
    assert "Ebeveyn Yatak" in captured["prompt"]


def test_explain_decision_uses_client(monkeypatch):
    monkeypatch.setattr(llm, "_call_text", lambda prompt, model: "Çünkü yüksek güç.")
    txt = llm.explain_decision("kitchen separate circuit", {"area": 14.5})
    assert "yüksek güç" in txt.lower() or len(txt) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.llm'`

- [ ] **Step 3: core/llm.py yaz**

```python
# core/llm.py
from __future__ import annotations
import os

MODEL_NORMALIZE = "claude-haiku-4-5-20251001"
MODEL_EXPLAIN = "claude-sonnet-4-6"

# Kanonik oda tipleri — LLM çıktısı bu kümeyle sınırlanır.
CANONICAL_TYPES = {
    "living", "kitchen", "bedroom", "bathroom", "wc",
    "circulation", "balcony", "office", "stairs", "other",
}


def _call_text(prompt: str, model: str) -> str:
    """Gerçek Anthropic çağrısı. Testlerde monkeypatch ile değiştirilir."""
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def normalize_room_name(raw_name: str) -> str:
    """Bilinmeyen oda ismini kanonik tipe eşler. Sayı/mühendislik kararı ÜRETMEZ."""
    prompt = (
        "Aşağıdaki Türkçe oda ismini şu standart tiplerden BİRİNE eşle ve "
        "yalnızca tek kelime tip adını döndür.\n"
        f"Tipler: {', '.join(sorted(CANONICAL_TYPES))}\n"
        f"Oda ismi: {raw_name!r}\n"
        "Yanıt (tek kelime):"
    )
    result = _call_text(prompt, MODEL_NORMALIZE).strip().lower()
    return result if result in CANONICAL_TYPES else "other"


def explain_decision(rule_summary: str, context: dict) -> str:
    """Deterministik kararın insan-dili gerekçesini üretir. Kararı DEĞİŞTİRMEZ."""
    prompt = (
        "Bir elektrik mühendisliği kararının kısa (1-2 cümle) gerekçesini Türkçe yaz. "
        "Karar zaten verildi; sen yalnızca neden mantıklı olduğunu açıkla. Sayı önerme.\n"
        f"Karar: {rule_summary}\n"
        f"Bağlam: {context}\n"
    )
    return _call_text(prompt, MODEL_EXPLAIN)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_llm.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil (API'ye gidilmedi, mock kullanıldı).

---

## Task 8: Mahallendirme — sözlük + LLM fallback

**Files:**
- Create: `core/semantics.py`
- Test: `tests/test_semantics.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_semantics.py
from core.ir import Room, Floor, BuildingIR
from core import semantics


def _building(*names):
    rooms = [Room(raw_name=n, label_xy=(0.0, 0.0), area_m2=10.0) for n in names]
    return BuildingIR(floors=[Floor(index=0, rooms=rooms)])


def test_known_names_mapped_by_dictionary(monkeypatch):
    # Sözlük yeterse LLM ASLA çağrılmamalı
    def boom(*a, **k):
        raise AssertionError("LLM çağrılmamalıydı")
    monkeypatch.setattr(semantics.llm, "normalize_room_name", boom)

    b = semantics.classify(_building("Salon", "Mutfak", "Yatak Odası", "WC", "Kat Holü"))
    types = [r.room_type for r in b.floors[0].rooms]
    assert types == ["living", "kitchen", "bedroom", "wc", "circulation"]


def test_unknown_name_falls_back_to_llm(monkeypatch):
    monkeypatch.setattr(semantics.llm, "normalize_room_name", lambda raw: "bedroom")
    b = semantics.classify(_building("Ebeveyn Suiti"))
    assert b.floors[0].rooms[0].room_type == "bedroom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_semantics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.semantics'`

- [ ] **Step 3: core/semantics.py yaz**

```python
# core/semantics.py
from __future__ import annotations

from core.ir import BuildingIR
from core import llm

# Ham isim (casefold edilmiş) → kanonik tip
ROOM_DICTIONARY = {
    "salon": "living",
    "oturma odası": "living",
    "mutfak": "kitchen",
    "yatak odası": "bedroom",
    "çocuk odası": "bedroom",
    "banyo": "bathroom",
    "wc": "wc",
    "hol": "circulation",
    "kat holü": "circulation",
    "balkon": "balcony",
    "ofis": "office",
    "merdiven": "stairs",
}


def map_name(raw_name: str) -> str | None:
    """Sözlükten kanonik tip döndürür; yoksa None."""
    return ROOM_DICTIONARY.get(raw_name.strip().casefold())


def classify(building: BuildingIR) -> BuildingIR:
    """Aşama 2: her odaya room_type atar. Sözlük tutmazsa LLM'e sorar."""
    for floor in building.floors:
        for room in floor.rooms:
            mapped = map_name(room.raw_name)
            if mapped is None:
                mapped = llm.normalize_room_name(room.raw_name)
            room.room_type = mapped
    return building
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_semantics.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 9: Kural tablosu (YAML)

**Files:**
- Create: `rules/residential.yaml`
- Test: `tests/test_rules.py` (yükleme testi)

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_rules.py
from core.rules import load_rules


def test_load_rules_has_expected_types():
    rules = load_rules("rules/residential.yaml")
    assert "living" in rules
    assert rules["kitchen"]["circuit"] == "kitchen"
    assert rules["bedroom"]["sockets"]["min"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.rules'`

- [ ] **Step 3: rules/residential.yaml yaz**

```yaml
# Konut katı — aydınlatma/priz/linye kuralları (prototip seviyesi).
# lighting.per_m2: bir armatürün kapsadığı alan; adet = max(min, ceil(area/per_m2))
# sockets.min: asgari priz adedi
# circuit: linye grubu adı (aynı grup aynı linyeye bağlanır)

living:    {lighting: {min: 1, per_m2: 12}, sockets: {min: 4}, circuit: general}
kitchen:   {lighting: {min: 1, per_m2: 10}, sockets: {min: 4}, circuit: kitchen}
bedroom:   {lighting: {min: 1, per_m2: 14}, sockets: {min: 3}, circuit: general}
bathroom:  {lighting: {min: 1, per_m2: 12}, sockets: {min: 1}, circuit: wet}
wc:        {lighting: {min: 1, per_m2: 12}, sockets: {min: 0}, circuit: wet}
circulation: {lighting: {min: 1, per_m2: 12}, sockets: {min: 1}, circuit: general}
balcony:   {lighting: {min: 1, per_m2: 20}, sockets: {min: 1}, circuit: general}
office:    {lighting: {min: 1, per_m2: 10}, sockets: {min: 4}, circuit: general}
stairs:    {lighting: {min: 1, per_m2: 15}, sockets: {min: 0}, circuit: general}
other:     {lighting: {min: 1, per_m2: 15}, sockets: {min: 1}, circuit: general}
```

- [ ] **Step 4: core/rules.py'a yükleyici ekle (ilk parça)**

```python
# core/rules.py
from __future__ import annotations
import yaml


def load_rules(path: str = "rules/residential.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Checkpoint** — tüm testler yeşil.

---

## Task 10: Karar motoru (deterministik)

**Files:**
- Modify: `core/rules.py`
- Test: `tests/test_rules.py` (ek testler)

- [ ] **Step 1: Failing test ekle**

```python
# tests/test_rules.py (append)
from core.ir import Room, Floor, BuildingIR
from core.rules import decide


def _b(name, rtype, area):
    r = Room(raw_name=name, label_xy=(0.0, 0.0), area_m2=area, room_type=rtype)
    return BuildingIR(floors=[Floor(index=0, rooms=[r])])


def test_decide_counts_lighting_by_area(monkeypatch):
    # LLM gerekçesini devre dışı bırak (deterministik sayıyı test ediyoruz)
    import core.rules as R
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: None)
    rules = R.load_rules("rules/residential.yaml")
    design = decide(_b("Salon", "living", 25.0), rules)
    rd = design.rooms[0]
    # 25 m² / 12 per_m2 -> ceil = 3 armatür
    assert len(rd.fixtures) == 3
    assert len(rd.sockets) == 4          # living min 4
    assert all(s.kind == "light" for s in rd.fixtures)


def test_decide_assigns_kitchen_separate_circuit(monkeypatch):
    import core.rules as R
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: None)
    rules = R.load_rules("rules/residential.yaml")
    design = decide(_b("Mutfak", "kitchen", 14.5), rules)
    assert design.rooms[0].circuit_id.startswith("kitchen")
    kinds = {c.id: c.kind for c in design.circuits}
    assert design.rooms[0].circuit_id in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rules.py::test_decide_counts_lighting_by_area -v`
Expected: FAIL with `ImportError: cannot import name 'decide'`

- [ ] **Step 3: core/rules.py'a karar motoru ekle**

```python
# core/rules.py (append)
import math
from core.ir import BuildingIR, DesignIR, RoomDesign, Symbol, Circuit
from core import llm


def _rationale(room_type: str, circuit_group: str, area: float):
    """LLM gerekçe metni (opsiyonel). Sayı üretmez."""
    try:
        return llm.explain_decision(
            f"{room_type} odası '{circuit_group}' linye grubuna atandı",
            {"area_m2": area},
        )
    except Exception:
        return None  # LLM yoksa pipeline yine de çalışır


def _lighting_count(area: float | None, rule: dict) -> int:
    minimum = rule["lighting"]["min"]
    per = rule["lighting"].get("per_m2")
    if area and per:
        return max(minimum, math.ceil(area / per))
    return minimum


def decide(building: BuildingIR, rules: dict) -> DesignIR:
    """Aşama 3: her odaya armatür/priz adedi ve linye atar. Konumlar Aşama 4'te."""
    design = DesignIR()
    circuits: dict[str, Circuit] = {}

    for floor in building.floors:
        for room in floor.rooms:
            rule = rules.get(room.room_type, rules["other"])
            group = rule["circuit"]

            light_cid = f"{group}-L"
            socket_cid = f"{group}-P"
            for cid, kind in ((light_cid, "lighting"), (socket_cid, "socket")):
                c = circuits.setdefault(cid, Circuit(id=cid, kind=kind))
                if room.raw_name not in c.room_names:
                    c.room_names.append(room.raw_name)

            n_light = _lighting_count(room.area_m2, rule)
            n_socket = rule["sockets"]["min"]

            rd = RoomDesign(
                room=room,
                fixtures=[Symbol(kind="light", xy=(0.0, 0.0), circuit_id=light_cid)
                          for _ in range(n_light)],
                sockets=[Symbol(kind="socket", xy=(0.0, 0.0), circuit_id=socket_cid)
                         for _ in range(n_socket)],
                circuit_id=light_cid,
                rationale=_rationale(room.room_type, group, room.area_m2 or 0.0),
            )
            design.rooms.append(rd)

    design.circuits = list(circuits.values())
    return design
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rules.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 11: Yerleşim (etiket-merkezli)

**Files:**
- Create: `core/layout.py`
- Test: `tests/test_layout.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_layout.py
from core.ir import Room, RoomDesign, Symbol, DesignIR
from core.layout import place


def _design():
    room = Room(raw_name="Salon", label_xy=(100.0, 200.0), area_m2=14.0, room_type="living")
    rd = RoomDesign(
        room=room,
        fixtures=[Symbol("light", (0.0, 0.0), "general-L")],
        sockets=[Symbol("socket", (0.0, 0.0), "general-P") for _ in range(3)],
        circuit_id="general-L",
    )
    return DesignIR(rooms=[rd])


def test_single_light_placed_at_label():
    d = place(_design())
    light = d.rooms[0].fixtures[0]
    assert light.xy == (100.0, 200.0)


def test_sockets_distributed_around_label_uniquely():
    d = place(_design())
    coords = [s.xy for s in d.rooms[0].sockets]
    # her priz ayrı konumda ve hiçbiri etiket noktasıyla çakışmıyor
    assert len(set(coords)) == len(coords)
    assert (100.0, 200.0) not in coords
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.layout'`

- [ ] **Step 3: core/layout.py yaz**

```python
# core/layout.py
from __future__ import annotations
import math

from core.ir import DesignIR, Symbol

SOCKET_RADIUS = 30.0   # etiket çevresinde priz dağıtım yarıçapı (çizim birimi)
LIGHT_GAP = 25.0       # birden fazla armatür arası yatay aralık


def _ring(cx: float, cy: float, n: int, r: float) -> list[tuple[float, float]]:
    """Merkez etrafında n noktayı çembersel dağıtır."""
    if n <= 0:
        return []
    return [
        (cx + r * math.cos(2 * math.pi * i / n),
         cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def place(design: DesignIR) -> DesignIR:
    """Aşama 4: armatür ve prizlere etiket-merkezli konum verir."""
    for rd in design.rooms:
        cx, cy = rd.room.label_xy

        # Armatürler: tek ise merkeze, çok ise yatay sırada
        n = len(rd.fixtures)
        start = cx - (n - 1) * LIGHT_GAP / 2
        for i, f in enumerate(rd.fixtures):
            rd.fixtures[i] = Symbol("light", (start + i * LIGHT_GAP, cy), f.circuit_id)

        # Prizler: etiket çevresinde çembersel
        ring = _ring(cx, cy, len(rd.sockets), SOCKET_RADIUS)
        for i, s in enumerate(rd.sockets):
            rd.sockets[i] = Symbol("socket", ring[i], s.circuit_id)

    return design
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_layout.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 12: DXF üretimi (bloklar + yeni layer'lar)

**Files:**
- Create: `core/cad.py`
- Test: `tests/test_cad.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_cad.py
import ezdxf
from core.ir import Room, RoomDesign, Symbol, Circuit, DesignIR
from core.cad import write_dxf


def _design():
    room = Room(raw_name="Salon", label_xy=(100.0, 200.0), area_m2=14.0, room_type="living")
    rd = RoomDesign(
        room=room,
        fixtures=[Symbol("light", (100.0, 200.0), "general-L")],
        sockets=[Symbol("socket", (130.0, 200.0), "general-P")],
        circuit_id="general-L",
    )
    return DesignIR(rooms=[rd], circuits=[Circuit("general-L", "lighting", ["Salon"]),
                                          Circuit("general-P", "socket", ["Salon"])])


def test_write_dxf_preserves_source_and_adds_layers(synthetic_dxf, tmp_path):
    out = str(tmp_path / "out.dxf")
    write_dxf(_design(), source_path=synthetic_dxf, out_path=out)

    doc = ezdxf.readfile(out)
    layer_names = {l.dxf.name for l in doc.layers}
    assert {"EL-AYDINLATMA", "EL-PRIZ", "EL-LINYE"} <= layer_names
    # mimari altlık korunmuş (YAZI hâlâ var)
    assert "YAZI" in layer_names

    msp = doc.modelspace()
    inserts = [e for e in msp if e.dxftype() == "INSERT"]
    used_blocks = {e.dxf.name for e in inserts}
    assert "EL_LIGHT" in used_blocks
    assert "EL_SOCKET" in used_blocks


def test_write_dxf_draws_circuit_polyline(synthetic_dxf, tmp_path):
    out = str(tmp_path / "out2.dxf")
    write_dxf(_design(), source_path=synthetic_dxf, out_path=out)
    doc = ezdxf.readfile(out)
    msp = doc.modelspace()
    linye = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "EL-LINYE"]
    assert len(linye) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cad.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.cad'`

- [ ] **Step 3: core/cad.py yaz**

```python
# core/cad.py
from __future__ import annotations
import os

import ezdxf

from core.ir import DesignIR

LAYER_LIGHT = "EL-AYDINLATMA"
LAYER_SOCKET = "EL-PRIZ"
LAYER_LINYE = "EL-LINYE"
SYM_SIZE = 8.0  # sembol yarıçapı (çizim birimi)


def _ensure_layers(doc):
    for name, color in ((LAYER_LIGHT, 2), (LAYER_SOCKET, 4), (LAYER_LINYE, 3)):
        if name not in doc.layers:
            doc.layers.add(name, color=color)


def _define_blocks(doc):
    """Basit sembol blokları: lamba = daire + çarpı, priz = yarım daire benzeri."""
    if "EL_LIGHT" not in doc.blocks:
        blk = doc.blocks.new(name="EL_LIGHT")
        blk.add_circle((0, 0), SYM_SIZE)
        blk.add_line((-SYM_SIZE, 0), (SYM_SIZE, 0))
        blk.add_line((0, -SYM_SIZE), (0, SYM_SIZE))
    if "EL_SOCKET" not in doc.blocks:
        blk = doc.blocks.new(name="EL_SOCKET")
        blk.add_circle((0, 0), SYM_SIZE)
        blk.add_line((0, 0), (0, SYM_SIZE * 1.5))


def write_dxf(design: DesignIR, source_path: str, out_path: str) -> str:
    """Aşama 5: kaynak DXF'i koru, yeni layer'lara semboller + linye ekle, yaz."""
    doc = ezdxf.readfile(source_path)
    msp = doc.modelspace()
    _ensure_layers(doc)
    _define_blocks(doc)

    # Linye grubuna göre sembol konumlarını topla (sıralı polyline için)
    circuit_points: dict[str, list[tuple[float, float]]] = {}

    for rd in design.rooms:
        for f in rd.fixtures:
            msp.add_blockref("EL_LIGHT", f.xy, dxfattribs={"layer": LAYER_LIGHT})
            circuit_points.setdefault(f.circuit_id, []).append(f.xy)
        for s in rd.sockets:
            msp.add_blockref("EL_SOCKET", s.xy, dxfattribs={"layer": LAYER_SOCKET})
            circuit_points.setdefault(s.circuit_id, []).append(s.xy)

    # Her linye için sembolleri birbirine bağlayan basit polyline
    for cid, pts in circuit_points.items():
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs={"layer": LAYER_LINYE})

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    doc.saveas(out_path)
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cad.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 13: Doğrulama (aşamalar arası)

**Files:**
- Create: `core/validate.py`
- Test: `tests/test_validate.py`

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_validate.py
import pytest
from core.ir import Room, Floor, BuildingIR, RoomDesign, Symbol, DesignIR
from core.validate import validate_building, validate_design, PipelineError


def test_validate_building_requires_room_type():
    b = BuildingIR(floors=[Floor(0, [Room("Salon", (0, 0), 10.0, room_type=None)])])
    with pytest.raises(PipelineError, match="room_type"):
        validate_building(b)


def test_validate_building_passes_when_typed():
    b = BuildingIR(floors=[Floor(0, [Room("Salon", (0, 0), 10.0, room_type="living")])])
    validate_building(b)  # raise etmemeli


def test_validate_design_requires_symbol_circuit():
    rd = RoomDesign(room=Room("Salon", (0, 0)), fixtures=[Symbol("light", (1, 1), "")])
    with pytest.raises(PipelineError, match="circuit"):
        validate_design(DesignIR(rooms=[rd]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.validate'`

- [ ] **Step 3: core/validate.py yaz**

```python
# core/validate.py
from __future__ import annotations

from core.ir import BuildingIR, DesignIR


class PipelineError(Exception):
    """Aşama kontratı ihlal edildiğinde fırlatılır; pipeline durur."""


def validate_building(building: BuildingIR) -> None:
    if not building.floors:
        raise PipelineError("BuildingIR boş: hiç kat yok")
    for floor in building.floors:
        for room in floor.rooms:
            if not room.room_type:
                raise PipelineError(f"Oda room_type eksik: {room.raw_name!r}")


def validate_design(design: DesignIR) -> None:
    if not design.rooms:
        raise PipelineError("DesignIR boş: hiç oda yok")
    for rd in design.rooms:
        for sym in (*rd.fixtures, *rd.sockets):
            if not sym.circuit_id:
                raise PipelineError(f"Sembol circuit_id eksik: {rd.room.raw_name!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_validate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 14: LangGraph orkestrasyon kabuğu

**Files:**
- Create: `graph.py`
- Test: `tests/test_graph.py`

LangGraph yalnızca saf aşama fonksiyonlarını düğüm olarak bağlar; mantık `core/` içindedir.

- [ ] **Step 1: Failing test yaz**

```python
# tests/test_graph.py
from graph import build_graph, run_pipeline


def test_run_pipeline_end_to_end(synthetic_dxf, tmp_path, monkeypatch):
    # LLM'i tamamen mock'la (gerekçe + bilinmeyen isim ihtimaline karşı)
    import core.semantics as S
    import core.rules as R
    monkeypatch.setattr(S.llm, "normalize_room_name", lambda raw: "other")
    monkeypatch.setattr(R, "_rationale", lambda *a, **k: "test gerekçe")

    out = str(tmp_path / "result.dxf")
    state = run_pipeline(synthetic_dxf, out_path=out, target_floor=0,
                         gap=200.0, rules_path="rules/residential.yaml")
    assert state["out_path"] == out

    import ezdxf
    doc = ezdxf.readfile(out)
    layer_names = {l.dxf.name for l in doc.layers}
    assert "EL-AYDINLATMA" in layer_names


def test_build_graph_is_constructible():
    g = build_graph()
    assert g is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph'`

- [ ] **Step 3: graph.py yaz**

```python
# graph.py
from __future__ import annotations
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END

from core.parse import parse_dxf
from core.semantics import classify
from core.rules import load_rules, decide
from core.layout import place
from core.cad import write_dxf
from core.validate import validate_building, validate_design


class PipelineState(TypedDict, total=False):
    dxf_path: str
    out_path: str
    target_floor: int
    gap: float
    rules_path: str
    building: object       # BuildingIR
    design: object         # DesignIR


def _parse_node(s: PipelineState) -> PipelineState:
    return {"building": parse_dxf(s["dxf_path"], s.get("target_floor", 1), s.get("gap", 80.0))}


def _semantics_node(s: PipelineState) -> PipelineState:
    b = classify(s["building"])
    validate_building(b)
    return {"building": b}


def _decide_node(s: PipelineState) -> PipelineState:
    rules = load_rules(s.get("rules_path", "rules/residential.yaml"))
    return {"design": decide(s["building"], rules)}


def _layout_node(s: PipelineState) -> PipelineState:
    d = place(s["design"])
    validate_design(d)
    return {"design": d}


def _cad_node(s: PipelineState) -> PipelineState:
    write_dxf(s["design"], source_path=s["dxf_path"], out_path=s["out_path"])
    return {}


def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse", _parse_node)
    g.add_node("semantics", _semantics_node)
    g.add_node("decide", _decide_node)
    g.add_node("layout", _layout_node)
    g.add_node("cad", _cad_node)
    g.add_edge(START, "parse")
    g.add_edge("parse", "semantics")
    g.add_edge("semantics", "decide")
    g.add_edge("decide", "layout")
    g.add_edge("layout", "cad")
    g.add_edge("cad", END)
    return g.compile()


def run_pipeline(dxf_path: str, out_path: str, target_floor: int = 1,
                 gap: float = 80.0, rules_path: str = "rules/residential.yaml") -> dict:
    app = build_graph()
    return app.invoke({
        "dxf_path": dxf_path,
        "out_path": out_path,
        "target_floor": target_floor,
        "gap": gap,
        "rules_path": rules_path,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_graph.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Checkpoint** — tüm testler yeşil.

---

## Task 15: CLI giriş noktası + gerçek dosyada uçtan uca çalıştırma

**Files:**
- Create: `main.py`

- [ ] **Step 1: main.py yaz**

```python
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
```

- [ ] **Step 2: Tüm test paketini çalıştır**

Run: `python3 -m pytest -v`
Expected: tüm testler PASS.

- [ ] **Step 3: Gerçek örnek dosyada uçtan uca çalıştır**

> LLM aktif (Task seçimi C). `ANTHROPIC_API_KEY` ortam değişkeni gerekir. Bilinmeyen isim çıkmazsa normalize LLM çağrılmaz; gerekçe için Sonnet çağrılır.

Run:
```bash
export ANTHROPIC_API_KEY=sk-...   # kullanıcı sağlar
python3 main.py ornekler/empty-structure.dxf -o output/elektrik.dxf --floor 1
```
Expected: `Tamam → output/elektrik.dxf` ve `output/elektrik.dxf` oluşur.

- [ ] **Step 4: Çıktıyı gözle doğrula**

Run:
```bash
python3 -c "import ezdxf; d=ezdxf.readfile('output/elektrik.dxf'); m=d.modelspace(); print('INSERT:', sum(1 for e in m if e.dxftype()=='INSERT')); print('LINYE:', sum(1 for e in m if e.dxftype()=='LWPOLYLINE' and e.dxf.layer=='EL-LINYE'))"
```
Expected: INSERT sayısı > 0 (semboller), LINYE sayısı > 0.

- [ ] **Step 5: AutoCAD'de aç (manuel, kullanıcı)**

`output/elektrik.dxf`'i AutoCAD'de aç; KAT 2 odalarında lamba/priz sembolleri ve linyeler görünmeli; mimari altlık bozulmamış olmalı. Bu, feasibility kanıtının görsel teyididir.

- [ ] **Step 6: Checkpoint** — tüm testler yeşil + örnek dosyada DXF üretildi.

---

## Self-Review Notları (yazım sırasında yapıldı)

- **Spec kapsamı:** Parse (T4-6), Mahallendirme + LLM (T7-8), Karar motoru + YAML (T9-10), Yerleşim (T11), DXF üretim (T12), Doğrulama (T13), LangGraph (T14), uçtan uca (T15) — spec'teki tüm aşamalar karşılandı.
- **Tip tutarlılığı:** `Room`, `Symbol`, `RoomDesign`, `Circuit`, `BuildingIR`, `DesignIR` Task 2'de tanımlandı; sonraki tüm görevler aynı imzaları kullanıyor. `circuit_id` alanı sembollerde tutarlı; linye id formatı `{group}-L` / `{group}-P` her yerde aynı.
- **LLM sınırı:** `decide` sayıları deterministik üretir; LLM yalnızca `_rationale` ve `normalize_room_name`'de — sayı üretmiyor (spec ilkesiyle uyumlu).
- **Placeholder yok:** Her kod adımı tam içerikli; TODO/TBD yok.
