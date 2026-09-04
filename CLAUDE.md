# vibedraw — Claude Code çalışma kuralları

Bu dosya her oturumda okunur. Mimari ayrıntı için `docs/ARCHITECTURE.md`,
yapılacak işlerin sırası için `docs/REFACTOR_PLAN.md` dosyasına bak.

## Proje nedir

Nihai ürün: mimari altlıktan (DWG/DXF) **elektrik projesi** üretmek.
Bu iki katmandan oluşur:

1. **Perception (drawing understanding / CAD normalization)** — altlığı anla,
   `BuildingIR` üret. **Şu anki tek odak budur.**
2. **Elektrik tasarım motoru** — `BuildingIR`'ı tüketir, elektrik projesi üretir.
   Henüz planlanmadı; `core/rules.py`, `core/layout.py`, `core/devices.py`,
   `core/cad.py` eski prototip, dokunma ve perception koduna karıştırma.

İki katman arasındaki tek sözleşme `BuildingIR`dır. Perception elektrik bilmez;
elektrik motoru DXF okumaz.

## Değişmez ilkeler

1. **Geometri deterministik koddan çıkar.** Koordinat, kalınlık, poligon, topoloji
   hiçbir LLM/VLM'den istenmez. LLM = isim/enum normalizasyonu ve metin;
   VLM = belirsiz bölge için sınıflandırma (evet/hayır/seçenek), koordinat değil.
2. **Kural yazma, sinyal yaz.** Bir tespit tek bir `if` ile karara bağlanmaz;
   bağımsız sinyaller skor üretir, skorlar birleşir, sonuç `confidence` taşır.
   Yeni bir durum için yeni `if` değil, yeni sinyal ya da ağırlık değişikliği eklenir.
3. **Her tespit güven + kanıt taşır.** `confidence: float` ve `evidence: dict`
   olmayan bir Room/Door/Window/Wall IR'a giremez.
4. **Erken kesin karar yok.** Aşamalar aday listesi taşır; belirsizlik sonraki
   aşamaya ve sonunda HITL'e akar.
5. **Ofise özgü bilgi kodda yaşamaz.** Katman adları, blok adları, ofis
   standartları `source_profiles/` altındaki veri dosyalarındadır; kodda yalnızca
   genel sinyaller (anahtar kelime, içerik istatistiği, geometri) vardır.
6. **Eşikler config/kalibrasyondan gelir.** Dosyadan türetilebilen her sayı
   (birim, duvar kalınlığı, kapı genişliği, text yüksekliği) `calibration`
   aşamasında türetilir; kalanlar `config/` altında adlandırılmış sabit olur.
   Fonksiyon gövdesine gömülü yeni "sihirli sayı" eklenmez.
7. **Tek dosyalık düzeltme yapılmaz.** Bir hata yalnızca tek dosyada görülüyorsa
   sinyal eklenmez; `docs/HITL_QUESTIONS.md`'ye "soru adayı" olarak yazılır.
   Bir desen ≥3 dosyada tekrar ederse sinyal olur.
8. **Eval kapısı.** Perception'a dokunan her değişiklik öncesi ve sonrası
   `python3 experiments/run_baseline.py && python3 evaluate.py` koşulur, sonuç
   `docs/EVAL_HISTORY.md`'ye tarih + commit + özet tablo olarak eklenir.
   Toplam oda F1 veya kapı F1 düşüyorsa değişiklik girmez (bilinçli trade-off
   ise gerekçesiyle yazılır).

## Yapma listesi

- `core/geometry.py`'ye yeni fonksiyon ekleme; refactor sonrası modüller
  (`core/perception/*`) kullanılır.
- `WALL_LAYERS` / `DOOR_LAYERS` / `WINDOW_LAYERS` gibi hardcode katman
  kümelerine yeni isim ekleme → `source_profiles/`.
- Kod yorumuna "tip-4 ANTRE için", "KAYAPINAR Hol için" gibi tek dosya referansı
  yazma → HITL soru adayı.
- VLM'e tam kat planı gönderip koordinat isteme.
- Perception IR'ına elektrik alanı (device, circuit, appliance) ekleme.
- Yeni oda/katman kelime listesi açma; tek kaynak `core/perception/vocab.py`.

## Komutlar

```
pip install -r requirements.txt
python3 -m pytest -q                                   # birim testleri
python3 triage_dataset.py data/dataset                 # veri seti profili
python3 experiments/run_baseline.py                    # tüm aday dosyalarda koşu
python3 evaluate.py                                    # GT ile ölçüm
python3 annotate.py <dxf>                              # GT etiketleme aracı
```

`data/raw`, `data/dataset`, `ornekler`, `output` repoda yoktur (telif/boyut).

## Çalışma tarzı

- Refactor adımlarını `docs/REFACTOR_PLAN.md`'deki sırayla, her adımı ayrı
  commit olarak yap. Adım bitince plan dosyasındaki kutucuğu işaretle.
- Davranış değiştirmeyen refactor'da eval sonucu birebir aynı kalmalı; farklıysa
  önce nedenini bul.
- Belirsiz bir tasarım kararı varsa kodu yazmadan önce `docs/DECISIONS.md`'ye
  kısa bir madde yaz (ne, neden, alternatif) ve devam et.
- Türkçe yorum/dokümantasyon; kod tanımlayıcıları İngilizce.
