# Kararlar ve adaylar

Biçim: **[karar|aday] tarih — başlık** · ne · neden · alternatif. "Aday" = görülen ama
uygulanmayan iyileştirme fikri; uygulanınca "karar" olur ve commit'i yazılır.

## Kararlar

- **[karar] 2026-09-04 — v1 IR'ın perception/elektrik bölünmesi (Adım 1).**
  `core/ir.py` ikiye ayrıldı: `core/perception/ir.py` (Room, Door, Floor, BuildingIR — perception
  sahibi) ve `core/electrical/ir.py` (Device, Symbol, RoomDesign, Circuit, DesignIR — Room'u
  perception'dan import eder). Neden: plan "ir.py electrical'a taşınır" diyor ama perception
  kodu Room/Floor/BuildingIR'a bağımlı; perception elektrikten import edemez (ARCHITECTURE §0).
  Alanlar ve mantık birebir korundu; `Floor.devices` şimdilik tipsiz liste olarak perception
  Floor'unda kaldı (aşağıdaki aday). Alternatif: tek dosyayı electrical'a taşıyıp perception'ı
  ona bağlamak — bağımlılık yönü ters olurdu.

- **[karar] 2026-09-04 — v2 IR koordinatları çizim biriminde kalır.** `FileParams.units_per_meter`
  ölçeği taşır, `to_mm()` yardımcısı var ama pipeline'da kullanılmaz; mm normalizasyonu Adım 3'te
  `calibration.py` ile. Neden: 7 GT dosyası ve `evaluate.py` çizim biriminde; eval dokunulmaz kalır.
  Alternatif: v2'de mm'ye dönüştürüp GT'yi de dönüştürmek — Adım 3'e ertelendi.
- **[karar] 2026-09-04 — kapı bağlantı metriği v1 gibi kalır.** v2 `Opening.rooms=(a, b)` taşır;
  uyumluluk katmanı `room_name = a` (yayın açıldığı oda). "Çift doğruluğu" yalnız raporlanır, GT'de
  ikinci oda alanı olana kadar boş kalır (veri seti görevi).
- **[karar] 2026-09-04 — güven değerleri (Adım 2, kaba ama dürüst).** Plan tablosuna ek: takma ad
  birleşimi 0.6 (`evidence.source="alias_merge"`), raster kenarına değen küçük bölge 0.4
  (`"edge_fragment"`), pencere bloğu anahtar kelimesiz geometriyle 0.7 (`"block_geometry"`; planda
  yoktu). Kalibrasyon tablosunda kaynaklar ayrı görünür.
- **[karar] 2026-09-04 — `Floor.devices` v2'de yok.** Elektrik motoru `BuildingIR`'dan kendi
  `DesignIR`'ını türetir; v1 Floor (ir_v1) prototip için alanı korur.
- **[karar] 2026-09-04 — `validate.py` bölündü.** `core/perception/validate.py` (validate_building,
  PipelineError) ve `core/electrical/validate.py` (validate_design). Kökte ortak dosya yok.
- **[karar] 2026-09-04 — v1 IR `core/perception/ir_v1.py`'ye alındı; `core/perception/ir.py` = v2.**
  Neden: v2 sınıf adları (Room/Floor/BuildingIR) v1 ile çakışıyor; pipeline içi v1 ile çalışmaya
  devam eder, çıktı `ir_compat.to_v2` ile v2'ye çevrilir (Adım 3-4'te iç kod da v2'ye geçer).
- **[karar] 2026-09-04 — geometry.py'ye kaynak (provenance) bilgisi eklendi, yeni tespit
  fonksiyonu eklenmedi.** Mevcut fonksiyonlar isteğe bağlı olarak "hangi yol buldu" döndürür
  (kapı: block+arc/arc/block/layer_raw; oda: exclusive/edge_fragment/alias_merge/voronoi/fallback;
  duvar: pair+layer/pair; pencere: layer/block_keyword/block_geometry/thin_lines). Davranış aynı.
- **[karar] 2026-09-04 — v2 `Wall.thickness` isteğe bağlı.** v1 duvarları YÜZ parçalarıdır
  (merkez hattı + kalınlık yok); merkez hattı Adım 9'da (duvar grafı) gelir. Şimdilik `a/b` yüz
  parçası, `thickness=None`, `kind="unknown"`.

- **[karar] 2026-09-04 — kalibrasyon bulguları (Adım 2 tablosu, 7 GT dosyası).**
  - `edge_fragment` (0.4) 5/5 eşleşti, `exclusive` (0.85) 0.89: dilim monotonluğu odada tutmuyor.
    0.4'te BIRAKILDI — 5 örnek tek kaynaktan (aynı ofis) ve hepsi balkon; bu "edge_fragment
    güvenilir" değil, "bu ofisin balkon çizim tarzı tutarlı" demek. Yeniden değerlendirme: yeni
    parmak izinden edge_fragment örneği gelince.
  - `window:thin_lines` (0.55) 0/9: dokuz aday dokuzu sahte. Sinyalin kendisi şüpheli → güven
    0.55→0.3 (yol silinmedi). Aynı tek-kaynak uyarısı geçerli ama 0/9 ile 5/5 aynı ağırlıkta değil.
    Adım 7'de bu sinyal `ambiguous_opening` sorusu üretecek (HITL_QUESTIONS #21).
  - `block+arc` (0.95) henüz gözlenmedi: blok kapıları ve bağımsız yaylar hiçbir dosyada aynı
    kümeye düşmedi. Değer duruyor.
  - NOT: `evaluate.py` güven eşiği uygulamaz; tüm tahminler sayılır. Güven değişikliği F1'i
    değiştirmez, yalnız kalibrasyon tablosunu. Aday: "güven ≥ eşik" ikinci metrik tablosu (aşağıda).

- **[karar] 2026-09-04 — Adım 3 modül bölünmesi, plandan sapmalar.** 400 satır sınırı için
  `rooms.py` üçe ayrıldı: `raster.py` (_Raster, dilatasyon, tohum, flood), `polygons.py` (maske →
  poligon), `rooms.py` (_segment_rooms, takma ad birleştirme, Voronoi — birleştirme mantığı
  `_segment_rooms` içinde olduğu için `binding.py`'ye alınmadı). `openings.py` kapılar, pencereler
  `windows.py`. `reconstruct` → `pipeline.run_floor` (aynı imza; `reconstruct` takma adı Adım 4'e
  kadar duruyor). `parse.parse_dxf` eski yolu `binding.pair_names_with_areas`'ı fonksiyon içi
  import ile çağırıyor (döngü önleme; Adım 4'te parse_dxf silinince kalkar). `FileParams` `ir.py`'de
  kaldı, `calibration` yeniden dışa aktarır.

- **[karar] 2026-09-04 — eval kapısı "taze çıktı" şartı.** Adım 3'te koşucu import hatasıyla anında
  çökünce `evaluate.py` eski JSON'ları okuyup "birebir aynı" dedi; tam kapı koşusu yakaladı.
  Kural: karşılaştırmadan önce koşu günlüğünde dosya başına "→ ok" satırı ve pred JSON mtime'ı
  doğrulanır. Aday (aşağıda): `evaluate.py` pred JSON'un koşu zaman damgasını rapora yazsın.

- **[karar] 2026-09-04 — Adım 4 tazelik kapısı kodda.** `core/perception/run_stamp.py`: koşu damgası
  = perception kaynaklarının içerik hash'i (12 hex) + git commit/kirli bayrağı + başlangıç zamanı;
  `run_baseline` her results.json kaydına yazar. `evaluate.py` her GT dosyası için kayıt yok / koşu
  hatalı / damgasız / kod hash'i farklı / JSON koşudan eski durumlarında rapor üretmeden çıkış 2 verir.
  İçerik hash'i seçildi (commit hash'i değil): commit'lenmemiş düzenleme de yakalanır. Geçersiz kılma
  bayrağı YOK (insan kontrolüne bırakılmasın). Rapor başlığına koşu damgası ve ölçüm anı commit'i yazılır.

- **[karar] 2026-09-04 — Adım 4 sözlük birleştirme.** `parse.ROOM_WORDS` (üst küme) ile
  `triage.ROOM_VOCAB` (alt küme; "kat holü, yemek, çalışma, toilet, dining, entrance, lobby" eksikti)
  tek liste `vocab.ROOM_WORDS` oldu; triage artık üst kümeyi kullanır. Etki ölçüldü: veri seti
  triage'ı (68 dosya) birleştirme öncesi/sonrası karşılaştırıldı: 68/68 verdict aynı (53 ADAY); tek profil
  farkı detayli-villa (İngilizce altlık): 'entrance' 2 etiket eklendi, n_room_texts 13→15, zaten ADAY.
  `vocab.fold` tek Türkçe casefold; `triage.tr_fold` ona alias, `metrics._tr_fold` alan ekini atan
  sarmalayıcı olarak kaldı (davranış aynı).

- **[karar] 2026-09-04 — Adım 4 eski yol silindi; yan etkiler.** `parse_dxf`, `extract_yazi_texts`,
  `cluster_floors` (x-only) kaldırıldı; `pipeline.reconstruct` alias'ı kaldırıldı (tek ad `run_floor`).
  results.json'daki `parse_stock` aşaması ve baseline raporundaki "Stok oda" sütunu gitti (eski yolun
  tek kullanıcısıydı). `run_baseline.run_one` akışı `pipeline.select_plan` (etiket → ölçek → kümeleme →
  kapı kanıtı → ölçek düzeltme) + `run_selected` (ölçekli parametreler → run_floor → v2) oldu; ölçek
  düzeltme adımı artık "labels_generic" aşamasında (eskiden "geometry" try bloğundaydı) — yalnız hata
  etiketlemesi değişir, çıktı değil. `MAX_CELLS` pipeline'a taşındı (config/ adayı). Test/araçlar için
  `pipeline.label_floors(dxf, gap)` yardımcısı eklendi (ölçek/plan seçimi yok; 2-etiketli sentetik
  dosyalar ≥3 kuralına takıldığı için). `graph.py` `select_plan` kullanır; `target_floor`/`gap`
  parametreleri kalktı. Döngüsel import: `parse_dxf` silinince parse→binding yerel importu da gitti.

- **[gözlem] 2026-09-04 — performans: AVİDA_PLAN.** Tek başına 900 s sınırıyla koşu: 547 s (tam kapıda 420 s'ye
  takılıyor). cProfile (select_plan 564 s + run_selected 217 s, profil yükü dahil): dosya 50 k modelspace
  entity, 1 845 INSERT ama **24 294 blok tanımı / 582 503 blok içi entity** (Revit tarzı export), 152 katman;
  ezdxf.readfile tek başına 36,5 s. Raster küçük: 58×14 m, res 3,23 → 1945×465 = 0,9 M hücre — darboğaz raster
  değil. En çok zaman yiyen üç şey: (1) `ezdxf.readfile` tekrarları — `extract_room_labels` 1 kez,
  `estimate_units_from_doors` msp verilmeyince her çağrıda yeniden okuyor (kapı-kanıtı döngüsü 8 küme + ölçek
  düzeltme 1 + run_floor 1 + parmak izi 1 ≈ 12 okuma ≈ 430 s; tagger.ascii_tags_loader/tag_compiler cProfile'da
  135 s), (2) `run_floor` kendi hesabı ≈ 40 s (duvar/pencere taraması 2 482 duvar parçası), (3) `raster._flood`
  200 çağrı 7,4 s. Düzeltme yapılmadı (kural). Aday: DXF'i bir kez okuyup `msp`'yi select_plan → calibration →
  run_floor boyunca taşımak (davranış değişmez, ~10× okuma kalkar); `experiments/` zaman aşımını dosya boyutuna
  göre ölçeklemek.

- **[karar] 2026-09-04 — Adım 5 kaynak profilleri (kullanıcı kararları + uygulama).** Anahtar triage ailesi
  (`source_profiles/fam<NN>.yaml`, NN = triage aile indeksi; aile 4+5 ve aynı parmak izli 33 → fam04).
  Profil yalnızca eski hardcode kümelerden taşınan ofise özgü adları taşır (12 profil, 3-19 ad); anahtar
  kelime kademesi kodda (`vocab.LAYER_WORDS`, `names.keyword_class`). Sınıf → tüketici kodda: bariyer
  {wall, beam, column, chimney, window}, duvar taraması {wall}, hariç {door, text, stair, beam} (eski
  WALL_EXCLUDE anlamı; dim/grid/hatch hariç tutulmadı — davranış değişmesin), kapı {door}, pencere {window}.
  Aile eşleştirme: parmak izi → yapısal örtüşme ≥0,5 → Jaccard ≥0,5 (`layer_union` profilde; 77-505 ad)
  → unknown. `.ABM-KIRIS`, `MERDIVEN YAZI` silindi (hiç dosyada yok). Kabul grep'i core/perception'da
  boş; `core/electrical/appliances.py` "ince" eşitliği elektrik prototipinde kaldı (dokunulmaz).
  Bilinen davranış değişiklikleri: (1) `pair+layer` kaynağı artık yalnız wall sınıfı (eskiden KOLON/BACA/
  pencere de) → duvar güveni 0,9→0,6 bazı parçalarda; (2) anahtar kelime kademesi profilsiz/ek katmanları
  da sınıflar (DUVAR, A_WALL_*, PENCERE, KAPI, A_DOOR_*, YAZI, OLCU, AKS…) → bariyer/kapı/pencere kaynağı
  genişledi. Eval farkları EVAL_HISTORY adım 5 satırında dosya bazında açıklanır.
- **[karar] 2026-09-04 — elektrik çizimi tespiti (triage).** Katman + blok adı ipuçları (`vocab.ELECTRICAL_*`),
  toplam ≥ ELECTRICAL_MIN=3 → verdict ELEKTRİK, ADAY dışı; aynı proje numaralı mimari dosyalar "girdi-çıktı
  çifti adayı" olarak raporlanır (`pair_candidates`). Yalnız katman adıyla (ELK/PRİZ/AYDINLATMA/LİNYE/ARMATÜR)
  2510-9 dosyaları 2 isabette kalıyordu (yalnız 'linye'); anahtar/buat/etanj blokları ayırt edici.

- **[ölçüm] 2026-09-04 — Adım 5 sözlük kademesi ablasyonu (GT-7, karar bekliyor).** Eski tahminler 7147322
  worktree'sinde yeniden üretilip varlık bazında karşılaştırıldı. Farkın kaynağı iki mekanizma:
  (a) `text`/`stair` sınıfına düşen katmanlar (A_ANNO_*, A_STAIR_*) duvar taramasından çıkınca onların çizgileri
  artık çift filtresine girmiyor → tip-1'de ANTRE+HOL birleşti (HOL kayıp, oda F1 1,0→0,842; DEPO sızdı IoU
  0,96→0,11), tip-4'te aynı mekanizma ANTRE'yi doğru birleştirdi (0,957→1,0). HITL #1/#2 ile aynı belirsizlik.
  (b) `door` sınıfına düşen A_DOOR_* katmanlarındaki INSERT'ler "kesin kapı" yoluna girdi → tip-1 +3, tip-6 +1
  sahte aday, menteşe blok matrisinden alınınca hata 0→0,021 m. (c) `window` (A_GLZ_GLS) pencere kaynağı:
  tip-6 pencere 0,75→0,828 (iyileşme). `wall` sınıfı yalnız IoU'yu ±0,01 oynatıyor.
  Kapılı varyant ölçüldü: sözlük kademesi yalnız EKLEYİCİ tüketicilere (bariyer, pencere kaynağı, duvar-katmanı
  güveni) beslenir; hariç tutma ve "kesin kapı" INSERT yolu profil güveni (0,9) ister → GT-7 toplam oda F1 0,901,
  kapı F1 0,951, pencere F1 0,802, IoU 0,885, bağlantı 0,904 = baseline ile aynı (IoU −0,003); tip-4 iyileşmesi
  ve tip-6 pencere iyileşmesi bu varyantta yok. Seçenekler: (1) kapılı varyant (baseline korunur, sinyal
  güvenine göre tüketim — CLAUDE.md ilke 2 ile uyumlu), (2) tam varyant (toplam düşer, tip-4/tip-6 iyileşir),
  (3) tam varyant + text/stair hariç tutmayı ve keyword-door INSERT yolunu ayrı sinyal ağırlığıyla Adım 6'ya
  bırakmak. Öneri: (1) şimdi, (3) Adım 6'da.

- **[karar] 2026-09-04 — Adım 5 kapılı varyant uygulandı (kullanıcı kararı).** `NameMap.has(layer, classes,
  min_conf)`; `GATED_MIN_CONF = PROFILE_CONF (0,9)`. Profil güveni isteyen yollar: duvar taramasından hariç
  tutma (`_wall_segments`) ve "kesin kapı" INSERT yolu (`_Raster`, `_swing_dirs` blok süzgeci gevşetme).
  Sözlük güveni (0,6) yeten ekleyici yollar: raster bariyeri, snap hedefi, pencere katman kaynağı, duvar
  katmanı güveni (`pair+layer`), kapı katmanı çizgileri (`layer_raw` adayı) ve ince-çizgi pencere adayı
  dışlaması. Pencere açıklaması: tip-6'daki 0,75→0,828 iyileşmesi pencere KAYNAĞINDAN değil, A_ANNO_* yazı
  katmanı çizgilerinin `_thin_line_windows` adaylarından dışlanmasından geliyordu (3 `thin_lines` sahtesi
  gitti: FP 5→2); ilk kapılı ölçümde bu dışlama da kapatıldığı için 0,802'ye dönmüştü. Dışlama pencere
  tarafında ekleyici tüketici sayıldı (kapının dışında) → tip-6 0,828 korunur, tip-1 1,0'a döner, tip-4 0,957
  (HITL #22 çelişen sinyal). `layer_union` yaml'dan `source_profiles/unions/<fam>.json` yan dosyasına taşındı.
  results.json tam koşuda ADAY dışına çıkan dosyaların eski kayıtlarını atar (rapor 49 satır).

- **[karar] 2026-09-04 — HITL #22 çelişen sinyal, Adım 6'da genel sinyal olarak.** Özel kural yok: `parallel_pair`
  katman sınıfından bağımsız her segment için hesaplanır, `layer_class` ayrı sinyal; ikisi çelişince düşük güvenli
  duvar + `conflicting_signal` issue (Adım 7). Adım 5'teki IoU −0,003 bilinçli kabul (EVAL_HISTORY).

- **[karar] 2026-09-04 — Adım 6 iskeleti (davranış değiştirmeden).** `config/thresholds.yaml` (adlandırılmış
  sabitler), `config/weights.yaml` (sinyal ağırlıkları), `config.py` (önbellekli yükleyici, eksik anahtar
  KeyError), `scoring.py`, `signals/{layer,geometry,block,topology,text}.py`. Kapı yolu: block+arc / arc /
  block / layer_raw / vlm etiketleri `block_class`, `arc_signature`, `layer_class` (geçiş: layer_raw yolu),
  `vlm` sinyallerine; eski deterministik filtreler kapı (gate) sinyali: `wall_gap` (menteşe ↔ duvar ≤
  door_wall_dist; duvar yoksa None = uygulanmaz) ve `room_boundary` (yalnız layer_raw yolunda, oda poligonu
  varsa). Birleşim max + uyum bonusu (0,20) tabloyu birebir üretir: 0,75+0,20 = 0,95. ARCHITECTURE'daki
  "ağırlıklı toplam" yerine bu biçim seçildi çünkü toplam (0,70+0,75) tabloyu üretemezdi. `Door.confidence`
  ve `Door.signals` v1'e eklendi; `ir_compat` varsa bunu kullanır (tablo yedek). `FileParams` dosyadan
  türeyen koşu parametrelerini alan olarak taşır (`calibration.file_params`); BASE ölçekleme ifadesi
  korundu (bit-bit aynı eval). config/*.yaml ve source_profiles/*.yaml koşu damgası hash'ine girdi.
  Ağırlık ayarı yapılmadı (kullanıcı kararı: holdout ile, fam00 GT sonrası).

  **Sabit envanteri (nereye gitti):**
  | Sabit (eski yer) | Değer | Yeni yer |
  |---|---|---|
  | BASE res/seal/margin/door_arc_radius/door_wall_dist/door_max_boundary_dist (calibration) | 3.0/18/250/(55,130)/25/15 @upm 100 | thresholds `base.*` → `FileParams` alanları (`file_params`) |
  | MAX_CELLS (pipeline) | 30 M | thresholds `raster.max_cells` |
  | seal_small 0.25 m, min 3 px, `seal // 2` (run_floor) | | `raster.seal_small_m / seal_small_min_px / seal_fallback_div` |
  | seed_rad 0.7 m / 12 px (run_floor) | | `raster.seed_radius_m / seed_radius_fallback_px` |
  | oda min piksel 30 (run_floor) | | `raster.min_room_px` |
  | kapı çizgisi merdiven elemesi 0.15–1.0 m, upm_est = amin/0.55 (raster, openings) | | `raster.door_seg_ladder_m`, `door.upm_from_arc_min_m` |
  | duvar kalınlığı 0.06–0.45 m, örtüşme 0.18 m (run_floor) | | `wall.thickness_m`, `wall.min_overlap_m` (+ FileParams.wall_thickness/wall_min_overlap) |
  | min_len 8·res, açılı 15·res, küme 3·res, oda başına 8 duvar, leak 0.45 (run_floor) | | `wall.min_len_res / angled_min_len_res / cluster_tol_res / adaptive_walls_per_room / leak_fraction` |
  | kapı yayı süpürme 55–125° (openings) | | `door.arc_sweep_deg` |
  | aday kümeleme max(20, amin·0.5), primary ≥2, yay eşleşme ×1.6, VLM tol 10 (run_floor) | | `door.cluster_radius_min_units / cluster_radius_frac / primary_min / swing_match_factor / vlm_snap_tol_units` |
  | kanat 0.875 m, küme %85, ≥3 yay, öncüller 100/1000, yarıçap 0.3–2.0×, kabul 0.25–4× (calibration, select_plan) | | `door.leaf_m / calib_top_frac / calib_min_doors / calib_priors / calib_radius_frac / upm_ratio_accept` |
  | açılış yönü cos ≥0.2, ceza 0.4, 460 birim (binding) | | `swing.cos_min / dist_penalty / max_dist_units` (460 ölçeklenmemiş — aday: metreye çevir) |
  | etiket: dedupe 0.5 m, küme 7/8 m, ≥3 oda, ilk 8 küme, bbox 2.5 m, tipik oda 3.5 m, tablo 0.85/16/0.3 m (select_plan, parse, calibration) | | `labels.*` |
  | run_floor imza varsayılanları (res 1.0, seal 8, margin 25, door_arc_radius (50,130), door_wall_dist 25, boundary 15) | | KALDI: API varsayılanı; sentetik testler kullanır (aday: FileParams zorunlu yapıp kaldır) |
  | walls: _pair_filter 4/42/8°/18, _ladder_filter 8°/0.5/3, _wall_lines 10°/15/3/90, etiket çerçevesi 3 m² | | KALDI (sonraki tur, `wall.*`) |
  | windows: yakın duvar 0.25/0.3 m, paralellik 0.97, blok 0.3–4.5 m / 0.4–4.0 m / 1.2 m, kapı yayı 0.65–1.5 m, aykırı 5 m, ince çizgi ≤0.1 m / 0.4–3.5 m / 0.6 m / 6, dedupe 0.3 m | | KALDI (sonraki tur, `window.*`) |
  | rooms/raster/polygons/blocks: leak 0.2, edge 40 %/30 px, seed 12 px, dilate 0.55/0.15, snap 4/8/12/3, colinear 0.05, büyük blok 3 m, explode derinliği 3, segment 0.2 | | KALDI (sonraki tur, `room.*`, `polygon.*`, `block.*`) |

- **[karar] 2026-09-04 — Adım 6 duvar sinyalleri (kullanıcı kararı).** `parallel_pair` (katman bağımsız;
  `_pair_filter`'ı geçen her parça 1), `layer_class` oyu (hedef sınıf 1 / başka BİLİNEN sınıf 0 / bilinmiyor
  None — None çelişki sayılmaz), `thickness_mode` (`calibration.thickness_modes`: 1 cm kutulu histogram, pay
  ≥ %10 olan yerel tepeler; `FileParams.wall_thickness_modes`; segment kalınlığı moda ≤ 2 cm → 1; ağırlık 0,
  holdout ayarına kadar), `graph_connectivity` (iskelet, None, ağırlık 0). Ağırlıklar parallel_pair 0,60 +
  layer_class 0,70 + uyum 0,20 → eski tablo birebir (pair 0,60 / pair+layer 0,90). `Wall.thickness` v2'ye
  çift kalınlığı olarak yazılır. Çelişki tanımı `scoring.is_conflicting`: ağırlığı > 0 ve değerlendirilmiş en
  az iki sinyal 0,5'in farklı taraflarında → `Evidence.note = conflicting_signal` (kapı için de: blok var, yay
  yok). Adım 7 bunu issue'ya çevirir; davranışa etkisi yok.
- **[karar] 2026-09-04 — holdout.** `config/holdout.yaml`: tip-6_mimari, 386_8 (GT gelince); kural: yeni
  kaynaktan her üç GT'den biri. `evaluate.py` holdout/geliştirme satırlarını ayrı basar, dosya tablosunda Küme
  sütunu. `learning/calibrate.py` iskeleti holdout dosyasını `--only` ile isteyeni HoldoutError ile reddeder.
  holdout.yaml koşu damgası hash'ine GİRMEZ (tahmini etkilemez); thresholds/weights/profiller girer.
- **[karar] 2026-09-04 — `swing.max_dist` metreye (ayrı commit).** 460 çizim birimi → 4,6 m × upm; upm yoksa
  (sentetik testler) 460 birim yedek. "Aynı" şartı yok; dosya bazında fark EVAL_HISTORY'de nedeniyle.

- **[karar] 2026-09-04 — oda/pencere güvenleri scoring'e.** Kaynaklar tek-sıcak sinyal (`flood_outcome`,
  `window_source`; uygulanmayanlar None → çelişki yok); ağırlıklar eski tablolar (room: exclusive 0,85 /
  alias_merge 0,60 / voronoi 0,50 / edge_fragment 0,40 / fallback 0,20; window: layer 0,85 / block_keyword 0,85 /
  block_geometry 0,70 / thin_lines 0,30), bonus 0. Eval birebir.
- **[karar] 2026-09-04 — Adım 7 validator + HITL CLI (kullanıcı kararları).** `conflicting_layer` katman
  düzeyinde: dosya × katman çelişkili segment oranı ≥ 0,3 ve sayı ≥ 20 → tek issue (katman, sınıf oyu, oran,
  sayı); segment bayrağı evidence'ta. `unit_suspect`: upm standart (1/10/100/1000) ±%25 dışında. Diğerleri
  ARCHITECTURE §7. `Wall.layer` v2'ye eklendi (provenance). `ValidationReport` run_selected'da dolar (JSON'da).
  `hitl/cli.py`: --list / --issue i (crop PNG: hedef kırmızı, DXF gri, odalar yeşil) / --answer; cevap
  `learning/log.py` JSONL (ARCHITECTURE §8 şeması) + IR JSON'a uygulanır (status human_confirmed/rejected,
  katman override'ı params.extra.hitl_layer_overrides, birim params.extra.hitl_units). Yeniden koşu yok (aday:
  run_baseline override'ları okusun). Dosya başına issue hedefi ≤ 5 (thresholds); ölçüm EVAL_HISTORY'de.

- **[düzeltme] 2026-09-04 — Türkçe katlama İngilizce büyük I'yı bozuyordu.** `vocab.fold` I→ı yapınca "WINDOW"
  → "wındow", "DIM" → "dım", "KITCHEN" → "kıtchen": sözlük eşleşmesi tutmuyordu (adım 7 issue yükünde
  unknown_layer 758'in büyük kısmı; İngilizce oda etiketleri de kaçıyordu). Çözüm `vocab.folds`/`has_word`:
  Türkçe ve düz casefold ikisi de denenir; tüketiciler: names.keyword_class, parse.looks_like_room_label,
  triage.room_hits/electrical_hits, windows._window_word, sheets başlık kelimeleri. Davranış değişir (İngilizce
  altlıklar): triage ADAY seti ve eval farkı EVAL_HISTORY'de dosya bazında.

- **[karar] 2026-09-05 — Adım 7 issue politikası (kullanıcı kararları a–g).** (a) `metrics.issue_coverage`:
  GT-7'deki her hatalı varlık (FP/FN oda-kapı-pencere, yanlış ad, yanlış bağlantı) için onu işaret eden issue
  var mı; evaluate "Issue kapsama" tablosu; her politika değişikliği issue/dosya + kapsama ile raporlanır.
  (b) `names.layer_stats/stats_class/refine_with_stats`: 3. kademe içerik istatistiği (upm bilinince): uzun düz
  çizgisi (≥1 m) olmayan katman → yazı/ölçü payı ≥ %80 text/dim, tarama ≥ %80 hatch, küçük yay + kısa çizgi
  ≥ %60 furniture, aksi ignore (güven 0,4, kaynak stats); uzun çizgisi olan katmana karar verilmez. Kalan
  unknown katmanlar entity × uzun-çizgi-oranı ile sıralanır, dosya başına en fazla 3 unknown_layer.
  (c) ambiguous_opening: yalnız penceresiz odaya (≤0,3 m) değen düşük güvenli adaylar, dosya başına tek toplu
  issue (data.targets; CLI cevabı her hedefe uygulanır). (d) `FileParams.area_convention` = dosya medyanı
  (yazı/geometri); yalnız medyandan ±%20 sapan odalar area_mismatch. (e) room_no_door muafiyeti
  `vocab.EXEMPT_ROOM_WORDS` {balcony, terrace, shaft, stair, elevator, light_well}. (f) bütçe: heavy dosyada
  etki sırasıyla ilk 10 (`budget_dropped` son issue'da); hedef typical ≤ 10, medyan ≤ 8. (g) run_baseline
  önceki pred JSON'daki `hitl_layer_overrides` (sınıf güven 1,0, kaynak hitl) ve `hitl_units` (upm, kestirim
  atlanır) ile yeniden koşar; cevaplar yeni IR'a taşınır. Eşikler `thresholds.validate.* / stats.*`.
  Davranış etkisi: stats kademesi text/dim/ignore sınıfları ince-çizgi pencere adayı dışlamasına girer
  (pencere F1 değişebilir); eval farkı EVAL_HISTORY'de.
- **[gözlem] 2026-09-05 — (h) fam00 kapı/ölçek raporu (GT öncesi).** Aile 0 dosyalarında (541_3, 541_5,
  553_3, 554_1, 560_8, 386_8, 6249, 536_1) kapı-adlı blok yok; kapılar modelspace'te standalone ARC (541_3: 63
  yay 55–130 cm bandında; 553_3: 131; 560_8: 48). $INSUNITS 5 (cm) ya da 6 (m) ama geometri cm. upm 21–44'ün
  nedeni: etiket-mesafesi kestirimi (tipik oda 3,5 m varsayımı) bu dosyalarda yoğun etiket gruplarından
  (mahal listesi/lejant, tekrar eden "SALON+MUTFAK") 37–67 birim medyan üretiyor → upm 21–41; yanlış upm ile
  7 m kümeleme aralığı 1,5–3 m'ye düşüyor, kat kümeleri parçalanıyor ve seçilen "plan" bir etiket tablosu
  oluyor (541_3: 32 etiket, 4×6 m bbox, 0 kapı yayı). Kapı-yayı kalibrasyonu yalnız bu yanlış kümelerin
  bbox'ında bakıyor → 0 yay → düzeltme yok. Doğru öncülle (upm 100) kümeleme 29 ve 25 odalı gerçek katları
  buluyor (20×12 m, 25/23 kapı yayı). 536_1 tek istisna (kapı yayı bulundu, upm 76). Öneri (GT öncesi, ayrı
  ölçüm): kapı kanıtı hiçbir kümede yoksa standart öncüllerle (100, 1000, 1) yeniden kümeleyip kapı
  kanıtı aramak; GT (541_3, 536_1, 386_8) bu düzeltmeden SONRA çıkarılmalı, aksi halde ölçek ve kat seçimi
  tartışmalı olur.

- **[karar] 2026-09-05 — yeni issue tipleri (kullanıcı kararı 2).** `window_missing`: yalnız bedroom/living/
  kitchen/study (vocab.WINDOW_EXPECTED_ROOM_WORDS, "ODA" tam kelime → bedroom), oda kenarı kat dış sınırına
  (oda poligonları birleşiminin sınırı) ≤ 0,3 m ve hiçbir pencere adayı (her güvende) ≤ 0,3 m değmiyor.
  `door_side_ambiguous`: açılış yayı eşleşmeyen kapı (width yok, merkez-mesafesi fallback) ya da yön skoru
  marjı (`_room_by_swing` en iyi − ikinci, Door.signals.swing_margin, ağırlıksız) < 0,15. area_mismatch'e
  mutlak kural: oran < 0,5 ya da > 2 her zaman issue. `ir.floor_from_dict/building_from_dict` (JSON → IR)
  ile validator çevrimdışı koşturulup kapsama tip tip ölçüldü (GT-7, politika sonrası çıktı): 15/57 →
  + area mutlak 15/57 → + window_missing 22/57 (window_fn 0→7/14) → + door_side_ambiguous çevrimdışı
  ölçülemedi (eski JSON'da swing_margin yok; tam kapı sonrası EVAL_HISTORY'de). Hedef ≥ 0,6.
- **[doğrulanmış örnek] 2026-09-05 — HITL #22 conflicting_signal.** detayli-villa: `STAIR` katmanında 34/34
  segment duvar çifti geometrisi taşıyor (katman sınıfı stair) — merdiven basamak çizgileri; `arkipedia.net`
  katmanında 45/45 (sınıf ignore, stats kademesi) — filigran/çerçeve çizgileri. İkisi de conflicting_layer
  issue'su olarak çıktı; #22 tanımının (geometri duvar der, katman başka sınıf der) sahada doğrulanması.

- **[karar] 2026-09-05 — kalibrasyon sağlamlığı (kullanıcı kararı 1, ayrı commit).** select_plan: etiket
  öncülüyle kümelenen hiçbir kümede kapı kanıtı yoksa standart öncüllerle (100, 1000, 1, 10 birim/m) yeniden
  kümelenir; kapı yayı sayısı (öncül × [0,3, 2,0] yarıçap bandı) en yüksek küme/hipotez seçilir (`stats.pick =
  hypothesis`, `upm_source = prior`), ardından mevcut kapı-yayı düzeltmesi bu öncülle koşar. Etiket-mesafesi
  kestirimine güven (`calibration.label_upm_confidence`): <6 etiket 0,3; nn IQR/medyan < 0,3 (dar) −0,4;
  nn değerlerinin > %40'ı aynı (tekrarlı) −0,4. `FileParams.units_confidence`: doors 0,9 (kapı/etiket sapması
  ≤ %30) ya da 0,5 (sapma > %30, 536_1 örneği), prior 0,4, hitl 1,0, labels → etiket güveni. unit_suspect:
  standart dışı upm YA DA güven < 0,6. Sonuç EVAL_HISTORY'de (fam00 plan/upm tablosu).

- **[karar] 2026-09-05 — kalibrasyon sağlamlığı, ölçüm sonrası düzeltmeler.** İlk sürümde (a) hipotez kümesi
  ham "en çok yay" ile seçilince 519_ADA'da 6 yaylı 6 odalık küme 82 odalık planı geçti, (b) hipotez öncülü
  (100) sonrasındaki kapı-yayı düzeltmesi fam00'da 160 cm'lik büyük yay kümesinden upm 182,9 üretip katları
  birleştirdi (541_5 142, 554_1 280 "oda"), (c) kapı/etiket sapması > %30 kuralı 47 dosyanın 30'unu şüpheli
  yaptı (etiket kestirimi sistematik ~%35 düşük, tipik oda 3,5 m varsayımı). Düzeltmeler: hipotez = toplam yayı
  en yüksek öncül; kat = yayı ≥ 10 olan küme, yoksa o öncülde pick_plan_floor; hipotez yolunda düzeltme kabul
  bandı [0,7, 1,4] (183/100 reddedilir, `upm_doors_rejected` stats'ta); şüphe eşiği sapma > 1,0 (2 kat);
  unit_tol_frac 0,25 → 0,15 (536_1 76 birim/m işaretlenir). Sonuç: fam00 6 dosya upm 100 (prior, güven 0,4 →
  unit_suspect), 541_3 29 oda / 23 kapı, 541_5 22 / 20, 554_1 22 / 20, 560_8 14 / 15, 386_8 upm 103 (doors)
  7 oda / 8 kapı; 553_3 hâlâ etiket (41,7): etiket-öncülü kümesinde 2 yay "kapı kanıtı" sayıldığı için hipotez
  yolu çalışmadı — aday: kapı kanıtı eşiği calib_min_doors (3) yerine hypothesis_strong_arcs ile. GT-7 eval
  birebir aynı.

- **[karar] 2026-09-05 — son issue tipi `room_merged`, bütçe ölçütü issue/oda, hipotez tetiği (kullanıcı kararları).**
  `room_merged`: takma-ad birleşmesi (evidence flood:alias_merge, aliases dolu) → "aynı oda mı?" (HITL #8); kapsama
  room_fn/room_fp kümesine girer. Bundan sonra yeni issue tipi eklenmez. `window_fp` 11/16 kapsanmıyor: bunlar
  block_keyword / layer kaynaklı yüksek güvenli sahte pencereler — **kalibrasyon sorunu: block_keyword (0,85) ve
  layer (0,85) pencere güveni fazla, ağırlık turunda (holdout) düşürülecek**; issue ile değil. Bütçe: üretim sınırı
  yok (heavy bütçesi kaldırıldı); ölçüt issue/oda, evaluate ve rapor medyan + typical ≤ 0,5 oranını basar; CLI
  etki sıralı ilk 10 (`cli_page`) + `--offset`/`--all`. Hipotez tetiği genelleştirildi: etiket-öncülü kümelerinde
  en yüksek kapı yayı sayısı < hypothesis_strong_arcs (10) ise hipotez yolu; etiket öncülü de aday (eşitlikte
  korunur), en çok toplam yay kazanır (553_3: 2 yaylı kanıt artık yeterli sayılmaz).

- **[gerileme] 2026-09-05 — mimarlik-evi: etiket öncülü hipotez, kapı-tabanlı kestirimden düşük güvenle kazandı.**
  Hipotez tetiği genelleşince (kanıt < 10 yay) etiket öncülü (44,1) aday oldu ve toplam yay sayısında standart
  öncülü (100) geçti; upm 100 → 44,1'e geriledi, units_confidence etiket güveni (1,0) ile yüksek kaldı ama
  dosya unit_suspect listesinde (standart dışı). Kural: **etiket öncülü hipotez, kapı-tabanlı kestirimden
  düşük güvenle kazanmamalı** — hipotez karşılaştırmasında etiket öncülünün toplam yayı standart öncülün en az
  X katı olmalı ya da etiket güveni ağırlık olarak girmeli. Ağırlık turunda (holdout) düzeltilecek; şimdilik
  dokunulmadı (yeni kaynak girişi kod değişikliği istemiyor).

- **[kaynak] 2026-09-05 — src02 dokunulmamış koşu (commit 71a52a9), yalnız gözlem; hiçbir eşik/ağırlık/profil/sözlük
  değişmedi.** 15 dosya, 15/15 ok; upm 13 doors / 1 prior (src02-06) / 1 labels (src02-13, 0 kapı); issue/oda medyan
  1,46 (mevcut kaynak 1,39). Adaylar (uygulanmadı):
  - **Yapısal eşleşme tek anahtarlı profilde her dosyayı alıyor**: fam06 (hafif çelik) profili yalnız `YAZI` taşıyor,
    "YAZI" olan her dosya fam06'ya structural 1,0 ile bağlanıyor (src02'de 10/15). Aday: yapısal kademe için en az
    3 kayıtlı ad şartı ya da anahtar sayısıyla ağırlıklı skor; src02 aileleri (2 büyük, 5 tekil) için profil GT sonrası.
  - **conflicting_layer yapısal sınıflarda yanlış pozitif**: KOLON (column), KİRİŞ İZD (beam), KAPI___PENCERE (window),
    TARAMA (hatch), MERDIVEN (stair) katmanları 30–54 segmentin tamamında "çift" geometrisi taşıyor — kolon ve kiriş
    zaten paralel çift ÇİZER, bu çelişki değil. Aday: `layer_class_vote` bariyer sınıfları (column/beam/window/chimney)
    için 1 (ya da None) dönsün; çelişki yalnız text/dim/furniture/hatch/ignore/stair oylarında. src02-07'de 6 sahte
    conflicting_layer bundan.
  - **area_mismatch src02'de 14/dosya** (mevcut 5,6): dosya medyanı konvansiyonu tutuyor ama sapanlar çok; yazı alanı
    net/brüt ve "SALON+MUTFAK" birleşik alan yazıları olabilir. Aday: GT çıkınca yazı/geometri oranını oda tipine göre
    incelemek; mutlak kural (0,5–2) burada büyük pay taşıyor mu ölçmek.
  - **src02-13: 0 kapı, 31 oda, upm etiketten (83)** — kapı yayı bulunmadı; kapılar muhtemelen yaysız blok ya da
    KAPI___PENCERE çizgisi. Aday: blok adı "KAPI/KP" → door_block sinyali (profil ya da sözlük), bu dosya GT adayı değil.
  - **Pencere sayısı yüksek** (src02 medyan 34/dosya, mevcut 12): KAPI___PENCERE katmanı window sınıfı (profil notu
    "kapı içerebilir"); kapı kanatları pencere sayılıyor olabilir. Aday: GT ile pencere FP ölçümü, ağırlık turu.
  - **AA-0.xx katmanları** (kalem kalınlığı adlı katmanlar: AA-0.00…0.60, 10+ dosyada) unknown_layer sorusu üretiyor;
    içerik istatistiği karar veremiyor (uzun çizgi var). Aday: sözlük deseni `AA-\d` → ignore ya da HITL cevabıyla profil.
  - **unit_suspect 115,2 (src02-07, doors)**: %15 tolerans sınırında; kapı kanadı 0,875 m varsayımı ofis standardına
    (0,80/0,90) göre kayıyor. Aday: tolerans yerine kanat genişliği histogramından ofis kanadı.
  - **consistency_pair 430-35**: src02-09 (1 Eylül) 13 oda / 3 kapı / 12 pencere, src02-10 (2 Temmuz) 6 oda (3 poligon)
    / 3 kapı / 8 pencere, upm 99,8 vs 108,5. İki sürümde plan seçimi farklı küme buluyor; GT src02-09 üzerinde çıkınca
    revizyon tutarlılığı ölçülebilir.
  - **Kapı güveni tek dilimde** (%100 0,7–0,9) her kaynakta: block+arc 0,95 hiç gözlenmiyor, kapılar blok (0,70) ya da
    yay (0,75). Kalibrasyon tablosu için ayırt edici değil; ağırlık turu notu.

- **[karar] 2026-09-05 — A: conflicting_layer yalnız text/dim/furniture/ignore/unknown oylarında; yapısal profil
  eşleşmesi en az 3 ortak ad.** Bariyer sınıfları (wall/beam/column/chimney/window) ve hatch/stair çelişki üretmez
  (kolon/kiriş zaten paralel çift çizer); segment bayrağı evidence'ta kalır. `names.STRUCT_MIN_KEYS = 3`.
  GT-7 eval ve kapsama değişmedi (EVAL_HISTORY).
- **[gözlem] 2026-09-05 — D raporu (src02, kod yok).** (a) src02-07 area_mismatch 20/24 oda: dosya konvansiyonu 1,91
  (yazı ≈ 1,9 × geometri!) — oranlar 1,3–2,7 arasında geniş dağılıyor; KAT HOLÜ 17,6 / 2,0 m² (8,6×), HOL 4,6 / 0,9
  (5,1×), BALKON 5,9 / 89,7 (0,07, alias_merge sızması). Yorum: geometri alanları sistematik küçük → oda poligonları
  bu dosyada duvar kalınlığı/sıva çizgileri arasında dar kalıyor ya da mm/cm karışımı; GT src02-07 bunu ölçecek.
  (b) src02-13 kapılar YAYSIZ bloklar: '95 KAPI' ×32 (6 LWPOLYLINE, iç INSERT), '110 KAPI' ×9, 'Single_Door_12' ×5,
  '95-200-20 kapı' ×4, 'yangın kapısı' ×2; blok içinde ARC yok, modelspace 51 ARC hepsi < 1 m yarıçap (sembol).
  Kapı katmanı KAPI___PENCERE'de 53 INSERT. Mevcut kapı yolu (yay imzası) bu ofiste kör; blok ADI sinyali gerekir.
  (c) Duvar sayısı şişmesi: src02-08 2123 parça — .ABM-SIVA 523, '0' 477 (unknown), ABM.DUVAR 217, ABM.SIVA 207,
  ABM.ALAN 194 (unknown, alan çizgileri); src02-11 4344 parça — 'PLAN DUVAR' 3056, .ABM-SIVA 647, PLAN SIVA 445.
  Crop: PLAN DUVAR katmanı tüm kat planlarını (çok daire, çok kat) kapsıyor; seçilen kat bbox'ı geniş olduğu için
  komşu daire/katların duvarları da sayılıyor; '0' ve ABM.ALAN sınıfsız katmanlar çift filtresinden geçiyor.
  (d) Revizyon çifti 430-35: src02-09 (1 Eylül) 13 odalı kat (9×16 m, BANYO/KAT HOLÜ/MUTFAK/YATAK…) seçildi,
  src02-10 (2 Temmuz) 6 odalı küme (8×10 m, WC×4/APT. GİRİŞ HOLÜ/KAT HOLÜ) — iki sürümde etiket kümeleri [6,12,12,15,5]
  vs [6,12,12,13], kapı kanıtı 4 yay; 2 Temmuz'da 13'lük küme yok, plan seçimi WC ağırlıklı zemin/giriş katına
  kaydı. Kat seçimi kanıtı zayıf (4 yay) olduğunda revizyonlar arasında kararsız.
- **[aday] 2026-09-05 — `unknown_block` issue tipi (yeni tip yasağı sonrası ilk istisna adayı, karar bekliyor):**
  bir dosyada adı kapı/pencere kelimesi taşıyan ya da kapı katmanında yer alan ama yayı olmayan, ≥ N kez yerleştirilmiş
  blok → "Bu blok ne?" [kapı/pencere/mobilya/sembol/yoksay]; cevap profile `blocks:` olarak yazılır (ARCHITECTURE §5
  şemasında yer var). src02-13'te 0 kapının nedeni; sinyal tarafı `block_class`'ın blok adı/katman oyu almasıyla
  tamamlanır (ağırlık turu).

- **[gözlem] 2026-09-05 — src02-07 GT süreci (assisted, kullanıcı kararları + araç).** Kör sayım → tahmin kıyası →
  bölge bölge (ham crop, sonra overlay) → kullanıcı kırpılmış annotate görünümünde çizdi (`annotate.py --view/--serve`:
  tarayıcı indirmesi yerine POST ile taslağa yazma; meta korunur; blok geometrisi kesim komşuluğunda açılır).
  Bulgular (adaylar): (1) sözlükte "asansör", "aydınlık" yok → çizimdeki "ASANSÖR A: 4.85 m²" etiketi oda olmadı;
  ROOM_WORDS'e eklenmeli (ölçümle). (2) Çekirdek (kat holü + merdiven + asansör) flood-fill'de KAPI___PENCERE kanat
  çizgileri, kiriş izdüşümü ve tefriş bariyerleriyle parçalanıyor; kat holü 2.7 m² şerit kaldı (GT 14.1). Etiketi
  olmayan mahal (merdiven, aydınlık) hiç üretilmiyor — "etiketsiz kapalı bölge" sinyali (Adım 9 duvar grafı).
  (3) Ham görselde/araçta kapı blokları (A$C7b0df17d: 27 çizgi + yay + WIPEOUT) zor görünüyor; kullanıcı kör
  sayımda 12 kapı saydı, tahmin 20 doğruydu — kör sayım görselleştirmesi blok geometrisini belirgin çizmeli.
  (4) Pencere tahmini 57 → GT 36: 15 sahte (thin_lines/keyword) + giriş kapısı kasaları pencere sayılmış
  (KAPI___PENCERE window sınıfı, profil notu "kapı içerebilir" doğrulandı). (5) Balkon takma-ad sızması (r13 119 m²)
  cam korkuluk çizgisinin bariyer olmamasından (kullanıcı: "korkuluk gözden kaçmış"); korkuluk katmanı → barrier
  adayı. (6) GT şeması genişledi: kapıda `type/subtype/note` (sliding), odada `type` (stairs/elevator/light_well/
  balcony) ve `note`; pencerede `note`. gt_check ve metrics ek alanları yok sayar.

## Adaylar (uygulanmadı)

- **[aday] 2026-09-05 — yapısal profil eşleşmesi hâlâ küçük profillere kayıyor:** ≥3 ortak ad şartı fam06'yı (1 anahtar) eledi ama 3 anahtarlı fam10 (KOLON/BACA/YAZI), fam11, fam16 src02'nin 10 dosyasını 1,00 ile aldı; KOLON/BACA/YAZI genel adlar. Aday: yapısal kademede yalnız ofise ÖZGÜ adlar sayılsın (sözlükle sınıflanabilen genel adlar hariç) ya da skor anahtar sayısıyla ağırlıklansın; src02 kendi profillerini GT sonrası alsın.

- ~~[aday] 553_3 kanıt eşiği~~ → 2026-09-05 uygulandı (hipotez tetiği < 10 yay).
- ~~[aday] room_merged~~ → 2026-09-05 uygulandı.

- ~~[aday] kat seçimi: standart öncüllerle yeniden kümeleme~~ → 2026-09-05 karar olarak uygulandı.

- **[aday] 2026-09-04 — Adım 6 devamı:** (a) walls/windows/rooms/polygons/raster/blocks sabitleri thresholds'a (envanter yukarıda); (b) duvar sinyalleri `parallel_pair` (katman sınıfından bağımsız) + `layer_class` + `thickness_mode`, çelişki → düşük güvenli duvar + conflicting_signal (HITL #22); (c) oda/pencere güven tabloları (ir_compat) → scoring; (d) `swing.max_dist_units` metreye; (e) run_floor imza varsayılanları FileParams'a.

- **[aday] 2026-09-04 — `classify_layers` 3. kademe (içerik istatistiği: entity tipi dağılımı, ortalama uzunluk, paralel çift oranı) ve 4. kademe (LLM, cache'li).** Adım 5'te yalnız profil + sözlük yapıldı.
- **[aday] 2026-09-04 — WALL_EXCLUDE_CLASSES'a dim/grid/hatch/revision/ignore eklensin** (ölçü/aks çizgileri sahte duvar üretebilir); eval ile ölçülmeli.

- **[aday] 2026-09-04 — DXF tek okuma.** `select_plan`/`estimate_units_from_doors`/`run_floor`/parmak izi aynı `doc`'u paylaşsın; AVİDA'da ~12 `readfile` → 1 (performans gözlemi yukarıda).

- ~~[aday] `evaluate.py` mtime/koşu zamanı~~ → Adım 4'te karar olarak uygulandı (run_stamp).

- **[aday] 2026-09-04 — `evaluate.py`'de güven eşikli ikinci tablo.** Tüm tahminler + "güven ≥ 0.5"
  tahminleri için ayrı P/R/F1; düşük güvenli sahteler (thin_lines) HITL'e gidecekse otomatik F1
  onlarsız da görülmeli. Kullanıcı kararı bekliyor.

- **[aday] 2026-09-04 — `Floor.devices` perception IR'dan çıksın.** Elektrik alanı; Adım 2'de
  v2 IR yazılırken elektrik motoru kendi Floor görünümünü türetmeli.
- **[aday] 2026-09-04 — `core/validate.py` electrical'a taşınsın.** `validate_design` DesignIR
  doğruluyor; `validate_building` perception'a ait. Plan listelemediği için Adım 1'de kökte
  bırakıldı, importları güncellendi.
- **[aday] 2026-09-04 — `evaluate.py`, `triage_dataset.py`, `annotate.py` → `experiments/`.**
  ARCHITECTURE §10 hedef yapıda orada; Adım 0 kapsamı dışı olduğu için taşınmadı.
- ~~[aday] `run_baseline.run_one` akışı pipeline'a~~ → Adım 4'te yapıldı (`select_plan`/`run_selected`).
- **[aday] 2026-09-04 — `core/sheets.py` çıktısı (görünümler, kat adları) runner'ın kat
  seçimine bağlansın; tek kat yerine tüm kat planları çıksın.** Pafta anlama v1 hazır ama
  bağlı değil.

## 2026-09-05 — GT araçlarında blok açma hatası (annotate.py, tools/render_gt_ref.py)

**Ne:** Kırpılmış altlık (`annotate.py --view`) ve ham PNG (`render_gt_ref.py --raw`) blok içi
geometriyi yalnız bloğun yerleşim noktası kesim içindeyse çiziyordu. Plan bloğu/merdiven bloğu
gibi yerleşim noktası uzakta olan bloklar tümüyle düşüyordu. Düzeltme: her blok açılır, parçalar
tek tek kesime göre süzülür.

**Etkisi:** src02-02 kör sayımı eksik ham PNG üzerinde yapıldı (merdiven bloğu görünmüyordu;
kullanıcı merdiven saymadı). src02-07 kör sayımındaki kapı eksikliği (12 vs 20) de büyük olasılıkla
aynı nedendir (kapı blokları görünmüyordu). İki dosyanın da `meta.note` alanına yazıldı; kör sayım
tekrarlanmadı (kullanıcı tahmini artık gördü), karşılaştırma "araç hatası" notuyla değerlendirilir.

**Alternatif:** Kör sayımı düzeltilmiş PNG ile yenilemek; reddedildi, tahmin görüldükten sonra kör
sayım anlamını yitirir. src02-12 ve src02-09 düzeltilmiş araçla yapılacak.

## 2026-09-06 — src02-02 GT süreci gözlemleri (aday, karar yok)

- **KAPI___PENCERE katmanındaki 6 "pencere" tahmininin tamamı kapı çıktı** (5 cam sürgülü kapı + asansör
  kapısı). src02-07'de de aynı katman "kapı içerebilir" notu düşülmüştü; artık 2 dosyada tekrar ediyor.
  Aday sinyal: blok adı deseni (`sk180x220`, `200x220 sk`, `KAPI 250X160`) → kapı; `60x60x20pen1` → pencere.
  Üçüncü dosyada görülürse sinyal olur.
- **Etiketsiz merdiven** (blok içinde, yazı yok) yine üretilmedi; src02-07'deki gözlemle birlikte
  "etiketsiz kapalı bölge" sinyali adayı güçleniyor (2 dosya).
- **Giriş katı**: kör sayım "normal kat" dedi; bina giriş kapısı (kat holü–dış) ve saçak izdüşümü ancak
  kapı turunda anlaşıldı. IR'da kat türü alanı yok; HITL soru adayı ("bu kat giriş katı mı?").
- **Sürgülü kapı genişliği 1.6–2.0 m**: gt_check 0.6–1.5 m uyarısı sürgülüde beklenen durum; `subtype: sliding`
  için üst sınır ayrı olmalı (araç, perception değil).
- Tahminde kat holü ve banyo poligonları çok küçüktü (kat holü 8465–8576 şeridi doğru ama banyo yalnız
  duşakabin); IoU 1.0 raporlanıyor çünkü eşleşen 6 odada poligonlar birebir tahminden alındı.

## 2026-09-08 — src02-12 GT süreci gözlemleri (aday, karar yok)

- **Büyük dosya süreci:** 8 daire + 2 çekirdek; daire başına (ham → overlay → kullanıcı kırpılmış annotate'te
  hol/banyo/e.banyo/balkon çizer → kapılar DXF yaylarından, sürgülüler bloklardan → pencere listesi) döngüsü işledi.
  Kullanıcı yalnız zikzaklı/küçük poligonları yeniden çizdi; büyük odalar (salon, yatak, çocuk, mutfak) tahminden
  alındı (IoU 0.91). Tahminin **hol ve banyo poligonları sistematik olarak bozuk** (zikzak, duşakabin boyu) —
  3 dosyada tekrar: sinyal adayı "küçük/ince oda poligonu + etiket alanı uyuşmazlığı".
- **DXF etiketleri alan taşıyor** ("SALON / A:21.70 M²"): GT alanları etiketin %5–10 altında (sıva yüzü). Aday:
  etiket alanı varsa `area_mismatch` için doğrudan referans; perception'da text sinyali olarak kullanılabilir (3 dosya:
  src02-02, src02-07, src02-12).
- **Sürgülü / ebeveyn banyo kapıları DXF'te yay ya da blok olarak yok**; tahmin bunları "pencere" olarak buluyor
  (KAPI___PENCERE katmanı, 142–180 birim). GT'de konum/genişlik o pencere parçasından alındı. 3 dosyada tekrar →
  "KAPI___PENCERE üzerindeki 1.4–2.0 m parça iki oda arasındaysa kapı" sinyal adayı güçlendi.
- **60x60 baca pencereleri** (`_60x60p10` bloğu) kullanıcıya göre cam; tahmin bazılarının eksenini yanlış (yatay)
  veriyor; blok kutusundan düzeltildi (2 örnek). Aday: blok kutusu uzun kenarı = pencere ekseni.
- **Kat holü çekirdeği** yine tahminde yok/parçalı (0.8 m² şerit); merdiven/asansör/yangın merdiveni etiketsiz.
  "Etiketsiz kapalı bölge" sinyali artık 3 dosyada.
- **Kör sayım ↔ GT:** 8 daire, ~86 mahal / ~81 kapı sayımı; GT 83 oda / 82 kapı. Sağ üst dairede "3 balkon" yerine
  2 balkon + 3 balkon kapısı; bir dairede kullanıcı banyo poligonunu unuttu (gt_check bağlantı uyarısıyla yakalandı).
- **Araç:** annotate `--view` ile tek daire çizimi verimli; yanlışlıkla komşu daire düzenlemesi 1 kez oldu
  (yedek + fark listesi ile yakalandı). gt_check'e "kayıt öncesi/sonrası fark" çıktısı eklenebilir (aday).

## 2026-09-08 — src02-09 blind GT süreci gözlemleri (holdout; aday, karar yok)

- **Blind akış çalıştı:** tahmin hiç açılmadı; ham PNG + `gt_draft --empty` şablonu, oda poligonları kullanıcı tarafından
  annotate `--view/--serve` ile çizildi, kapı/pencere geometrisi DXF'ten deterministik türetildi (yay merkezi; blok
  `matrix44` dönüşümü). İlk menteşe önerisi blok **insert** noktasından alınmıştı, kullanıcı D/E/F'in kaydığını gördü;
  doğru menteşe `Single_Door_12` bloğunun yerel (0,10) noktası (kanat 95 cm, kasa 10 cm). Aday: kapı bloğu için
  "menteşe = blok yerel kanat başlangıcı" kuralı `unknown_block` HITL cevabından öğrenilebilir (blok adı → yerel menteşe/genişlik).
- **Çatı katı = ortak çekirdek ağırlıklı kat:** 16 odanın 6'sı ortak/teknik (kat holü, 3 merdiven bölgesi, su deposu yeri,
  asansör makine dairesi); su deposu ve makine dairesi **etiketsiz** → tahminde yok. "Etiketsiz kapalı bölge" sinyali artık
  **4 dosyada** (src02-02/07/12/09).
- **Blok kapılar görünmez (4. dosya):** 5 `Single_Door_12`, 3 `210 SK`, 1 `120x220`; hiçbiri yay taşımadığı için kapı yolu
  görmüyor; bunlar KAPI___PENCERE katmanında "pencere" olarak çıkıyor (12 tahmin pencerenin 10'u sahte). `unknown_block`
  adayı güçlendi; gerçek pencere bloğu `_60X60X10LUKKDUVAR` ile kapı bloğu aynı katmanda → katman değil blok geometrisi ayırt eder.
- **Yay kapılarında oda ataması zayıf:** 3 yay kapısının konumu 0,0 m hatalı ama bağlantı 1/3 doğru (KAT HOLÜ parçalı,
  HOL'ler IoU<0.5); kapı-oda ataması oda poligonu kalitesine bağımlı — ayrı sinyal değil, oda hatası kaynaklı.
- **Küçük oda poligonları (4. dosya):** HOL 2,2 m² ve 3,5 m² ile KAT HOLÜ 5,5 m² tahminde 0.22–0.47 IoU (şerit/bölünmüş);
  src02-07/12'deki desenin aynısı.
- **Çelişen etiket:** çocuk odası poligonu içinde ikinci bir "HOL A:3.10 M²" yazısı; kullanıcı kararı tek oda (yazı hatalı).
  `room_merged` bu durumu iki etiket/tek bölge olarak işaret eder (tahminde 2 room_merged issue var) — HITL #8 doğru soru.
- **Revizyon çifti kat düzeyinde karşılaştırılamadı:** src02-10 (2 Temmuz) plan seçimi giriş katına gitti (15 etiketli
  çatı kümesi yok/bölünmüş, `pick: doors`). Plan seçimi revizyona duyarlı; consistency_pair ölçümü için kat seçimi HITL
  cevabı (`hitl_floor`) gerekiyor — kod yok, aday.
- **Holdout ilk ölçüm:** oda 0.759 / kapı 0.400 / pencere 0.286; geliştirme kümesi (3 GT) 0.617 / 0.788 / 0.648. Kapı
  farkı blok kapı yoğunluğundan (12 kapının 9'u blok), oda farkı bu katın daha az daire içi bölünmesinden.

## 2026-09-08 — GT-7 revizyonu (kind alanı + eksik çekirdek/dış mahaller; aday, karar yok)

- **Yöntem:** yedi eski GT ham çizgi + GT poligonu üstünde tarandı; GT dışı kalan DXF yazıları listelendi ("60x60 şaft",
  "Asansör Boşluğu", "Kablo Bacası", "FRANSIZ BALKON"); etiketsiz bölgeler görselden seçildi. Poligonlar DXF çizgilerinden
  deterministik çıkarıldı: tohum noktası çevresindeki çizgiler `polygonize`, tohumu içeren en küçük yüz (şaft/asansör/sahanlık),
  basamak çizgileriyle parçalanan merdiven için kutu içindeki yüzlerin birleşimi. İki hata kullanıcı gözüyle yakalandı:
  merdiven birleşimi ocak tezgâhı yüzlerini aldı (alan filtresi yetmedi), sahanlık kablo bacası girintisini içerdi.
  Aday: gt araçlarına "tohumdan yüz" komutu (annotate `--face x,y`) — kullanıcı çizmek yerine tıklar.
- **Eklenen mahal profili:** 8 mahal / 7 dosyada; hepsi etiketsiz ya da mahal adı katmanı dışında etiketli (şaft yazısı
  A_ANNO_TXT, asansör yazısı MAHAL ADI değil). Tahmin bunların hiçbirini üretmiyor → "etiketsiz kapalı bölge" sinyali artık
  eski kaynakta da 4 dosyada (KAYAPINAR, tip-1, tip-2, hafif_celik); src02 ile toplam 8.
- **FRANSIZ BALKON yazıları** (KAYAPINAR, 10 adet) mahal değil, pencere/korkuluk notu; "balkon" kelimesi tek başına oda
  sinyali olamaz — kelime + kapalı bölge birlikte gerekli (vocab'a olumsuz örnek adayı).
- **Kapatma noktası / geçersiz poligon:** eski GT'lerde 15 poligon kapatma noktasını tekrar ediyordu, biri onarım gerektirdi;
  gt_check uyarısı yeterli oldu. Eski GT meta'ları (tier/holdout/source/status) boştu, dolduruldu; birimler (78.5–103.3)
  eski kapı kalibrasyonu, bilinçli olarak korundu (meta.note).
- **Dış mahal adlandırması:** aynı ofis ailesinde (fam01) giriş önü örtülü alan "GİRİŞ VERANDA" (tip-4 etiketi); tip-2'deki
  etiketsiz eşdeğeri aynı adla yazıldı, hafif_celik'te "GİRİŞ SAHANLIĞI". Aday: type=terrace altında ad serbest, kind=dış.

## 2026-09-09 — fam00 (ArchiCAD) GT ertelendi; taslak yöntemi gözlemleri (aday, karar yok)

- **Erteleme nedeni:** fam00 dosyaları için ofis kullanım izni bekleniyor (kullanıcı). İzin gelince 541_3 taslağı repo dışından
  geri alınır; 541_5 aynı bina ailesi (benzer plan), 386_8 küçük ve kapı yaylı — sıra: 541_3 → 386_8 → 541_5.
- **ArchiCAD dışa aktarım profili adayı:** fam00 = ArchiCAD DXF. Belirtiler: katman adı sonunda sayı ("Structural - Bearing27"),
  `_Pen_No__NN` eki, 'Interior - Furniture 82' katmanında hem mobilya hem pencere çerçevesi, blok yok (INSERT 0), aks çizgileri
  'Structural - Shear4' katmanında Double Dashed 19 m çizgi. Tahmin bu ailede 'Interior - Furniture' katmanını duvar sayıyor
  (541_3: 1769 duvarın 737'si bu katmandan) → oda poligonları 0.5–3.5 m² parçalar. Aday: profil için katman adında
  "Furniture" → furniture sınıfı (source_profiles/fam00.yaml), linetype Double Dashed + çok uzun → axis sınıfı sinyali.
- **GT taslağı için işe yarayan yöntem** (kod perception'a girmedi, scratch betiği): yalnız yapısal katman çizgileri
  (aks çizgileri hariç: uzun ve iki ucu bina dışında) + tahmin kapı kapatma segmentleri → `polygonize`, tohum = oda etiketi,
  tohumu içeren en küçük yüz. 541_3'te 29 etiketin 27'si tek geçişte doğru yüz aldı (alanlar 2–18 m², plana uygun);
  balkonlar korkuluk katmanı eklenince çıktı; merdiven (etiketsiz, basamak çizgileri) ve bir balkon çıkmadı.
  Pencere adayı: oda poligonunun dış kenar bandında (±45 cm) ince paralel çizgiler → 21 aday. Bu yöntem `gt_draft`'a
  "--faces" seçeneği olarak eklenebilir (deterministik, LLM yok) ve perception'da "kapı kapatmalı polygonize" oda sinyali adayıdır.
- **Birim doğrulama:** 541_3 prior 100 (güven 0.4) doğru çıktı; INSUNITS=5 (cm) başlığı + kapı yayı yarıçapı ~100 birim.
  Aday: `$INSUNITS` başlığı units sinyali olarak (INSUNITS 4=mm, 5=cm, 6=m) — kalibrasyonda şu an kullanılmıyor.

## 2026-09-09 — Adım 9: duvar grafından bağımsız oda tespiti (5a/5c)

**Ne:** `walls.build_wall_graph` (5a) ve `rooms.graph_faces` + `rooms.reconcile_rooms` (5c); flood-fill odalarıyla uzlaştırma
`pipeline.run_floor` içinde; `unlabeled_region` issue tipi ve `open_room` "duvar grafında boşluk" notu `validate.py`'de.
Eşikler `thresholds.yaml graph.*`, ağırlıklar `weights.yaml room.graph_face / graph_only / stair_footprint`.

**Kararlar ve gerekçeleri (kullanıcı direktifinden sapmalar dahil):**
- **WallGraph iki kenar kümesi taşır.** `edges` = merkez hatları (paralel yüz çiftleri → orta hat → doğrultudaş birleştirme →
  uç-uç snap ≈ kalınlık/2, `FileParams.extra.graph_snap_tol`); topoloji/graph_connectivity için. `face_edges` = duvar YÜZ
  parçaları + bariyer sınıfı katman çizgileri (HATCH sınırı dahil) + pencere camları + kapı kapatmaları; polygonize bunlarla.
  Neden: merkez hatları gerçek dosyalarda çok parçalı ve eksik (tip-1'de 400 parça, 44 sarkan uç; dış duvar 3–6 paralel çizgi,
  kalınlık modu 15 cm iken dış duvar 25–38 cm) → kapalı yüz 0. Yüz çizgileri raster bariyerinin vektör eşdeğeri; oda poligonu
  bitmiş yüzeyde (GT gibi), içe çekme gerekmez. Direktifteki "merkez hattı grafı" korunuyor ama odalar yüzlerden.
- **Mühür (seal) polygonize.** Yüz kenarları `graph.seal_m` (0,12 m) kadar şişirilir, şişmiş bandın sınırı polygonize edilir,
  banda ait olmayan sınırlı yüzler oda adayı ve mühür kadar geri büyütülür — raster flood-fill'in (`seal_small_m` 0,25) vektör
  karşılığı. Denemeler (9 GT dosyası, 108 flood odası): salt snap/uzatma polygonize 70 eşleşme; mühür 0,25 → 67 (ince holler
  yutuluyor), 0,12 → 70, 0,06 → 69. Geçiş kapatması (sarkan↔sarkan doğrultudaş uç, 0,5–1,6 m) açık/kapalı fark: 70/70; düğüme
  kapatma (T-birleşimden devam eden boşluk) odaları böldü (KAYAPINAR 4→2) → geri alındı. Kalan açıklar: KAYAPINAR 4/14 (bariyer
  katmanında olmayan duvar parçaları, 1 m boşluklar), input-2 0/8 (tek çizgili referans dosyası), src02-07 15/24.
- **Kapı kapatması = kapalı kanat + dik kapaklar.** `openings._door_barriers` kanadı (menteşe→kilit ucu) iki uçtan uzatılır ve
  uçlarına duvar kalınlığı boyunca dik kapak eklenir; raster mühürsüz vektörde kanat tek başına iki yüzü kesmiyordu.
- **Adaylar kapı bağlamadan SONRA eklenir.** Yalnız grafın bulduğu yüzler `raw_name=""`, `source="graph"`, güven
  `graph_only` 0,45 ile `floor.rooms`'a kapı-oda ataması bittikten sonra girer → GT-7 kapı/pencere ve bağlantı değişmez.
  Aday bağlama (kapı → etiketsiz mahal) ileride, unlabeled_region cevabıyla.
- **Uzlaştırma sinyali.** IoU ≥ 0,7 → `graph_face=1` (ağırlık 0,80) + `agreement_bonus` 0,05 → flood_exclusive 0,85 → 0,90;
  evidence `graph_iou` taşır. Yüz yok → `graph_face=0` (evidence'ta, çelişki notu) → `open_room` "duvar grafında boşluk".
  Yüz oda birleşimiyle ≥ 0,5 örtüşüyor ama IoU < 0,7 → belirsiz, aday değil (çift sayım önlenir).
- **Merdiven ayak izi:** stair sınıfı katman çizgileri tampon birleşimi → dışbükey zarf; içinde bulunduğu yüzden çıkarılır, ayrı
  yüz (`stair_footprint` bilgi sinyali, unlabeled_region "merdiven çizgileri içeriyor"). src02-07'de çekirdek merdiveni böyle çıktı.
- **Yeni issue tipi kuralı:** 2026-09-05 kararı ("room_merged'den sonra yeni tip yok") kullanıcının Adım 9 direktifiyle
  (unlabeled_region) bilinçli olarak aşıldı; başka tip eklenmedi.
- **Ölçüm öncesi düzeltmeler (kod değil):** triage `data/dataset` altındaki her DWG'yi gerçek adıyla `_dxf/`'e çeviriyordu
  (src02/raw → 15 gerçek adlı DXF; fam00 `_excluded_fam00/dwg` yeniden dönüştü) → raw ve dışlananlar kök dışına taşındı
  (`data/src02_raw/`, `data/excluded_fam00/`). Aday: triage'a `--exclude-dir` / `.triageignore`.
- **Aday kapısı (dışbükey zarf):** yalnız-graf yüzü, etiketli flood odaları birleşiminin dışbükey zarfının (−0,3 m) içinde
  değilse aday olmaz (`graph.candidate_hull_buffer_m/min_frac`). 11 GT: oda TP/FP/FN 168/73/49 → 165/59/52 (F1 0,734 → 0,748);
  kaybedilen 3 TP dış teras/balkon (src02-02, src02-12) — bilinçli; holdout FP'leri (tip-6 2, src02-09 2) elendi.
- **GEOS askıda kalma:** birleşik çizgi kümesinin gönye (mitre) tamponu detayli-villa ve deniz-evi'nde 180 s'yi aştı (ilk tam
  koşuda 2 zaman aşımı); çizgiler tek tek düz uçlu/yuvarlak birleşimli tamponlanıp birleştirildi → 6–8 s. src02-12 38 s
  (1716 yüz kenarı, 305 geçiş kapatması) — geçiş kapatması O(n²) Python; aday: uzamsal indeks (STRtree).

## 2026-09-12 — Adım 9 sonrası düzeltmeler: open_room eski semantiğine dönüş, ad/kind ölçümü, FP analizi

**Ne (kullanıcı kararı, 2026-09-09 direktifi):**
- **open_room eski semantiğine döndü:** yalnız flood-fill poligonu kapanmayan/sızan odalar (`polygon` yok). Duvar grafında
  kapalı yüz bulunamaması artık issue değil; graf uzlaşması yalnız `evidence.signals.graph_match` (1 / 0; eski adı
  `graph_face`, `weights.yaml room.graph_match` 0,80). Gerekçe: Adım 9 koşusunda open_room 2 → 75'e çıktı; input-2 gibi tek
  çizgili referanslarda ve KAYAPINAR'da grafın boşluğu dosya sorunu, oda sorunu değil → HITL'e soru olarak taşımak bütçeyi
  şişiriyor, bilgi evidence'ta zaten var.
- **Ad doğruluğu ikiye ayrıldı (`metrics.match_rooms`):** `name_acc` yalnız etiketli tahminlerde (`raw_name` dolu, `name_n`);
  etiketsiz adaylarda (`raw_name` boş) `kind_acc` = tahmin `kind` vs GT `kind` (`kind_n`; tahmin henüz kind vermiyor → n=0).
  evaluate toplamı dosya ortalaması yerine n-ağırlıklı (önceki satırlarla birebir kıyaslanmaz; EVAL_HISTORY'de not).
  Kapsama tablosuna `room_kind` (unlabeled_region işaret ediyorsa kapsanmış) eklendi; `room_name` yalnız etiketli çiftler.
- **KAYAPINAR ve input-2 duvar boşlukları → walls.py ağırlık-turu maddesi:** KAYAPINAR'da 14 odadan 4'ü grafla eşleşiyor
  (duvar parçaları bariyer sınıfı dışındaki katmanlarda, ~1 m boşluklar; `seal_m` 0,12 kapatmıyor, büyütmek odaları böldü —
  bkz. 2026-09-09 maddesi), input-2'de 0/8 (tek çizgili referans; yüz çifti yok → `face_edges` boş). Ağırlık turunda:
  (a) `parallel_pair` bulunamayan tek çizgilere `layer_class` + uzunluk/hizalanma sinyaliyle "tek çizgili duvar" güveni,
  (b) graf snap toleransını kalınlık yerine dosya boşluk histogramından türetme (FileParams), (c) bariyer dışı katmandaki
  duvar-benzeri çizgiler için `stats_class` kademesinin `face_edges`'e katkısı. Tek dosya kuralı yok; iki dosya + src02-07 (15/24)
  aynı desen → sinyal adayı.

**FP analizi (kod değişikliği yok; Adım 9 çıktısı, `output/fp_analysis/*_fp15.png`, script scratchpad `fp_analysis.py`):**
- **src02-12 (40 FP / 97 tahmin, 24 etiketsiz aday) en büyük 15:** bölünmüş oda 9 (etiketli HOL parçaları r28/r22/r42 ve graf
  dilimleri r91/r93/r92 — GT KAT HOLÜ/HOL tek mahal, tahmin SIVA/_TEFRİŞ çizgileriyle 3–8 m² parçalara bölünmüş; r75 yangın
  merdiveni sahanlığı ayrı yüz), balkon kısa poligon 5 (r57/r58/r69/r60/r66: korkuluk katmanı bariyer sayıldığından tahmin
  balkonun yalnız bir bölümünü alıyor, GT'nin %84–100'ü tahminin içinde ama IoU < 0,5), sızma 1 (r71 KAT HOLÜ 16,8 m²:
  flood-fill komşu etiketsiz alanlara taştı, GT payı %55), birleşik 1 (r97: iki asansör tek graf yüzü, 14 m²),
  mobilya cebi 1 (r77: ÇOCUK ODASI içinde dolap şeridi, yalnız SIVA çizgileri). GT dışı gerçek mahal: 0.
- **src02-07 (8 FP / 31 tahmin, 7 aday), hepsi:** sızma/dış 1 (r13 BALKON 89,7 m², alias_merge: balkon etiketleri binanın
  dış halkasına sızdı), niş/mobilya cebi 2 (r27/r26: SALON+MUTFAK içinde 3,4 m² mutfak cebi, DUVAR+SIVA ile kapalı),
  merdiven ayak izi 1 (r25: GT'de KAT HOLÜ içinde, ayrı mahal değil), bölünmüş oda 4 (r18/r21/r17/r16 HOL/KAT HOLÜ 0,9–2,2 m²
  parçalar; KİRİŞ İZD ve SIVA çizgileri bölüyor).
- **Sonuç:** FP'lerin ~%70'i tek kök neden: ince çizgi katmanları (SIVA, KİRİŞ İZD, _TEFRİŞ, korkuluk) bariyer/yüz kenarı olarak
  odayı bölüyor. Aday sinyaller (ağırlık turu, sinyal olarak, `if` değil): (1) yüz/oda birleştirme — komşu iki parçayı ayıran
  kenarın katman sınıfı `hatch/furniture/unknown` ve kenar uzunluğu ortak sınırın ≥ %80'i ise `split_by_thin_line` sinyali,
  etiketli parça ile etiketsiz komşu birleştirilir; (2) balkon için korkuluk (`railing`) katmanı sınıfı — `LayerClass`'a girmez,
  profil/keyword ile `furniture` gibi ekleyici-olmayan sınıfa; (3) sızma için mevcut `flood_outcome` ile GT payı < 0,6 örnekleri
  (r71, r13) zaten düşük güven taşımalı → `alias_merge` + alan/etiket-alanı oranı sinyali. Bu üçü `docs/HITL_QUESTIONS.md` #8/#22
  ile ilişkili; hiçbiri tek dosya değil (src02-07, src02-12, KAYAPINAR).

## 2026-09-13 — FP kök nedeni: duvar grafı kenar kümesi, aday örtüşme kapısı, ince çizgi birleştirme

**Ne (kullanıcı direktifi, tek commit):**
1. **Polygonize kenar kümesi yalnız `GRAPH_EDGE_CLASSES` = {wall, beam, column, chimney, railing}** (`names.py`, sınıf → tüketici
   kodda). `floor.walls` içinden yalnız bu sınıflardaki yüz parçaları (`face_walls`) + bu sınıfların çizgileri (`barrier_segments`)
   kenar olur; hatch/stair/furniture/text/dim/unknown kenar üretmez. **Pencere kapı gibi mühürlenir:** tespit edilen pencere
   açıklığı (`floor.windows`) geçici kenar (closure, iki uçtan `door_closure_extend_frac` × kalınlık), pencere katmanı çizgisi
   kenar değil. Merkez hatları (topoloji, `edges`, `cavities`) katman bağımsız kalır (2026-09-05 kararı).
   Sözlüğe **`railing`** sınıfı (korkuluk / railing / parapet): graf kenarı üretir, raster bariyeri DEĞİL (flood-fill ve
   kapı/pencere değişmesin diye BARRIER_CLASSES'a girmedi).
2. **Aday kapısı:** yüz, mevcut flood-fill odaları birleşimiyle > `graph.candidate_max_overlap` (0,3; eski `overlap_ambiguous`
   0,5) örtüşüyorsa aday olmaz.
3. **İnce çizgi birleştirme (`rooms.merge_split_faces`):** iki yüz arasındaki şerit (aralık ≤ `merge_gap_max_m` 0,35 — polygonize
   ince çizgi bandını yüz yapmaz, yüzler bandın iki yanında kalır; ortak sınır ≥ `merge_min_shared_m` 0,5) duvar boşluğuyla
   ≤ `merge_thin_cavity_max_frac` (0,3) örtüşüyorsa ayıran şey ince çizgidir → aynı oda. **Yorum:** "aynı odanın içinde" =
   ince-komşuluk bileşeni en fazla `merge_max_labels` (1) oda etiketi taşır; iki etiketli bileşen (salon | mutfak ince çizgiyle)
   ayrı odalardır, dokunulmaz. Flood odasının içinde olma şartı KULLANILMADI: flood poligonu da aynı ince çizgilerle parçalı
   (raster `extra_segs` = katman bağımsız çiftler), o yüzden yüzler "flood odasının içinde" çıkmıyordu (src02-07 SALON+MUTFAK 9,8 m²
   flood / 19,1 m² yazı). Boşluk testi: **kiriş sınıfı çiftler boşluk sayılmaz** (`MERGE_THIN_EXEMPT_CLASSES` = {beam};
   KİRİŞ İZD iki paralel çizgi → 25 birimlik "duvar" → odayı bölüyordu), **korkuluk çizgisi tek çizgi olsa da sert**
   (`MERGE_HARD_LINE_CLASSES` = {railing}; merdiven/boşluk kenarı). Merdiven ayak izi yüzleri birleşmez (ilk denemede kat holü
   ile birleşip MERDİVEN TP'sini düşürdü).

**Sonuç (11 GT, ayrıntı EVAL_HISTORY):** oda FP 61 → 52, FN 52 → 49, TP 165 → 168, F1 0,745 → 0,769; kapı/pencere birebir aynı;
IoU 0,881 → 0,880. Dosya bazında FN artışı yalnız src02-12'de (+4 / −5), nedenleri:
- HOL r16 (7,6 m² yüz GT ile IoU 0,64, flood parçası 3,1 m² ile örtüşme 0,40) → **kapı (2)** eledi; önce 0,5 altında aday olup TP idi.
- HOL r6 → **(3)** 1,9 + 4,1 m² yüzleri 6,0 m²'ye birleştirdi (GT 6,4), sonra **(2)** flood parçasıyla (2,9 m²) %45 örtüşünce eledi.
- ASANSÖR c_as_sag1 → **(1)**: asansör şaftı duvarları MERDIVEN katmanında (712 birim), stair kenar üretmeyince yüz kayboldu.
- MERDİVEN c_merd_sag_ust → **(1)**: MERDIVEN çizgileri kenar olmayınca çevre yüz 11,2 → 29,4 m² büyüdü, IoU 0,74 → 0,29.
İlk ikisi tek desen: **flood parçası ⊂ graf yüzü**. Aday: kapı bağlamadan SONRA, etiketli flood odası bir yüzün içinde kalıyorsa
(oda ∩ yüz ≥ 0,9 × oda, yüz ≤ 1 etiket) oda poligonu yüzle değiştirilsin (`graph_extends` sinyali; kapı/pencere değişmez, IoU ve
TP artar). src02-12'de 2 FN, src02-07'de HOL parçaları (r16–r18) bu desende. Son ikisi stair katmanı kararı; aday: stair sınıfı
çizgiler yalnız merdiven ayak izi dışında kenar üretsin (asansör şaftı çizgileri).
**Kod dışı gözlem:** raster flood-fill'in parçalanması aynı kök nedenden (`extra_segs` katman bağımsız çiftler: SIVA/KİRİŞ İZD
çiftleri bariyer). Bu turda dokunulmadı (kapı/pencere değişmesin); ağırlık turunda `_wall_segments` çiftlerine katman sınıfı
sinyali ile bariyer güveni.

## 2026-09-13 (2) — merdiven sınıfı kenarları ve örtüşme kapısı istisnası (flood parçası ⊂ yüz)

**Ne (kullanıcı direktifi, tek commit):**
1. **Merdiven sınıfı ayrımı (`walls.stair_segments / split_stair_segments / stair_footprints / stair_edge_segments`):**
   merdiven katmanı çizgileri basamak (ladder: `stair_step_m` [0,15, 0,6] dik aralıkta ≥ `stair_step_min_neighbors` 2 paralel
   komşu; blok basamaklar için merdiven katmanındaki INSERT'ler açılır) ve diğer olarak ayrılır. Ayak izi = basamak çizgilerinin
   tamponlu dışbükey zarfı (önce tüm merdiven çizgileri → komşu asansör şaftı da ayak izine giriyordu). Basamak olmayan, ayak
   izinin (tampon kadar geri çekilmiş) dışındaki, eksene yakın (`stair_edge_ang_tol_deg` 10; asansör çarpısı 45° → değil)
   modelspace çizgileri kenar üretir (kova çevre duvarı, şaft duvarı). Basamak bulunamazsa (kısa kol, yalnız çevre çizgisi)
   eski davranış: tüm merdiven çizgileri ayak izi, kenar yok (`stats.stair_fallback`). `_staircase_polygon` (polygons.py) raster
   maskesinden dik-açılı poligon yardımcıdır, merdivenle ilgisi yok; ayrım ayak izi poligonuyla yapıldı.
2. **Örtüşme kapısı istisnası (`rooms.reconcile_rooms(absorb_min_frac)`):** aday kapısına (> `candidate_max_overlap`) takılan yüz,
   tam olarak bir etiketli flood odasını kapsıyorsa (oda ∩ yüz ≥ `absorb_min_room_frac` 0,9 × oda alanı) ve başka etiketli odaya
   %5'ten fazla değmiyorsa ve etiket alan yazısı varsa yüz/yazı oranı [0,5, 2] içindeyse (`absorb_area_ratio_max`; area_mismatch
   mutlak kuralıyla aynı — ±%30 toleransı denendi, KAT HOLÜ/BANYO kayıpları verdi) elenmez; oda poligonu yüz ∪ oda olur
   (`signals.graph_absorb`), tek mahal. Kapı bağlamadan SONRA
   uygulanır → kapı-oda ataması ve pencere değişmez. `graph_extends` (eşleşen/eşleşmeyen tüm yüzler için genişletme) ağırlık
   turunda kalır; bu istisna yalnız kapıya takılan yüzler içindir.

**Beklenti ve gerçekleşme:** src02-12'de HOL r16/r6 deseni (2) ile geri geldi (absorb 16; TP 58 → 71, FP 30 → 13, FN 25 → 12).
İlk denemede BANYO r14 (4,4 m²) 14,4 m² yüze yutuldu → yazı alanı oran kuralı eklendi. Sol çekirdek ASANSÖR ×2 ve KULLANILMAYAN
ALAN ×2 yeni FN: önce tüm-çizgi ayak izi zarfı asansör çarpısını kapsayıp şaftla çakışıyordu (rastlantısal TP), basamak tabanlı
ayak izi bunu yapmaz; şaft duvarları hatch-only (aşağıdaki kök neden).
**ASANSÖR c_as_sag1 ve MERDİVEN c_merd_sag_ust geri GELMEDİ:** kök neden merdiven sınıfı değil — bu dosyada çekirdek duvarları
yalnız `..taramam` (hatch sınıfı) HATCH sınırlarıyla çizili, DUVAR çizgisi tek yüz (295 birim); MERDIVEN katmanındaki 712 birim
asansör çarpısıdır (kenar olmamalı). Deney: hatch sınıfı ÇİFTLERİ kenar kümesine alınca src02-12 69/16/14 → 53/36/30 (hatch
çiftleri odaları bölüyor) → geri alındı. Aday (ağırlık turu): hatch çifti kalınlığı dosya duvar kalınlığı moduna eşitse ve
başka duvar-sınıfı çizgiyle çakışmıyorsa `hatch_wall` sinyali (yalnız o çiftler kenar).
Basamak tespiti src02-07'de (72 çizgi, blok basamak yok, KOTBLK08 kot blokları merdiven katmanında) ayak izi < 1 m² → fallback;
src02-12'de 15 basamak, 1 ayak izi (6,7 m²), 12 kenar.

## 2026-09-14 — İki not (kullanıcı): genellik şüphesi ve kapsama

- **(a) Genellik:** 2026-09-13'ün iki commit'inin (a5f6c8f FP kök nedeni, d910eb4 merdiven ayrımı + absorb) kazancı büyük ölçüde
  src02-12'den geldi (oda TP/FP/FN 57/40/26 → 71/13/12); holdout (tip-6, src02-09) sabit kaldı (0,868 → 0,873, ikinci commit'te
  aynı). Kurallar (kenar sınıfları, aday örtüşme kapısı, ince çizgi birleştirme, absorb) tek dosyaya göre ayarlanmış olabilir;
  genelliği src02-13 ve src02-06 (holdout, GT yok) GT'leri gelince doğrulanacak. O zamana kadar bu eşiklere dokunulmaz.
- **(b) Kapsama 0,30:** kalan 35 FN'nin (ve 34 FP'nin) issue üretmemesi ağırlık turunun ayrı maddesi. Yöntem: her FN için
  "hangi issue tipi bunu yakalamalıydı" analizi (unlabeled_region / open_room / room_merged / area_mismatch / yeni tip yok),
  dosya × tip tablosu; issue üretmeyen FN desenleri (hatch-only çekirdek, etiketli parça ⊂ yüz ama yazı alanı yok, bina dışı
  teras) için mevcut tiplerin tetiğine sinyal eklenir, yeni issue tipi açılmaz (2026-09-05 kuralı).

## 2026-09-14 — Anlamsız katman adları (non_semantic) ve learning log `answered_by`

**Ne:** `vocab.NON_SEMANTIC_LAYER_PATTERNS` / `is_non_semantic_layer`: kalem kalınlığı (AA-0.20, A-5), çizgi tipi (ÇİZ KALIN,
ÇİZGİ 2), PEN-3, saf sayı/nokta (0, 1, 0.5, 2,25) desenleri. Bu adlar içerik hakkında bilgi taşımaz: `classify_layers` kaynağı
`non_semantic` (sınıf unknown, güven 0), sınıf yalnız `refine_with_stats` içerik istatistiğinden; `validate` unknown_layer
sorusu üretmez. Sınıflandırma sonucu değişmez (stats kademesi zaten bilinmeyenlere uygulanıyordu), yalnız soru sayısı düşer.
Desenler genel (ofise özgü değil), vocab.py'de; ofise özgü adlar profilde kalır.
**C turu (src02-07 HITL) için:** cevaplar GT'den türetilecek → `learning/log.append` `answered_by` ∈ {human, gt, auto} zorunlu;
`hitl/cli.py --answered-by gt`. İnsan cevabı yalnız çizime bakılarak verilen (görsel soru) cevaplar için `human`.
**Aday:** src02 ailesinde AA-* katmanları kalem kalınlığına göre bölünmüş (AA-0.05/0.09/0.15/0.20 = farklı içerik: ince mobilya
çizgisi ↔ kalın duvar); içerik istatistiği kademesinin bu katmanlarda ne verdiği ağırlık turunda ölçülecek (`stats.conf` 0,4).

## 2026-09-14 — C turu (src02-07 HITL): cevaplar, aktarılabilirlik, learning/to_profile.py

**Cevaplar:** 28 issue; 2 görsel (insan): MERİZD → stair (döner merdiven basamak izdüşümü, radyal çizgiler), Tefriş → furniture
(duşakabin + şaft/çamaşır makinesi kutuları; ikili hat duvar çifti gibi eşleşiyordu). 26 GT'den türetildi (`answered_by: gt`):
unit cm; unlabeled_region 5 (aydınlık ×2, asansör, merdiven, 1 yoksay = kat holü parçası); room_merged → ayrı odalar;
room_no_door 2 → kapı eksik (GT'de HOL 5, KAT HOLÜ 4 kapı); window_missing → pencere var; door_side 3 doğru / 1 diğer oda
(op14: giriş kapısı ÇOCUK O.'ya atanmış); area_mismatch 12 → 10 "yazı", 2 "ikisi de yanlış" (KAT HOLÜ, BALKON r13 iki balkonu
yutmuş). Türetme kuralları scratch `gt_answers.py` (GT poligon kapsaması ≥ 0,5 → çekirdek tipi; GT alanına %20 içinde olan taraf;
door side = GT menteşe noktasına en yakın bağlı mahal).

**Aktarılabilirlik (learning/to_profile.py, Adım 10):**
- Aktarılabilir → `source_profiles/<fam>.yaml`: unknown_layer / conflicting_layer (katman adı → sınıf; ad ofise özgü, sınıf aile
  geneli), unit_suspect (profile.units = ofis çizim birimi; pipeline'da yalnız hipotez yolunda standart öncüllerin önünde aday —
  dosyanın kendi kapı kestirimi öncelikli, o yüzden 11 GT geometrisi değişmez), blok cevabı (henüz issue tipi yok; unknown_block
  gelince profile.blocks). Profilde farklı sınıf varsa mevcut korunur + uyarı; learned_from ve fingerprints güncellenir.
- Aktarılamayan (yalnız o dosyanın IR'ı + learning log; HITL yükünün kalıcı kısmı): unlabeled_region, room_merged, room_no_door,
  window_missing, door_side_ambiguous, area_mismatch, open_room, ambiguous_opening. src02-07'de 28 cevabın 25'i bu sınıfta
  (%89); kalıcı yük ≈ 25/29 oda = 0,86 issue/oda. Bunları azaltmanın yolu profil değil, algılama (ağırlık turu).
- Dosya düzeyi birim cevabı (`hitl_units`) src02-07'nin kendi yeniden koşusunda uygulanır (politika g) → src02-07 geometrisi
  115,2 → 100 birim/m ile DEĞİŞİR; bu profil etkisi değil, dosyanın kendi HITL cevabı. Ölçüm EVAL_HISTORY'de ayrı satır.

**Ağırlık turu maddesi — raster flood-fill daralması:** area_mismatch cevaplarının 10/12'si "yazı doğru" (geometri %40–86
küçük): fam10'da flood-fill poligonları sistematik daralıyor. Neden graf tarafında çözülen kök nedenin raster karşılığı:
`_Raster(extra_segs=floor.walls)` katman bağımsız paralel çiftleri (SIVA, KİRİŞ İZD, _TEFRİŞ ikili hatları) bariyer olarak
çiziyor, oda ince çizgilerle parçalanıyor (SALON+MUTFAK 19 m² → 10,8; HOL 5,4 → 2,2; KAT HOLÜ 14,1 → 2,0). Aday: raster
extra_segs'e yalnız `layer_class`/`thickness_mode` sinyali yüksek çiftler (GRAPH_EDGE_CLASSES ile aynı küme + kalınlık modu),
ya da flood poligonunu graf yüzüyle değiştirme (`graph_extends`). Kapı/pencere tarafı etkilenmesin diye ayrı ölçüm.

## 2026-09-14 — Ağırlık turu (1): raster flood-fill daralması — bariyer çiftlerine sınıf/kalınlık sinyali

**Ne:** `_Raster(extra_segs)` artık `floor.walls`'ın tamamı değil: bir paralel çift, üç sinyal birden aleyhteyse bariyer
olarak çizilmez — `layer_class == 0` (bilinen, bariyer dışı sınıf) ∧ `wall_word == 0` (adında duvar kelimesi yok; yeni sinyal
`signals/layer.wall_word`, ağırlık 0 → duvar güveni değişmez) ∧ `thickness_mode != 1` (kalınlık dosya modunda değil).
Sınıfı bilinmeyen çiftler ('0', AA-*) bariyer kalır. Eşik `raster.extra_exclude_class_vote`. Kapı/pencere yolu dokunulmadı.
**Referans:** fam10 area_mismatch cevapları (10/12 "yazı doğru"): ..taramam / TARAMA / _TEFRİŞ / KİRİŞ İZD / Tefriş ikili
hatları odaları bölüyordu.
**Deneyler (11 GT, hızlı koşu):**
- r1/r2 yalnız `layer_class == 0` (+ wall_word): 182/33/35 → 189/18/28 (F1 0,892) ama tip-1 HOL kaybı (A_ANNO_AREA_NET net-alan
  çiftleri HOL–ANTRE arasındaki tek bariyerdi) ve holdout tip-6 IoU 0,912 → 0,897 (F1 aynı).
- r3 (+ thickness_mode koşulu): 189/20/28 (F1 0,887), tip-1 korundu, holdout IoU 0,860 → 0,859, F1 aynı → **seçildi**
  (holdout kapısı). src02-12 76/2/7 yerine 75/3/8 — ..taramam çiftlerinin 276/858'i kalınlık modunda, bariyer kaldı.
**Gözlem:** tip ailesinde net-alan (A_ANNO_*) polilineleri oda sınırıyla çakışıyor; "şanslı bariyer". Gerçek açık geçiş
(HOL–ANTRE, kapısız) raster tarafında yalnız mühürle kapanıyor; graf tarafındaki passage_closures'ın raster karşılığı yok →
aday (ağırlık turu 5 ile birlikte).

## 2026-09-14 — Ağırlık turu sırası (kullanıcı): (1) raster bariyer ✓, (2) graph_extends, (3) hatch_wall, (7) alan-polyline
katmanları → `area` sınıfı (ALAN, NET ALAN, MAHAL ALANI, M2, A_ANNO_AREA* deseni): kapalı polyline doğrudan oda adayı (güven
0,9), içindeki etiketle bağlanır, flood/graf ile uzlaşır; bariyer değil, kaynak — (3)'ten sonra. Sonra (4) pencere güven
kalibrasyonu (monoton tablo), (5) tek çizgili duvar + snap toleransı, (6) kalan FN'ler için issue kapsama analizi. Her parça
ayrı commit, 11 GT + holdout kapısı, aynı tablo.

## 2026-09-14 — Ağırlık turu (3) hatch_wall: DENENDİ, GİRMEDİ

**Deney:** yeni duvar sinyali `hatch_wall` (tarama sınıfı çift ∧ kalınlık dosya modunda → 1; ağırlık 0,65) ve bu çiftler graf
yüz kenarı (`face_walls`). Tarama sınıfı çiftlerin kalınlık-modu payı dosya bazında %0–%90 (tip ailesi %70–90: A_WALL_PAT
duvar deseni; src02-12 276/858; fam00 0 — mod yok). 11 GT hızlı koşu: oda 189/20/28 → 189/23/28 (F1 0,887 → 0,881),
IoU 0,883 → 0,872, kapı/pencere aynı, holdout aynı. src02-12'de +3 FP (hatch kenarları 2,7–9,3 m² aday yüzler üretti,
GT çekirdek mahalleriyle hizalanmadı; E.BANYO poligonu 1,2 m²'ye daraldı), hedeflenen sağ çekirdek ASANSÖR/MERDİVEN geri
gelmedi. **Kapı geçmedi → kod geri alındı.** Öğrenilen: tarama sınırı çiftleri kalınlık modunda olsa da duvar hattıyla
çakışmıyor (dolgu sınırı sıva/kaplama çizgisinden içeride/dışarıda) → mevcut kenarlarla çift hat, sahte yüz. Aday: tarama
çiftini yalnız yakınında (≤ kalınlık) hiçbir wall-sınıfı kenar YOKSA eklemek (boşluk doldurma), tam kenar kümesi değil.

## 2026-09-14 — Ağırlık turu (7): alan-polyline katmanları → `area` sınıfı, oda kaynağı

**Ne:** `vocab.is_area_layer` (tam kelime: alan / area / m2 / m² — A_ANNO_AREA_NET, ALAN HESAP, M2, .ABM_Alan; YALITIM2 ve
YAZIALAN değil), `LayerClass.area` (açıklama kelimesini yener), `AREA_CLASSES` tüketici: `rooms.area_polygons` (kapalı
LWPOLYLINE/POLYLINE, alan ≥ min_room_area) + `apply_area_polygons` (poligon tam olarak BİR odanın etiketini içeriyorsa o odanın
poligonu; 0 etiket = parsel/etiketsiz, ≥2 etiket = daire/toplam sınırı → kullanılmaz, sayılır). Sinyal `area_polyline` (ağırlık
0,90), kaynak `area+<flood>`; graf uzlaşması ve kapı bağlama bu poligonla çalışır. Bariyer değil; `WALL_EXCLUDE_CLASSES`'a
eklendi (ince çizgi pencere adaylarından da dışlanır — ilk denemede net-alan çizgileri tip-6'da 3 sahte pencere üretti,
holdout pencere 0,828 → 0,750; düzeltildi).
**Ölçüm (11 GT hızlı koşu):** oda/kapı/pencere F1 aynı; IoU 0,883 → 0,886 (tip-1 0,941 → 0,954, tip-2 0,928 → 0,956,
tip-6 holdout 0,910 → 0,908 — üçüncü ondalık, kabul); issue/oda medyan 0,83 → 0,79 (room_no_door 40 → 39; tip-4 0,83 → 0,67).
Alan poligonu yalnız tip ailesinde ve hafif_celik'te var (11 GT'de 5 dosya; 55 dosyada tip-* 16 + hafif_celik 3 + M2/ALAN HESAP
taşıyan ABM dosyaları). Etiketsiz alan poligonları (area_skipped_0: tip-2 1, tip-4 2) şimdilik aday değil → ileride
unlabeled_region kaynağı olabilir (aday).

## 2026-09-14 — Ağırlık turu (4): pencere güven kalibrasyonu; holdout'un ilk somut katkısı

**Holdout notu:** (7) alan-polyline turunun ilk denemesinde net-alan çizgileri (A_ANNO_AREA_NET) ince-çizgi pencere adayı
olabildi; tip-6 (holdout) pencere F1 0,828 → 0,750 ile yan etkiyi yakaladı, geliştirme kümesinde görünmüyordu (tip-1/2/4 pencere
aynı kaldı). Holdout kapısının ilk somut katkısı; düzeltme: area sınıfı WALL_EXCLUDE_CLASSES'a.
**Pencere kalibrasyonu:** kaynak doğruluğu geliştirme kümesinde (9 GT): layer 0,79 (n=61), block_keyword 0,70 (54),
block_geometry 0,44 (84), thin_lines 0,00 (11); holdout: block_keyword 0,76 (17), block_geometry 0,17 (6), thin_lines 0,00 (3).
Eski ağırlıklar (0,85 / 0,85 / 0,70 / 0,30) tek dilime yığıyordu (0,7–0,9: 0,62, n=222). Yeni: layer 0,80, block_keyword 0,65
(0,70 kalibre; dilim sınırı altında tutuldu), block_geometry 0,45, thin_lines 0,05 (kaynak kaldırılmadı, kanıt kalır; aday:
thin_lines tamamen kapatılırsa 14 FP düşer — ayrı karar). `ir_compat.WINDOW_CONF` geçiş tablosu aynı değerlere çekildi.
**Kalibrasyon tablosu (yeni, dev):** 0–0,5 → 0,39 (n=95), 0,5–0,7 → 0,70 (54), 0,7–0,9 → 0,79 (61): monoton ✓; holdout
0–0,5 → 0,11 (9), 0,5–0,7 → 0,76 (17). F1/TP/FP/FN değişmez (güven çıktıyı elemez); değişen: block_geometry < 0,5 →
penceresiz odaya değen adaylar `ambiguous_opening` toplu sorusuna girer: window_fp kapsamı 8/99 → 36/99 (dev 33/87, holdout 3/12);
ambiguous_opening issue 4 → 6 (dosya başına tek soru); kapsama 0,27 → 0,39.
**Triage notu (kullanıcı sorusu):** src02 ailelerinde alan-polyline katmanı var mı? — yalnız src02-08'de ('ABM.ALAN':
32 kapalı poligon, 26 oda bağlandı, 4 etiketsiz, 2 çok etiketli); diğer 14 src02 dosyasında alan/area/m2 tam kelimeli katman
yok (area_polys = 0). src02-08 GT'siz → kazanç ölçülemedi; GT önceliği adayı (fam02 için ikinci GT). Alan kaynağı 55 dosyanın
12'sinde (tip ailesi, hafif_celik, ABM M2/ALAN HESAP, src02-08).

## 2026-09-15 — Ağırlık turu (4b): pencere çıktı eşiği (`output_threshold.window`)

**Ne:** güven < eşik pencere `status: candidate` — IR'da kalır (kanıt, ambiguous_opening sorusu, window_missing "aday" sayımı),
tespit sayılmaz (`ir_compat.floor_v2_to_eval` candidate ve human_rejected'ı atlar → evaluate ve tüketiciler). Oda/kapı
dokunulmadı.
**Ölçüm (koşu çıktısı üzerinde, güvene göre eleme; 11 GT):**

| eşik | dev TP/FP/FN | dev F1 | holdout TP/FP/FN | holdout F1 | toplam F1 |
|---|---|---|---|---|---|
| 0 (yok) | 123/87/12 | 0,713 | 14/12/3 | 0,651 | 0,706 |
| 0,3 | 123/76/12 | 0,737 | 14/9/3 | 0,700 | 0,733 |
| 0,5 | 86/29/49 | 0,688 | 13/4/4 | 0,765 | 0,697 |
| 0,6 | 86/29/49 | 0,688 | 13/4/4 | 0,765 | 0,697 |

**Karar: 0,3** — geliştirme ve holdout'ta tutarlı (+0,024 / +0,049; yalnız thin_lines elenir, 0/14 doğru). 0,5 holdout'ta en iyi
(0,765) ama geliştirmede düşüyor (block_geometry 84 aday: %44 doğru ama 37 TP taşıyor) → kural gereği seçilmedi. block_geometry
adaylarının ayrıştırılması (kaynak içi sinyal: blok adı/boyut/duvar hizası) ağırlık turu sonrası aday.

## 2026-09-15 — Ağırlık turu (5) tek çizgili duvar ve snap toleransı: DENENDİ, GİRMEDİ

**(5b) Snap toleransı:** `graph.snap_tol_frac` 0,5 → 1,0 ve/veya `extend_tol_m` 0,6 → 1,0 (3 varyant, 11 GT hızlı koşu):
oda/kapı/pencere ve graf uzlaşma sayıları (matched 125 / flood_only 64 / graph_only 20) **birebir aynı** — yüzleri sınırlayan
uç-uç boşluk değil, mühürlü polygonize bandı (seal_m 0,12) ve kenar kümesi. KAYAPINAR "1 m boşluk" gözlemi (2026-09-09) snap ile
kapanmıyor. Eşikler geri alındı.
**(5a) Tek çizgili duvar (deney):** sınıfı bilinmeyen katmanlardaki ≥ 1 m, eksene yakın tek çizgiler graf yüz kenarı
(`single_line_wall_segments`; raster bariyeri değil). 11 GT: 189/20/28 → 188/19/29; geliştirme −1 TP (KAYAPINAR KAT HOLÜ
13/8/5 → 12/8/6: '0' katmanı tek çizgileri kat holünü böldü), holdout −1 FP (src02-09 3 → 2); matched 125 → 129. Geliştirme ve
holdout tutarsız → kural gereği girmedi; kod geri alındı. Öğrenilen: bilinmeyen katman tek çizgileri duvar olduğu kadar aks/
tefriş sınırı da; katman içeriği istatistiği (stats_class) olmadan ayrılmıyor → (c) maddesi: stats kademesi 'wall' verdiğinde
tek çizgi kenar olsun (bilinmeyen değil) — ağırlık turu sonrası.
**KAYAPINAR Banyo FN'lerinin (r9/r10) nedeni tek çizgi değil:** küvet/duşakabin çizgileri bariyer sınıfı katmanda (.DUVAR/KOLON)
→ flood ve graf banyoyu ikiye bölüyor; aday 1,8 m² = küvet içi. Aday: bariyer sınıfı katmandaki KISA kapalı dikdörtgenler
(≤ 2 m², oda etiketi içermeyen) tefriş sayılsın (sinyal: kapalı küçük çevrit) — ayrı madde.

## 2026-09-15 — Ağırlık turu (6): kalan FN/FP için issue kapsama analizi; küçük şaft kuralı; kapsama kuralı düzeltmesi

Kaynak: 11 GT, koşu 91919e0 (4b sonrası); tablo scratch `fn_fp_analysis.py` çıktısı (dosya × GT × desen × en iyi tahmin × issue).

**FN (28 → küçük şaft kuralıyla 25) — desen, sayı, hangi issue yakalamalıydı, neden üretilmedi, önerilen kural:**
| desen | n | issue | durum | öneri |
|---|---:|---|---|---|
| tahmin GT'den büyük (hol birleşmiş/sızmış): src02-09 HOL ×2, src02-02 KAT HOLÜ, src02-12 MERDİVEN ×2, tip-6 KAT HOLÜ | 6 | area_mismatch / room_no_door | 5'inde üretildi (birleşen büyük odada); tip-6'da yok (area+exclusive kaynağı, alan yazısı yok, kapısı var) | (a) alan poligonu ≥2 etiket içeriyorsa (`area_skipped_2plus`) o etiketler için room_merged; (b) etiketi başka odanın poligonunda kalan (etiket ⊂ komşu poligon) oda → room_merged |
| dış mahal (balkon/veranda/sahanlık): KAYAPINAR Balkon ×2, src02-07 BALKON ×2, hafif_celik GİRİŞ SAHANLIĞI, tip-2 GİRİŞ VERANDA | 6 | area_mismatch / room_merged | 4'ünde üretildi (daralmış/birleşmiş balkon); 2'sinde hiç tahmin yok (etiket yok, dışbükey zarf dışı) | (10): korkuluk kenarlı, etiketli odaya bitişik yüzler zarf dışında da aday |
| yalnız etiketsiz aday, IoU < 0,5: KAYAPINAR Banyo ×2, src02-07 KAT HOLÜ, src02-12 ASANSÖR, KULLANILMAYAN ALAN | 5 | unlabeled_region | üretildi (aday üzerinde) — eski kapsama kuralı unlabeled_region'ı oda issue'su saymıyordu | kapsama kuralı: ROOM_ISSUES += unlabeled_region ✓ (bu commit) |
| hiç tahmin yok (hatch-only çekirdek): src02-12 ASANSÖR ×2, KULLANILMAYAN ALAN, src02-02 ve src02-09 MAKİNE DAİRESİ ASANSÖR | 5 | — | aday yok → hiçbir tip tetiklenemez | (9): tarama alanı dolgu olarak raster bariyerine; aday çıkınca unlabeled_region |
| tahmin GT'den küçük (parçalı): src02-07 HOL ×2, src02-12 KAT HOLÜ | 3 | area_mismatch | üretildi ama parça GT merkezini içermiyordu → eski kural kapsamıyordu | kapsama kuralı: GT alanının ≥ 0,3'ünü örten tahminde issue varsa kapsanmış ✓ |
| küçük şaft ≤ 1 m²: KAYAPINAR, tip-1, tip-2 | 3 | — | alt sınır 1 m² | GT_GUIDE kuralı: oda F1 dışı, ayrı `shaft` satırı ✓ (0/3 bulunuyor) |

**FP (20):** etiketli parça 10 (area_mismatch 9'unda; tip-4 ANTRE 3,0 m² / GT 10,9: alan yazısı yok, kapısı var → hiçbir tip;
öneri: graph_match = 0 ∧ alan yazısı yok ∧ komşu etiketsiz yüz → "oda parçalı" sinyali, mevcut open_room mesajıyla), etiketsiz
aday 8 (unlabeled_region hepsinde), GT dışı 1 (src02-07 BALKON 96 m²: room_merged + area_mismatch), IoU kayması 1 (src02-12
KAT HOLÜ: room_no_door). Kapsanmayan tek FP: tip-4 ANTRE.

**Kapsama kuralı düzeltmesi (metrics.py, ölçüm; algılama değişmedi):** ROOM_ISSUES'a unlabeled_region; room_fn için "GT merkezini
içeren tahmin" yerine "GT alanının ≥ `eval.fn_overlap` 0,3'ünü örten ya da merkezini içeren tahminlerden birinde oda issue'su".
Sonuç: room_fp 11/20 → 19/20, room_fn 13/28 → 15/25, toplam 81/222 (0,36) → 91/219 (0,42). Kapsanmayan 10 FN: hatch-only
çekirdek 5, zarf dışı dış mahal 2, tip-6 KAT HOLÜ 1, src02-02 KAT HOLÜ (büyük odada issue yok) 1, src02-12 c_as_sol2 1.
**Küçük şaft kuralı:** `config/eval.yaml shaft_max_m2` 1,0 (ölçüm parametreleri `config/eval.yaml`'da, algılama hash'i dışında);
oda 189/20/28 → **189/20/25**, F1 0,887 → 0,894 (kod değişmedi; ölçüm tanımı değişti — EVAL_HISTORY'de ayrı satır).
Sıradaki parçalar: (8) bariyer katmanında ≤ 2 m² etiketsiz kapalı çevritler tefriş, (9) tarama dolgusu raster bariyeri,
(10) korkuluk kenarlı dış yüzler zarf dışında aday.
