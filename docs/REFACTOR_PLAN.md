# Refactor planı — mevcut koddan hedef mimariye

Sıra önemli: her adım bir öncekine dayanır. Her adım ayrı commit (gerekirse birkaç).
Adım biterken kutucuğu işaretle ve `docs/EVAL_HISTORY.md`'ye satır ekle.

**Genel kural:** 0–4. adımlar davranış değiştirmez; eval sonucu birebir aynı kalmalı.
Fark çıkarsa refactor'da hata var demektir, önce onu bul.

---

## Adım 0 — Ölçüm tabanı ve temizlik
- [x] `docs/EVAL_HISTORY.md` oluştur; mevcut `main` için baseline satırı ekle
      (toplam oda F1/IoU, kapı F1/konum/bağlantı, pencere F1, dosya sayısı).
- [x] `docs/DECISIONS.md`, `docs/HITL_QUESTIONS.md` boş şablonla oluştur.
- [x] `debug_*.py`, `render_raw.py`, `clean_input.py` → `tools/`. Import yollarını düzelt.
- [x] `requirements.txt`: `langgraph` opsiyonel (`requirements-electrical.txt`);
      `tests/test_graph.py` langgraph yoksa `pytest.importorskip` ile atlansın.
- [x] Kod içindeki tek-dosya referanslı yorumları (`tip-4 ANTRE`, `KAYAPINAR Hol` vb.)
      topla → `docs/HITL_QUESTIONS.md`'ye soru adayı olarak yaz. Yorumları kodda
      kısalt (mantık kalır, dosya adı gider).

**Kabul:** testler geçer, eval değişmez.

## Adım 1 — Perception / elektrik ayrımı
- [x] `core/electrical/` oluştur; `rules.py`, `layout.py`, `devices.py`, `cad.py`,
      eski `ir.py` (v1) buraya taşınır. `graph.py` bunlara bağlanır. Test yolları güncellenir.
- [x] `core/perception/` oluştur; `parse.py`, `geometry.py`, `sheets.py`, `triage.py`,
      `metrics.py`, `vlm_doors.py`, `semantics.py`, `llm.py` buraya taşınır (içerik aynı).
- [x] `_detect_stove` ve `appliance_pts`'i perception'dan çıkar → `core/electrical/`
      içinde `BuildingIR` üzerinden çalışan ayrı fonksiyon.

**Kabul:** testler geçer, eval değişmez.

## Adım 2 — IR v2: güven + kanıt
- [x] `core/perception/ir.py`'de ARCHITECTURE §3 şemasını yaz (`Detected`, `Evidence`,
      `Wall`, `Opening`, `Room`, `Unit`, `Floor`, `BuildingIR` v2).
- [x] Eski v1 IR'dan v2'ye dönüştürücü (`ir_compat.py`) yaz; `run_baseline` v2 JSON yazsın,
      `evaluate.py` v2 okusun (v1 alan adlarını da tanısın, geçiş süresince).
- [x] Mevcut mantıktan güven türet — ilk sürüm kaba ama dürüst:
  - kapı: blok+yay 0.95 · yalnız yay 0.75 · yalnız blok 0.7 · ham katman kümesi 0.4
  - oda: dışlayıcı flood + poligon kapalı 0.85 · Voronoi paylaşım 0.5 · fallback (label_xy) 0.2
  - duvar: paralel çift + katman eşleşmesi 0.9 · yalnız paralel çift 0.6
  - pencere: katman/blok anahtar kelime 0.85 · ince paralel çizgi grubu 0.55
- [x] Her tespite `evidence.source` ve `evidence.signals` doldur (hangi yol bulduysa).
- [x] `evaluate.py`'ye **güven kalibrasyonu** tablosu ekle: [0–0.5, 0.5–0.7, 0.7–0.9, 0.9–1]
      dilimlerinde TP oranı.

**Kabul:** eval metrikleri değişmez; kalibrasyon tablosu üretilir. Yüksek dilimde
doğruluk düşük dilimden yüksek olmalı; değilse güven atamaları yanlış, düzelt.

## Adım 3 — geometry.py'yi parçala
`core/perception/geometry.py` (1424 satır) → aşağıdaki modüller (+ `raster.py`, `polygons.py`, `windows.py`; bkz. DECISIONS). Fonksiyonlar
taşınır, mantık değişmez. `reconstruct` yalnızca sıralayan bir orkestratör olur.
- [x] `calibration.py` — `estimate_units_from_doors`, `estimate_units_per_meter`,
      `scaled_params` (run_baseline'dan), `FileParams` dataclass.
- [x] `walls.py` — `_wall_segments`, `_pair_filter`, `_wall_lines`, `_hatch_segments`,
      `_is_label_frame`, `_ladder_filter`.
- [x] `openings.py` — `_swing_dirs`, `_block_door_hinge`, `_door_like_arc`,
      `_door_barriers`, `_cluster_doors`, `_insert_window`, `_thin_line_windows`,
      `_window_segments`, `_dedupe_windows`.
- [x] `rooms.py` — `_Raster`, `_flood`, `_seed_*`, `_segment_rooms`, `_mask_polygon`,
      `_staircase_polygon`, `_edge_snap_rect`, `_remove_small_steps`, `_force_rectilinear`.
- [x] `binding.py` — `_room_by_swing`, kapı↔oda eşleştirme, alias birleştirme,
      `pair_names_with_areas` (parse'tan).
- [x] `blocks.py` — `_explode`, `_block_extent`, `_is_big_block`, `_entity_segments`.
- [x] `reconstruct` → `pipeline.py::run_floor(drawing, params, profile) -> Floor`.
- [x] Her modül için mevcut testleri böl; her modüle en az bir test.

**Kabul:** testler geçer, eval değişmez, hiçbir modül 400 satırı geçmez.

## Adım 4 — Tek parse yolu, tek sözlük
- [x] `vocab.py` oluştur; `parse.ROOM_WORDS`, `triage.ROOM_VOCAB`,
      `semantics.ROOM_DICTIONARY`, `geometry.WINDOW_WORDS`, `_ANNO_LAYER_WORDS`,
      `sheets._KIND_WORDS` tek yere. Dil-bağımsız, genel kelimeler.
- [x] Eski `parse_dxf`, `extract_yazi_texts`, `cluster_floors` (x-only) sil;
      `graph.py` ve tüm çağıranlar `extract_room_labels` + `cluster_floors_2d` +
      `pick_plan_floor` yoluna geçer. `run_baseline.run_one` içindeki akış
      `pipeline.py`'ye taşınır (deney scripti pipeline'ı çağırır, mantık taşımaz).

**Kabul:** testler geçer, eval değişmez.

## Adım 5 — Katman adlarını koddan çıkar
- [x] `source_profiles/` + `SourceProfile` dataclass + yükleyici (`names.py`).
      `triage.layer_fingerprint` ile eşleşme.
- [x] Mevcut `WALL_LAYERS`, `DOOR_LAYERS`, `WINDOW_LAYERS`, `WALL_EXCLUDE_LAYERS`,
      `"ince"` içeriğini ilgili parmak izlerinin profil dosyalarına dağıt
      (hangi ofis hangi ad — triage çıktısına bak). Kodda kümeler boşalır.
- [~] `names.py::classify_layers(drawing, profile) -> NameMap`: (1-2 yapıldı; 3-4 aday)
      1) profil eşlemesi, 2) vocab anahtar kelimesi, 3) içerik istatistiği
      (entity tipi dağılımı, ortalama uzunluk, paralel çift oranı), 4) LLM (cache'li).
      Her katman için `LayerClass` + güven.
- [x] `walls/openings/rooms` modülleri katman adı yerine `NameMap` sınıfını kullanır.

**Kabul:** eval aynı ya da daha iyi; `grep -r "ABM\|PislikMimar\|\"ince\"" core/` boş.

## Adım 6 — Sinyal motoru ve config
- [x] `config/thresholds.yaml`, `config/weights.yaml`; `scoring.py`.
- [~] Fonksiyon gövdelerindeki sabitleri iki gruba ayır (kapı/kalibrasyon/plan seçimi/run_floor yapıldı; walls/windows/rooms/polygons/raster/blocks envanteri DECISIONS'ta, sonraki tur): dosyadan türeyenler
      `FileParams`'a, kalanlar `thresholds.yaml`'a adlandırılmış olarak. Sihirli sayı
      kalmayana kadar.
- [~] Mevcut heuristikleri `signals/` altında saf sinyal fonksiyonlarına dönüştür
      (kapı ve duvar yapıldı; oda/pencere sonraki tur — önce kapı: `block_class`, `arc_signature`, `wall_gap`, `layer_class`).
      Skor = ağırlıklı toplam; `confidence` artık buradan gelir.
- [ ] Kalibrasyon tablosu ile ağırlıkları ayarla — kullanıcı kararı: elle DEĞİL, yeni kaynak + fam00 GT geldikten sonra holdout ile.

**Kabul:** kalibrasyon tablosu monoton; kapı F1 düşmez.

## Adım 7 — Validator + issue üretimi
- [x] `validate.py`: ARCHITECTURE §7 tablosundaki issue tipleri (+ conflicting_layer, unit_suspect; unlabeled_region/unit_split planlı); `ValidationReport` IR'da.
- [x] `evaluate.py`'ye "issue/dosya" ve "issue tipine göre dağılım" ekle.
- [x] `hitl/cli.py`: issue'ları sırayla göster (crop PNG + seçenekler), cevabı
      `learning/log.py`'ye yaz, cevabı IR'a uygula, ilgili aşamadan yeniden koş (run_baseline hitl override'ları okur) — yapıldı.

**Kabul:** 7 GT dosyasında issue listesi elle bakıldığında anlamlı (sahte issue < %30).

## Adım 8 — Second opinion arayüzü
- [ ] `second_opinion/` Protocol + Anthropic sağlayıcı; `config/models.yaml`.
- [ ] `llm.py` → `normalize_name` (structured output, cache, profile'a yazma).
- [ ] `vlm_doors.py` → `classify_region` (aday başına crop, kapalı uçlu soru);
      tam-plan koordinat isteyen yol kaldırılır. `check_overlay` ilk sürüm.
- [ ] Eval: VLM açık/kapalı iki koşu; fark ve maliyet `EVAL_HISTORY`'ye.

## Adım 9 — Duvar grafı tabanlı ikinci oda sinyali
- [ ] `walls.py`'de merkez hattı birleştirme + kesişim snap → `WallGraph`.
- [ ] `rooms.py`'de shapely `polygonize` ile kapalı bölgeler (kapı bariyerleri kapalı).
- [ ] Flood-fill ve polygonize sonuçlarını eşleştir; ikisi örtüşüyorsa güven ↑,
      yalnız biri buluyorsa issue (`unlabeled_region` / `open_room`).

**Kabul:** oda recall artar ya da issue sayısı düşer; IoU düşmez.

## Adım 10 — Learning log tüketicileri
- [ ] `learning/to_profile.py`, `learning/to_gt.py`, `learning/calibrate.py` (basit
      lojistik regresyon, ≥200 kayıt olunca çalışır).

---

## Veri seti görevleri (paralel, kod değil)
- [ ] GT dosyalarına `tier` alanı ekle (clean/typical/hard).
- [ ] **fam00 GT önceliği (güncel karar 2026-09-05): 541_3, 541_5, 386_8 (536_1 çıkarıldı: plan seçimi şüpheli); ardından 553_3 veya 6249'dan birine sayısal-özet GT** (oda/kapı/pencere sayıları, poligonsuz; ağır dosya). 10 dosyalık en büyük aile, GT'si yok; ABM satırı yalnız fam04'ten besleniyor.
- [ ] GT kapılarına `rooms: [a, b]` (kapının bağladığı iki oda; v1 `connects` zaten bunu taşıyor)
      ve annotate aracına "ikinci oda" desteği → v2 "çift doğruluğu" metriği dolsun.
- [ ] En az 3 Revit/ArchiCAD export, 2 patlatılmış blok, 1 yabancı dil dosyası bul; GT çıkar.
- [ ] `triage` raporuna parmak izi başına dosya sayısı ve tier dağılımı ekle.
