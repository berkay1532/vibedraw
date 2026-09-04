# Veri seti (docs/DATASET.md)

Veri klasörleri repoda yoktur (`data/raw`, `data/dataset`, `ornekler`, `output`; telif/boyut). Bu belge veri setinin
bileşimini, ADAY dışı bırakılan dosyaları, girdi-çıktı çiftlerini ve GT listesini kayıt altında tutar.
Sayılar `python3 triage_dataset.py data/dataset` çıktısındandır (2026-09-04, fold düzeltmesi sonrası; deniz-evi-projesi-dwg-2 ADAY oldu).

## Kaynaklar

- Bakanlık tip projeleri (`tip-N_mimari`), Arkipedia/Dropbox arşivleri (detayli-villa, modern-apartman, hafif çelik…),
  meslektaştan alınan 37 gerçek ruhsat DWG'si (5xx_MİMARİ, 2510, 290, KAYAPINAR…), referans dosya `input-2-clean`.
- DWG → DXF: LibreDWG `dwg2dxf` (`data/dataset/_dxf/`).

## Sayılar

| Ölçüt | Değer |
|---|---:|
| Taranan dosya | 68 |
| Okunabilen | 67 |
| ADAY (≥3 oda metni + çizgi geometrisi, elektrik değil) | 50 |
| ELEKTRİK (mimari altlık değil) | 4 |
| ZAYIF | 13 |
| HATA | 1 |
| Katman ailesi (Jaccard ≥ 0,5) / aday içeren | 34 / 20 |
| Ağır dosya (heavy) | 5 |
| Ground truth | 7 |

## ADAY dışı bırakılanlar

### Elektrik çizimleri (triage `verdict: ELEKTRİK`; girdi-çıktı çifti adayları)

Tespit: katman/blok adında elektrik ipucu (linye, anahtar, buat, etanj, priz, armatür…) toplamı ≥ 3.
Aynı proje numaralı mimari ADAY dosya = çift adayı (elektrik motoru eval'i için ileride kullanılabilir).

| Elektrik çizimi | Mimari eş (çift adayı) | Not |
|---|---|---|
| 1484A7P | — | **combined**: altlık + elektrik aynı dosyada (mimari eş yok); ileride altlık katmanları ayrıştırılarak çift üretilebilir |
| 2510-9_ELEKTRİK_3 | 2510_912.05.2023 | elektrik çizimi; 2510_912.05.2023 ile girdi-çıktı çifti adayı |
| 2510-9_ELK | 2510_912.05.2023 | elektrik çizimi; 2510_912.05.2023 ile girdi-çıktı çifti adayı (aynı projenin iki sürümü) |
| 290-10_KOLDERE | 290_ADA_10_PARSEL_KOLDERE_21062023 | normal çift: elektrik çizimi ↔ mimari altlık |

### Elle atlananlar (`data/raw/atlanan`, girdi değil)

- 1148_PARSEL_MİMARİ_PROJE_01.12.dwg
- 183_ADA_6_PARSEL.REVİZE_11.06.2025.dwg
- HouseProject11_Simple_Villa.dwg
- bungalov-villa-projesi-mumbai.dwg
- tip-14_mimari.dwg

Gerekçe (oturum notları): tip-14 ve bungalov-mumbai iki dairenin yansıması / anlaşılmaz plan; HouseProject11 ve 1148
kapı geometrisi yok; 183 anlamsız çizim. Tek dosyaya özgü durumlar HITL_QUESTIONS'a soru adayı olarak yazıldı.

## Ağır dosyalar (tier: hard adayı)

triage `heavy`: modelspace ≥ 250k entity ya da blok içi ≥ 200k entity. run_baseline bu dosyalara `--heavy-timeout`
(900 s) uygular. GT üretildiğinde `meta.tier: hard` yazılmalı; evaluate raporunda Tier sütunu vardır.

- 132_SÜMBÜLTEPE_20.01.2026
- 553_3_MİMARİ_18.01.2025
- 554_1_MİMARİ_09.02.2026
- 6249_MİMARİ_11.12.2025
- AVİDA_PLAN

AVİDA_PLAN: 24 294 blok tanımı / 582 k blok içi entity (Revit tarzı export); DXF tek okuma sonrası 63 s (önce 547 s).
AVİDA için henüz GT yok; GT yazıldığında `tier: hard`.

## Sayısal-özet GT adayı ve review örneği: detayli-villa-uygulama-projesi-dwg

İngilizce altlık (Arkipedia), upm 4528 (inç ölçekli), profilsiz (family unknown). swing.max_dist metreye
geçince 35 kapının 21'inde oda ataması değişti (SUBMASTER BEDROOM ↔ BALCONY); GT olmadığı için doğrulanamadı.
Karar (2026-09-04): sayısal-özet GT adayı (oda/kapı/pencere sayıları) ve Adım 7 HITL review modunun ilk örneği.

## Birim kestirimi aykırı dosyalar (`unit_suspect` issue adayları)

upm standart değerlerin (1, 10, 100, 1000 birim/m) ±%25 dışında; çoğu etiket-mesafesi tahmini (kapı yayı
kalibrasyonu tutmadı). Validator bunlara `unit_suspect` issue üretir (HITL sorusu: çizim birimi ne?).

| Dosya | upm | Kaynak |
|---|---:|---|
| detayli-apartman-yup-projesi-2 | 2.9 | labels |
| 386_8_MİMARİ_19.08.2026 | 21.4 | labels |
| 560_8_MİMARİ_20.02.2026 | 21.9 | labels |
| ZA_EVİ_RUHSAT_PROJESİ_11 | 25.0 | labels |
| 541_3_MİMARİ_PROJE_25.03.25 | 41.0 | labels |
| 553_3_MİMARİ_18.01.2025 | 41.7 | labels |
| 541_5_mimari_proje_06.05.25 | 42.3 | labels |
| 554_1_MİMARİ_09.02.2026 | 43.6 | labels |
| mimarlik-evi-atolyesi-projesi | 44.1 | labels |
| 519_ADA_6_PARSEL_26082026 | 67.0 | labels |
| 132_SÜMBÜLTEPE_20.01.2026 | 181.5 | doors |
| detayli-villa-uygulama-projesi-dwg | 4528.2 | doors |

## fam00 (aile 0) GT öncesi kapı/ölçek notu (2026-09-05)

Kapı-adlı blok yok, kapılar standalone yay; geometri cm. Etiket-mesafesi upm'i (21–44) yanlıştı → kat kümeleri
parçalanıyordu (DECISIONS (h)). Kalibrasyon sağlamlığı (2026-09-05) sonrası: 541_3 upm 100 (prior), 29 oda / 23 kapı;
536_1 upm 76 (doors, unit_suspect); 386_8 upm 103 (doors), 7 oda / 8 kapı. GT bu koşunun katı üzerinde çıkarılabilir;
upm'i 'prior' olan dosyalarda GT'ye units_per_meter elle yazılmalı (unit_suspect sorusu).

## Aileler ve kaynak profilleri

Profil anahtarı triage ailesi (`source_profiles/fam<NN>.yaml`, NN = ilk numaralandırmadaki aile indeksi; aile 4+5 → fam04).
Yeni triage koşusunda aile indeksleri kayabilir; eşleşme parmak izi → yapısal ad → Jaccard sırasıyla yapılır, indeks kullanılmaz.

| Triage aile (bu koşu) | ADAY dosya | Profil | Örnek |
|---:|---:|---|---|
| 0 | 10 | fam00 | 132_SÜMBÜLTEPE_20.01.2026, 386_8_MİMARİ_19.08.2026, 536_1_Mimari_12.05.2026 |
| 1 | 7 | fam01, — | tip-1_mimari, tip-2_mimari, tip-3_mimari |
| 2 | 6 | fam02 | 110-11822.10.2024SON, 127-26-NACİZAĞLI-22.01.2025KLİMA, 1481-826.05.2023 |
| 3 | 5 | — | tip-11_mimari, tip-12_mimari, tip-13_mimari |
| 5 | 4 | fam04 | 211_ADA_6_PARSEL_HACIRAHMANLI_06062023_1, 290_ADA_10_PARSEL_KOLDERE_21062023, 505_PARSEL_KARAKOCA_FATİH_17072023 |
| 6 | 3 | fam06 | hafif_celik_tip_koy_konutu_100_m2_mimari, hafif_celik_tip_koy_konutu_70_m2_mimari, hafif_celik_tip_koy_konutu_90_m2_mimari |
| 8 | 1 | — | 4-tip-villa-yapi-uygulama-projesi-dwg |
| 9 | 1 | fam09 | 519_ADA_6_PARSEL_26082026 |
| 10 | 1 | fam10 | 536_2_Mimari__16.06.2026 |
| 11 | 1 | fam11 | AVİDA_PLAN |
| 15 | 1 | fam15 | MURADİYE_6161_PARSEL_TADİLAT |
| 16 | 1 | fam16 | ZA_EVİ_RUHSAT_PROJESİ_11 |
| 20 | 1 | — | detayli-apartman-yup-projesi-2 |
| 21 | 1 | — | detayli-villa-uygulama-projesi-dwg |
| 23 | 1 | — | mimarlik-evi-atolyesi-projesi |
| 25 | 1 | — | modern-apartman-projesi-dwg |
| 29 | 1 | — | tip-10_mimari |
| 30 | 1 | fam30 | tip-7_mimari |
| 31 | 1 | fam31 | tip-8_mimari |
| 33 | 1 | fam04 | input-2-clean |

## Ground truth (`data/ground_truth/`)

- KAYAPINAR_2892_ADA_8_PARSEL_KAYAPINAR_23.08.2023
- hafif_celik_tip_koy_konutu_70_m2_mimari
- input-2-clean
- tip-1_mimari
- tip-2_mimari
- tip-4_mimari
- tip-6_mimari

Etiketleme aracı `annotate.py` (tarayıcı). Kapı GT'sine `rooms: [a, b]` eklenmesi planlı (REFACTOR_PLAN).
