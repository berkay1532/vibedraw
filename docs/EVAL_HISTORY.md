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
| 2026-09-04 | bb6ad0b | adım 3 (geometry.py → modüller) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı; 52/53 ok (ZA_EVİ), 82 test |
