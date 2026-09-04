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

## Adaylar (uygulanmadı)

- **[aday] 2026-09-04 — `evaluate.py` her pred JSON'un mtime'ını ve `results.json` koşu zamanını
  rapora yazsın; GT'den eski pred için uyarı.**

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
- **[aday] 2026-09-04 — `run_baseline.run_one` içindeki akış (etiket → ölçek → kat seçimi →
  reconstruct) `pipeline.py`'ye taşınsın.** Adım 4'te planlı.
- **[aday] 2026-09-04 — `core/sheets.py` çıktısı (görünümler, kat adları) runner'ın kat
  seçimine bağlansın; tek kat yerine tüm kat planları çıksın.** Pafta anlama v1 hazır ama
  bağlı değil.
