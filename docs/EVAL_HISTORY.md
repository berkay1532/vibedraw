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
| 2026-09-04 | (adım 5, yerel) | adım 5: kaynak profilleri + sözlük kademesi; elektrik tespiti (ADAY 53→49) | 0.886 | 0.871 | 0.937 | 0.009 | 0.887 | 0.817 | 7 / 49 | FARK VAR — karar bekliyor. tip-1 oda F1 1.0→0.842 (A_ANNO/A_STAIR katmanları 'text/stair' sınıfıyla duvar taramasından çıkınca ANTRE+HOL birleşti, DEPO sızdı), tip-4 oda F1 0.957→1.0 (aynı mekanizma, ANTRE doğru birleşti), tip-1/tip-6 kapı F1 düştü (A_DOOR_* INSERT 'kesin kapı' yolu: +3/+1 aday, menteşe kayması 0→0.021 m), tip-6 pencere 0.75→0.828 (A_GLZ_GLS pencere kaynağı). Ablasyon ve kapılı varyant DECISIONS'ta. 49/49 ok, AVİDA 73 s |
