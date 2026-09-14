# Eval geçmişi

Her perception commit'i için bir satır. Kaynak: `python3 experiments/run_baseline.py && python3 evaluate.py`
(GT: `data/ground_truth/*.json`, mikro ortalama). "Dosya" = GT dosya sayısı / koşulan aday sayısı.

Birimler: F1 ve IoU 0–1. **Kapı konum = metre**, yalnızca GT ile eşleşen kapılarda (eşleşme
eşiği 0.5 m) menteşe mesafesinin ortalaması; kaçırılan/sahte kapılar bu sütuna girmez, F1'de
görünür. Kapı bağlantı = eşleşen kapılarda "açıldığı oda" doğruluğu (0–1).

| Tarih | Commit | Adım | Oda F1 | Oda IoU | Kapı F1 | Kapı konum (m) | Kapı bağlantı | Pencere F1 | Dosya | Not |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | 35c9405 | baseline (refactor öncesi) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | 73 test; ZA_EVİ koşuda hatalı (bozuk dosya) |
| 2026-09-04 | 6f69cf7 | adım 0 (temizlik) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı |
| 2026-09-04 | db22a0a | adım 1 (perception/elektrik ayrımı) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı; JSON'da appliance_pts alanı kalktı |
| 2026-09-04 | 3f119ad | adım 2 (IR v2: güven + kanıt) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı; v2 JSON, kalibrasyon tablosu eklendi |
| 2026-09-04 | 7a8c3a9 | thin_lines güveni 0.3 | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | F1 aynı (eval güven eşiği uygulamıyor); pencere kalibrasyonu monoton: 0–0.5 dilimi 0.00 (n=9) |
| 2026-09-04 | bb6ad0b | adım 3 (geometry.py → modüller) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı; 52/53 ok (AVİDA_PLAN 420 s zaman aşımı, baseline'da da), 82 test |
| 2026-09-04 | be06f94 | adım 4 (tek parse yolu, vocab.py, select_plan; tazelik kapısı 8c506c2) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı (dosya bazında da); 52/53 ok (AVİDA zaman aşımı, değişmedi); evaluate tazelik kapısından geçti; triage 68/68 verdict aynı; 84 test |
| 2026-09-04 | 7147322 | DXF tek okuma + triage heavy bayrağı + GT tier sütunu | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | GT-7 birebir aynı (13 dosyalık --only koşusu, taze); AVİDA_PLAN 547 s → 63 s (12 readfile → 1); heavy: ≥250k entity ya da ≥200k blok entity, heavy-timeout 900 s |
| 2026-09-04 | b188ef2 | adım 5: kaynak profilleri + sözlük kademesi; elektrik tespiti (ADAY 53→49) | 0.886 | 0.871 | 0.937 | 0.009 | 0.887 | 0.817 | 7 / 49 | FARK VAR — karar bekliyor. tip-1 oda F1 1.0→0.842 (A_ANNO/A_STAIR katmanları 'text/stair' sınıfıyla duvar taramasından çıkınca ANTRE+HOL birleşti, DEPO sızdı), tip-4 oda F1 0.957→1.0 (aynı mekanizma, ANTRE doğru birleşti), tip-1/tip-6 kapı F1 düştü (A_DOOR_* INSERT 'kesin kapı' yolu: +3/+1 aday, menteşe kayması 0→0.021 m), tip-6 pencere 0.75→0.828 (A_GLZ_GLS pencere kaynağı). Ablasyon ve kapılı varyant DECISIONS'ta. 49/49 ok, AVİDA 73 s |
| 2026-09-04 | 3de225e | adım 5 kapılı varyant: profil güveni isteyen hariç tutma + kesin-kapı; sözlük ekleyici tüketicilere; unions yan dosyası; results.json temizliği | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 49 | oda/kapı F1 ve bağlantı baseline ile aynı; pencere 0.802→0.817 (tip-6: A_ANNO_* yazı çizgileri thin_lines adayından dışlandı, 3 sahte gitti); IoU dosya bazında ±0.02 (wall sınıfı A_WALL_*/DUVAR bariyer+snap hedefi: tip-1 0.954→0.935, tip-4 0.959→0.937, tip-2 0.885→0.904, tip-6 0.899→0.912, hafif 0.856→0.845); 49/49 ok, AVİDA 68 s. **Kabul (kullanıcı, 2026-09-04): IoU −0.003 bilinçli trade-off** — ofis katman adları koddan çıktı, pencere F1 +0.015, oda/kapı F1 aynı; IoU kayması wall sınıfı bariyerinin snap kenarlarını oynatmasından, Adım 6'da parallel_pair sinyaliyle yeniden ölçülecek |

### Aile bazında (adım 5 kapılı, GT-7)

| Grup / aile | Dosya | Oda F1 | Oda IoU | Kapı F1 | Bağlantı | Pencere F1 |
|---|---:|---:|---:|---:|---:|---:|
| ABM aileleri (fam00, fam02, fam04) — yalnız fam04 GT'li | 2 | 0.727 | 0.831 | 0.971 | 0.959 | 0.923 |
| tip aileleri (fam01, fam03) — yalnız fam01 GT'li | 4 | 0.976 | 0.922 | 0.946 | 0.852 | 0.845 |
| diğer (fam06 hafif çelik) | 1 | 1.000 | 0.845 | 0.923 | 1.0 | 0.267 |
| toplam | 7 | 0.901 | 0.885 | 0.951 | 0.904 | 0.817 |

fam00 (10 dosya) ve fam02 (6 dosya) GT'siz → veri seti görevi: fam00'dan 2–3 dosyaya GT önceliği.
| 2026-09-04 | 4c14649 | adım 6 iskeleti: config/thresholds+weights, scoring, signals/ (kapı yolu sinyallere), FileParams koşu parametreleri | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 49 | adım 5 ile BİREBİR aynı: 49 dosyada 413 kapının menteşe/güven/kaynak/oda, tüm oda/pencere/duvar sayıları eşit (varlık bazında karşılaştırıldı); eval raporu satır satır aynı; 99 test |
| 2026-09-04 | 1af656d | adım 6: duvar sinyalleri (parallel_pair, layer_class oyu, thickness_mode w=0, graph_connectivity iskelet), çelişki kuralı, holdout.yaml + calibrate iskeleti | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 49 | GT-7 (13 dosyalık --only koşusu) adım 6 ile birebir aynı; 13 dosyada 5807 duvar (a,b,güven,kaynak) + oda/kapı/pencere eşit; duvar güveni tabloya eşit; kalınlık modları FileParams'ta; çelişki bayrağı 2139 duvar (geometri çift der, katman başka sınıf der — HITL #22), 0 kapı; holdout satırı: tip-6 |
| 2026-09-04 | 9da5e5d | swing.max_dist 460 birim → 4,6 m × upm (ayrı commit) | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 49 | GT-7 birebir aynı (7 GT dosyasının upm'i 95-100 → 460 birim ≈ 4,6 m zaten). Tam sette fark tek dosyada: detayli-villa (upm 4528, GT yok) 35 kapının 21'inde oda ataması değişti — eski eşik 460 birim = 0,10 m idi, mesafe cezası cos'u eziyordu (SUBMASTER BEDROOM↔BALCONY takasları); yeni eşik 4,6 m. Diğer 48 dosyada menteşe ve oda ataması aynı |
| 2026-09-04 | 96fdcfe | oda/pencere güvenleri scoring'e (tablo birebir) + adım 7 validator (7 issue tipi), ValidationReport IR'da, hitl/cli.py, learning/log.py, evaluate issue tablosu | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 49 | eval ve 49 dosyada oda/açıklık/duvar (güven dahil) birebir aynı. Issue yükü 49 dosya: toplam 2062 — unknown_layer 758, ambiguous_opening 368, area_mismatch 336, room_no_door 317, open_room 161, conflicting_layer 110, unit_suspect 12; dosya başına medyan 20, min 8, max 335 (536_1); hedef ≤5'i tutan dosya 0/49. GT-7: 110 issue (KAYAPINAR 35, tip-1 18). Ana neden: unknown_layer — İngilizce büyük harfli katman adları Türkçe fold ile (I→ı) sözlüğe uymuyor (WINDOW→wındow); ayrı düzeltme commit'i |
| 2026-09-04 | 48a92e7 | düzeltme: Türkçe katlama İngilizce büyük I'yı bozuyordu (vocab.folds/has_word) | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT-7 birebir aynı (Türkçe altlıklar). Triage: deniz-evi-projesi-dwg-2 ZAYIF→ADAY (KITCHEN 5 etiket), ADAY 49→50; 4-tip-villa +12 oda metni (KITCHEN/LIVING). Tam sette değişen 5 dosya: 4-tip-villa oda 5→8, açıklık 0→2, duvar 353→534 (WINDOW/STAIR/DIM katmanları sınıflandı); detayli-villa açıklık 38→74, duvar 348→517 (WINDOW pencere kaynağı, DIM/AXIS hariç); tip-13 oda 10→11 (KİLER etiketi 'kiler' ile); tip-7 açıklık 20→19. 42 dosyada +149 katman sınıfı. Issue yükü 2062→2071 (unknown_layer 758→748: kalanlar 家具/0/LAYER3/S_SURFACE gibi sözlüksüz adlar) |
| 2026-09-05 | 937c4c5 | adım 7 issue politikası (a–g): kapsama metriği, içerik-istatistiği katman kademesi, toplu ambiguous, area_convention, muafiyet, bütçe, HITL yeniden koşu | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT-7 birebir aynı; tam sette yalnız 553_3 pencere 140→138 (stats kademesi text/ignore katmanları ince-çizgi adayından dışladı). Issue yükü 50 dosya: 2071 → 846 (unknown_layer 748→145, ambiguous 370→12, area 338→165, room_no_door 321→240, open_room 160→140, conflicting 122→132, unit 12); dosya başına medyan 23→10, ≤10 olan 26/50, heavy 5 dosya bütçe 10. GT-7: 110→67 issue; kapsama 20/57 (0.35) → 15/57 (0.26): room_fp 4/7, room_fn 2/7, door_fn 4/4, door_fp 0/2, window_fp 5/16, window_fn 0/14, ad 0/1, bağlantı 0/6 |
| 2026-09-05 | 5fdef54 | yeni issue tipleri: window_missing, door_side_ambiguous; area_mismatch mutlak kural (<0.5, >2); JSON→IR yükleyici | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | validator; tahmin değişmez. Kapsama GT-7 (tam koşuda): 15/57 → 26/57 (0.46): window_fn 0→7/14, door_connect 0→4/6; kalan açık room_fn 2/7, window_fp 5/16, door_fp 0/2, room_name 0/1. Hedef ≥0.6 tutmadı (aday: room_merged tipi). GT-7 issue 67 → 94 |
| 2026-09-05 | d4bf947 | kalibrasyon sağlamlığı: kapı kanıtı yoksa standart öncüllerle (100/1000/1/10) yeniden kümeleme, hipotez = toplam yay; etiket kestirimi güveni; units_confidence; unit_suspect güven kuralı; unit_tol 0.15 | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT-7 birebir aynı. fam00: 541_3 upm 41→100 (prior) 29 oda/23 kapı; 541_5 42→100, 22/20; 554_1 44→100, 22/20; 560_8 22→100, 14/15; 386_8 21→103 (doors) 7/8; 553_3 41.7 (etiket, hipotez yolu çalışmadı — aday); 536_1 76 (doors, unit_suspect). Diğer: 519_ADA 67→100 (82 oda), ZA_EVİ 25→94, mimarlik-evi 44→100. Bütçe 50 dosya: 1051 issue (area 210, open_room 179, room_no_door 165, unknown 143, conflicting 137, door_side 100, window_missing 90, unit 14, ambiguous 13); medyan 12; typical (45) medyan 13, ≤10: 12/45 (%27); heavy 5 dosya hepsi 10. Hedef (typical medyan ≤8, ≤10) tutmadı; en yüklü 536_1 157, 519_ADA 124, 536_2 67 |
| 2026-09-05 | ca027ad | room_merged (son issue tipi); bütçe ölçütü issue/oda (üretim sınırı yok, CLI ilk 10 + --offset); hipotez tetiği: etiket kümelerinde kapı kanıtı < 10 yay, etiket öncülü de aday | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT-7 birebir aynı. Kapsama 26/57 (0.46) değişmedi: GT-7 tahminlerinde alias_merge odası yok (tip-1 HOL kapılı varyantla geri gelmişti); room_merged 50 dosyada 11 issue. Kalan açıklar room_fn 5 (KAYAPINAR bölünmüş Mutfak/Banyo, tip-6 KAT HOLÜ→MERDİVEN), window_fp 11 (block_keyword/layer güveni fazla — ağırlık turu), door_fp 2, ad 1. Issue/oda: GT-7 medyan 1.22, ≤0.5: 0/7; 50 dosya medyan 1.39, typical ≤0.5: 0/45. 553_3 hipotez yolu: upm 41.7→100 (prior), 14→29 oda, 23 kapı. 560_5 106→100 (8→36 oda); mimarlik-evi 100→44 (etiket öncülü hipotez adayı olarak daha çok yay). Toplam 1258 issue |
| 2026-09-05 | 71a52a9 | **src02, dokunulmamış** (15 dosya, anonim; GT yok, eval metrikleri hesaplanamaz) | — | — | — | — | — | — | 0 / 15 | 15/15 ok (src02-03 heavy 73 s). upm: 13 doors (99,8–115,2), 1 prior (src02-06, güven 0,4), 1 labels (src02-13: 0 kapı). Oda/dosya medyan 24, kapı 14, pencere 34 (mevcut kaynak 10,5 / 8,5 / 12). Issue/oda medyan 1,46 (mevcut 1,39); issue/dosya medyan 35; tip başına ort: area_mismatch 14,0, room_no_door 7,0, door_side_ambiguous 5,7, window_missing 4,6, unknown_layer 2,9, open_room 2,3, conflicting_layer 2,1, room_merged 0,7, unit_suspect 0,3 (4 dosya). Güven: oda %84 0,7–0,9 / %10 <0,5; kapı %100 0,7–0,9; pencere %88 / %12 <0,5. Profil eşleşmesi yapısal: fam06 10, fam02 3, fam00 2 (tek anahtarlı profil kusuru, DECISIONS). Holdout: src02-03/06/09/13; consistency_pair src02-10 |
| 2026-09-05 | 87693ed | A: conflicting_layer yalnız text/dim/furniture/ignore/unknown oylarında; yapısal profil eşleşmesi ≥3 ortak ad | 0.901 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT-7 eval, aile tablosu ve kapsama (26/57) birebir aynı (13 dosyalık --only koşusu). GT-7 issue 94→84 (conflicting_layer 16→6); issue/oda medyan 1,22→1,11. src02 yeniden koşu: 577 issue (conflicting_layer 32→8, 2,1→0,5/dosya), issue/oda medyan 1,46→1,39; src02-07 39→34. Yapısal eşleşme: fam06 (1 anahtar) artık almıyor ama 3 anahtarlı fam10/fam11/fam16 alıyor (8+1+1 dosya) — kusur sürüyor, DECISIONS |
| 2026-09-05 | a187050 | **src02-07 GT** (assisted; ilk src02 ölçümü, evaluate --pred output/src02) | 0.717 | 0.816 | 0.952 | 0.006 | 0.950 | 0.774 | 1 / 15 | GT: 29 oda (4 daire × 6 + kat holü U, merdiven, asansör, 2 aydınlık), 22 kapı (2 sürgülü, type/subtype), 36 pencere. Oda F1 0.717: tahmin 24 odada merdiven/asansör/aydınlık ve 4. balkon yok, kat holü 2.7 m² şerit; kapı F1 0.952 bağlantı 0.95; pencere F1 0.774 (tahmin 57 → GT 36: 15 sahte + kapı kasaları). Kapsama 11/39 (0.28). Issue 34, 1.42/oda |
| 2026-09-06 | d4690ec | **src02-02 GT** (assisted; giriş katı; evaluate --pred output/src02, koşu a187050) | 0.667 | 1.0 | 0.700 | 0.003 | 1.0 | 0.0 | 2 / 15 | GT: 10 oda (7 daire + kat holü, merdiven, asansör; kind 6 daire içi/3 ortak/1 dış), 13 kapı (8 menteşeli, 5 sürgülü 1.6–2.0 m, 1 asansör), 1 pencere (banyo 60x60). Tahmin: 8 oda (merdiven/asansör yok, kat holü ve banyo çok küçük → 6 TP), 7 kapı hepsi doğru (sürgülü+asansör yok), 6 pencere hepsi kapı (F1 0.0). src02 toplam (2 GT): oda 0.704/IoU 0.908, kapı 0.871/0.005 m/0.975, pencere 0.720. Issue 8, 1.00/oda. Kör sayım eksik ham PNG ile yapıldı (blok açma hatası, DECISIONS 2026-09-05) |
| 2026-09-08 | 126d98f | **src02-12 GT** (assisted; 8 daire, evaluate --pred output/src02, koşu a187050) | 0.577 | 0.912 | 0.748 | 0.0 | 0.918 | 0.582 | 3 / 15 | GT: 83 oda (56 daire içi, 15 dış, 10 ortak, 2 teknik), 82 kapı (49 menteşeli, 29 sürgülü, 4 asansör), 32 pencere. Tahmin 73 oda/49 kapı/78 pencere: hol-banyo-e.banyo-balkon poligonları bozuk (kullanıcı 35 odayı yeniden çizdi), çekirdek (kat holü, 3 merdiven, 4 asansör) yok; menteşeli kapılar hepsi doğru, sürgülü/e.banyo/asansör kapıları yok; pencerelerin çoğu kapı ya da boş. src02 toplam (3 GT): oda 0.617/IoU 0.909, kapı 0.788/0.003 m/0.956, pencere 0.648; kapsama 74/207 (0.36). Issue 78, 1.07/oda |
| 2026-09-08 | 2c70338 | **src02-09 GT** (blind, **holdout**; çatı katı; evaluate --pred output/src02, koşu a187050) | 0.759 | 0.818 | 0.400 | 0.0 | 0.333 | 0.286 | 4 / 15 | GT: 16 oda (9 daire içi, 4 ortak, 2 teknik, 3 dış), 12 kapı (8 menteşeli: 3 yay + 5 Single_Door_12 bloğu; 3 sürgülü '210 SK'; 1 asansör), 2 pencere (60x60). Tahmin 13 oda/3 kapı/12 pencere: oda TP 11 (kat holü 0.22, iki HOL 0.47/0.35 IoU ile kaçtı; su deposu ve makine dairesi etiketsiz → yok; 2 FP: bölünmüş KAT HOLÜ parçası, 'gemici merdiveni' notu oda sayılmış), 3 yay kapısı konumu tam (0.0 m) ama oda ataması 1/3 doğru; blok kapıların (5 menteşeli, 3 sürgülü, asansör) hiçbiri yok; 12 'pencere'nin 10'u sahte (kapı kasası/blok). Holdout satırı ilk kez dolu. src02 toplam (4 GT): oda 0.633/IoU 0.886, kapı 0.760/0.002 m/0.8, pencere 0.625; kapsama 87/238 (0.37); geliştirme (3 GT) 0.617/0.788/0.648. Issue 19, 1.46/oda. Revizyon çifti: src02-10 tahmini farklı katı (giriş katı: WC/APT. GİRİŞ HOLÜ) seçmiş → kat düzeyinde karşılaştırılamaz, DATASET |
| 2026-09-08 | 738f448 | **GT-7 revizyonu** (kind alanı + 8 eksik mahal; tam 50 dosya koşusu, kod e19455b4fc03 = src02 koşusuyla aynı) | 0.853 | 0.885 | 0.951 | 0.006 | 0.904 | 0.817 | 7 / 50 | GT değişti, kod değişmedi: kapı ve pencere satırları a187050 ile birebir aynı (0.951/0.006/0.904/0.817), oda TP 64 aynı; oda FN 7→15 = eklenen 8 mahal (KAYAPINAR ASANSÖR/MERDİVEN/KAT HOLÜ/HAVALANDIRMA ŞAFTI, tip-1 ŞAFT, tip-2 ŞAFT+GİRİŞ VERANDA, hafif_celik GİRİŞ SAHANLIĞI) tahminde yok → oda F1 0.901→0.853 (bilinçli: GT artık çekirdek/dış mahalleri kapsıyor). Dosya bazında oda F1: KAYAPINAR 0.5 (14→18 oda, 4 FN + eski 2 bölünmüş), tip-2 0.9, hafif 0.933, tip-1 0.952, tip-4/tip-6 0.957, input-2 1.0. Holdout (tip-6) 0.957/0.947/0.828; geliştirme (6) 0.835/0.951/0.815. Kapsama 26/65 (0.40): room_fn 2/15 (etiketsiz mahaller issue üretmiyor — etiketsiz kapalı bölge sinyali adayı). Issue 84, issue/oda medyan 1.11, ≤0.5: 0/7. kind dağılımı 7 dosya: 64 daire içi, 5 ortak, 3 teknik, 7 dış |

### Adım 9 öncesi taban (2026-09-09, commit 24e86c0, kod e19455b4fc03; 11 GT dosyası, 55 dosyalık koşu)

Koşu seti: fam00 (10 dosya) `status: excluded` (dosya sorunu, 2026-09-09) → ADAY 40 eski kaynak + 15 src02 = 55; src02 artık ana
koşuda (`output/baseline`), ayrı src02 koşusu yok. GT: GT-7 revizyonu (6fcf5b8) + src02-02/07/09/12. Holdout: tip-6, src02-09.
**Blok-kapı değişikliği (src02-13 `unknown_block`) yapılmadı** — yalnız DECISIONS adayı (2026-09-05/06); bu tabanda kod aynı.

| Grup | Dosya | Oda F1 | Oda TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| ABM (fam04) | 2 | 0.667 | 16/6/10 | 0.831 | 0.971 | 0.923 | 12/22 (0.55) | 1.64 |
| tip (fam01) | 4 | 0.943 | 41/1/4 | 0.922 | 0.946 | 0.845 | 10/30 (0.33) | 1.02 |
| src02 aile A (fam10) | 2 | 0.704 | 25/7/14 | 0.908 | 0.871 | 0.720 | 15/58 (0.26) | 1.31 |
| src02 aile B (fam02) | 2 | 0.605 | 56/30/43 | 0.865 | 0.712 | 0.548 | 72/180 (0.40) | 1.13 |
| diğer (fam06) | 1 | 0.933 | 7/0/1 | 0.845 | 0.923 | 0.267 | 4/13 (0.31) | 0.71 |
| **geliştirme** | 9 | 0.695 | 123/42/66 | 0.890 | 0.845 | 0.713 | 99/264 (0.38) | 1.19 |
| **holdout** (src02-09, tip-6_mimari) | 2 | 0.846 | 22/2/6 | 0.865 | 0.706 | 0.651 | 14/39 (0.36) | 1.12 |
| **toplam** | 11 | 0.714 | 145/44/72 | 0.886 | 0.830 | 0.706 | 113/303 (0.37) | 1.18 |

Kapsama tip başına (kapsanan/toplam): room_fp 41/44, room_fn 37/72, door_fn 12/54, door_fp 0/2, window_fp 7/99, window_fn 7/15,
room_name 0/4, door_connect 9/13 → toplam 113/303 (0.37). Issue dağılımı (11 dosya, 223): area_mismatch 72, room_no_door 40,
window_missing 36, door_side_ambiguous 31, unknown_layer 27, conflicting_layer 8, room_merged 3, ambiguous_opening 3, open_room 2,
unit_suspect 1. Issue/oda medyan 1.11, typical ≤0.5: 0/11.

### Adım 9 — duvar grafından bağımsız oda tespiti (2026-09-09, ec8f616; 55 dosya, 11 GT)

| Grup | Dosya | Oda F1 | Oda TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| ABM (fam04) | 2 | 0.692 | 18/8/8 | 0.841 | 0.971 | 0.923 | 12/24 (0.50) | 2.23 |
| tip (fam01) | 4 | 0.943 | 41/1/4 | 0.922 | 0.946 | 0.845 | 12/30 (0.40) | 1.19 |
| src02 aile A (fam10) | 2 | 0.759 | 30/10/9 | 0.885 | 0.871 | 0.720 | 17/61 (0.28) | 1.57 |
| src02 aile B (fam02) | 2 | 0.657 | 69/42/30 | 0.855 | 0.712 | 0.548 | 73/193 (0.38) | 1.39 |
| diğer (fam06) | 1 | 0.933 | 7/0/1 | 0.845 | 0.923 | 0.267 | 5/13 (0.38) | 1.14 |
| **geliştirme** | 9 | 0.728 | 142/59/47 | 0.884 | 0.845 | 0.713 | 104/282 (0.37) | 1.50 |
| **holdout** (src02-09, tip-6_mimari) | 2 | 0.868 | 23/2/5 | 0.871 | 0.706 | 0.651 | 15/39 (0.38) | 1.24 |
| **toplam** | 11 | 0.745 | 165/61/52 | 0.881 | 0.830 | 0.706 | 119/321 (0.37) | 1.47 |

**Öncesi → sonrası (11 GT):** oda F1 0,714 → **0,745** (TP 145→165, FP 44→61, FN 72→52; recall 0,668→0,760, precision
0,767→0,730), oda IoU 0,886 → 0,881 (adayların poligonu kabaca), ad doğruluğu 0,967 → 0,894 (etiketsiz adaylar TP olunca ad boş).
**Kapı ve pencere birebir aynı** (137/2/54 ve 137/99/15; konum 0,005 m, bağlantı 0,866). Geliştirme 0,695 → 0,728; holdout
(tip-6, src02-09) 0,846 → 0,868. Kapsama 113/303 (0,37) → 119/321 (0,37): room_fn 37/72 → 36/52 (0,69), room_name 0/4 → 0/25
(yeni: adsız adaylar), room_fp 41/44 → 43/61. Issue 223 → 333: open_room 2 → 75 ("duvar grafında boşluk" notu, flood odası grafta
yüz bulamayınca), unlabeled_region 37 (yeni), diğerleri aynı; issue/oda medyan 1,11 → 1,33 (toplam 1,18 → 1,47).
**Uzlaşma (55 dosya):** 681 yüz; 418 mahal iki yöntemde, 370 yalnız flood-fill, 135 yalnız graf (aday). 11 GT: 122 / 71 / 37.
**Sorunlu dosyalar:** KAYAPINAR 4/14 eşleşme (bariyer katmanında olmayan duvar parçaları, 1 m boşluklar; F1 0,50→0,556),
input-2 0/8 (tek çizgili referans; 8 open_room notu, F1 1,0 korundu), src02-12 24 aday / 40 FP (parçalı oda poligonları,
F1 0,577→0,633), src02-07 15/24. Koşu süresi: AVİDA 74 s, src02-03 69 s; ilk denemede GEOS gönye tamponu detayli-villa/deniz-evi'nde
askıda kaldı (DECISIONS). Kabul ölçütü: recall ↑ ✓, F1 ↑ ✓, IoU −0,005 (adaylardan; bilinçli).

### Adım 9 düzeltmeleri — open_room eski semantiği, graph_match, ad/kind ölçümü (2026-09-12; 55 dosya, 11 GT)

| Varlık | TP/FP/FN | F1 | Ek |
|---|---|---:|---|
| rooms | 165/61/52 | 0.745 | IoU 0.881; ad doğruluğu (etiketli, n=144) 0.972; kind doğruluğu (etiketsiz) n=0 |
| doors | 137/2/54 | 0.830 | konum 0.005 m, bağlantı 0.866 |
| windows | 137/99/15 | 0.706 | |

Geometri ve F1 Adım 9 satırıyla **birebir aynı** (rooms/doors/windows, IoU, aile ve holdout tabloları: holdout 0.868 / 0.706 / 0.651,
geliştirme 0.728 / 0.845 / 0.713). Değişen yalnız issue'lar ve ad ölçümü:
- **open_room** 75 → 2 (graf boşluğu notu kaldırıldı; yalnız poligonu kapanmayan odalar). Issue toplamı 333 → **260**:
  area_mismatch 72, room_no_door 40, unlabeled_region 37, window_missing 36, door_side_ambiguous 31, unknown_layer 27,
  conflicting_layer 8, room_merged 3, ambiguous_opening 3, open_room 2, unit_suspect 1. Issue/oda medyan 1.33 → **1.11**
  (toplam 1.47 → 1.15); typical ≤0.5: 0/11. Dosya bazında: KAYAPINAR 1.72, tip-1 1.50, src02-09 1.43, src02-07 1.32,
  input-2 1.12, tip-2 1.11, src02-12 1.05, src02-02 1.00, tip-4 0.83, tip-6 0.73, hafif_celik 0.71.
- **Ad doğruluğu** artık yalnız etiketli tahminlerde ve n-ağırlıklı: 0.972 (n=144). Adım 9 satırındaki 0.894 dosya ortalamasıydı
  ve adsız adayları hata sayıyordu → kıyaslanmaz; Adım 9 öncesi 0.967 ile aynı tabanda. Etiketsiz adaylarda kind doğruluğu
  n=0 (tahmin kind vermiyor).
- **Kapsama** 119/321 → 112/300 (0.37): room_name 0/25 → 0/4 (yalnız etiketli), room_kind 0/0 (yeni), room_fp 43/61 → 42/61
  (bir FP'yi yalnız open_room graf notu işaret ediyordu), room_fn 36/52 → 35/52; kapı/pencere aynı.
- FP analizi (src02-12 15, src02-07 8; kod yok) ve KAYAPINAR/input-2 duvar boşlukları → DECISIONS 2026-09-12.

### FP kök nedeni — graf kenar sınıfları, aday örtüşme kapısı, ince çizgi birleştirme (2026-09-13; 55 dosya, 11 GT)

Tek commit: (1) polygonize kenar kümesi yalnız {wall, beam, column, chimney, railing}, pencere kapı gibi mühürlenir; sözlüğe
`railing` (korkuluk/railing/parapet); (2) aday yüz flood odalarıyla > 0,3 örtüşürse elenir (`candidate_max_overlap`);
(3) ince çizgiyle ayrılmış komşu yüzler (bileşen ≤ 1 etiket, kiriş çiftleri boşluk sayılmaz, korkuluk sert) birleştirilir.
Eşikler `thresholds.yaml graph.*`. Kabul: FP 61 → **52** ✓, FN 52 → **49** ✓ (artmadı), kapı/pencere birebir aynı ✓, IoU −0,001.

| Küme | Dosya | Oda F1 | TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda medyan |
|---|---:|---|---|---|---|---|---|---|
| geliştirme | 9 | 0.728 → 0.754 | 142/59/47 → 144/49/45 | 0.884 → 0.884 | 0.845 → 0.845 | 0.713 → 0.713 | 98/262 (0.37) → 96/250 (0.38) | 1.11 → 1.11 |
| holdout | 2 | 0.868 → 0.873 | 23/2/5 → 24/3/4 | 0.871 → 0.86 | 0.706 → 0.706 | 0.651 → 0.651 | 14/38 (0.37) → 14/38 (0.37) | 1.43 → 1.38 |
| toplam | 11 | 0.745 → 0.769 | 165/61/52 → 168/52/49 | 0.881 → 0.88 | 0.83 → 0.83 | 0.706 → 0.706 | 112/300 (0.37) → 110/288 (0.38) | 1.11 → 1.11 |

| Dosya | Küme | Oda TP/FP/FN önce → sonra | Oda F1 | Kapı F1 | Pencere F1 | Issue/oda | FN farkı |
|---|---|---|---|---|---|---|---|
| KAYAPINAR_2892_ADA_8_PARSEL_ | gel. | 10/8/8 → 11/10/7 | 0.556 → 0.564 | 1.0 → 1.0 | 1.0 → 1.0 | 1.72 → 1.62 |  −KAT HOLÜ |
| hafif_celik_tip_koy_konutu_7 | gel. | 7/0/1 → 7/0/1 | 0.933 → 0.933 | 0.923 → 0.923 | 0.267 → 0.267 | 0.71 → 0.71 |  |
| input-2-clean | gel. | 8/0/0 → 8/0/0 | 1.0 → 1.0 | 0.909 → 0.909 | 0.857 → 0.857 | 1.12 → 1.12 |  |
| src02-02 | gel. | 7/2/3 → 7/2/3 | 0.737 → 0.737 | 0.7 → 0.7 | 0.0 → 0.0 | 1.00 → 1.00 |  |
| src02-07 | gel. | 23/8/6 → 23/6/6 | 0.767 → 0.793 | 0.952 → 0.952 | 0.774 → 0.774 | 1.32 → 1.34 |  |
| src02-09 | holdout | 12/2/4 → 13/3/3 | 0.8 → 0.812 | 0.4 → 0.4 | 0.286 → 0.286 | 1.43 → 1.38 |  −KAT HOLÜ |
| src02-12 | gel. | 57/40/26 → 58/30/25 | 0.633 → 0.678 | 0.748 → 0.748 | 0.582 → 0.582 | 1.05 → 1.06 | +ASANSÖR |
| tip-1_mimari | gel. | 10/0/1 → 10/0/1 | 0.952 → 0.952 | 0.857 → 0.857 | 0.333 → 0.333 | 1.50 → 1.50 |  |
| tip-2_mimari | gel. | 9/0/2 → 9/0/2 | 0.9 → 0.9 | 0.947 → 0.947 | 0.824 → 0.824 | 1.11 → 1.11 |  |
| tip-4_mimari | gel. | 11/1/0 → 11/1/0 | 0.957 → 0.957 | 1.0 → 1.0 | 1.0 → 1.0 | 0.83 → 0.83 |  |
| tip-6_mimari | holdout | 11/0/1 → 11/0/1 | 0.957 → 0.957 | 0.947 → 0.947 | 0.828 → 0.828 | 0.73 → 0.73 |  |

Issue tipi (11 GT) önce → sonra: {'area_mismatch': '72→72', 'room_no_door': '40→40', 'window_missing': '36→36', 'unlabeled_region': '37→31', 'door_side_ambiguous': '31→31', 'unknown_layer': '27→26', 'conflicting_layer': '8→8', 'ambiguous_opening': '3→4', 'room_merged': '3→3', 'open_room': '2→2', 'unit_suspect': '1→1'}

Aile: ABM (fam04) 0,692 → 0,706; src02 aile B (fam02) 0,657 → 0,702; src02 aile A (fam10) 0,759 → 0,769; tip 0,943 aynı.
Issue 260 → 254 (unlabeled_region 37 → 31, unknown_layer 27 → 26, ambiguous_opening 3 → 4); issue/oda medyan 1,11 aynı.
Uzlaşma (55 dosya): faces_in 863 → 467 (src02-07; AA-*/'0' katmanı çiftleri kenar dışı); src02-12 aday 24 → 15.
**Dosya bazında FN artışı yalnız src02-12 (+4 / −5):** HOL r16 → kapı (2) [7,6 m² yüz flood parçasıyla 0,40 örtüşme];
HOL r6 → (3) birleştirdi, (2) eledi; ASANSÖR ve MERDİVEN → (1) [şaft duvarları MERDIVEN katmanında; stair kenar üretmiyor].
Ayrıntı ve adaylar (flood parçası ⊂ yüz → poligon değişimi; stair çizgileri ayak izi dışında kenar) DECISIONS 2026-09-13.
Korkuluk sert-çizgi kuralının 11 GT'de ölçülebilir etkisi yok (run1 = run2), semantik gerekçeyle tutuldu.

### Merdiven sınıfı kenarları + örtüşme kapısı istisnası (flood parçası ⊂ yüz) (2026-09-13; 55 dosya, 11 GT)

Tek commit: (1) merdiven katmanı çizgileri basamak (ladder, blok basamaklar açılır) / diğer olarak ayrılır; ayak izi yalnız
basamaklardan; basamak olmayan, ayak izi dışı, eksene yakın çizgiler kenar üretir; basamak yoksa eski davranış (fallback).
(2) aday kapısına takılan yüz, tam bir flood odasını kapsıyorsa (≥ 0,9 oda alanı, başka odaya değmiyor, yazı alanı oranı
0,5–2) oda poligonu yüz ∪ oda olur (kapı bağlamadan sonra). Eşikler `thresholds.yaml graph.stair_* / absorb_*`.
Kabul: FN 49 → **35** ✓, FP 52 → **34** ✓ (artmadı), kapı/pencere birebir aynı ✓, IoU 0,880 → 0,888.

| Küme | Dosya | Oda F1 | TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda medyan |
|---|---:|---|---|---|---|---|---|---|
| geliştirme | 9 | 0.754 → 0.836 | 144/49/45 → 158/31/31 | 0.884 → 0.894 | 0.845 → 0.845 | 0.713 → 0.713 | 96/250 (0.38) → 64/218 (0.29) | 1.11 → 1.03 |
| holdout | 2 | 0.873 → 0.873 | 24/3/4 → 24/3/4 | 0.86 → 0.86 | 0.706 → 0.706 | 0.651 → 0.651 | 14/38 (0.37) → 14/38 (0.37) | 1.38 → 1.38 |
| toplam | 11 | 0.769 → 0.841 | 168/52/49 → 182/34/35 | 0.88 → 0.888 | 0.83 → 0.83 | 0.706 → 0.706 | 110/288 (0.38) → 78/256 (0.30) | 1.11 → 1.03 |

| Dosya | Küme | Oda TP/FP/FN önce → sonra | Oda F1 | Kapı F1 | Pencere F1 | Issue/oda | FN farkı |
|---|---|---|---|---|---|---|---|
| KAYAPINAR_2892_ADA_8_PARSEL_ | gel. | 11/10/7 → 11/10/7 | 0.564 → 0.564 | 1.0 → 1.0 | 1.0 → 1.0 | 1.62 → 1.62 |  |
| hafif_celik_tip_koy_konutu_7 | gel. | 7/0/1 → 7/0/1 | 0.933 → 0.933 | 0.923 → 0.923 | 0.267 → 0.267 | 0.71 → 0.71 |  |
| input-2-clean | gel. | 8/0/0 → 8/0/0 | 1.0 → 1.0 | 0.909 → 0.909 | 0.857 → 0.857 | 1.12 → 1.12 |  |
| src02-02 | gel. | 7/2/3 → 8/1/2 | 0.737 → 0.842 | 0.7 → 0.7 | 0.0 → 0.0 | 1.00 → 0.89 |  −BANYO |
| src02-07 | gel. | 23/6/6 → 23/6/6 | 0.793 → 0.793 | 0.952 → 0.952 | 0.774 → 0.774 | 1.34 → 1.03 |  |
| src02-09 | holdout | 13/3/3 → 13/3/3 | 0.812 → 0.812 | 0.4 → 0.4 | 0.286 → 0.286 | 1.38 → 1.38 |  |
| src02-12 | gel. | 58/30/25 → 71/13/12 | 0.678 → 0.85 | 0.748 → 0.748 | 0.582 → 0.582 | 1.06 → 0.93 | +KULLANILMAYAN ALAN,KULLANILMAYAN ALAN −BANYO,BANYO,BANYO,KAT HOLÜ,BANYO |
| tip-1_mimari | gel. | 10/0/1 → 10/0/1 | 0.952 → 0.952 | 0.857 → 0.857 | 0.333 → 0.333 | 1.50 → 1.50 |  |
| tip-2_mimari | gel. | 9/0/2 → 9/0/2 | 0.9 → 0.9 | 0.947 → 0.947 | 0.824 → 0.824 | 1.11 → 1.11 |  |
| tip-4_mimari | gel. | 11/1/0 → 11/1/0 | 0.957 → 0.957 | 1.0 → 1.0 | 1.0 → 1.0 | 0.83 → 0.83 |  |
| tip-6_mimari | holdout | 11/0/1 → 11/0/1 | 0.957 → 0.957 | 0.947 → 0.947 | 0.828 → 0.828 | 0.73 → 0.73 |  |

Issue tipi (11 GT) önce → sonra: {'area_mismatch': '72→52', 'room_no_door': '40→40', 'window_missing': '36→35', 'door_side_ambiguous': '31→31', 'unlabeled_region': '31→27', 'unknown_layer': '26→26', 'conflicting_layer': '8→8', 'ambiguous_opening': '4→4', 'room_merged': '3→3', 'open_room': '2→2', 'unit_suspect': '1→1'}

Aile: src02 aile B (fam02) 0,702 → 0,844; src02 aile A (fam10) 0,769 → 0,826; ABM (fam04) 0,706 → 0,691 (KAYAPINAR aynı,
input-2 aynı; fark yuvarlama/ağırlık); tip 0,943 aynı. Issue 254 → 229 (area_mismatch 72 → 52: yutulan parçalar yazı alanına
yaklaştı; unlabeled_region 31 → 27); issue/oda medyan 1,11 → 1,03. Kapsama 0,38 → 0,30 (hatalı varlık 288 → 256; kapsanan 110 → 78:
issue'su olan FP/FN'ler düzeldi, kalanlar issue'suz — çoğu src02-12 çekirdek/hatch-only).
**src02-12:** absorb 16 (HOL r1/r6/r16/r22/r28, BANYO ×4, E.BANYO ×5, BALKON ×2, KAT HOLÜ); yeni FN: sol çekirdek ASANSÖR ×2 ve
KULLANILMAYAN ALAN ×2 (önceki TP rastlantısaldı: tüm-çizgi ayak izi zarfı asansör çarpısını kapsıyordu). **Beklenen ASANSÖR
c_as_sag1 / MERDİVEN c_merd_sag_ust geri gelmedi:** çekirdek duvarları hatch-only (`..taramam`), MERDIVEN katmanındaki çizgiler
asansör çarpısı; hatch çiftlerini kenar yapma deneyi 69/16/14 → 53/36/30 (geri alındı). Ayrıntı DECISIONS 2026-09-13 (2).
Merdiven istatistiği (55 dosya): basamak bulunan dosyada kenar üreten çizgi az (src02-12: 18 basamak, 1 kenar); çoğu dosyada
fallback (src02-07, src02-02, KAYAPINAR: basamak çizgisi yok ya da < 1 m²).

### Anlamsız katman adları (non_semantic) — unknown_layer sorusu yok (2026-09-14; 55 dosya, 11 GT)

`vocab.is_non_semantic_layer` (AA-0.20, ÇİZ KALIN, PEN-3, saf sayı/nokta): sınıf yalnız içerik istatistiğinden, unknown_layer
sorusu üretilmez; learning log `answered_by` zorunlu. **11 GT eval birebir aynı** (oda 182/34/35 F1 0,841, IoU 0,888; kapı 0,830;
pencere 0,706; holdout aynı; kapsama 78/256). Yalnız soru sayısı: unknown_layer 26 → 18 (11 GT), 186 → 151 (55 dosya);
issue/oda medyan 1,03 → 0,97. src02-07 30 → 28 (0 / AA-0.20 / ÇİZ KALIN düştü; sıradaki aday MERİZD sorulur), src02-04 10 → 8
(AA-0.05 / AA-0.15 düştü, MERİZD kaldı), src02-15 49 → 48 (AA-* üçü düştü, MERİZD ve KESİT sıraya girdi — sıralama ilk 3'ü
doldurur). Gözlem: src02-07'de AA-0.20 ve ÇİZ KALIN'ın seçilen kat kutusu içinde HİÇ entity'si yok (596 / 117 entity başka
pafta/kesitte); unknown_layer sayımı dosya geneli (`layer_counts`) → aday: sayım seçilen kat kutusuyla sınırlansın.

### C turu — src02-07 HITL cevapları → fam10 profili (learning/to_profile.py) (2026-09-14; 55 dosya, 11 GT)

28 cevap (2 insan, 26 GT): MERİZD → stair, Tefriş → furniture, birim cm → `source_profiles/fam10.yaml` (layers, units,
learned_from, fingerprints); 25 geometri cevabı yalnız IR + learning log. src02-07 kendi `hitl_units` (100) ve katman
cevaplarıyla yeniden koştu (politika g); fam10'daki diğer dosyalar (src02-02, 04, 15) profil üzerinden etkilendi.

| Küme | Dosya | Oda F1 | TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda medyan |
|---|---:|---|---|---|---|---|---|---|
| geliştirme | 9 | 0.836 → 0.838 | 158/31/31 → 158/30/31 | 0.894 → 0.896 | 0.845 → 0.845 | 0.713 → 0.713 | 64/218 (0.29) → 63/217 (0.29) | 0.97 → 0.92 |
| holdout | 2 | 0.873 → 0.873 | 24/3/4 → 24/3/4 | 0.86 → 0.86 | 0.706 → 0.706 | 0.651 → 0.651 | 14/38 (0.37) → 14/38 (0.37) | 1.31 → 1.31 |
| toplam | 11 | 0.841 → 0.843 | 182/34/35 → 182/33/35 | 0.888 → 0.89 | 0.83 → 0.83 | 0.706 → 0.706 | 78/256 (0.30) → 77/255 (0.30) | 0.97 → 0.92 |

| Dosya | Küme | Oda TP/FP/FN önce → sonra | Oda F1 | Kapı F1 | Pencere F1 | Issue/oda | FN farkı |
|---|---|---|---|---|---|---|---|
| KAYAPINAR_2892_ADA_8_PARSEL_ | gel. | 11/10/7 → 11/10/7 | 0.564 → 0.564 | 1.0 → 1.0 | 1.0 → 1.0 | 1.62 → 1.62 |  |
| hafif_celik_tip_koy_konutu_7 | gel. | 7/0/1 → 7/0/1 | 0.933 → 0.933 | 0.923 → 0.923 | 0.267 → 0.267 | 0.57 → 0.57 |  |
| input-2-clean | gel. | 8/0/0 → 8/0/0 | 1.0 → 1.0 | 0.909 → 0.909 | 0.857 → 0.857 | 1.00 → 1.00 |  |
| src02-02 | gel. | 8/1/2 → 7/1/3 | 0.842 → 0.778 | 0.7 → 0.7 | 0.0 → 0.0 | 0.67 → 0.62 | +MAKİNE DAİRESİZ ASANSÖR |
| src02-07 | gel. | 23/6/6 → 24/5/5 | 0.793 → 0.828 | 0.952 → 0.952 | 0.774 → 0.774 | 0.97 → 0.83 |  |
| src02-09 | holdout | 13/3/3 → 13/3/3 | 0.812 → 0.812 | 0.4 → 0.4 | 0.286 → 0.286 | 1.31 → 1.31 |  |
| src02-12 | gel. | 71/13/12 → 71/13/12 | 0.85 → 0.85 | 0.748 → 0.748 | 0.582 → 0.582 | 0.92 → 0.92 |  |
| tip-1_mimari | gel. | 10/0/1 → 10/0/1 | 0.952 → 0.952 | 0.857 → 0.857 | 0.333 → 0.333 | 1.50 → 1.50 |  |
| tip-2_mimari | gel. | 9/0/2 → 9/0/2 | 0.9 → 0.9 | 0.947 → 0.947 | 0.824 → 0.824 | 1.11 → 1.11 |  |
| tip-4_mimari | gel. | 11/1/0 → 11/1/0 | 0.957 → 0.957 | 1.0 → 1.0 | 1.0 → 1.0 | 0.83 → 0.83 |  |
| tip-6_mimari | holdout | 11/0/1 → 11/0/1 | 0.957 → 0.957 | 0.947 → 0.947 | 0.828 → 0.828 | 0.73 → 0.73 |  |

Issue tipi (11 GT) önce → sonra: {'area_mismatch': '52→50', 'room_no_door': '40→40', 'window_missing': '35→35', 'door_side_ambiguous': '31→31', 'unlabeled_region': '27→26', 'unknown_layer': '18→17', 'conflicting_layer': '8→8', 'ambiguous_opening': '4→4', 'room_merged': '3→3', 'open_room': '2→2', 'unit_suspect': '1→0'}

**Kapı/pencere 11 GT'de birebir aynı** (137/2/54; 137/99/15). Oda toplamı 182/34/35 → 182/33/35 (F1 0,841 → 0,843) ama iki fam10
GT dosyasında geometri DEĞİŞTİ: src02-07 23/6/6 → 24/5/5 (birim 115,2 → 100: dosya düzeyi HITL cevabı, profil etkisi değil);
src02-02 8/1/2 → 7/1/3 (−1 TP: MAKİNE DAİRESİZ ASANSÖR; önceki TP rastlantısaldı — tüm-çizgi merdiven ayak izi zarfı asansörle
çakışıyordu, MERİZD stair olunca zarf değişti). "Yalnız issue düşsün" şartı katman sınıfı cevaplarında tutmaz: stair/furniture
sınıfı kapılı tüketicilere (duvar taraması hariç tutma, merdiven ayak izi, graf kenarı) girer; bu, profil cevabının tasarım gereği
sonucudur (Adım 5 kapılı varyant). Holdout birebir aynı.
**Issue öncesi/sonrası (fam10):** src02-07 28 → 24 (unknown_layer 1 → 0, unit_suspect 1 → 0, area_mismatch 12 → 10 — birim
düzelince); src02-04 8 → 7 (unknown_layer MERİZD 1 → 0; geometri aynı: 11 oda, 9 kapı, 15 pencere); src02-15 48 → 47 ama dağılım
değişti (oda 44 → 47; unlabeled_region 12 → 15, open_room 5 → 11, area_mismatch 12 → 8, window_missing 6 → 1; unknown_layer
2 → 1; kapı 20 / pencere 20 aynı) — MERİZD'in stair olması duvar taramasını ve ayak izini değiştirdi; GT yok, ölçülemedi;
src02-02 6 → 5 (unlabeled_region 1 → 0, o aday TP idi). unknown_layer + conflicting_layer (fam10 4 dosya): 5 → 2
(kalan: src02-07 conflicting Tefriş sayısal olarak hâlâ üretiliyor — profil sınıfı furniture ama geometri oyu duvar; src02-15
unknown KESİT). 11 GT toplam issue 229 → 224; issue/oda medyan 0,97 → 0,92.

### conflicting_layer: insan/GT cevaplı katman sınıfı için soru yok (2026-09-14; 55 dosya, 11 GT)

`NameMap.source(layer)` ∈ {hitl, profile:hitl} (dosya cevabı ya da learning/to_profile ile profile giren sınıf) → conflicting_layer
üretilmez. 11 GT eval birebir aynı (182/33/35; kapı/pencere aynı; holdout aynı); src02-07 24 → 23 issue (Tefriş çelişkisi düştü),
conflicting_layer 11 GT 8 → 7.

### Ağırlık turu (1) — raster bariyer çiftlerine sınıf/kalınlık sinyali (2026-09-14; 55 dosya, 11 GT)

Paralel çift raster bariyerine girmez ⇔ layer_class == 0 ∧ wall_word == 0 ∧ thickness_mode != 1 (`raster.extra_exclude_class_vote`;
yeni sinyal `wall_word`, ağırlık 0). Kapı/pencere yolu dokunulmadı. Kapı: kapı/pencere aynı ✓, holdout F1 aynı ✓ (IoU −0,001).

| Küme | Dosya | Oda F1 | TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda medyan |
|---|---:|---|---|---|---|---|---|---|
| geliştirme | 9 | 0.838 → 0.889 | 158/30/31 → 165/17/24 | 0.896 → 0.888 | 0.845 → 0.845 | 0.713 → 0.713 | 63/217 (0.29) → 49/198 (0.25) | 0.92 → 0.83 |
| holdout | 2 | 0.873 → 0.873 | 24/3/4 → 24/3/4 | 0.86 → 0.859 | 0.706 → 0.706 | 0.651 → 0.651 | 14/38 (0.37) → 14/38 (0.37) | 1.31 → 1.31 |
| toplam | 11 | 0.843 → 0.887 | 182/33/35 → 189/20/28 | 0.89 → 0.883 | 0.83 → 0.83 | 0.706 → 0.706 | 77/255 (0.30) → 63/236 (0.27) | 0.92 → 0.83 |

| Dosya | Küme | Oda TP/FP/FN önce → sonra | Oda F1 | Kapı F1 | Pencere F1 | Issue/oda | FN farkı |
|---|---|---|---|---|---|---|---|
| KAYAPINAR_2892_ADA_8_PARSEL_ | gel. | 11/10/7 → 13/8/5 | 0.564 → 0.667 | 1.0 → 1.0 | 1.0 → 1.0 | 1.62 → 1.52 |  −Mutfak,Mutfak |
| hafif_celik_tip_koy_konutu_7 | gel. | 7/0/1 → 7/0/1 | 0.933 → 0.933 | 0.923 → 0.923 | 0.267 → 0.267 | 0.57 → 0.57 |  |
| input-2-clean | gel. | 8/0/0 → 8/0/0 | 1.0 → 1.0 | 0.909 → 0.909 | 0.857 → 0.857 | 1.00 → 1.00 |  |
| src02-02 | gel. | 7/1/3 → 8/0/2 | 0.778 → 0.889 | 0.7 → 0.7 | 0.0 → 0.0 | 0.62 → 0.62 |  −MERDİVEN |
| src02-07 | gel. | 24/5/5 → 24/5/5 | 0.828 → 0.828 | 0.952 → 0.952 | 0.774 → 0.774 | 0.79 → 0.79 |  |
| src02-09 | holdout | 13/3/3 → 13/3/3 | 0.812 → 0.812 | 0.4 → 0.4 | 0.286 → 0.286 | 1.31 → 1.31 |  |
| src02-12 | gel. | 71/13/12 → 75/3/8 | 0.85 → 0.932 | 0.748 → 0.748 | 0.582 → 0.582 | 0.92 → 0.74 | +KAT HOLÜ −E.BANYO,BALKON,HOL,BALKON,BALKON |
| tip-1_mimari | gel. | 10/0/1 → 10/0/1 | 0.952 → 0.952 | 0.857 → 0.857 | 0.333 → 0.333 | 1.50 → 1.50 |  |
| tip-2_mimari | gel. | 9/0/2 → 9/0/2 | 0.9 → 0.9 | 0.947 → 0.947 | 0.824 → 0.824 | 1.11 → 1.11 |  |
| tip-4_mimari | gel. | 11/1/0 → 11/1/0 | 0.957 → 0.957 | 1.0 → 1.0 | 1.0 → 1.0 | 0.83 → 0.83 |  |
| tip-6_mimari | holdout | 11/0/1 → 11/0/1 | 0.957 → 0.957 | 0.947 → 0.947 | 0.828 → 0.828 | 0.73 → 0.73 |  |

Issue tipi (11 GT) önce → sonra: {'room_no_door': '40→40', 'area_mismatch': '50→37', 'window_missing': '35→35', 'door_side_ambiguous': '31→31', 'unlabeled_region': '26→20', 'unknown_layer': '17→17', 'conflicting_layer': '7→7', 'ambiguous_opening': '4→4', 'room_merged': '3→3', 'open_room': '2→0'}

Aile: src02 aile B (fam02) 0,844 → 0,912; ABM (fam04) 0,691 → 0,764; src02 A + diğer 0,826 → 0,857; tip 0,943 aynı (IoU 0,922 → 0,927).
Issue 224 → 195 (area_mismatch 50 → 37, unlabeled_region 26 → 20, open_room 2 → 0); issue/oda medyan 0,92 → 0,83.
Kapsama 0,30 → 0,27 (hatalı varlık 255 → 236; kapsanan 77 → 63). Deney kayıtları (r1/r2 vs r3, tip-1 HOL, tip-6 IoU) DECISIONS.

### Ağırlık turu (2) — graph_extends (2026-09-14; 55 dosya, 11 GT)

2026-09-13 örtüşme kapısı istisnasının genellemesi: IoU ile eşleşmeyen HER yüz (örtüşme koşulu kalktı), tam olarak bir etiketli
flood odasını kapsıyorsa (≥ 0,9 oda alanı, başka odaya değmiyor, yazı alanı oranı 0,5–2) odayı genişletir; yüz aday olmaz.
Sinyal adı `graph_extends`. **11 GT birebir aynı** (189/20/28, F1 0,887; kapı/pencere/holdout/kapsama aynı): (1) raster
düzeltmesinden sonra 11 GT'de "flood parçası ⊂ yüz, örtüşme < 0,3" deseni kalmadı. GT'siz 7 dosyada etkisi var (290_10, 505,
Nihal_Akgöl, src02-01, src02-08, src02-15: 1–2 yüz aday yerine oda genişletmesi; oda sayısı 1–2 düştü). Basitleştirme olarak
tutuldu; ölçülebilir kazanç yok.

### Ağırlık turu (7) — alan-polyline katmanları → `area` sınıfı, oda kaynağı (2026-09-14; 55 dosya, 11 GT)

`LayerClass.area` (vocab tam kelime alan/area/m2), kapalı polyline tek etiketi içeriyorsa oda poligonu (`area_polyline` 0,90,
kaynak `area+<flood>`), bariyer değil; area katmanı `WALL_EXCLUDE_CLASSES`'ta (ince çizgi pencere adayı olmaz).
Kapı: oda/kapı/pencere F1 aynı ✓; holdout F1 aynı ✓ (IoU 0,859 → 0,858: tip-6 0,910 → 0,908).

| Küme | Dosya | Oda F1 | TP/FP/FN | IoU | Kapı F1 | Pencere F1 | Kapsama | Issue/oda medyan |
|---|---:|---|---|---|---|---|---|---|
| geliştirme | 9 | 0.889 → 0.889 | 165/17/24 → 165/17/24 | 0.888 → 0.893 | 0.845 → 0.845 | 0.713 → 0.713 | 49/198 (0.25) → 49/198 (0.25) | 0.83 → 0.79 |
| holdout | 2 | 0.873 → 0.873 | 24/3/4 → 24/3/4 | 0.859 → 0.858 | 0.706 → 0.706 | 0.651 → 0.651 | 14/38 (0.37) → 14/38 (0.37) | 1.31 → 1.31 |
| toplam | 11 | 0.887 → 0.887 | 189/20/28 → 189/20/28 | 0.883 → 0.886 | 0.83 → 0.83 | 0.706 → 0.706 | 63/236 (0.27) → 63/236 (0.27) | 0.83 → 0.79 |

| Dosya | Küme | Oda TP/FP/FN önce → sonra | Oda F1 | Kapı F1 | Pencere F1 | Issue/oda | FN farkı |
|---|---|---|---|---|---|---|---|
| KAYAPINAR_2892_ADA_8_PARSEL_ | gel. | 13/8/5 → 13/8/5 | 0.667 → 0.667 | 1.0 → 1.0 | 1.0 → 1.0 | 1.52 → 1.52 |  |
| hafif_celik_tip_koy_konutu_7 | gel. | 7/0/1 → 7/0/1 | 0.933 → 0.933 | 0.923 → 0.923 | 0.267 → 0.267 | 0.57 → 0.57 |  |
| input-2-clean | gel. | 8/0/0 → 8/0/0 | 1.0 → 1.0 | 0.909 → 0.909 | 0.857 → 0.857 | 1.00 → 1.00 |  |
| src02-02 | gel. | 8/0/2 → 8/0/2 | 0.889 → 0.889 | 0.7 → 0.7 | 0.0 → 0.0 | 0.62 → 0.62 |  |
| src02-07 | gel. | 24/5/5 → 24/5/5 | 0.828 → 0.828 | 0.952 → 0.952 | 0.774 → 0.774 | 0.79 → 0.79 |  |
| src02-09 | holdout | 13/3/3 → 13/3/3 | 0.812 → 0.812 | 0.4 → 0.4 | 0.286 → 0.286 | 1.31 → 1.31 |  |
| src02-12 | gel. | 75/3/8 → 75/3/8 | 0.932 → 0.932 | 0.748 → 0.748 | 0.582 → 0.582 | 0.74 → 0.74 |  |
| tip-1_mimari | gel. | 10/0/1 → 10/0/1 | 0.952 → 0.952 | 0.857 → 0.857 | 0.333 → 0.333 | 1.50 → 1.40 |  |
| tip-2_mimari | gel. | 9/0/2 → 9/0/2 | 0.9 → 0.9 | 0.947 → 0.947 | 0.824 → 0.824 | 1.11 → 1.00 |  |
| tip-4_mimari | gel. | 11/1/0 → 11/1/0 | 0.957 → 0.957 | 1.0 → 1.0 | 1.0 → 1.0 | 0.83 → 0.67 |  |
| tip-6_mimari | holdout | 11/0/1 → 11/0/1 | 0.957 → 0.957 | 0.947 → 0.947 | 0.828 → 0.828 | 0.73 → 0.64 |  |

Issue tipi (11 GT) önce → sonra: {'room_no_door': '40→39', 'area_mismatch': '37→37', 'window_missing': '35→35', 'door_side_ambiguous': '31→31', 'unlabeled_region': '20→20', 'unknown_layer': '17→17', 'ambiguous_opening': '4→4', 'room_merged': '3→3', 'conflicting_layer': '7→3'}

IoU 0,883 → 0,886 (tip-1 0,941 → 0,954, tip-2 0,928 → 0,956, tip-4 0,929 → 0,930); issue/oda medyan 0,83 → 0,79
(tip-1 1,50 → 1,40, tip-2 1,11 → 1,00, tip-4 0,83 → 0,67, tip-6 0,73 → 0,64; room_no_door 40 → 39). Alan poligonu 55 dosyanın
12'sinde (116 oda bağlandı; tip ailesi, hafif_celik, ABM M2/ALAN HESAP), 11 GT'de 5. İlk deneme (area katmanı WALL_EXCLUDE dışı) tip-6'da 3 sahte
ince-çizgi pencere üretti (holdout pencere 0,828 → 0,750) → düzeltildi. (3) hatch_wall denendi, kapıyı geçmedi (DECISIONS).
