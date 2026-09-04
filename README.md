# vibedraw

Mimari altlık (DWG/DXF) → Building IR (oda / duvar / kapı / pencere) → elektrik projesi.

Şu anki odak: farklı mimarların farklı CAD alışkanlıklarıyla çizdiği konut projelerinden
ölçülebilir doğrulukla **Building IR** çıkarmak. Elektrik motoru (v1/v2) mevcut ama askıda.

## Yapı
- `core/perception/` — DWG/DXF → BuildingIR (v1): `parse.py` (oda etiketleri, ölçek, kat kümeleme),
  `geometry.py` (duvar/kapı/pencere, flood-fill odalar), `sheets.py` (pafta anlama),
  `metrics.py`, `triage.py`, `ir.py`, `semantics.py`, `llm.py`, `vlm_doors.py`
- `core/electrical/` — eski elektrik prototipi (dokunulmaz): `ir.py`, `rules.py`, `layout.py`,
  `devices.py`, `cad.py`, `appliances.py`
- `evaluate.py` — ground truth ölçümü · `annotate.py` + `templates/annotate.html` — etiketleme aracı
- `experiments/run_baseline.py` — tüm veri setinde koşu + başarısızlık kataloğu ·
  `experiments/survey_views.py` — pafta anlama taraması
- `triage_dataset.py` — DWG/DXF veri seti tarama · `tools/` — debug/render/temizleme scriptleri
- `data/ground_truth/` — elle doğrulanmış etiketler (JSON)
- `docs/` — `ARCHITECTURE.md`, `REFACTOR_PLAN.md`, `EVAL_HISTORY.md`, `DECISIONS.md`, `HITL_QUESTIONS.md`

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
