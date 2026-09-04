# Mimari — Perception katmanı (DWG/DXF → Building IR)

Bu belge hedef mimariyi tanımlar. Mevcut kod (`core/geometry.py`, `core/parse.py`)
bu hedefe `docs/REFACTOR_PLAN.md` ile taşınır. Sözleşmeler burada; kod buraya uyar,
tersi değil.

Perception, daha büyük ürünün ilk katmanıdır:

```
DWG/DXF ──► [ PERCEPTION ] ──► BuildingIR ──► [ ELEKTRİK MOTORU ] ──► elektrik projesi (DXF)
                 bu belge                          henüz planlanmadı
```

`BuildingIR` iki katman arasındaki tek sözleşmedir. Perception'ın çıktısına elektrik
kavramı girmez; elektrik motoru DXF'e dokunmaz.

---

## 1. Akış

```
                    DWG / DXF
                        │
                        ▼
          ┌──────────────────────────┐
          │ 1. Parser                │  DWG→DXF (libredwg/ODA), ezdxf
          │    flatten + normalize   │  xref/blok çözme, birim → mm, ayrık pafta kümeleri
          └────────────┬─────────────┘
                       ▼
          ┌──────────────────────────┐
          │ 2. Discovery &           │  katman istatistikleri, kalınlık histogramı,
          │    Calibration           │  text yükseklikleri, kapı yayı yarıçapları
          └────────────┬─────────────┘  → FileParams (upm, wall_thickness_modes, ...)
                       ▼
          ┌──────────────────────────┐
          │ 3. Name Normalizer       │  katman/blok/oda-etiketi → enum
          │    (vocab + LLM, cache)  │  ◄── source_profiles/<fingerprint>.yaml
          └────────────┬─────────────┘
                       ▼
          ┌──────────────────────────┐
          │ 4. Signal Engine         │  bağımsız sinyaller, her biri → (skor, kanıt)
          │    (deterministik)       │  layer · geometry · block · topology · text
          └────────────┬─────────────┘
                       ▼
          ┌──────────────────────────┐
          │ 5. Staged Detection      │  walls → wall graph → openings → rooms
          │    (adaylar, sabit       │  → text binding → units
          │     sözleşmeler)         │  erken kesin karar yok
          └────────────┬─────────────┘
                       ▼
                 Candidate IR  (her eleman: confidence + evidence)
                       │
                       ▼
          ┌──────────────────────────┐
          │ 6. Validator             │  kapalı oda, oda başına ≥1 kapı, alan≈text,
          │    (deterministik)       │  dış çevre kapalı, kalınlık makul ...
          └────────────┬─────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
  yüksek güven                  düşük güven / kontrol başarısız
        │                             ▼
        │              ┌──────────────────────────┐
        │              │ 7. VLM/LLM ikinci görüş  │  bölge crop → {label, conf}
        │              │    (arayüz arkasında)    │  overlay → "eksik var mı?"
        │              └──────────────┬───────────┘
        │                ┌────────────┴────────────┐
        │                ▼                         ▼
        │            çözüldü                 hâlâ belirsiz
        │                │                         ▼
        │                │              ┌──────────────────────┐
        │                │              │ 8. Human-in-the-loop │  görsel kart, tek tık
        │                │              │    + %5 rastgele     │
        │                │              └──────────┬───────────┘
        └────────────────┴─────────────────────────┘
                                 │
                                 ▼
                          Building IR  (JSON + temiz DXF)
                                 │
                                 ▼
          ┌──────────────────────────┐
          │ 9. Learning Log          │  {signals, prediction, answer, source, file}
          └────────────┬─────────────┘
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
  source profile   ağırlık kalibrasyonu  eval / regresyon seti
```

---

## 2. Aşama sözleşmeleri

Her aşama saf fonksiyondur: girdi dataclass → çıktı dataclass. Aşama, kendinden
önceki aşamanın çıktısından başka şey okumaz; ezdxf `doc`/`msp` yalnızca 1–2. aşamaya
girer, sonrasına `Drawing` modelimiz geçer.

| # | Modül | Girdi | Çıktı | YAPMAZ |
|---|---|---|---|---|
| 1 | `perception/parser.py` | dosya yolu | `Drawing` (entity listesi, dünya koordinatı, mm; `sheets: list[Sheet]`) | anlam çıkarma |
| 2 | `perception/calibration.py` | `Drawing` | `FileParams` | tespit |
| 3 | `perception/names.py` | `Drawing`, `SourceProfile` | `NameMap` (layer→LayerClass, block→BlockClass, text→RoomType) | geometri |
| 4 | `perception/signals/*.py` | `Drawing`, `FileParams`, `NameMap` | `Signal(name, target_id, score, evidence)` listesi | karar |
| 5a | `perception/walls.py` | sinyaller | `list[WallCandidate]` + `WallGraph` | kapı/oda |
| 5b | `perception/openings.py` | `WallGraph`, sinyaller | `list[OpeningCandidate]` (door/window/passage) | oda |
| 5c | `perception/rooms.py` | `WallGraph`, açıklıklar | `list[RoomCandidate]` (poligon) | isim |
| 5d | `perception/binding.py` | odalar, text'ler, açıklıklar | isim↔oda, kapı↔(oda,oda), daire kümeleri | geometri değişikliği |
| 6 | `perception/validate.py` | `CandidateIR` | `ValidationReport` (issue listesi, her issue bir hedef id + tip) | düzeltme |
| 7 | `perception/second_opinion.py` | issue + crop | `Resolution(label, conf)` | koordinat |
| 8 | `hitl/` | issue + crop | `Answer` | — |
| 9 | `learning/log.py` | her Answer/Resolution | JSONL | — |

**Kural:** bir aşamayı komple yeniden yazmak mümkün olmalı; girdi/çıktı tipi
değişmedikçe diğer aşamalar etkilenmez. Modül içi yardımcı fonksiyonlar `_` ile
başlar ve dışarıdan çağrılmaz.

---

## 3. Building IR şeması

`core/perception/ir.py`. Her tespit `Detected` tabanından türer.

```python
@dataclass
class Evidence:
    signals: dict[str, float]        # {"layer_name": 0.9, "parallel_pair": 0.8, ...}
    source: str                      # "block:KAPI80" | "arc" | "layer:.ABM-DUVAR" | "flood" | "hitl"
    note: str = ""

@dataclass
class Detected:
    id: str
    confidence: float                # 0..1, kalibre edilmiş
    evidence: Evidence
    status: str = "auto"             # auto | vlm_confirmed | human_confirmed | human_rejected

@dataclass
class Wall(Detected):
    a: Point; b: Point               # merkez hattı, mm
    thickness: float                 # mm
    kind: str                        # exterior | interior | partition | unknown

@dataclass
class Opening(Detected):
    kind: str                        # door | window | passage
    wall_id: str
    center: Point; width: float
    hinge: Point | None = None       # kapı için
    swing_dir: Point | None = None
    rooms: tuple[str | None, str | None] = (None, None)   # bağladığı oda id'leri

@dataclass
class Room(Detected):
    polygon: list[Point]
    raw_name: str | None
    room_type: str | None            # RoomType enum
    area_m2_text: float | None       # çizimdeki yazı
    area_m2_geom: float | None       # poligondan
    aliases: list[str]
    unit_id: str | None

@dataclass
class Unit:                          # daire
    id: str; room_ids: list[str]; entry_opening_id: str | None

@dataclass
class Floor:
    index: int; name: str | None
    walls: list[Wall]; openings: list[Opening]; rooms: list[Room]; units: list[Unit]
    params: FileParams

@dataclass
class BuildingIR:
    source_path: str
    source_fingerprint: str
    floors: list[Floor]
    validation: ValidationReport
    version: str = "2"
```

Kurallar:
- Koordinatlar **çizim biriminde**, orijin dosyanın kendi orijini; ölçek `FileParams.units_per_meter`
  ile taşınır ve `FileParams.to_mm()` yardımcısı vardır (Adım 2'de pipeline'da kullanılmaz).
  mm normalizasyonu Adım 3'te `calibration.py` ile gelir (bkz. docs/DECISIONS.md, 2026-09-04).
- `confidence` olmayan hiçbir eleman listeye giremez.
- Elektrik alanı (device, circuit, appliance) **yok**. Elektrik motoru kendi IR'ını
  `BuildingIR`'dan türetir.
- Eski `core/ir.py` (v1) elektrik prototipi için kalır; yeni kod v2'yi kullanır.

---

## 4. Sinyal motoru

Her sinyal `signals/<domain>.py` içinde saf fonksiyon:

```python
def signal_parallel_pair(drawing, params) -> list[Signal]:
    """Her düz segment için: kalınlık aralığında, örtüşen paralel eşi var mı → 0..1"""
```

Skor birleştirme `perception/scoring.py`'de, ağırlıklar `config/weights.yaml`'da:

```yaml
wall:
  layer_class: 0.35
  parallel_pair: 0.30
  thickness_mode: 0.20
  graph_connectivity: 0.15
door:
  block_class: 0.40
  arc_signature: 0.30
  wall_gap: 0.20
  layer_class: 0.10
```

Ağırlıklar başta elle; learning log biriktikçe lojistik regresyonla yeniden
hesaplanır (`learning/calibrate.py`). Kod içine yeni ağırlık yazılmaz.

Eşik ve sabitler iki yerden gelir:
- `FileParams` — dosyadan türetilen (upm, kalınlık modları, kapı genişliği medyanı,
  text yüksekliği medyanı).
- `config/thresholds.yaml` — dosyadan türetilemeyen, adlandırılmış (ör.
  `door_arc_sweep_deg: [55, 125]`, `min_room_area_m2: 1.0`).

---

## 5. Kaynak profili (source profile)

`source_profiles/<layer_fingerprint>.yaml`:

```yaml
fingerprint: 3fa9c1d2
label: "Ofis X (tahmini)"
layers:
  ".ABM-DUVAR": wall
  ".ABM-SIVA": wall
  "kapi": door
  "ince": furniture
blocks:
  "KAPI80": door
  "PEN120": window
room_names:
  "Y.O.": bedroom
learned_from: [tip-2_mimari, tip-4_mimari]
```

Profil `triage`'ın ürettiği parmak izinden bulunur. Yoksa boş profil ile başlanır;
HITL cevapları profile yazılır. Kodda hiçbir ofis katman adı yer almaz.

Genel sözlük (`perception/vocab.py`) yalnızca dil-bağımsız anahtar kelimeler içerir
(`duvar/wall/mur`, `kapi/door/porte`, `salon/living`...). Tek dosya, tek kaynak.

---

## 6. LLM / VLM slotları

Tek arayüz: `perception/second_opinion.py`

```python
class SecondOpinion(Protocol):
    def normalize_name(self, raw: str, options: list[str]) -> tuple[str, float]: ...
    def classify_region(self, png: bytes, question: str, options: list[str]) -> tuple[str, float]: ...
    def check_overlay(self, png: bytes) -> list[Issue]: ...
```

Model seçimi `config/models.yaml`; Anthropic/OpenAI/açık kaynak sağlayıcı
uygulamaları `second_opinion/providers/`. Pipeline kodu sağlayıcı adını bilmez.

Kullanım kuralları:
- `normalize_name`: yalnızca vocab tutmayınca; sonuç cache'lenir (`.cache/names.json`)
  ve profile yazılır.
- `classify_region`: yalnızca Validator issue'ları için; crop = hedef eleman +
  2 m margin; soru kapalı uçlu, seçenekler sabit.
- `check_overlay`: tespit overlay'i çizilmiş plan; çıktı "şurada bir şey eksik
  olabilir" tipi issue, koordinat değil bölge id'si.
- Hiçbir slot koordinat, kalınlık, poligon döndürmez.

---

## 7. Validator ve HITL

Validator issue tipleri (`perception/validate.py`):

| tip | tetik | HITL sorusu |
|---|---|---|
| `unknown_layer` | LayerClass=unknown ve ≥N entity | "Bu katman ne?" [duvar/kapı/pencere/mobilya/yazı/yoksay] |
| `open_room` | poligon kapanmıyor | "Bu boşluk?" [kapı/geçiş/pencere/duvar eksik] |
| `room_no_door` | oda kapısız | "Giriş nerede?" (crop, seçenek) |
| `area_mismatch` | \|text − geom\| > %15 | "Hangisi doğru?" |
| `ambiguous_opening` | door/window skoru yakın | [kapı/pencere/geçiş/hiçbiri] |
| `unlabeled_region` | kapalı bölge, etiket yok | "Bu alan?" [oda tipi listesi/yoksay] |
| `unit_split` | daire kümesi belirsiz | "Tek daire mi?" [evet/böl] |

Sıralama: etkisi en yüksek issue önce (unknown_layer → open_room → opening → text).
Her cevap `learning/log.py`'ye yazılır ve pipeline ilgili aşamadan itibaren
yeniden koşar. Yüksek güvenli tespitlerin %5'i rastgele denetime düşer.

HITL arayüzü bu repo kapsamında ilk aşamada CLI/JSON'dır (`hitl/cli.py`); web arayüzü
ayrı iş.

---

## 8. Learning log

`output/learning/<date>.jsonl`, her satır:

```json
{"ts": "...", "file": "tip-2_mimari", "fingerprint": "3fa9c1d2",
 "issue": "ambiguous_opening", "target_id": "op_17",
 "signals": {"arc_signature": 0.6, "wall_gap": 0.7, "block_class": 0.0},
 "predicted": "door", "predicted_conf": 0.58,
 "answer": "window", "answered_by": "human", "skipped": false}
```

Tüketiciler: `learning/to_profile.py` (kaynak profilini günceller),
`learning/calibrate.py` (ağırlık), `learning/to_gt.py` (onaylanmış dosyayı GT setine
ekler).

---

## 9. Eval

- `data/ground_truth/*.json` — el ile doğrulanmış; kademeler `tier: clean|typical|hard`.
- `evaluate.py` mevcut metriklere ek olarak: **güven kalibrasyonu** (confidence
  dilimlerine göre gerçek doğruluk), **issue sayısı / dosya** (HITL yükü),
  **tier bazlı** tablo.
- `docs/EVAL_HISTORY.md` — her perception commit'i için satır.

Veri seti hedefi: ≥15 dosya, ≥6 farklı parmak izi, en az 2 Revit/ArchiCAD export,
en az 2 patlatılmış-blok, en az 1 yabancı dil, birim mm/cm/m/boş hepsinden.

---

## 10. Dizin yapısı

Adım 3 sonrası gerçek yapı (Adım 4'te `vocab.py` eklendi). "(planlı)" olanlar henüz yok.

```
core/
  perception/
    ir.py  ir_v1.py  ir_compat.py         # v2 şema, eski v1 (pipeline içi), v1→v2 köprü + güven tablosu
    parse.py  vocab.py  calibration.py    # etiket çıkarımı + kat kümeleme, tek sözlük, dosya parametreleri
    blocks.py  walls.py  openings.py  windows.py   # blok açma, duvar, kapı, pencere tespiti
    raster.py  polygons.py  rooms.py      # bariyer/flood-fill, maske→poligon, oda ayrıştırma
    binding.py  pipeline.py  validate.py  # kapı↔oda / ad↔alan bağlama, orkestratör (plan seçimi + run_floor), doğrulama
    sheets.py  sheet_segment.py           # pafta anlama: görünüm ayırma + sınıflama (runner'a bağlı değil)
    triage.py  metrics.py  run_stamp.py   # veri seti profili/parmak izi, ölçüm, koşu damgası (tazelik)
    semantics.py  llm.py  vlm_doors.py    # isim normalizasyonu ve LLM/VLM (planlı: second_opinion/ altına)
    (planlı) names.py  scoring.py  signals/{layer,geometry,block,topology,text}.py
    (planlı) second_opinion/  providers/anthropic.py  providers/openai.py
  electrical/  ir.py rules.py layout.py devices.py cad.py appliances.py validate.py   # eski prototip (dokunulmaz)
graph.py                                  # elektrik prototipi LangGraph kablolaması (opsiyonel bağımlılık)
experiments/ run_baseline.py  survey_views.py        # koşucular: pipeline'ı çağırır, mantık taşımaz
evaluate.py  annotate.py  triage_dataset.py          # (planlı: experiments/ altına)
tools/       debug_*.py  render_raw.py  clean_input.py
(planlı) hitl/cli.py  learning/  config/  source_profiles/
docs/        ARCHITECTURE.md  REFACTOR_PLAN.md  EVAL_HISTORY.md  DECISIONS.md  HITL_QUESTIONS.md
```
