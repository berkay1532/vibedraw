# Eval geçmişi

Her perception commit'i için bir satır. Kaynak: `python3 experiments/run_baseline.py && python3 evaluate.py`
(GT: `data/ground_truth/*.json`, mikro ortalama). "Dosya" = GT dosya sayısı / koşulan aday sayısı.

| Tarih | Commit | Adım | Oda F1 | Oda IoU | Kapı F1 | Kapı konum (m) | Kapı bağlantı | Pencere F1 | Dosya | Not |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | 35c9405 | baseline (refactor öncesi) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | 73 test; ZA_EVİ koşuda hatalı (bozuk dosya) |
| 2026-09-04 | 6f69cf7 | adım 0 (temizlik) | 0.901 | 0.888 | 0.951 | 0.006 | 0.904 | 0.802 | 7 / 53 | baseline ile birebir aynı |
