# Perception durumu — v0.1 (2026-09-16, etiket `perception-v0.1`, commit 123ffa1)

Bu belge perception katmanının donmuş halini özetler: ne ölçüyoruz, ne kadar iyi, nerede açık, HITL ne kadar yük bırakıyor
ve perception'a ne zaman geri dönülür. Ayrıntılı tarihçe `EVAL_HISTORY.md`, kararlar `DECISIONS.md`, açık backlog
`REFACTOR_PLAN.md` "Perception v0.2 adayları".

## 1. Ölçüm tabanı

- Veri seti: 55 ADAY dosya (40 eski kaynak + 15 src02), fam00 (ArchiCAD, 10 dosya) dışlandı (ofis izni bekleniyor).
- GT: 11 tam geometrik GT (`data/ground_truth/`, GT_GUIDE.md şeması). Holdout: tip-6 ve src02-09 (kör etiketlendi); ayrıca
  src02-03/06/13 holdout ama GT'siz. Eşik/ağırlık ayarı holdout'a bakılarak yapılmadı; holdout kapısı "düşüş varsa parça girmez".
- Eval: `python3 experiments/run_baseline.py && python3 evaluate.py` (tazelik kapısı: kod hash + damga). Ölçüm kuralları
  `config/eval.yaml` (küçük şaft ≤ 1 m² oda F1 dışı; kapsama örtüşme 0,3).

## 2. 11 GT sonucu (koşu 2026-09-15)

| Varlık | TP / FP / FN | Precision | Recall | F1 | Ek |
|---|---|---:|---:|---:|---|
| rooms | 189 / 20 / 25 | 0,904 | 0,883 | **0,894** | IoU 0,886; ad doğruluğu (etiketli) 0,972 (n=177) |
| doors | 137 / 2 / 54 | 0,986 | 0,717 | **0,830** | konum hatası 0,005 m; bağlantı 0,866 |
| windows | 137 / 85 / 15 | 0,617 | 0,901 | **0,733** | çıktı eşiği 0,3 (thin_lines candidate) |
| shaft (≤ 1 m², F1 dışı) | 0 / – / 3 | | 0,000 | | KAYAPINAR, tip-1, tip-2 |

Aile bazında:

| Grup / aile | Dosya | Oda F1 | Oda IoU | Kapı F1 | Bağlantı | Pencere F1 |
|---|---:|---:|---:|---:|---:|---:|
| ABM (fam02, fam04) | 4 | 0,883 | 0,839 | 0,762 | 0,792 | 0,682 |
| fam02 (src02-09, src02-12) | 2 | 0,912 | 0,858 | 0,712 | 0,626 | 0,576 |
| fam04 (KAYAPINAR, input-2) | 2 | 0,778 | 0,821 | 0,971 | 0,959 | 0,923 |
| tip (fam01) | 4 | 0,965 | 0,937 | 0,946 | 0,852 | 0,901 |
| diğer (fam06 hafif_celik, fam10 src02-02/07) | 3 | 0,857 | 0,882 | 0,880 | 0,983 | 0,673 |
| **toplam** | 11 | 0,894 | 0,886 | 0,830 | 0,866 | 0,733 |

Holdout / geliştirme:

| Küme | Dosya | Oda F1 | Oda IoU | Kapı F1 | Bağlantı | Pencere F1 |
|---|---:|---:|---:|---:|---:|---:|
| holdout (src02-09, tip-6) | 2 | 0,873 | 0,858 | 0,706 | 0,611 | 0,700 |
| geliştirme | 9 | 0,897 | 0,893 | 0,845 | 0,923 | 0,737 |

Dosya bazında en zayıflar: KAYAPINAR oda 0,684 (tefriş çevritleri banyoları bölüyor); src02-09 (holdout) kapı 0,400 ve bağlantı
0,333 (kapı blokları/yaysız kapılar); src02-02 pencere 0,0 (6 aday, hepsi sahte); hafif_celik pencere 0,267.

Kaynağa göre doğruluk: oda flood:exclusive 0,94 (n=143), area+flood 1,00 (39), graph adayı 0,60 (20); kapı block 0,98 (130),
arc 1,00 (9); pencere layer 0,79 (61), block_keyword 0,72 (71), block_geometry 0,42 (90).

## 3. Kalibrasyon tablosu (güven dilimi → eşleşme oranı)

| Varlık | 0–0,5 | 0,5–0,7 | 0,7–0,9 | 0,9–1 |
|---|---|---|---|---|
| rooms | 0,62 (n=21) | 0,25 (n=4) | 0,86 (n=51) | 0,98 (n=133) |
| doors | — | — | 0,99 (n=139) | — |
| windows | 0,42 (n=90) | 0,72 (n=71) | 0,79 (n=61) | — |

Pencere monoton (ağırlık turu 4). Oda 0,5–0,7 dilimi (alias_merge/voronoi, n=4) tersine; sayı az, ağırlık turu sonrası.
Kapı tek dilimde: block/arc kaynakları ayrışmıyor, kalibrasyon yapılmadı (recall sorunu precision değil).

## 4. Kalan FN/FP kökleri (25 FN, 20 FP; DECISIONS 2026-09-15 (6))

| Kök neden | FN | FP | Not |
|---|---:|---:|---|
| Hol birleşmiş / sızmış (tahmin GT'den büyük) | 6 | 1 | issue üretiliyor (area_mismatch/room_no_door), geometri düzelmiyor |
| Dış mahal (balkon/veranda/sahanlık): daralmış, birleşmiş ya da hiç yok | 6 | 1 | 2'si etiketsiz + zarf dışı → tahmin yok; (10) denendi, etkisiz |
| Hatch-only çekirdek (asansör/merdiven duvarı yalnız tarama) | 5 | – | aday üretilemiyor; (3) ve (9) denendi, girmedi |
| Yalnız etiketsiz aday, IoU < 0,5 | 5 | 8 | unlabeled_region soruyor; cevap gelirse çözülür |
| Parçalı hol (tahmin GT'den küçük) | 3 | 10 | tefriş/ince çizgi bölmesi; (8) denendi, girmedi |
| Küçük şaft ≤ 1 m² | (3, F1 dışı) | – | GT_GUIDE kuralı; algılama alt sınırı 1 m² |

Kapı FN 54: src02 ailesinde yaysız/bloklu kapılar (src02-12 kapı 0,748, src02-09 0,400): `unknown_block` sinyali yok (v0.2).
Pencere FP 85: block_geometry kaynağı %42 doğru; dosya başına tek `ambiguous_opening` sorusu 26'sını kapsıyor.

## 5. Bilinen açıklar

- Kapı: blok adı/katman oyu kaynaklı sinyal yok (block_class yalnız geometri); sürgülü kapılar yalnız blok eşleşmesiyle.
- Pencere: block_geometry adayı ayrıştırılamıyor (blok adı/boyut/duvar hizası sinyali yok).
- Oda: hatch-only duvarlar (tarama sınırı kenar sayılmıyor); tefriş çevritleri (küvet/tezgâh) odayı bölüyor; kapısız açık
  geçiş raster tarafında yalnız mühürle kapanıyor; etiketsiz dış mahaller zarf dışında.
- Katman sınıflama: profil yalnız 12 ailede; içerik istatistiği kademesi (stats_class) zayıf; unknown_layer sayımı dosya geneli
  (seçilen kat kutusuyla sınırlı değil).
- Birim: label/kapı kestirimi src02-07'de 115 (gerçek 100) — profil birimi yalnız hipotez öncülü.
- fam00 (ArchiCAD, 10 dosya) ölçülemiyor; kapı/pencere bloğu yok, çizgisel.
- VLM/LLM second opinion (Adım 8) yok; belirsizlik HITL'e akıyor.

## 6. HITL kalıcı yükü

11 GT: 191 issue / 209 oda, medyan **0,83 issue/oda** (hedef ≤ 0,5: 0/11 dosya). Dağılım: room_no_door 39, area_mismatch 37,
window_missing 35, door_side_ambiguous 31, unlabeled_region 20, unknown_layer 17, conflicting_layer 7, ambiguous_opening 6,
room_merged 3, open_room 2. Kapsama (hatalı varlık → issue) 91/219 = 0,42; oda FP 19/20, oda FN 15/25, kapı FN 15/54,
pencere FP 26/85.
Aktarılabilir cevaplar (profil: katman sınıfı, birim) tek seferlik; geometri cevapları (C turunda 25/28) dosyaya özgü —
kalıcı yük ≈ 0,8 issue/oda. Yükü düşürmenin yolu profil değil, algılama (yukarıdaki açıklar).

## 7. Perception'a dönüş tetiği

Perception kodu donduruldu (v0.1). Yeniden açılır, ancak şunlardan biri olursa:
1. **Yeni kaynak/GT ölçümü düşerse:** yeni bir ofis ailesinin GT'sinde oda F1 < 0,80 ya da kapı F1 < 0,70 (11 GT tabanının
   altında bariz düşüş) — önce profil (katman/birim cevabı), o yetmezse algılama.
2. **Elektrik motoru bir IR alanını yanlış bulursa:** tüketici tarafında sistematik hata (örn. kapı yönü, oda tipi) ≥ 3 dosyada
   tekrar ediyor ve HITL cevabı gerektirmeden çözülebilecek bir sinyal eksikliği → perception'a madde.
3. **HITL yükü:** bir ailede issue/oda medyanı > 1,5 ya da aynı issue tipi cevabı 3+ dosyada aynıysa (profile aktarılamayan
   ama tekrar eden) → o tipin tetiğine sinyal.
4. **Holdout:** yeni GT (src02-13/06/08) geldiğinde holdout oda/kapı F1 geliştirme kümesinin 0,10'dan fazla altındaysa
   (aşırı uyum işareti) → ağırlık turunun ilgili parçası geri alınır.
Bunlar dışında perception'a "iyileştirme" için dönülmez; backlog `REFACTOR_PLAN.md` "Perception v0.2 adayları".
