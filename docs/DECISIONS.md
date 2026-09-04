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

## Adaylar (uygulanmadı)

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
