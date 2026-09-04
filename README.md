# vibedraw

Mimari altlık (DWG/DXF) → Building IR (oda / duvar / kapı / pencere) → elektrik projesi.

Şu anki odak: farklı mimarların farklı CAD alışkanlıklarıyla çizdiği konut projelerinden
ölçülebilir doğrulukla **Building IR** çıkarmak. Elektrik motoru (v1/v2) mevcut ama askıda.

## Yapı
- `core/parse.py` — katman-bağımsız oda etiketi çıkarımı, ölçek tahmini, kat kümeleme
- `core/geometry.py` — duvar/kapı/pencere tespiti, raster flood-fill oda poligonları
- `core/sheets.py` — pafta anlama: görünüm ayrımı ve sınıflama (plan/kesit/görünüş/...)
- `core/metrics.py`, `evaluate.py` — ground truth ölçümü (IoU, F1, bağlantı doğruluğu)
- `annotate.py` + `templates/annotate.html` — tarayıcıda ground truth etiketleme aracı
- `experiments/run_baseline.py` — tüm veri setinde koşu + başarısızlık kataloğu
- `experiments/survey_views.py` — pafta anlama taraması
- `triage_dataset.py` — DWG/DXF veri seti tarama (katman ailesi, aday kat planı)
- `data/ground_truth/` — elle doğrulanmış etiketler (JSON)

## Çalıştırma
```
pip install -r requirements.txt
python3 -m pytest -q
python3 triage_dataset.py data/dataset
python3 experiments/run_baseline.py
python3 evaluate.py
```
DWG girdisi için `brew install libredwg` (dwg2dxf) yeterli.

Veri klasörleri (`data/raw`, `data/dataset`, `ornekler`) ve `output/` repoda yok.
